from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import cv2
import numpy as np
from PIL import Image

from rfdetr.detr import RFDETRMedium
import rtree

# 标签放置：重叠面积超过自身 10% 时视为“过挤”,会干扰其他元素的识别，四方向均过挤则用框内左上角
OVERLAP_AREA_RATIO_THRESHOLD = 0.1
# rtree 优化：每个方向只考虑“有重叠的至多 5 个”+“最近邻 5 个”参与重叠面积累加
RTREE_OVERLAP_TOP_K = 5
RTREE_NEAREST_K = 5


def _sort_boxes_lrtb(
    boxes: Iterable[Sequence[float]], height: int
) -> List[Sequence[float]]:
    """
    Sort boxes left-to-right, then top-to-bottom so that nearby elements
    have nearby indices. Uses a simple row-based grouping via cell height.
    """
    boxes = list(boxes)
    if not boxes:
        return []
    cell_h = 20

    def row_key(box: Sequence[float]) -> Tuple[int, float]:
        x1, y1, x2, y2 = float(box[0]), float(box[1]), float(box[2]), float(box[3])
        cy = (y1 + y2) / 2
        cx = (x1 + x2) / 2
        row = int(cy // cell_h)
        return (row, cx)

    return sorted(boxes, key=row_key)


def _bboxes_overlap(a: Sequence[float], b: Sequence[float]) -> bool:
    """
    判断两个 bbox 是否有重叠（相交）。
    两个轴对齐矩形相交当且仅当在 x、y 两轴上都存在重叠区间。

    参数
    ----
    a, b:
        各为长度至少为 4 的序列 [x1, y1, x2, y2]（左上、右下），可为 int 或 float。

    返回
    ----
    True 表示有重叠，False 表示不重叠（相离或仅边/角相接视为不重叠）。
    """
    if len(a) < 4 or len(b) < 4:
        raise ValueError("a and b must be sequences of length at least 4")
    ax1, ay1, ax2, ay2 = float(a[0]), float(a[1]), float(a[2]), float(a[3])
    bx1, by1, bx2, by2 = float(b[0]), float(b[1]), float(b[2]), float(b[3])
    return not (ax2 <= bx1 or bx2 <= ax1 or ay2 <= by1 or by2 <= ay1)
    
def _intersection_area(a: Tuple[int, int, int, int], b: Tuple[int, int, int, int]) -> int:
    """两矩形相交面积（像素数）；不交返回 0。"""
    if not _bboxes_overlap(a, b):
        return 0
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1 = max(ax1, bx1)
    iy1 = max(ay1, by1)
    ix2 = min(ax2, bx2)
    iy2 = min(ay2, by2)
    if ix1 >= ix2 or iy1 >= iy2:
        return 0
    return (ix2 - ix1) * (iy2 - iy1)


def _compute_overlap_stats(
    label_rect: Tuple[int, int, int, int],
    rtree_index: object,
    rect_by_id: List[Tuple[int, int, int, int]],
    overlap_top_k: int = RTREE_OVERLAP_TOP_K,
    nearest_k: int = RTREE_NEAREST_K,
) -> Tuple[float, float]:
    """
    使用预建 rtree 索引计算标签矩形对「其他元素」的覆盖比例统计。

    - total_overlap: 对各其它矩形的「覆盖比例」之和（覆盖比例 = 交集面积 / 该其它矩形面积）。
    - max_single: 对单个其它矩形的最大覆盖比例（分母为该其它元素面积，非标签自身面积）。
    只考虑与 label_rect 相交的至多 overlap_top_k 个 + 最近邻 nearest_k 个。
    """
    total = 0.0
    max_single = 0.0
    if not rect_by_id:
        return total, max_single
    lx1, ly1, lx2, ly2 = label_rect
    overlapping_ids = list(rtree_index.intersection((lx1, ly1, lx2, ly2)))
    overlap_areas = [
        (_intersection_area(label_rect, rect_by_id[rid]), rid)
        for rid in overlapping_ids
        if rid < len(rect_by_id)
    ]
    overlap_areas.sort(key=lambda x: -x[0])
    candidate_ids = set(rid for _, rid in overlap_areas[:overlap_top_k])
    nearest_ids = list(rtree_index.nearest((lx1, ly1, lx2, ly2), nearest_k))
    candidate_ids.update(nearest_ids)
    for rid in candidate_ids:
        if rid >= len(rect_by_id):
            continue
        other = rect_by_id[rid]
        inter = _intersection_area(label_rect, other)
        if inter <= 0:
            continue
        other_area = (other[2] - other[0]) * (other[3] - other[1])
        if other_area <= 0:
            continue
        ratio = inter / other_area
        total += ratio
        if ratio > max_single:
            max_single = ratio
    return total, max_single


def _rects_overlap_rate(a: Tuple[int, int, int, int], b: Tuple[int, int, int, int]) -> float:
    # 先判断是否有交集
    if not _bboxes_overlap(a, b):
        return 0
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    area_a = (ax2 - ax1) * (ay2 - ay1)
    area_b = (bx2 - bx1) * (by2 - by1)
    area_intersection = (max(ax1, bx1) - min(ax2, bx2)) * (max(ay1, by1) - min(ay2, by2))
    return area_intersection * area_intersection / (area_a * area_b + 1e-6)

def trim_by_overlab_optimize(
    boxes_with_scores: List[Tuple[Sequence[float], float]],
    overlap_threshold: float = 0.9,
) -> List[Tuple[Sequence[float], float]]:
    """
    按 overlap_threshold 过滤：按 score 降序保留框，若与已保留框的 _rects_overlap_rate > threshold 则剔除。
    使用 rtree 只对与当前框相交的已保留框做重叠率判断，不遍历全部。
    """
    if not boxes_with_scores:
        return []
    sorted_list = sorted(boxes_with_scores, key=lambda x: x[1], reverse=True)
    idx = rtree.index.Index()
    kept_rects: List[Tuple[float, float, float, float]] = []
    result: List[Tuple[Sequence[float], float]] = []
    for box_with_score in sorted_list:
        box = box_with_score[0]
        x1, y1, x2, y2 = float(box[0]), float(box[1]), float(box[2]), float(box[3])
        bbox = (x1, y1, x2, y2)
        overlapping_ids = list(idx.intersection(bbox))
        is_overlap = False
        for rid in overlapping_ids:
            if rid >= len(kept_rects):
                continue
            if _rects_overlap_rate(kept_rects[rid], bbox) > overlap_threshold:
                is_overlap = True
                break
        if not is_overlap:
            kept_rects.append(bbox)
            idx.insert(len(kept_rects) - 1, bbox)
            result.append(box_with_score)
    return result

class BoxAnnotator:
    """
    在图片上根据检测框进行标注的工具类。

    - 输入：boxes（每个元素为 [x1, y1, x2, y2]）、PIL Image 对象
    - 输出：标注后的 PIL Image 对象
    """

    def __init__(
        self,
        palette: Optional[Sequence[tuple[int, int, int]]] = None,
        font_scale: float = 0.5,
        thickness: int = 1,
        pretrain_weights: str = "data/rfdetr_medium.pth",
        resolution: int = 1600,
    ) -> None:
        # BGR 调色板，色相尽量拉开以减少相邻序号同色
        self.palette: Sequence[tuple[int, int, int]] = palette or [
            (0, 0, 255),      # 红
            (0, 255, 0),      # 绿
            (255, 0, 0),      # 蓝
            (0, 255, 255),    # 黄
            (255, 0, 255),    # 品红
            (255, 255, 0),    # 青
            (0, 128, 255),    # 橙
            (0, 165, 255),    # 橙红
            (203, 192, 255),  # 淡紫
            (0, 255, 127),    # 春绿
            (255, 165, 0),    # 深橙
            (147, 20, 255),   # 深粉
            (255, 128, 0),    # 天蓝
            (0, 215, 255),    # 金
        ]
        self.font = cv2.FONT_HERSHEY_SIMPLEX
        self.font_scale = font_scale
        self.thickness = thickness

        self.model = RFDETRMedium(pretrain_weights=pretrain_weights, resolution=resolution)
        self._text_detection: Optional[object] = None  # lazy: only loaded when predict_with_ocr is used (avoids paddle/pyharp/netcdf at startup)

    @property
    def text_detection(self):  # type: ignore[no-any-return]
        """Lazy-load PaddleOCR TextDetection so normal UI detection (RF-DETR only) does not require netcdf."""
        if self._text_detection is None:
            from paddleocr import TextDetection as _TextDetection
            self._text_detection = _TextDetection(model_name="PP-OCRv5_server_det")
        return self._text_detection

    @staticmethod
    def _contrasting_text_color(bgr_color: tuple[int, int, int]) -> tuple[int, int, int]:
        b, g, r = bgr_color
        luminance = 0.299 * r + 0.587 * g + 0.114 * b
        return (255, 255, 255) if luminance < 128 else (0, 0, 0)

    def predict(self, image: Image.Image, threshold: float = 0.35) -> Iterable[Sequence[float]]:
        """
        预测图片中的物体。返回值为 boxes 和 scores。如果 scores 小于 threshold，则不返回。
        """
        detections = self.model.predict(image, threshold=threshold)
        boxes = detections.xyxy
        scores = detections.confidence
        return list(zip(boxes, scores))

    def predict_with_ocr(self, image: Image.Image, threshold: float = 0.8, padding: int = 3) -> Iterable[Sequence[float]]:
        """
        预测图片中的物体并进行OCR识别。返回值为 boxes 和 scores。如果 scores 小于 threshold，则不返回。
        """
        image = np.array(image)
        ocr_results = self.text_detection.predict(image)
        if len(ocr_results) == 0:
            return [], []

        points = ocr_results[0].json['res']['dt_polys']
        boxes = [[*result[0], *result[2]] for result in points]
        # 边框扩大5像素
        boxes = [[x1 - padding, y1 - padding, x2 + padding, y2 + padding] for x1, y1, x2, y2 in boxes]
        scores = ocr_results[0].json['res']['dt_scores']
        boxes_with_scores = list(zip(boxes, scores))
        boxes_with_scores_filtered = list(filter(lambda x: x[1] > threshold, boxes_with_scores))
        return boxes_with_scores_filtered

    def annotate(
        self,
        boxes: Iterable[Sequence[float]],
        pil_image: Image.Image,
        start_index: int = 1,
    ) -> Image.Image:
        """
        根据给定的 boxes 在图片上绘制彩色边框和序号标签（1 起编）。

        标签放置规则：
        1. 四个方向（上/下/右/左）分别计算该方向标签对「其他元素」的覆盖比例之和（覆盖比例 = 交集面积/该其它元素面积），
           在边界内的候选中按总覆盖比例最小优先采用该方向。
        2. 特殊情况：记录每个方向对单个其它元素的最大覆盖比例（分母为其它元素面积）；若四个方向该最大比例均 > 50%，
           则在当前元素框内左上角放置标签（方向 id 4）。
        3. 边界：标签背景不得超出图像范围；仅在有边界内的候选中比较重叠面积。
        4. 无合适外侧位置（如均越界）时使用框内左上角作为兜底。

        参数
        ----
        boxes:
            可迭代对象，元素为长度至少为 4 的序列 [x1, y1, x2, y2]。
        pil_image:
            输入的 PIL Image 对象。

        返回
        ----
        标注后的 PIL Image 对象。
        """
        # --- 图像与 box 预处理 ---
        cv_img = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
        height, width = cv_img.shape[:2]
        boxes_list = list(boxes)
        n_boxes = len(boxes_list)

        # 预计算所有 box 的裁剪坐标，供边框绘制与重叠检测复用，避免在循环内重复转换
        boxes_rects: List[Tuple[int, int, int, int]] = []
        for box in boxes_list:
            x1, y1, x2, y2 = map(int, map(float, box[:4]))
            boxes_rects.append((
                max(0, min(x1, width - 1)),
                max(0, min(y1, height - 1)),
                max(0, min(x2, width - 1)),
                max(0, min(y2, height - 1)),
            ))

        # 缓存数字标签的 (tw, th)，避免重复 getTextSize（序号多为 1～2 位）
        _text_size_cache: Dict[str, Tuple[int, int]] = {}

        def _get_label_size(label: str) -> Tuple[int, int]:
            if label not in _text_size_cache:
                (tw, th), _ = cv2.getTextSize(
                    label, self.font, self.font_scale, self.thickness
                )
                _text_size_cache[label] = (tw, th)
            return _text_size_cache[label]

        pad = 2  # 仅用于标签背景与文字的内边距，标签与 bbox 之间不留空白
        n_palette = len(self.palette)
        # 相邻序号使用色相间隔更大的颜色，便于区分
        color_step = max(1, (n_palette // 2) + 1)

        # 预建 rtree 索引一次，后续只增不改（每放置一个标签即插入）；rect_by_id[id] 与索引 id 一一对应
        rtree_index = rtree.index.Index()
        rect_by_id = list(boxes_rects)
        for rid, r in enumerate(rect_by_id):
            x1, y1, x2, y2 = r
            rtree_index.insert(rid, (x1, y1, x2, y2))

        for i in range(n_boxes):
            x1, y1, x2, y2 = boxes_rects[i]

            color_box = self.palette[(i * color_step) % n_palette]
            color_text = self._contrasting_text_color(color_box)

            # --- 绘制元素边框 ---
            cv2.rectangle(cv_img, (x1, y1), (x2, y2), color_box, 2)

            # --- 标签候选：规则 1 的四个方向（上/下/右/左）---
            label = str(i + start_index)
            tw, th = _get_label_size(label)
            cx = (x1 + x2) // 2
            cy = (y1 + y2) // 2

            def _in_bounds(bg_x1: int, bg_y1: int, bg_x2: int, bg_y2: int) -> bool:
                """标签背景是否在图像范围内。"""
                return bg_x1 >= 0 and bg_y1 >= 0 and bg_x2 <= width and bg_y2 <= height

            # 五个候选：四方向 + 框内左上角。标签与 bbox 贴齐无空白。(方向id, (标签背景 rect, 文字坐标))
            _in_left = min(x1 + tw + pad * 2, x2)
            _in_bottom = min(y1 + th + pad * 2, y2)
            raw_candidates: List[Tuple[int, Tuple[Tuple[int, int, int, int], Tuple[int, int]]]] = [
                (0, (
                    (cx - tw // 2 - pad, y1 - th - pad * 2, cx + tw // 2 + pad, y1),
                    (cx - tw // 2 + 2, y1 - 2),
                )),
                (1, (
                    (cx - tw // 2 - pad, y2, cx + tw // 2 + pad, y2 + th + pad * 2),
                    (cx - tw // 2 + 2, y2 + pad + th - 2),
                )),
                (2, (
                    (x2, cy - th // 2 - pad, x2 + tw + pad * 2, cy + th // 2 + pad),
                    (x2 + pad + 2, cy + th // 2 - 2),
                )),
                (3, (
                    (x1 - tw - pad * 2, cy - th // 2 - pad, x1, cy + th // 2 + pad),
                    (x1 - tw - pad + 2, cy + th // 2 - 2),
                )),
                (4, (
                    (x1, y1, _in_left, _in_bottom),
                    (x1 + pad + 2, _in_bottom - 2),
                )),
            ]

            def _clip_chosen(
                bg_x1: int, bg_y1: int, bg_x2: int, bg_y2: int, tx: int, ty: int
            ) -> Tuple[Tuple[int, int, int, int], Tuple[int, int]]:
                return (
                    (max(0, bg_x1), max(0, bg_y1), min(width, bg_x2), min(height, bg_y2)),
                    (max(0, tx), min(height - 1, ty)),
                )

            # --- 四方向重叠统计（0,1,2,3）：每方向算 total_overlap、max_single、自身面积 ---
            dir_stats_all: List[Tuple[int, int, int, int, int, int, int, int, int, int]] = []
            for dir_id, ((bg_x1, bg_y1, bg_x2, bg_y2), (tx, ty)) in raw_candidates:
                if dir_id == 4:
                    continue
                label_rect = (bg_x1, bg_y1, bg_x2, bg_y2)
                area = (bg_x2 - bg_x1) * (bg_y2 - bg_y1)
                total_overlap, max_single = _compute_overlap_stats(
                    label_rect, rtree_index, rect_by_id
                )
                dir_stats_all.append((dir_id, total_overlap, max_single, area, bg_x1, bg_y1, bg_x2, bg_y2, tx, ty))

            # 特殊情况：四个方向各自对某其它元素的最大覆盖比例均 > 50%（分母为其它元素面积）-> 用框内左上角
            use_inside = False
            if len(dir_stats_all) == 4 and all(
                max_single > OVERLAP_AREA_RATIO_THRESHOLD for (_, _, max_single, *_) in dir_stats_all
            ):
                use_inside = True

            # 仅考虑在边界内的候选，按 total_overlap 最小选取
            dir_stats = [s for s in dir_stats_all if _in_bounds(s[4], s[5], s[6], s[7])]

            if use_inside:
                (_, (bg_rect, text_pos)) = raw_candidates[4]
                chosen = _clip_chosen(bg_rect[0], bg_rect[1], bg_rect[2], bg_rect[3], text_pos[0], text_pos[1])
            elif dir_stats:
                # 按总覆盖比例最小选方向；同分保持上→下→右→左顺序
                dir_stats.sort(key=lambda s: (s[1], s[0]))
                _, _, _, _, bg_x1, bg_y1, bg_x2, bg_y2, tx, ty = dir_stats[0]
                chosen = _clip_chosen(bg_x1, bg_y1, bg_x2, bg_y2, tx, ty)
            else:
                # 无合法外侧候选（均越界或压已放标签），兜底用框内左上角
                (_, (bg_rect, text_pos)) = raw_candidates[4]
                chosen = _clip_chosen(bg_rect[0], bg_rect[1], bg_rect[2], bg_rect[3], text_pos[0], text_pos[1])

            (bg_x1, bg_y1, bg_x2, bg_y2), (tx, ty) = chosen
            # 绘制标签背景与序号文字
            cv2.rectangle(cv_img, (bg_x1, bg_y1), (bg_x2, bg_y2), color_box, -1)
            cv2.putText(
                cv_img,
                label,
                (tx, ty),
                self.font,
                self.font_scale,
                color_text,
                self.thickness,
                cv2.LINE_AA,
            )
            # 同步更新预建 rtree，供后续元素直接使用
            rect_by_id.append((bg_x1, bg_y1, bg_x2, bg_y2))
            rtree_index.insert(len(rect_by_id) - 1, (bg_x1, bg_y1, bg_x2, bg_y2))

        # cv2 -> PIL
        return Image.fromarray(cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB))

    def predict_and_annotate(self, image: Image.Image, threshold: float = 0.35) -> Tuple[Image.Image, Iterable[float]]:
        """
        预测图片中的物体并进行标注。
        返回值为标注后的图片和 scores。如果 scores 小于 threshold，则不返回。
        """
        boxes, scores = self.predict(image, threshold=threshold)
        return self.annotate(boxes, image), scores

    def predict_and_annotate_all(
        self, image: Image.Image, threshold: float = 0.1, overlap_threshold: float = 0.1, padding: int = 3
    ) -> Tuple[Image.Image, List[Sequence[float]]]:
        """
        预测图片中的物体并进行标注，返回一张标注图与所有检测框（按左右上下次序排序）。
        返回: ( 标注图, boxes_sorted )
        """
        boxes_with_scores = self.predict(image, threshold=threshold)
        boxes_with_scores_ocr = self.predict_with_ocr(image, padding=padding)
        boxes_with_scores = [*boxes_with_scores, *boxes_with_scores_ocr]
        boxes_with_scores_trimmed = trim_by_overlab_optimize(boxes_with_scores, overlap_threshold=overlap_threshold)
        boxes_sorted = _sort_boxes_lrtb([b[0] for b in boxes_with_scores_trimmed], image.height)
        annotated_img = self.annotate(boxes_sorted, image, start_index=1)
        return annotated_img, boxes_sorted

if __name__ == "__main__":
    base_dir = "/Users/yunyun/Desktop/agent-zero"
    image = Image.open(base_dir + "/微信截图3.png")
    box_annotator = BoxAnnotator()
    annotated_img, boxes = box_annotator.predict_and_annotate_all(image)
    annotated_img.save(base_dir + "/test_annotated.png")

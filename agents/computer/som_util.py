from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import cv2
import numpy as np
from PIL import Image

from rfdetr.detr import RFDETRMedium


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

def trim_by_overlap(boxes_with_scores: List[Tuple[Sequence[float], float]], overlap_threshold: float = 0.9) \
            -> List[Tuple[Sequence[float], float]]:
    """
    按照overlap_threshold过滤boxes_with_scores
    """
    boxes_with_scores_trimmed = []
    sorted_boxes_with_scores = sorted(boxes_with_scores, key=lambda x: x[1], reverse=True)
    for i in range(len(sorted_boxes_with_scores)):
        box_with_score = sorted_boxes_with_scores[i]
        box = box_with_score[0]

        is_overlap = False
        for j in range(len(boxes_with_scores_trimmed)):
            box_trimmed = boxes_with_scores_trimmed[j][0]
            if _rects_overlap_rate(box, box_trimmed) > overlap_threshold:
                is_overlap = True
                break
        if not is_overlap:
            boxes_with_scores_trimmed.append(box_with_score)
    return boxes_with_scores_trimmed

def trim_by_overlab_optimize(boxes_with_scores: List[Tuple[Sequence[float], float]], overlap_threshold: float = 0.9) \
            -> List[Tuple[Sequence[float], float]]:
    """
    将bbox的左上角坐标都按照100个像素为单位等分量化，量化后所有的bboxes都变成100x100的网格，每个网格内的bboxes进行overlap_threshold过滤
    """
    grid_boxes = {}

    for box_with_score in boxes_with_scores:
        box = box_with_score[0]
        x1, y1, _, _ = box
        key = int(x1 // 500) + int(y1 // 500)
        if key not in grid_boxes:
            grid_boxes[key] = []
        grid_boxes[key].append(box_with_score)

    boxes_with_scores_trimmed = []
    for _, box_with_scores in grid_boxes.items():
        boxes_with_scores_trimmed.extend(trim_by_overlap(box_with_scores, overlap_threshold))
    return boxes_with_scores_trimmed

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
        # BGR 调色板
        self.palette: Sequence[tuple[int, int, int]] = palette or [
            (0, 0, 255),  # 红
            (0, 255, 0),  # 绿
            (255, 0, 0),  # 蓝
            (0, 255, 255),  # 黄
            (255, 0, 255),  # 品红
            (255, 255, 0),  # 青
            (128, 0, 128),  # 紫
            (0, 128, 255),  # 橙
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
        return boxes, scores

    def predict_with_ocr(self, image: Image.Image, threshold: float = 0.9, padding: int = 3) -> Iterable[Sequence[float]]:
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
        
        return boxes, scores

    def annotate(
        self,
        boxes: Iterable[Sequence[float]],
        pil_image: Image.Image,
        start_index: int = 1,
    ) -> Image.Image:
        """
        根据给定的 boxes 在图片上绘制彩色边框和序号标签（1 起编）。

        标签放置规则：
        1. 序号标签彼此不重叠（硬约束）。
        2. 序号标签尽量不与其它 bbox 重叠；无法满足时允许覆盖 bbox，但标签间仍不重叠。
        3. 方向优先级：正上方 → 正下方 → 右方居中 → 左边居中。
        4. 边界：标签背景不得超出图像范围。
        5. 无合适外侧位置时使用框内左上角作为第 5 个候选（方向 id 4），保证极端密集时仍有可放位置。
        6. 当四方向均无 Tier1（即必须与其它 bbox 或已放标签重叠）时，在 Tier2/Tier3 中按“不进一步
           制造更多重叠”优先：选择与其它 bbox 及已放标签的重叠数最少的方向；同分时按重叠面积升序。

        选择逻辑（三档）：生成五个候选（上/下/右/左 + 框内左上角）后，方向 4 排在最后，其余保持上→下→右→左顺序；
        Tier1：在边界内且不覆盖其它 bbox 且不覆盖已放置标签；Tier2：在边界内且不覆盖已放置标签，
        若有多个候选则按重叠数（及重叠面积）最小选取；Tier3：在边界内，若有多个候选则同样按重叠
        最少选取；若无则取第一个候选并裁剪到图像边界。

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

        # 已放置的标签矩形，用于保证标签彼此不重叠
        placed_label_rects: List[Tuple[int, int, int, int]] = []

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
                """规则 2：标签背景是否在图像范围内。"""
                return bg_x1 >= 0 and bg_y1 >= 0 and bg_x2 <= width and bg_y2 <= height

            def _overlaps_other(bg_x1: int, bg_y1: int, bg_x2: int, bg_y2: int) -> bool:
                """标签矩形是否与其它元素 box 相交。"""
                label_rect = (bg_x1, bg_y1, bg_x2, bg_y2)
                for j in range(n_boxes):
                    if j == i:
                        continue
                    if _bboxes_overlap(label_rect, boxes_rects[j]):
                        return True
                return False

            def _overlaps_placed_labels(bg_x1: int, bg_y1: int, bg_x2: int, bg_y2: int) -> bool:
                """标签矩形是否与已放置的任一标签相交（保证标签彼此不重叠）。"""
                label_rect = (bg_x1, bg_y1, bg_x2, bg_y2)
                for pr in placed_label_rects:
                    if _bboxes_overlap(label_rect, pr):
                        return True
                return False

            def _overlap_score(bg_x1: int, bg_y1: int, bg_x2: int, bg_y2: int) -> Tuple[int, int]:
                """用于 Tier2/Tier3 排序：优先不制造更多重叠。(重叠元素总数, 重叠面积总和)。"""
                label_rect = (bg_x1, bg_y1, bg_x2, bg_y2)
                count_bbox = 0
                count_placed = 0
                area_total = 0
                for j in range(n_boxes):
                    if j == i:
                        continue
                    if _bboxes_overlap(label_rect, boxes_rects[j]):
                        count_bbox += 1
                        area_total += _intersection_area(label_rect, boxes_rects[j])
                for pr in placed_label_rects:
                    if _bboxes_overlap(label_rect, pr):
                        count_placed += 1
                        area_total += _intersection_area(label_rect, pr)
                return (count_bbox + count_placed, area_total)

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
            # 方向 4（框内左上角）始终排在最后，其余保持 0,1,2,3 顺序
            candidates = sorted(raw_candidates, key=lambda c: (1 if c[0] == 4 else 0, c[0]))
            candidates = [c[1] for c in candidates]

            # --- 选择位置：三档。Tier1 不压 bbox 且不压已放标签；Tier2 仅不压已放标签；Tier3 仅边界内 ---
            def _clip_chosen(
                bg_x1: int, bg_y1: int, bg_x2: int, bg_y2: int, tx: int, ty: int
            ) -> Tuple[Tuple[int, int, int, int], Tuple[int, int]]:
                return (
                    (max(0, bg_x1), max(0, bg_y1), min(width, bg_x2), min(height, bg_y2)),
                    (max(0, tx), min(height - 1, ty)),
                )

            chosen = None
            for (bg_x1, bg_y1, bg_x2, bg_y2), (tx, ty) in candidates:
                if (
                    _in_bounds(bg_x1, bg_y1, bg_x2, bg_y2)
                    and not _overlaps_other(bg_x1, bg_y1, bg_x2, bg_y2)
                    and not _overlaps_placed_labels(bg_x1, bg_y1, bg_x2, bg_y2)
                ):
                    chosen = _clip_chosen(bg_x1, bg_y1, bg_x2, bg_y2, tx, ty)
                    break
            if chosen is None:
                # Tier2: 不压已放标签但允许压 bbox；按“重叠最少”优先（先重叠数再重叠面积）
                tier2 = [
                    ((bg_x1, bg_y1, bg_x2, bg_y2), (tx, ty))
                    for (bg_x1, bg_y1, bg_x2, bg_y2), (tx, ty) in candidates
                    if _in_bounds(bg_x1, bg_y1, bg_x2, bg_y2)
                    and not _overlaps_placed_labels(bg_x1, bg_y1, bg_x2, bg_y2)
                ]
                if tier2:
                    tier2.sort(key=lambda c: _overlap_score(c[0][0], c[0][1], c[0][2], c[0][3]))
                    (bg_x1, bg_y1, bg_x2, bg_y2), (tx, ty) = tier2[0]
                    chosen = _clip_chosen(bg_x1, bg_y1, bg_x2, bg_y2, tx, ty)
            if chosen is None:
                # Tier3: 仅边界内；按“重叠最少”优先（重叠元素数 + 重叠面积）
                tier3 = [
                    ((bg_x1, bg_y1, bg_x2, bg_y2), (tx, ty))
                    for (bg_x1, bg_y1, bg_x2, bg_y2), (tx, ty) in candidates
                    if _in_bounds(bg_x1, bg_y1, bg_x2, bg_y2)
                ]
                if tier3:
                    tier3.sort(key=lambda c: _overlap_score(c[0][0], c[0][1], c[0][2], c[0][3]))
                    (bg_x1, bg_y1, bg_x2, bg_y2), (tx, ty) = tier3[0]
                    chosen = _clip_chosen(bg_x1, bg_y1, bg_x2, bg_y2, tx, ty)
            if chosen is None:
                chosen = _clip_chosen(
                    candidates[0][0][0], candidates[0][0][1],
                    candidates[0][0][2], candidates[0][0][3],
                    candidates[0][1][0], candidates[0][1][1],
                )

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
            placed_label_rects.append((bg_x1, bg_y1, bg_x2, bg_y2))

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
        boxes, scores = self.predict(image, threshold=threshold)
        boxes_with_scores = list(zip(boxes, scores))
        try:
            boxes_with_scores_ocr, scores_ocr = self.predict_with_ocr(image, padding=padding)
            boxes_with_scores_ocr = list(zip(boxes_with_scores_ocr, scores_ocr))
            boxes_with_scores = [*boxes_with_scores, *boxes_with_scores_ocr]
        except Exception as e:
            import warnings
            warnings.warn(f"OCR skipped in predict_and_annotate_all: {e!r}. Using RF-DETR boxes only.", stacklevel=2)
        boxes_with_scores_trimmed = trim_by_overlab_optimize(boxes_with_scores, overlap_threshold=overlap_threshold)
        boxes_sorted = _sort_boxes_lrtb([b[0] for b in boxes_with_scores_trimmed], image.height)
        annotated_img = self.annotate(boxes_sorted, image, start_index=1)
        return annotated_img, boxes_sorted

if __name__ == "__main__":
    base_dir = "/Users/yunyun/Desktop/agent-zero"
    image = Image.open(base_dir + "/微信截图1.png")
    box_annotator = BoxAnnotator()
    annotated_img, boxes = box_annotator.predict_and_annotate_all(image)
    annotated_img.save(base_dir + "/test_annotated.png")

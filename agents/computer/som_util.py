from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import cv2
import numpy as np
from PIL import Image

from rfdetr.detr import RFDETRMedium


def sort_boxes_lrtb(
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

    def annotate(
        self,
        boxes: Iterable[Sequence[float]],
        pil_image: Image.Image,
    ) -> Image.Image:
        """
        根据给定的 boxes 在图片上绘制彩色边框和序号标签（1 起编）。

        标签放置规则（按优先级）：
        1. 方向优先级：正上方 → 正下方 → 右方居中 → 左边居中。
        2. 边界：标签背景不得超出图像范围。
        3. 不覆盖其他元素：标签矩形不得与其它 box 相交。
        4. 邻近降权：若某方向 50 像素内有其它元素，该方向不优先考虑，避免两标签贴在一起；
           仍会参与候选，仅排序时靠后。

        选择逻辑：按上述顺序生成四个候选位置，先排除“该方向 50px 内有其他元素”的降权；
        再在候选里取第一个满足「在边界内且不覆盖其它元素」的位置；若无则取第一个在边界内的
        位置（允许覆盖）；若仍无则取第一个候选并做边界裁剪。

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

        def _rects_overlap(a: Tuple[int, int, int, int], b: Tuple[int, int, int, int]) -> bool:
            ax1, ay1, ax2, ay2 = a
            bx1, by1, bx2, by2 = b
            return not (ax2 <= bx1 or bx2 <= ax1 or ay2 <= by1 or by2 <= ay1)

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
        _NEARBY_PX = 50  # 规则 4：该方向在此距离内有其他元素则降权
        n_palette = len(self.palette)
        # 相邻序号使用色相间隔更大的颜色，便于区分
        color_step = max(1, (n_palette // 2) + 1)

        for i in range(n_boxes):
            x1, y1, x2, y2 = boxes_rects[i]

            color_box = self.palette[(i * color_step) % n_palette]
            color_text = self._contrasting_text_color(color_box)

            # --- 绘制元素边框 ---
            cv2.rectangle(cv_img, (x1, y1), (x2, y2), color_box, 2)

            # --- 标签候选：规则 1 的四个方向（上/下/右/左）---
            label = str(i + 1)
            tw, th = _get_label_size(label)
            cx = (x1 + x2) // 2
            cy = (y1 + y2) // 2

            def _in_bounds(bg_x1: int, bg_y1: int, bg_x2: int, bg_y2: int) -> bool:
                """规则 2：标签背景是否在图像范围内。"""
                return bg_x1 >= 0 and bg_y1 >= 0 and bg_x2 <= width and bg_y2 <= height

            def _overlaps_other(bg_x1: int, bg_y1: int, bg_x2: int, bg_y2: int) -> bool:
                """规则 3：标签矩形是否与其它元素 box 相交。"""
                label_rect = (bg_x1, bg_y1, bg_x2, bg_y2)
                for j in range(n_boxes):
                    if j == i:
                        continue
                    if _rects_overlap(label_rect, boxes_rects[j]):
                        return True
                return False

            # --- 规则 4：标记“该方向 50px 内有其他元素”的方向，用于降权 ---
            # 方向 id：0=上 1=下 2=右 3=左
            directions_nearby: List[int] = []
            for j in range(n_boxes):
                if j == i:
                    continue
                ox1, oy1, ox2, oy2 = boxes_rects[j]
                if oy2 <= y1 and y1 - oy2 <= _NEARBY_PX:
                    if 0 not in directions_nearby:
                        directions_nearby.append(0)
                if oy1 >= y2 and oy1 - y2 <= _NEARBY_PX:
                    if 1 not in directions_nearby:
                        directions_nearby.append(1)
                if ox1 >= x2 and ox1 - x2 <= _NEARBY_PX:
                    if 2 not in directions_nearby:
                        directions_nearby.append(2)
                if ox2 <= x1 and x1 - ox2 <= _NEARBY_PX:
                    if 3 not in directions_nearby:
                        directions_nearby.append(3)

            # 四个候选：标签与 bbox 贴齐无空白。(方向id, (标签背景 rect, 文字坐标))
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
            ]
            candidates = sorted(
                raw_candidates,
                key=lambda c: (1 if c[0] in directions_nearby else 0, c[0]),
            )
            candidates = [c[1] for c in candidates]

            # --- 选择位置：先满足规则 2+3，否则仅满足规则 2，最后做边界裁剪 ---
            chosen = None
            for (bg_x1, bg_y1, bg_x2, bg_y2), (tx, ty) in candidates:
                if _in_bounds(bg_x1, bg_y1, bg_x2, bg_y2) and not _overlaps_other(
                    bg_x1, bg_y1, bg_x2, bg_y2
                ):
                    chosen = (
                        max(0, bg_x1),
                        max(0, bg_y1),
                        min(width, bg_x2),
                        min(height, bg_y2),
                    ), (max(0, tx), min(height - 1, ty))
                    break
            if chosen is None:
                # 兜底：选第一个在边界内的位置（允许覆盖其它元素）
                for (bg_x1, bg_y1, bg_x2, bg_y2), (tx, ty) in candidates:
                    if _in_bounds(bg_x1, bg_y1, bg_x2, bg_y2):
                        chosen = (
                            max(0, bg_x1),
                            max(0, bg_y1),
                            min(width, bg_x2),
                            min(height, bg_y2),
                        ), (max(0, tx), min(height - 1, ty))
                        break
            if chosen is None:
                # 最终兜底：取第一个候选并裁剪到图像边界
                chosen = candidates[0]
                chosen = (
                    (
                        max(0, chosen[0][0]),
                        max(0, chosen[0][1]),
                        min(width, chosen[0][2]),
                        min(height, chosen[0][3]),
                    ),
                    (max(0, chosen[1][0]), min(height - 1, chosen[1][1])),
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

        # cv2 -> PIL
        return Image.fromarray(cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB))

    def predict_and_annotate(self, image: Image.Image, threshold: float = 0.35) -> Tuple[Image.Image, Iterable[float]]:
        """
        预测图片中的物体并进行标注。
        返回值为标注后的图片和 scores。如果 scores 小于 threshold，则不返回。
        """
        boxes, scores = self.predict(image, threshold=threshold)
        return self.annotate(boxes, image), scores
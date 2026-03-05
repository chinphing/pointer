from __future__ import annotations

from typing import Iterable, List, Optional, Sequence, Tuple

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
        根据给定的 boxes 在图片上绘制彩色边框和序号标签。

        参数
        ----
        boxes:
            可迭代对象，元素为长度至少为 4 的序列 [x1, y1, x2, y2]，可以是 numpy、list 或 tensor 等。
            对应图片上标注的序号从1开始编号
        pil_image:
            输入的 PIL Image 对象。

        返回
        ----
        标注后的 PIL Image 对象。
        """
        # PIL -> cv2 (BGR)
        cv_img = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
        height, width = cv_img.shape[:2]

        for i, box in enumerate(boxes):
            x1, y1, x2, y2 = map(int, map(float, box[:4]))
            x1 = max(0, min(x1, width - 1))
            x2 = max(0, min(x2, width - 1))
            y1 = max(0, min(y1, height - 1))
            y2 = max(0, min(y2, height - 1))

            color_box = self.palette[i % len(self.palette)]
            color_text = self._contrasting_text_color(color_box)

            # 边框
            cv2.rectangle(cv_img, (x1, y1), (x2, y2), color_box, 2)

            # 标签：序号置于 bbox 正上方居中，若空间不足则正下方居中
            label = f"{i + 1}"
            (tw, th), _ = cv2.getTextSize(
                label, self.font, self.font_scale, self.thickness
            )
            pad = 4
            cx = (x1 + x2) // 2
            tx = cx - tw // 2
            tx = max(0, min(tx, width - tw - pad))
            # Prefer above bbox
            ty_above = y1 - pad
            bg_y1_above = ty_above - th - pad
            if bg_y1_above >= 0:
                ty = ty_above
                bg_x1 = tx
                bg_y1 = bg_y1_above
                bg_x2 = tx + tw + pad
                bg_y2 = ty + pad // 2
            else:
                # Below bbox
                ty = y2 + th + pad
                bg_x1 = tx
                bg_y1 = y2 + pad
                bg_x2 = tx + tw + pad
                bg_y2 = min(height, ty + pad // 2)
            bg_x1 = max(0, bg_x1)
            bg_y1 = max(0, bg_y1)
            bg_x2 = min(width, bg_x2)
            bg_y2 = min(height, bg_y2)

            cv2.rectangle(cv_img, (bg_x1, bg_y1), (bg_x2, bg_y2), color_box, -1)
            cv2.putText(
                cv_img,
                label,
                (tx + 2, ty),
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
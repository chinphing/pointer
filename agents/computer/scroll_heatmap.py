"""
Image hash for scroll validation and scroll-region detection from difference heatmaps.

All bboxes in this module use (x1, y1, x2, y2) format: left, top, right, bottom in image coordinates.

- _image_hash: stable hash for before/after scroll comparison.
- scroll_region_bbox_from_diff: base heatmap method — list of bboxes of scroll regions from abs-diff.
- find_nearest_scroll_region: given mouse (x, y) and bbox list, return the scroll region nearest to the mouse.
- scroll_pixels_from_region: scroll distance (pixel shift) of the specified target region bbox via correlation.
- ideal_scroll_ticks_for_80_percent: ideal scroll ticks to move 80% of region height.
- compute_dynamic_mask_bboxes: bboxes of dynamic content (video/animations) from two frames.
- scroll_region_bbox_from_diff_masked: list of scroll region bboxes with dynamic areas masked out.
"""

from __future__ import annotations

import hashlib
from typing import List, Optional, Tuple, Union

import cv2
import numpy as np
from PIL import Image

# -----------------------------------------------------------------------------
# 1) Image hash (moved from actions.py)
# -----------------------------------------------------------------------------


def _image_hash(
    pil_img: Image.Image,
    cell_size: int = 16,
    kernel_size: int = 2,
) -> str:
    """Stable hash for before/after scroll comparison (avoids hover/tooltip noise)."""
    side = max(8, min(pil_img.width, pil_img.height) // max(1, cell_size))
    gray = pil_img.convert("L").resize((side, side), Image.Resampling.LANCZOS)
    arr = np.array(gray, dtype=np.uint8)
    if kernel_size >= 1:
        k = max(2, int(kernel_size))
        kernel = np.ones((k, k), np.uint8)
        arr = cv2.morphologyEx(arr, cv2.MORPH_OPEN, kernel)
    return hashlib.md5(arr.tobytes()).hexdigest()


# -----------------------------------------------------------------------------
# Helpers: ensure BGR ndarray
# -----------------------------------------------------------------------------


def _to_gray_uint8(img: Union[np.ndarray, Image.Image]) -> np.ndarray:
    if isinstance(img, Image.Image):
        return np.array(img.convert("L"), dtype=np.uint8)
    if img.ndim == 3:
        return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return np.asarray(img, dtype=np.uint8)


# -----------------------------------------------------------------------------
# Base heatmap method: diff image -> single bbox (envelope of changed region)
# -----------------------------------------------------------------------------


def _scroll_region_bbox_from_diff_image(
    diff: np.ndarray,
    cell_size: int = 16,
    mean_threshold: float = 5.0,
    open_kernel_size: int = 2,
    min_region_cells: int = 4,
    padding: int = 5,
    min_size: int = 50,
    connectivity: int = 8,
    merge_gap: int = 1,
) -> List[Tuple[int, int, int, int]]:
    """
    From a single grayscale difference image (uint8), compute all significant changed
    regions as a list of bboxes (x1, y1, x2, y2). Uses grid scaling, threshold, morphology,
    optional dilation (merge_gap), and connected components; returns one bbox per region.
    padding: 连通域外接矩形映射回原图后向四周扩展的像素数，避免裁切时贴边漏掉边缘；单位原图像素。
    merge_gap: 做连通域前先膨胀的半径（缩放图像素）。>0 时相距不超过 merge_gap 像素的块会并成一块。
    """
    h, w = diff.shape[:2]
    cell_size = max(1, int(cell_size))
    scale_w = max(1, w // cell_size)
    scale_h = max(1, h // cell_size)
    scaled = cv2.resize(diff, (scale_w, scale_h), interpolation=cv2.INTER_AREA)
    _, mask = cv2.threshold(scaled, mean_threshold, 255, cv2.THRESH_BINARY)
    if open_kernel_size >= 1:
        kernel = np.ones((open_kernel_size, open_kernel_size), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    if merge_gap >= 1:
        k = int(merge_gap) * 2 + 1
        kernel = np.ones((k, k), np.uint8)
        mask = cv2.dilate(mask, kernel)
    connectivity = 8 if connectivity != 4 else 4
    num_labels, _, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=connectivity)
    boxes: List[Tuple[int, int, int, int]] = []
    for i in range(1, num_labels):
        area = stats[i, cv2.CC_STAT_AREA]
        if min_region_cells >= 1 and area < min_region_cells:
            continue
        sx = stats[i, cv2.CC_STAT_LEFT]
        sy = stats[i, cv2.CC_STAT_TOP]
        sw = stats[i, cv2.CC_STAT_WIDTH]
        sh = stats[i, cv2.CC_STAT_HEIGHT]
        x_min = sx * cell_size
        y_min = sy * cell_size
        x_max = (sx + sw) * cell_size
        y_max = (sy + sh) * cell_size
        x1 = max(0, x_min - padding)
        y1 = max(0, y_min - padding)
        x2 = min(w, x_max + padding)
        y2 = min(h, y_max + padding)
        if (x2 - x1) >= min_size and (y2 - y1) >= min_size:
            boxes.append((x1, y1, x2, y2))
    return boxes


def _envelope_bbox(bboxes: List[Tuple[int, int, int, int]]) -> Optional[Tuple[int, int, int, int]]:
    """Return one bbox (x1, y1, x2, y2) enclosing all given bboxes, or None if empty."""
    if not bboxes:
        return None
    x1 = min(b[0] for b in bboxes)
    y1 = min(b[1] for b in bboxes)
    x2 = max(b[2] for b in bboxes)
    y2 = max(b[3] for b in bboxes)
    return (x1, y1, x2, y2)


def find_nearest_scroll_region(
    mouse_x: int,
    mouse_y: int,
    bboxes: List[Tuple[int, int, int, int]],
) -> Optional[Tuple[int, int, int, int]]:
    """
    Given mouse position (mouse_x, mouse_y) and a list of scroll region bboxes,
    return the bbox that is nearest to the mouse. Priority: (1) if the mouse is
    inside one or more bboxes, return the smallest containing bbox; (2) otherwise
    return the bbox whose edge (boundary) is closest to the mouse.
    """
    if not bboxes:
        return None

    def contains(b: Tuple[int, int, int, int]) -> bool:
        x1, y1, x2, y2 = b
        return (x1 <= mouse_x < x2) and (y1 <= mouse_y < y2)

    def edge_dist_sq(b: Tuple[int, int, int, int]) -> float:
        """Squared distance from (mouse_x, mouse_y) to the nearest point on the bbox (edge or inside)."""
        x1, y1, x2, y2 = b
        cx = max(x1, min(mouse_x, x2))
        cy = max(y1, min(mouse_y, y2))
        return (mouse_x - cx) ** 2 + (mouse_y - cy) ** 2

    containing = [b for b in bboxes if contains(b)]
    if containing:
        return min(containing, key=lambda b: (b[2] - b[0]) * (b[3] - b[1]))
    return min(bboxes, key=edge_dist_sq)


# -----------------------------------------------------------------------------
# 1) Base: scroll region bbox from two images (absolute difference heatmap)
# -----------------------------------------------------------------------------


def scroll_region_bbox_from_diff(
    img_before: Union[np.ndarray, Image.Image],
    img_after: Union[np.ndarray, Image.Image],
    cell_size: int = 16,
    mean_threshold: float = 5.0,
    open_kernel_size: int = 2,
    min_region_cells: int = 4,
    padding: int = 5,
    min_size: int = 50,
    connectivity: int = 8,
    merge_gap: int = 1,
) -> List[Tuple[int, int, int, int]]:
    """
    Base heatmap method: compute scroll regions as a list of bboxes (x1, y1, x2, y2) from the
    absolute difference of two screenshots. Uses grid (cell_size), threshold,
    morphology, optional dilation (merge_gap), and connected components.
    padding: 差异区域外接矩形向四周扩展的像素数（原图），避免贴边裁切。
    merge_gap: 膨胀半径（缩放图像素），>0 时相近的差异块会合并。
    """
    g1 = _to_gray_uint8(img_before)
    g2 = _to_gray_uint8(img_after)
    if g1.shape != g2.shape:
        return []
    diff = cv2.absdiff(g1, g2)
    return _scroll_region_bbox_from_diff_image(
        diff,
        cell_size=cell_size,
        mean_threshold=mean_threshold,
        open_kernel_size=open_kernel_size,
        min_region_cells=min_region_cells,
        padding=padding,
        min_size=min_size,
        connectivity=connectivity,
        merge_gap=merge_gap,
    )


# -----------------------------------------------------------------------------
# 2) Pixel scroll distance via correlation in the target region
# -----------------------------------------------------------------------------


def scroll_pixels_from_region(
    img_before: Union[np.ndarray, Image.Image],
    img_after: Union[np.ndarray, Image.Image],
    bbox: Tuple[int, int, int, int],
) -> Tuple[float, float]:
    """
    Compute the scroll distance (pixel shift) of the specified target region bbox between
    img_before and img_after. bbox is (x1, y1, x2, y2). Uses phase correlation in that crop.
    Returns (shift_x, shift_y) in pixels; positive dy typically means content scrolled up
    (user scrolled down).
    """
    x1, y1, x2, y2 = bbox
    g1 = _to_gray_uint8(img_before)
    g2 = _to_gray_uint8(img_after)
    if g1.shape != g2.shape:
        return (0.0, 0.0)
    # clamp bbox to image
    h_img, w_img = g1.shape[:2]
    x1 = max(0, min(x1, w_img - 1))
    y1 = max(0, min(y1, h_img - 1))
    x2 = max(x1 + 1, min(x2, w_img))
    y2 = max(y1 + 1, min(y2, h_img))
    crop1 = g1[y1:y2, x1:x2].astype(np.float32)
    crop2 = g2[y1:y2, x1:x2].astype(np.float32)
    try:
        (shift_x, shift_y), _ = cv2.phaseCorrelate(crop1, crop2)
        return (float(shift_x), float(shift_y))
    except Exception:
        return (0.0, 0.0)


# -----------------------------------------------------------------------------
# 3) Ideal scroll ticks for 80% of region height
# -----------------------------------------------------------------------------


def ideal_scroll_ticks_for_percentage(
    pixel_scroll_dy: float,
    scroll_ticks_used: int,
    region_height: int,
    percentage: float = 0.5,
) -> float:
    """
    Given the pixel scroll distance (dy) from (2) and the scroll ticks used in that
    experiment, compute the ideal scroll ticks to move the specified percentage of the region height.
    scroll_ticks_used is the input parameter (e.g. the ticks you used when measuring
    pixel_scroll_dy). Returns the recommended ticks for the specified percentage of screen scroll.
    """
    if scroll_ticks_used == 0 or region_height <= 0:
        return 0.0
    pixels_per_tick = abs(pixel_scroll_dy) / abs(scroll_ticks_used)
    if pixels_per_tick <= 0:
        return 0.0
    target_pixels = percentage * float(region_height)
    sign = -1 if pixel_scroll_dy < 0 else 1
    return sign * (target_pixels / pixels_per_tick)


# -----------------------------------------------------------------------------
# 4a) Dynamic mask: bboxes of changed regions between two frames (no scroll)
# -----------------------------------------------------------------------------


def compute_dynamic_mask_bboxes(
    img_before: Union[np.ndarray, Image.Image],
    img_after: Union[np.ndarray, Image.Image],
    cell_size: int = 16,
    mean_threshold: float = 5.0,
    open_kernel_size: int = 2,
    min_region_cells: int = 4,
    padding: int = 5,
    min_size: int = 50,
    connectivity: int = 8,
    merge_gap: int = 1,
) -> List[Tuple[int, int, int, int]]:
    """
    Compute bboxes of dynamic content (video/animations) from two screenshots
    taken with a time gap (e.g. 1s), without scrolling. Uses the same pipeline
    as scroll_region_bbox_from_diff but returns all changed regions as a list.
    padding: 差异区域外接矩形向四周扩展的像素数（原图）。
    merge_gap: 膨胀半径，>0 时相近的差异块会合并。
    """
    g1 = _to_gray_uint8(img_before)
    g2 = _to_gray_uint8(img_after)
    if g1.shape != g2.shape:
        return []
    h, w = g1.shape[:2]
    diff = cv2.absdiff(g1, g2)
    cell_size = max(1, int(cell_size))
    scale_w = max(1, w // cell_size)
    scale_h = max(1, h // cell_size)
    scaled = cv2.resize(diff, (scale_w, scale_h), interpolation=cv2.INTER_AREA)
    _, mask = cv2.threshold(scaled, mean_threshold, 255, cv2.THRESH_BINARY)
    if open_kernel_size >= 1:
        kernel = np.ones((open_kernel_size, open_kernel_size), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    if merge_gap >= 1:
        k = int(merge_gap) * 2 + 1
        kernel = np.ones((k, k), np.uint8)
        mask = cv2.dilate(mask, kernel)
    connectivity = 8 if connectivity != 4 else 4
    num_labels, _, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=connectivity)
    result: List[Tuple[int, int, int, int]] = []
    for i in range(1, num_labels):
        area = stats[i, cv2.CC_STAT_AREA]
        if min_region_cells >= 1 and area < min_region_cells:
            continue
        sx = stats[i, cv2.CC_STAT_LEFT]
        sy = stats[i, cv2.CC_STAT_TOP]
        sw = stats[i, cv2.CC_STAT_WIDTH]
        sh = stats[i, cv2.CC_STAT_HEIGHT]
        x_min = sx * cell_size
        y_min = sy * cell_size
        x_max = (sx + sw) * cell_size
        y_max = (sy + sh) * cell_size
        x1 = max(0, x_min - padding)
        y1 = max(0, y_min - padding)
        x2 = min(w, x_max + padding)
        y2 = min(h, y_max + padding)
        if (x2 - x1) >= min_size and (y2 - y1) >= min_size:
            result.append((x1, y1, x2, y2))
    return result


# -----------------------------------------------------------------------------
# 4b) Scroll region bbox with dynamic areas masked out
# -----------------------------------------------------------------------------


def scroll_region_bbox_from_diff_masked(
    img_before: Union[np.ndarray, Image.Image],
    img_after: Union[np.ndarray, Image.Image],
    mask_bboxes: List[Tuple[int, int, int, int]],
    cell_size: int = 16,
    mean_threshold: float = 5.0,
    open_kernel_size: int = 2,
    min_region_cells: int = 4,
    padding: int = 5,
    min_size: int = 50,
    connectivity: int = 8,
    merge_gap: int = 1,
) -> List[Tuple[int, int, int, int]]:
    """
    Same as scroll_region_bbox_from_diff, but before computing the final bbox
    the difference image has all mask_bboxes regions set to 0 (so video/animations
    do not affect the scroll region detection). mask_bboxes typically come from
    compute_dynamic_mask_bboxes(before_wait, after_wait_1s). padding: 差异区域外接矩形向四周扩展像素数。merge_gap: 膨胀半径。
    """
    g1 = _to_gray_uint8(img_before)
    g2 = _to_gray_uint8(img_after)
    if g1.shape != g2.shape:
        return []
    diff = cv2.absdiff(g1, g2)
    h_img, w_img = diff.shape[:2]
    for (mx1, my1, mx2, my2) in mask_bboxes:
        x1 = max(0, min(mx1, w_img))
        y1 = max(0, min(my1, h_img))
        x2 = min(mx2, w_img)
        y2 = min(my2, h_img)
        if x2 > x1 and y2 > y1:
            diff[y1:y2, x1:x2] = 0
    return _scroll_region_bbox_from_diff_image(
        diff,
        cell_size=cell_size,
        mean_threshold=mean_threshold,
        open_kernel_size=open_kernel_size,
        min_region_cells=min_region_cells,
        padding=padding,
        min_size=min_size,
        connectivity=connectivity,
        merge_gap=merge_gap,
    )


# -----------------------------------------------------------------------------
# main: test with two images, visualize
# -----------------------------------------------------------------------------


def _draw_bbox(img: np.ndarray, bbox: Optional[Tuple[int, int, int, int]], color: Tuple[int, int, int], label: str = "") -> np.ndarray:
    out = img.copy()
    if img.ndim == 2:
        out = cv2.cvtColor(out, cv2.COLOR_GRAY2BGR)
    if bbox is not None:
        x1, y1, x2, y2 = bbox
        cv2.rectangle(out, (x1, y1), (x2, y2), color, 3)
        if label:
            cv2.putText(out, label, (x1, max(y1 - 6, 0)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
    return out


def _draw_bboxes(img: np.ndarray, bboxes: List[Tuple[int, int, int, int]], color: Tuple[int, int, int]) -> np.ndarray:
    out = img.copy()
    if img.ndim == 2:
        out = cv2.cvtColor(out, cv2.COLOR_GRAY2BGR)
    for x1, y1, x2, y2 in bboxes:
        cv2.rectangle(out, (x1, y1), (x2, y2), color, 2)
    return out


def main() -> None:
    import sys
    import matplotlib.pyplot as plt

    base_dir = "/Users/yunyun/Documents/PyProjects/agent-zero/agents/computer/snapshots/"
    path_before = base_dir + "K4eBhi6q/20260315_084131_raw.png"
    path_after = base_dir + "K4eBhi6q/20260315_084206_raw.png"
    scroll_ticks_used = -10
    no_show = False

    img1 = cv2.imread(path_before)
    img2 = cv2.imread(path_after)
    if img1 is None or img2 is None:
        print("Error: could not load images.", file=sys.stderr)
        sys.exit(1)
    if img1.shape != img2.shape:
        print("Warning: image shapes differ, results may be invalid.", file=sys.stderr)

    # 1) Base: scroll region bboxes (multiple regions)
    bboxes = scroll_region_bbox_from_diff(img1, img2, mean_threshold=5)
    print(f"1) scroll_region_bbox_from_diff -> {len(bboxes)} region(s): {bboxes}")
    envelope = find_nearest_scroll_region(mouse_x=700, mouse_y=500, bboxes=bboxes)

    # 2) Pixel shift in envelope region
    shift_x, shift_y = (0.0, 0.0) if envelope is None else scroll_pixels_from_region(img1, img2, envelope)
    print(f"2) scroll_pixels_from_region -> shift (x, y): ({shift_x:.2f}, {shift_y:.2f}) px, envelope: {envelope}")

    # 3) Ideal ticks for 80% of region height
    region_h = (envelope[3] - envelope[1]) if envelope else 0
    ideal_ticks = ideal_scroll_ticks_for_percentage(shift_y, scroll_ticks_used, region_h) if region_h else 0.0
    print(f"3) ideal_scroll_ticks_for_percentage (region_h={region_h}, ticks_used={scroll_ticks_used}) -> {ideal_ticks:.1f} ticks")

    # # 4) Dynamic mask bboxes (same two images as "before/after wait")
    # dynamic_bboxes = compute_dynamic_mask_bboxes(img1, img2)
    # print(f"4) compute_dynamic_mask_bboxes -> {len(dynamic_bboxes)} region(s)")

    # # 5) Scroll region with dynamic areas masked out
    # bbox_masked = scroll_region_bbox_from_diff_masked(img1, img2, dynamic_bboxes) if dynamic_bboxes else bbox
    # print(f"5) scroll_region_bbox_from_diff_masked -> bbox: {bbox_masked}")

    # Diff heatmap (raw)
    g1 = _to_gray_uint8(img1)
    g2 = _to_gray_uint8(img2)
    diff_raw = cv2.absdiff(g1, g2)
    diff_vis = cv2.applyColorMap(diff_raw, cv2.COLORMAP_HOT)

    # Visualize
    fig, axes = plt.subplots(2, 3, figsize=(14, 9))
    fig.suptitle("scroll_heatmap test: before vs after", fontsize=12)

    # Row 0: before + bboxes, after + bboxes, diff heatmap
    axes[0, 0].imshow(cv2.cvtColor(_draw_bboxes(img1, bboxes, (0, 0, 255)), cv2.COLOR_BGR2RGB))
    axes[0, 0].set_title("Before + scroll regions (red)")
    axes[0, 0].axis("off")

    axes[0, 1].imshow(cv2.cvtColor(_draw_bboxes(img2, bboxes, (0, 0, 255)), cv2.COLOR_BGR2RGB))
    axes[0, 1].set_title("After + scroll regions (red)")
    axes[0, 1].axis("off")

    axes[0, 2].imshow(cv2.cvtColor(diff_vis, cv2.COLOR_BGR2RGB))
    axes[0, 2].set_title("Abs diff (heatmap)")
    axes[0, 2].axis("off")

    # # Row 1: before + dynamic bboxes (green), before + masked bbox (blue), summary text
    # axes[1, 0].imshow(cv2.cvtColor(_draw_bboxes(img1, dynamic_bboxes, (0, 255, 0)), cv2.COLOR_BGR2RGB))
    # axes[1, 0].set_title("Dynamic mask regions (green)")
    # axes[1, 0].axis("off")

    # axes[1, 1].imshow(cv2.cvtColor(_draw_bbox(img1, bbox_masked, (255, 0, 0), "masked"), cv2.COLOR_BGR2RGB))
    # axes[1, 1].set_title("Scroll region masked (blue)")
    # axes[1, 1].axis("off")

    # summary = (
    #     f"shift (x,y): ({shift_x:.1f}, {shift_y:.1f}) px\n"
    #     f"ideal ticks (80%): {ideal_ticks:.1f}\n"
    #     f"dynamic regions: {len(dynamic_bboxes)}"
    # )
    # axes[1, 2].text(0.1, 0.5, summary, fontsize=11, verticalalignment="center", family="monospace")
    # axes[1, 2].set_title("Summary")
    # axes[1, 2].axis("off")

    plt.tight_layout()
    if not no_show:
        plt.show()
    else:
        plt.savefig("/tmp/scroll_heatmap_test.png", dpi=120, bbox_inches="tight")
        print("Saved /tmp/scroll_heatmap_test.png")


if __name__ == "__main__":
    main()

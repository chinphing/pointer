"""Draw mouse cursor and focus caret on screenshots. Shared by screen inject and periodic preview."""
from __future__ import annotations

import os
from io import BytesIO
from typing import Optional, Tuple

from PIL import Image, ImageDraw

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_CURSOR_POINTER_IMG: Optional[Image.Image] = None
_CURSOR_HOTSPOT = (3, 2)
_CURSOR_SIZE = 32


def _get_cursor_pointer_image() -> Optional[Image.Image]:
    """Load or build cursor-pointer as 32x32 RGBA. Returns None on failure."""
    global _CURSOR_POINTER_IMG
    if _CURSOR_POINTER_IMG is not None:
        return _CURSOR_POINTER_IMG
    try:
        import cairosvg  # type: ignore[import-untyped]
        svg_path = os.path.join(_THIS_DIR, "cursor-pointer.svg")
        if os.path.isfile(svg_path):
            png_bytes = cairosvg.svg2png(url=svg_path, output_width=_CURSOR_SIZE, output_height=_CURSOR_SIZE)
            _CURSOR_POINTER_IMG = Image.open(BytesIO(png_bytes)).convert("RGBA")
            return _CURSOR_POINTER_IMG
    except Exception:
        pass
    try:
        cur = Image.new("RGBA", (_CURSOR_SIZE, _CURSOR_SIZE), (0, 0, 0, 0))
        draw = ImageDraw.Draw(cur)
        pts = [(3, 2), (3, 21), (8, 16), (11, 23), (14, 22), (11, 15), (18, 15)]
        draw.polygon(pts, fill=(255, 255, 255), outline=(0, 0, 0))
        draw.line(pts + [pts[0]], fill=(0, 0, 0), width=1)
        _CURSOR_POINTER_IMG = cur
        return _CURSOR_POINTER_IMG
    except Exception:
        return None


def draw_cursor_pointer_overlay(pil_image: Image.Image, mouse_ix: int, mouse_iy: int) -> Image.Image:
    """Draw cursor at (mouse_ix, mouse_iy) in image coords. Fallback: red circle."""
    cursor = _get_cursor_pointer_image()
    if cursor is not None:
        out = pil_image.copy()
        if out.mode not in ("RGBA", "RGB"):
            out = out.convert("RGB")
        hx, hy = _CURSOR_HOTSPOT
        paste_x = mouse_ix - hx
        paste_y = mouse_iy - hy
        w, h = out.size
        box = (max(0, paste_x), max(0, paste_y), min(w, paste_x + _CURSOR_SIZE), min(h, paste_y + _CURSOR_SIZE))
        if box[0] < box[2] and box[1] < box[3]:
            crop = cursor.crop((box[0] - paste_x, box[1] - paste_y, box[2] - paste_x, box[3] - paste_y))
            mask = crop.split()[3] if crop.mode == "RGBA" else None
            if out.mode == "RGB" and crop.mode == "RGBA":
                crop = crop.convert("RGB")
            out.paste(crop, (box[0], box[1]), mask)
        return out
    out = pil_image.copy()
    if out.mode != "RGB":
        out = out.convert("RGB")
    draw = ImageDraw.Draw(out)
    r = 10
    x1, y1 = mouse_ix - r, mouse_iy - r
    x2, y2 = mouse_ix + r, mouse_iy + r
    draw.ellipse([x1, y1, x2, y2], outline=(255, 0, 0), width=3)
    draw.line([(mouse_ix - r - 2, mouse_iy), (mouse_ix + r + 2, mouse_iy)], fill=(255, 0, 0), width=2)
    draw.line([(mouse_ix, mouse_iy - r - 2), (mouse_ix, mouse_iy + r + 2)], fill=(255, 0, 0), width=2)
    return out


def _sample_luminance(pil_image: Image.Image, cx: int, cy: int, radius: int = 2) -> float:
    w, h = pil_image.size
    pixels = pil_image.load()
    total = 0.0
    count = 0
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            x, y = cx + dx, cy + dy
            if 0 <= x < w and 0 <= y < h:
                p = pixels[x, y]
                if isinstance(p, (list, tuple)):
                    r, g, b = p[0], p[1], p[2]
                else:
                    r = g = b = p
                total += 0.299 * r + 0.587 * g + 0.114 * b
                count += 1
    return total / count if count else 128.0


def draw_focus_caret_overlay(pil_image: Image.Image, focus_ix: int, focus_iy: int) -> Image.Image:
    """Draw I-beam caret at (focus_ix, focus_iy). Color adapts to background."""
    out = pil_image.copy()
    if out.mode not in ("RGB", "RGBA"):
        out = out.convert("RGB")
    if out.mode == "RGBA":
        out_rgb = out.convert("RGB")
    else:
        out_rgb = out
    draw = ImageDraw.Draw(out_rgb)
    w_caret = 3
    h_caret = 18
    x0 = focus_ix - w_caret // 2
    y0 = focus_iy - h_caret
    x1 = focus_ix + w_caret - w_caret // 2
    y1 = focus_iy
    lum = _sample_luminance(out_rgb, focus_ix, focus_iy)
    if lum > 140:
        caret_color = (0, 0, 0)
        outline_color = (255, 255, 255)
    else:
        caret_color = (255, 255, 255)
        outline_color = (0, 0, 0)
    for dx, dy in [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]:
        draw.rectangle(
            [x0 + dx, y0 + dy, x1 + dx, y1 + dy],
            outline=outline_color,
            fill=outline_color,
            width=1,
        )
    draw.rectangle([x0, y0, x1, y1], outline=caret_color, fill=caret_color, width=1)
    if out.mode == "RGBA":
        out = out_rgb.convert("RGBA")
    else:
        out = out_rgb
    return out


def apply_mouse_and_focus_overlays(
    pil_image: Image.Image,
    mon_left: int,
    mon_top: int,
) -> Image.Image:
    """Draw mouse cursor and focus caret on image. coords: (mon_left, mon_top) is monitor origin in screen coords."""
    w, h = pil_image.size
    out = pil_image
    try:
        import pyautogui  # noqa: E402
        mx, my = pyautogui.position()
        mouse_ix = mx - mon_left
        mouse_iy = my - mon_top
        if 0 <= mouse_ix < w and 0 <= mouse_iy < h:
            out = draw_cursor_pointer_overlay(out, mouse_ix, mouse_iy)
    except Exception:
        pass
    try:
        import focus_position  # noqa: E402
        fp = focus_position.get_focus_position()
        if fp is not None:
            focus_ix = fp[0] - mon_left
            focus_iy = fp[1] - mon_top
            if 0 <= focus_ix < w and 0 <= focus_iy < h:
                out = draw_focus_caret_overlay(out, focus_ix, focus_iy)
    except Exception:
        pass
    return out

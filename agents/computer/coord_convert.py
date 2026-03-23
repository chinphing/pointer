"""
Pluggable coordinate conversion: map model-normalized coordinates to screenshot pixels,
then add monitor offset for absolute screen coordinates.

Model families use different normalizations, e.g.:
- Qwen: ~1000×1000, i.e. (x, y) roughly in [0, 1000]
- Kimi: 0–1 × 0–1

Callers pass the coordinate system name, screenshot size, and monitor top-left offset.
"""
from __future__ import annotations

from typing import Callable, Dict, Tuple

# (norm_x, norm_y, image_width, image_height) -> (pixel_x, pixel_y) relative to screenshot
_Converter = Callable[[float, float, int, int], Tuple[float, float]]

_REGISTRY: Dict[str, _Converter] = {}


def register(name: str) -> Callable[[_Converter], _Converter]:
    """Register a coordinate-system conversion function."""

    def decorator(fn: _Converter) -> _Converter:
        _REGISTRY[name] = fn
        return fn

    return decorator


@register("qwen")
def _qwen(norm_x: float, norm_y: float, width: int, height: int) -> Tuple[float, float]:
    """Qwen-style normalization to 1000×1000."""
    return (norm_x / 1000.0 * width, norm_y / 1000.0 * height)


@register("kimi")
def _kimi(norm_x: float, norm_y: float, width: int, height: int) -> Tuple[float, float]:
    """Kimi-style normalization to 0–1 × 0–1."""
    return (norm_x * width, norm_y * height)


@register("pixel")
def _pixel(norm_x: float, norm_y: float, width: int, height: int) -> Tuple[float, float]:
    """Values are already screenshot pixels; only clamping applies downstream."""
    return (norm_x, norm_y)


def normalized_to_screen(
    norm_x: float,
    norm_y: float,
    system: str,
    image_width: int,
    image_height: int,
    mon_left: int,
    mon_top: int,
) -> Tuple[int, int]:
    """
    Convert model-normalized coordinates to screen pixel coordinates.

    norm_x, norm_y: model output (meaning depends on `system`)
    system: registry name, e.g. "qwen", "kimi", "pixel"
    image_width, image_height: current screenshot size
    mon_left, mon_top: monitor origin in global screen space

    Returns: (screen_x, screen_y) as integers
    """
    if system not in _REGISTRY:
        raise ValueError(
            f"Unknown coordinate system: {system}. Known: {list(_REGISTRY.keys())}."
        )
    px, py = _REGISTRY[system](norm_x, norm_y, image_width, image_height)
    # Clamp to screenshot, then add monitor offset
    px = max(0, min(image_width - 1, px))
    py = max(0, min(image_height - 1, py))
    return (int(round(mon_left + px)), int(round(mon_top + py)))


def list_systems() -> Tuple[str, ...]:
    """Return registered coordinate system names."""
    return tuple(_REGISTRY.keys())


def pixel_to_normalized(
    px: float,
    py: float,
    system: str,
    image_width: int,
    image_height: int,
) -> Tuple[float, float]:
    """
    Convert screenshot pixels to model-normalized coordinates (for prompts, matching model output).
    system: e.g. "qwen" (0–1000), "kimi" (0–1), "pixel" returns as-is.
    """
    if image_width <= 0 or image_height <= 0:
        raise ValueError("image_width and image_height must be positive.")
    if system == "qwen":
        return (px / image_width * 1000.0, py / image_height * 1000.0)
    if system == "kimi":
        return (px / image_width, py / image_height)
    if system == "pixel":
        return (px, py)
    raise ValueError(f"Unknown coordinate system: {system}. Known: {list(_REGISTRY.keys())}.")

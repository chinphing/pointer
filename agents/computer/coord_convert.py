"""
可扩展的坐标还原：将模型输出的归一化坐标转换为截图上的像素坐标，再叠加显示器偏移得到屏幕坐标。

不同模型输出坐标系不同，例如：
- Qwen：归一化到 1000×1000，即 (x, y) 范围约为 [0, 1000]
- Kimi：归一化到 1×1，即 (x, y) 范围约为 [0, 1]

调用方传入坐标系名称、截图宽高、显示器左上角偏移，得到屏幕像素坐标。
"""
from __future__ import annotations

from typing import Callable, Dict, Tuple

# 类型： (norm_x, norm_y, image_width, image_height) -> (pixel_x, pixel_y) 相对于截图
_Converter = Callable[[float, float, int, int], Tuple[float, float]]

_REGISTRY: Dict[str, _Converter] = {}


def register(name: str) -> Callable[[_Converter], _Converter]:
    """注册一个坐标系转换函数。"""

    def decorator(fn: _Converter) -> _Converter:
        _REGISTRY[name] = fn
        return fn

    return decorator


@register("qwen")
def _qwen(norm_x: float, norm_y: float, width: int, height: int) -> Tuple[float, float]:
    """Qwen：坐标归一化到 1000×1000。"""
    return (norm_x / 1000.0 * width, norm_y / 1000.0 * height)


@register("kimi")
def _kimi(norm_x: float, norm_y: float, width: int, height: int) -> Tuple[float, float]:
    """Kimi：坐标归一化到 1×1（0～1）。"""
    return (norm_x * width, norm_y * height)


@register("pixel")
def _pixel(norm_x: float, norm_y: float, width: int, height: int) -> Tuple[float, float]:
    """已是截图像素坐标，仅做边界裁剪（不改变含义）。"""
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
    将模型给出的归一化坐标转换为屏幕像素坐标。

    norm_x, norm_y: 模型输出的坐标（含义由 system 决定）
    system: 坐标系名称，如 "qwen", "kimi", "pixel"
    image_width, image_height: 当前截图的宽高
    mon_left, mon_top: 当前显示器在系统屏幕中的左上角偏移

    返回: (screen_x, screen_y) 整型屏幕坐标
    """
    if system not in _REGISTRY:
        raise ValueError(
            f"Unknown coordinate system: {system}. Known: {list(_REGISTRY.keys())}."
        )
    px, py = _REGISTRY[system](norm_x, norm_y, image_width, image_height)
    # 裁剪到截图范围内再叠加偏移
    px = max(0, min(image_width - 1, px))
    py = max(0, min(image_height - 1, py))
    return (int(round(mon_left + px)), int(round(mon_top + py)))


def list_systems() -> Tuple[str, ...]:
    """返回已注册的坐标系名称。"""
    return tuple(_REGISTRY.keys())


def pixel_to_normalized(
    px: float,
    py: float,
    system: str,
    image_width: int,
    image_height: int,
) -> Tuple[float, float]:
    """
    将截图像素坐标转换为模型归一化坐标（用于在提示词中展示，与模型输出一致）。
    system: 如 "qwen" (0–1000), "kimi" (0–1), "pixel" 则返回原样。
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

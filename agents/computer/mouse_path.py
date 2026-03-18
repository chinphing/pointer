"""
鼠标轨迹：用 numpy 实现三次贝塞尔曲线，支持两点间一段轨迹与多点串联成完整轨迹。
"""
from __future__ import annotations

from typing import List, Tuple

import numpy as np


def _bezier_segment(
    p0: Tuple[float, float],
    p1: Tuple[float, float],
    p2: Tuple[float, float],
    p3: Tuple[float, float],
    num_points: int = 10,
) -> List[Tuple[float, float]]:
    """
    三次贝塞尔曲线 B(t) = (1-t)^3 P0 + 3(1-t)^2 t P1 + 3(1-t) t^2 P2 + t^3 P3。
    p0..p3 为 (x,y)，返回 num_points 个插值点（不含起点，含终点，避免重复拼接时重复）。
    """
    if num_points < 1:
        num_points = 1
    t = np.linspace(0, 1, num_points + 1)[1:]  # 不含 t=0，含 t=1
    one_t = 1 - t
    x = (
        one_t ** 3 * p0[0]
        + 3 * one_t ** 2 * t * p1[0]
        + 3 * one_t * t ** 2 * p2[0]
        + t ** 3 * p3[0]
    )
    y = (
        one_t ** 3 * p0[1]
        + 3 * one_t ** 2 * t * p1[1]
        + 3 * one_t * t ** 2 * p2[1]
        + t ** 3 * p3[1]
    )
    return list(zip(x.tolist(), y.tolist()))


def mouse_path(
    point_from: List[float],
    point_to: List[float],
    num_points: int = 10,
) -> List[Tuple[float, float]]:
    """
    从 point_from 到 point_to 的三次贝塞尔轨迹。
    控制点与参考实现类似：from + diff/3, to - diff/3。
    返回 [(x,y), ...] 不含起点、含终点，共 num_points 个点。
    """
    x0, y0 = float(point_from[0]), float(point_from[1])
    x1, y1 = float(point_to[0]), float(point_to[1])
    diff_x = x1 - x0
    diff_y = y1 - y0
    p0 = (x0, y0)
    p1 = (x0 + diff_x / 3, y0 + diff_y / 3)
    p2 = (x1 - diff_x / 3, y1 - diff_y / 3)
    p3 = (x1, y1)
    return _bezier_segment(p0, p1, p2, p3, num_points)


def mouse_path_through_points(
    points: List[List[float]],
    num_points_per_segment: int = 10,
) -> List[Tuple[float, float]]:
    """
    多点串联成一条完整轨迹：相邻两点之间用三次贝塞尔连接。
    points: [[x0,y0], [x1,y1], ...]，至少 2 个点。
    返回整条路径的点列，顺序为：起点 -> 各段插值 -> 终点（中间点不重复）。
    """
    if not points or len(points) < 2:
        return []
    out: List[Tuple[float, float]] = []
    n = len(points)
    for i in range(n - 1):
        seg = mouse_path(
            points[i],
            points[i + 1],
            num_points=num_points_per_segment,
        )
        if i == 0:
            out.append((float(points[0][0]), float(points[0][1])))
        # seg 含终点不含起点；最后一段的终点保留，否则去掉避免与下一段起点重复
        out.extend(seg[:-1] if i < n - 2 else seg)
    return out

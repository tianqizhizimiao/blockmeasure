"""几何基础：平面拟合、连通域聚类、凸包。

这些实现全部从 1.0 逐句移植，**数值行为完全一致**（黄金回归逐值比对的依据）。
设计上刻意不依赖 Open3D/PCL/scipy——只用 numpy，所以核心依赖才能压到只有 numpy。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

from .config import DEFAULT_CONFIG, Config

__all__ = [
    "PlaneFit",
    "ransac_plane",
    "fit_plane_svd",
    "orient_toward_camera",
    "grid_labels_2d",
    "convex_hull_2d",
    "points_in_hull",
]


@dataclass
class PlaneFit:
    """平面 ``n·p + d = 0`` 及本次拟合的内点掩码。"""

    normal: np.ndarray
    """单位法向量，形状 ``(3,)``。"""
    offset: float
    """偏移 ``d``。"""
    inliers: np.ndarray
    """内点布尔掩码，形状 ``(N,)``。"""

    @property
    def count(self) -> int:
        return int(self.inliers.sum())


def ransac_plane(
    points: np.ndarray,
    rng: np.random.Generator,
    cfg: Config = DEFAULT_CONFIG,
    thresh: Optional[float] = None,
    min_inliers: Optional[int] = None,
) -> Optional[PlaneFit]:
    """RANSAC 拟合平面，返回内点最多的那个；点太少或找不到合格平面时返回 ``None``。

    Args:
        points: ``(N,3)`` 点集（米）。
        rng: 随机数发生器。**调用方必须传入并复用同一个 rng**，
            因为 1.0 的黄金结果依赖固定的抽样顺序。
        cfg: 参数；``thresh`` / ``min_inliers`` 可单独覆盖。
    """
    thresh = cfg.plane_thresh_m if thresh is None else thresh
    min_in = cfg.plane_min_inliers if min_inliers is None else min_inliers
    pts = np.asarray(points, dtype=np.float64)
    n = len(pts)
    if n < 3:
        return None

    best: Optional[PlaneFit] = None
    best_count = -1
    for _ in range(cfg.ransac_iters):
        p0, p1, p2 = pts[rng.choice(n, 3, replace=False)]
        nv = np.cross(p1 - p0, p2 - p0)
        length = np.linalg.norm(nv)
        if length < 1e-9:
            continue
        nv = nv / length
        d = -nv @ p0
        inliers = np.abs(pts @ nv + d) < thresh
        count = int(inliers.sum())
        if count >= min_in and count > best_count:
            best_count = count
            best = PlaneFit(normal=nv, offset=float(d), inliers=inliers)
    return best


def fit_plane_svd(points: np.ndarray) -> tuple:
    """最小二乘（SVD）精修平面。

    Returns:
        ``(normal, centroid)``——单位法向与点集质心。平面过质心，法向为最小奇异向量。
        与 1.0 的 ``refine_plane`` 等价。
    """
    pts = np.asarray(points, dtype=np.float64)
    centroid = pts.mean(axis=0)
    _, _, vt = np.linalg.svd(pts - centroid)
    return vt[2], centroid


def orient_toward_camera(normal: np.ndarray, centroid: np.ndarray) -> np.ndarray:
    """把法向统一为**指向相机**（即坐标原点）。

    这条规则与数据来源无关：无论 ``.ply``（RealSense Viewer 导出，Z 为负）还是
    ``.raw``（标准约定，Z 为正），相机都在原点，因此只要求 ``n·centroid < 0``。
    1.0 用这条统一规则抹平了两种相反的坐标系约定，避免写分支。已分别验证成立。
    """
    n = np.asarray(normal, dtype=np.float64)
    return -n if n @ np.asarray(centroid, dtype=np.float64) > 0 else n


def grid_labels_2d(u: np.ndarray, v: np.ndarray, cell: float) -> np.ndarray:
    """在 ``(u, v)`` 平面上按 ``cell`` 边长做 8 邻域连通域聚类。

    Returns:
        标签数组 ``(N,)``，``-1`` 表示该点未落入任何网格（正常不会发生）。
    """
    u = np.asarray(u, dtype=np.float64)
    v = np.asarray(v, dtype=np.float64)
    gi = np.floor(u / cell).astype(np.int64)
    gj = np.floor(v / cell).astype(np.int64)

    buckets: dict = {}
    for k in range(len(gi)):
        buckets.setdefault((gi[k], gj[k]), []).append(k)

    labels = np.full(len(gi), -1, dtype=np.int64)
    current = 0
    for seed in list(buckets):
        if labels[buckets[seed][0]] != -1:
            continue
        stack = [seed]
        labels[buckets[seed]] = current
        while stack:
            ci, cj = stack.pop()
            for di in (-1, 0, 1):
                for dj in (-1, 0, 1):
                    nb = (ci + di, cj + dj)
                    if nb in buckets and labels[buckets[nb][0]] == -1:
                        labels[buckets[nb]] = current
                        stack.append(nb)
        current += 1
    return labels


def convex_hull_2d(points: np.ndarray) -> np.ndarray:
    """Andrew monotone chain 凸包，返回逆时针顶点序列 ``(M,2)``。"""
    p = np.asarray(points, dtype=np.float64)
    p = p[np.lexsort((p[:, 1], p[:, 0]))]

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    def half(seq):
        h = []
        for q in seq:
            while len(h) >= 2 and cross(h[-2], h[-1], q) <= 0:
                h.pop()
            h.append(q)
        return h

    return np.array(half(p)[:-1] + half(p[::-1])[:-1])


def points_in_hull(queries: np.ndarray, hull: np.ndarray) -> np.ndarray:
    """判断二维点是否在逆时针凸包内（含边界），返回布尔掩码 ``(N,)``。"""
    q = np.asarray(queries, dtype=np.float64)
    result = np.ones(len(q), dtype=bool)
    for i in range(len(hull)):
        a, b = hull[i], hull[(i + 1) % len(hull)]
        result &= (
            (b[0] - a[0]) * (q[:, 1] - a[1]) - (b[1] - a[1]) * (q[:, 0] - a[0])
        ) >= -1e-9
    return result

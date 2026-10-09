"""预处理：无效值剔除、统计降噪、体素下采样。

从 1.0 逐句移植，数值行为一致。

.. note::
   :func:`radius_outlier_removal` 是整条管线的性能热点——它是
   Python 层按网格桶循环，对 13.6 万点的 ``sc03`` 尤其明显（全量 6 组约 18 秒，
   其中大部分在这里）。1.0 实测可接受，故此处保持原样以确保结果一致；
   若日后需要提速，方向是整体向量化，但要重新校验黄金回归。
"""

from __future__ import annotations

from collections import defaultdict

import numpy as np

from .config import DEFAULT_CONFIG, Config

__all__ = ["remove_invalid", "radius_outlier_removal", "voxel_downsample"]


def remove_invalid(points: np.ndarray, cfg: Config = DEFAULT_CONFIG) -> np.ndarray:
    """剔除无效数据：深度为 0、超范围、含 NaN/Inf 的点。

    Returns:
        保留掩码 ``(N,)`` bool。
    """
    pts = np.asarray(points, dtype=np.float64)
    z = pts[:, 2]
    return (
        np.isfinite(pts).all(1)
        & (np.abs(z) > cfg.invalid_min_m)
        & (np.abs(z) < cfg.invalid_max_m)
    )


def radius_outlier_removal(
    points: np.ndarray, cfg: Config = DEFAULT_CONFIG
) -> np.ndarray:
    """统计降噪：半径 ``r`` 邻域内邻居数不足的点判为离群点（稀疏噪点/飞点）。

    Returns:
        保留掩码 ``(N,)`` bool。
    """
    pts = np.asarray(points, dtype=np.float64)
    r = cfg.denoise_radius_m
    k = cfg.denoise_min_neighbors
    if r <= 0 or len(pts) == 0:
        return np.ones(len(pts), dtype=bool)

    keys = np.floor(pts / r).astype(np.int64)
    buckets: dict = defaultdict(list)
    for i in range(len(pts)):
        buckets[(keys[i, 0], keys[i, 1], keys[i, 2])].append(i)

    offsets = [
        (a, b, c) for a in (-1, 0, 1) for b in (-1, 0, 1) for c in (-1, 0, 1)
    ]
    keep = np.zeros(len(pts), dtype=bool)
    r2 = r * r
    for (a, b, c), idxs in buckets.items():
        neighbours: list = []
        for o in offsets:
            neighbours.extend(buckets.get((a + o[0], b + o[1], c + o[2]), ()))
        if not neighbours:
            continue
        nb = np.asarray(neighbours)
        sub = pts[np.asarray(idxs)]
        d2 = ((sub[:, None, :] - pts[nb][None, :, :]) ** 2).sum(-1)
        keep[np.asarray(idxs)] = (d2 < r2).sum(1) >= k
    return keep


def voxel_downsample(
    points: np.ndarray,
    colors: np.ndarray | None = None,
    cfg: Config = DEFAULT_CONFIG,
) -> tuple:
    """体素下采样（可选）：每格取质心，用于控制点数与均匀化密度。

    Returns:
        ``(points, colors)``；``colors`` 为 ``None`` 时原样返回 ``None``。
    """
    v = cfg.voxel_m
    pts = np.asarray(points, dtype=np.float64)
    if v <= 0:
        return pts, colors

    keys = np.floor(pts / v).astype(np.int64)
    order = np.lexsort((keys[:, 2], keys[:, 1], keys[:, 0]))
    ks = keys[order]
    new_group = np.any(np.diff(ks, axis=0) != 0, axis=1)
    start = np.concatenate([[True], new_group])
    gid = np.cumsum(start) - 1
    n = gid[-1] + 1
    count = np.bincount(gid, minlength=n)[:, None]

    out_pts = np.zeros((n, 3))
    np.add.at(out_pts, gid, pts[order])
    out_pts /= count

    out_cols = None
    if colors is not None:
        cols = np.asarray(colors)
        out_cols = np.zeros((n, 3))
        np.add.at(out_cols, gid, cols[order].astype(float))
        out_cols /= count
        out_cols = out_cols.astype(int)
    return out_pts, out_cols

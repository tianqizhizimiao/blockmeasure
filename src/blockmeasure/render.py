"""核对渲染：高度图 + 分割图。

从 1.0 ``pipeline.py`` 的 ``_render`` / ``height_color`` 逐句移植。需要可选依赖
``[render]``（pillow）；核心测量不依赖它——只在 ``outdir`` 被给出时惰性加载。
"""

from __future__ import annotations

import os
from typing import List, Sequence

import numpy as np

from .results import Block

__all__ = ["render_scene", "height_color"]

_CMAP = [(0.00, (0, 0, 255)), (0.25, (0, 255, 255)), (0.50, (0, 255, 0)),
          (0.75, (255, 255, 0)), (1.00, (255, 0, 0))]


def height_color(h, vmax: float = 0.07) -> np.ndarray:
    """高度 -> 彩色图（5 段渐变，与 1.0 一致）。

    Args:
        h: 高度数组（米）。
        vmax: 颜色条上界（米）。

    Returns:
        ``(N, 3)`` uint8。
    """
    t = np.clip(np.asarray(h, dtype=np.float64) / vmax, 0, 1)
    out = np.zeros((len(t), 3))
    for i in range(len(_CMAP) - 1):
        t0, c0 = _CMAP[i]
        t1, c1 = _CMAP[i + 1]
        m = (t >= t0) & (t <= t1)
        if m.any():
            f = ((t[m] - t0) / (t1 - t0))[:, None]
            out[m] = np.array(c0, dtype=np.float64) * (1 - f) + np.array(c1, dtype=np.float64) * f
    return out.clip(0, 255).astype(np.uint8)


def render_scene(
    points: np.ndarray,
    u: np.ndarray,
    v: np.ndarray,
    h: np.ndarray,
    foot: np.ndarray,
    obj: np.ndarray,
    obj_label: np.ndarray,
    blocks: Sequence[Block],
    hull: np.ndarray,
    outdir: str,
    name: str,
) -> List[str]:
    """在 ``outdir`` 输出 ``<name>_height.png`` / ``<name>_seg.png``。

    与 1.0 ``_render`` 完全一致：像素分辨率 1 mm，高度图用 ``height_color`` 色条，
    分割图每块一色。

    Returns:
        写出的文件路径列表。
    """
    from PIL import Image

    os.makedirs(outdir, exist_ok=True)
    sc = 0.001
    u0, u1 = float(hull[:, 0].min()) - 0.01, float(hull[:, 0].max()) + 0.01
    v0, v1 = float(hull[:, 1].min()) - 0.01, float(hull[:, 1].max()) + 0.01
    W, H = int((u1 - u0) / sc) + 1, int((v1 - v0) / sc) + 1

    inb = (u > u0) & (u < u1) & (v > v0) & (v < v1)
    px = np.clip(((u - u0) / sc).astype(np.int64), 0, W - 1)
    py = np.clip(((v - v0) / sc).astype(np.int64), 0, H - 1)

    img = np.zeros((H, W, 3), np.uint8)
    f = np.where(inb & foot)[0]
    img[py[f], px[f]] = [90, 90, 90]
    o = np.where(inb & obj)[0]
    o = o[np.argsort(h[o])]
    img[py[o], px[o]] = height_color(h[o])
    Image.fromarray(img[::-1]).save(os.path.join(outdir, f"{name}_height.png"))

    seg = np.zeros((H, W, 3), np.uint8)
    seg[py[f], px[f]] = [80, 80, 80]
    cols = [(255, 70, 70), (70, 255, 70), (90, 160, 255), (255, 255, 0),
            (255, 120, 255), (0, 255, 255)]
    for ci, b in enumerate(blocks):
        ii = np.where(inb & (obj_label == b.block_id))[0]
        if len(ii):
            seg[py[ii], px[ii]] = cols[ci % len(cols)]
    Image.fromarray(seg[::-1]).save(os.path.join(outdir, f"{name}_seg.png"))

    return [
        os.path.join(outdir, f"{name}_height.png"),
        os.path.join(outdir, f"{name}_seg.png"),
    ]

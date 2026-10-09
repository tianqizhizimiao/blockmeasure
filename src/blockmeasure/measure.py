"""测量核心：从 1.0 ``process()`` 逐句移植，数值行为完全一致。

流水线：预处理 -> 两级平面拟合（台面 -> 托盘）-> 基准面识别（最大连通域 + 凸包）
-> 目标分割（高度门限 + 平面内网格连通域）-> 逐块测量（高度平台 / L x W / 姿态 /
颜色 / 位置）。

与 1.0 的区别（对外可见）：

- 返回 :class:`~blockmeasure.results.SceneResult` 而非裸 dict；
- 参数走注入的 :class:`~blockmeasure.config.Config`；
- 可传入已标定的 :class:`~blockmeasure.TrayFrame`，把块坐标表达在该固定坐标系里
  （见 README「关于托盘坐标系」）。

黄金回归的要点：RANSAC 必须用 ``np.random.default_rng(cfg.random_seed)``，
且同一 rng 依次喂两级拟合——黄金值依赖固定抽样顺序。
"""

from __future__ import annotations

from dataclasses import replace
from typing import Optional, Tuple

import numpy as np

from .config import DEFAULT_CONFIG, Config
from .exceptions import PlaneFitError
from .frame import TrayFrame
from .geometry import (
    convex_hull_2d,
    fit_plane_svd,
    grid_labels_2d,
    orient_toward_camera,
    points_in_hull,
    ransac_plane,
)
from .preprocess import (
    radius_outlier_removal,
    remove_invalid,
    voxel_downsample,
)
from .results import Block, SceneResult

__all__ = ["measure", "color_name"]


def color_name(rgb) -> str:
    """平均 RGB -> 颜色归类（与 1.0 完全一致的规则）。

    规则：

    - 无彩色数据 -> ``-``
    - 最大-最小 < 40 -> ``白/灰``
    - 蓝：``b > r + 25`` 且 ``b > g + 25``
    - 红：``r > g + 25`` 且 ``r > b + 25``
    - 绿：``g > r + 15`` 且 ``g > b + 15``
    - 其余 -> ``其他``
    """
    if rgb is None:
        return "-"
    r, g, b = rgb
    if max(rgb) - min(rgb) < 40:
        return "白/灰"
    if b > r + 25 and b > g + 25:
        return "蓝"
    if r > g + 25 and r > b + 25:
        return "红"
    if g > r + 15 and g > b + 15:
        return "绿"
    return "其他"


def measure(
    points: np.ndarray,
    colors: Optional[np.ndarray] = None,
    cfg: Config = DEFAULT_CONFIG,
    frame: Optional[TrayFrame] = None,
    name: str = "",
    source: str = "数组",
    note: str = "",
    outdir: Optional[str] = None,
) -> SceneResult:
    """测量一次场景。

    Args:
        points: ``(N, 3)`` 点云，单位米。
        colors: ``(N, 3)`` 每点 RGB，可选；``None`` 表示无彩色数据。
        cfg: 算法参数（默认与 1.0 完全一致）。
        frame: 已标定的托盘坐标系。给出时，块坐标表达在该坐标系；
            否则用本次现算的坐标系（``reference="scan"``）。
        name: 输入名（通常文件名去扩展名）。
        source: 数据来源标识（``点云`` / ``深度原帧`` / ``数组``）。
        note: 加载阶段的补充说明。
        outdir: 非 ``None`` 时输出核对渲染图（需要 pillow，``[render]`` extra）。

    Returns:
        :class:`~blockmeasure.results.SceneResult`。

    Raises:
        PlaneFitError: 台面或托盘平面拟合失败。
    """
    P = np.asarray(points, dtype=np.float64)
    if P.ndim != 2 or P.shape[1] != 3:
        raise ValueError(f"points 必须是 (N, 3)，得到形状 {P.shape}")
    C = None
    if colors is not None:
        C = np.asarray(colors)
        if C.shape != P.shape:
            raise ValueError(f"colors 必须与 points 同形状，得到 {C.shape}")

    rng = np.random.default_rng(cfg.random_seed)
    log: list = []
    n0 = len(P)

    # --- 预处理 ---
    m = remove_invalid(P, cfg)
    P = P[m]
    if C is not None:
        C = C[m]
    log.append(("剔除无效值", f"{n0} -> {len(P)} 点"))

    if cfg.denoise_radius_m > 0 and len(P):
        k = radius_outlier_removal(P, cfg)
        P = P[k]
        if C is not None:
            C = C[k]
        log.append(("统计降噪", f"-> {len(P)} 点"))

    if cfg.voxel_m > 0:
        P, C = voxel_downsample(P, C, cfg)
        log.append(("体素下采样", f"-> {len(P)} 点"))

    # --- [3] 坐标系搭建：两级平面拟合 ---
    r1 = ransac_plane(P, rng, cfg)
    if r1 is None:
        raise PlaneFitError("未能拟合出基准面（台面）")
    rest = ~r1.inliers
    r2 = ransac_plane(P[rest], rng, cfg)
    if r2 is None:
        raise PlaneFitError("未能拟合出第二基准面（托盘）")
    idx2 = np.where(rest)[0][r2.inliers]

    n_t, cen0 = fit_plane_svd(P[idx2])
    n_t = orient_toward_camera(n_t, cen0)
    d_t = -float(n_t @ cen0)

    e1 = np.cross(n_t, np.array([0.0, 0.0, 1.0]))
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(n_t, e1)

    u = (P - cen0) @ e1
    v = (P - cen0) @ e2
    h = P @ n_t + d_t

    rms = float(h[idx2].std())
    log.append(("基准面拟合", f"内点 {len(idx2)}, 残差 std {rms * 1000:.1f} mm"))

    scan_frame = TrayFrame(
        origin=tuple(float(x) for x in cen0),
        axis_u=tuple(float(x) for x in e1),
        axis_v=tuple(float(x) for x in e2),
        normal=tuple(float(x) for x in n_t),
        reference="scan",
    )

    # --- [4] 基准面识别：最大连通域 + 凸包 ---
    lab2 = grid_labels_2d(u[idx2], v[idx2], cfg.face_cell_m)
    sizes = np.bincount(lab2[lab2 >= 0])
    face = lab2 == int(np.argmax(sizes))
    hull = convex_hull_2d(np.stack([u[idx2][face], v[idx2][face]], axis=1))
    tray_w, tray_h = float(np.ptp(hull[:, 0]) * 1000), float(np.ptp(hull[:, 1]) * 1000)
    log.append(("基准面识别", f"{tray_w:.0f} x {tray_h:.0f} mm"))

    foot = points_in_hull(np.stack([u, v], axis=1), hull)

    # --- [5] 目标分割 ---
    obj = foot & (h > cfg.obj_min_h_m) & (h < cfg.obj_max_h_m)
    blocks: list = []
    obj_label = np.full(len(P), -1, dtype=np.int64)  # 供渲染使用

    if obj.sum() >= cfg.obj_min_points:
        oi = np.where(obj)[0]
        labo = grid_labels_2d(u[oi], v[oi], cfg.obj_cell_m)
        for k in range(int(labo.max()) + 1):
            sel = oi[labo == k]
            if len(sel) < cfg.obj_min_points:
                continue
            obj_label[sel] = len(blocks) + 1

            hh = h[sel]
            hist, edges = np.histogram(hh, bins=np.arange(0, 0.2, 0.002))
            peaks = [
                i
                for i in range(1, len(hist) - 1)
                if hist[i] >= cfg.plateau_min_points
                and hist[i] >= hist[i - 1]
                and hist[i] >= hist[i + 1]
            ]
            h_top = (
                float((edges[peaks[-1]] + edges[peaks[-1] + 1]) / 2)
                if peaks
                else float(np.percentile(hh, 99))
            )
            top = sel[np.abs(h[sel] - h_top) < cfg.plateau_tol_m]

            # [6] 顶面尺寸
            L = float(np.ptp(u[top]) * 1000) if len(top) else 0.0
            W = float(np.ptp(v[top]) * 1000) if len(top) else 0.0

            # [6] 空间姿态 / 顶面平整度
            tilt, flat = None, None
            if len(top) >= 30 and min(np.ptp(u[top]), np.ptp(v[top])) >= 0.015:
                n_top, c_top = fit_plane_svd(P[top])
                n_top = orient_toward_camera(n_top, c_top)
                tilt = float(
                    np.degrees(np.arccos(np.clip(abs(n_top @ n_t), 0, 1)))
                )
                flat = float(np.std((P[top] - c_top) @ n_top) * 1000)

            rgb = tuple(int(x) for x in C[sel].mean(axis=0)) if C is not None else None
            blocks.append(
                Block(
                    block_id=len(blocks) + 1,
                    color=color_name(rgb),
                    rgb=rgb,
                    height_mm=h_top * 1000,
                    height_max_mm=float(hh.max() * 1000),
                    length_mm=L,
                    width_mm=W,
                    u_mm=float(u[sel].mean() * 1000),
                    v_mm=float(v[sel].mean() * 1000),
                    tilt_deg=tilt,
                    flatness_mm=flat,
                    points=int(len(sel)),
                )
            )

    blocks.sort(key=lambda b: -b.height_mm)
    blocks = [replace(b, block_id=i) for i, b in enumerate(blocks, 1)]
    log.append(("目标分割", f"检出 {len(blocks)} 个"))

    # --- 坐标表达：可选固定参考帧 ---
    if frame is not None:
        transformed = []
        for b in blocks:
            p_cam = scan_frame.to_camera(
                (b.u_mm / 1000.0, b.v_mm / 1000.0, b.height_mm / 1000.0)
            )
            uvh = frame.from_camera(np.asarray([p_cam]))[0]
            transformed.append(
                replace(
                    b,
                    u_mm=float(uvh[0] * 1000),
                    v_mm=float(uvh[1] * 1000),
                    height_mm=float(uvh[2] * 1000),
                )
            )
        blocks = transformed

    # --- 渲染（可选，惰性加载 [render] extra）---
    if outdir is not None and blocks:
        from .render import render_scene

        render_scene(P, u, v, h, foot, obj, obj_label, blocks, hull, outdir, name)

    return SceneResult(
        blocks=tuple(blocks),
        frame=frame if frame is not None else scan_frame,
        plane_rms_mm=rms * 1000.0,
        tray_size_mm=(tray_w, tray_h),
        points=int(len(P)),
        source=source,
        name=name,
        note=note,
        log=tuple(log),
    )

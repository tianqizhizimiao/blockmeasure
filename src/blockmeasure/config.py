"""算法参数。

与 1.0 的关键区别：1.0 用的是**模块级可变 dict ``CFG``**，``main()`` 还会就地改它
（``CFG["voxel_m"] = ...``）。那对库来说是灾难——调用一次就污染全局，不可重入、
多线程下互相干扰。这里改成**冻结 dataclass**，按调用注入。
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["Config", "DEFAULT_CONFIG"]


@dataclass(frozen=True)
class Config:
    """测量管线全部可调参数（相机相关参数见 :class:`~blockmeasure.camera.CameraProfile`）。

    单位一律为**米**。默认值与 1.0 完全一致，以保证黄金回归能逐值对上。
    """

    # --- 预处理 ---
    invalid_min_m: float = 0.05
    """有效深度下限。"""
    invalid_max_m: float = 5.00
    """有效深度上限。"""
    denoise_radius_m: float = 0.006
    """统计降噪邻域半径；``<= 0`` 表示跳过降噪。"""
    denoise_min_neighbors: int = 8
    """邻域内少于此数判为离群点。"""
    voxel_m: float = 0.0
    """体素下采样边长；``0`` 表示不下采样。"""

    # --- 平面拟合 ---
    plane_thresh_m: float = 0.006
    """RANSAC 内点距离门限。"""
    plane_min_inliers: int = 3000
    """平面最少内点数。"""
    ransac_iters: int = 800
    """RANSAC 迭代次数。"""

    # --- 基准面 ---
    face_cell_m: float = 0.004
    """基准面连通域网格边长。"""

    # --- 目标分割 ---
    obj_min_h_m: float = 0.008
    """高出基准面多少算目标。"""
    obj_max_h_m: float = 0.30
    """超过此高度视为干扰（机械臂等）。"""
    obj_cell_m: float = 0.004
    """物块聚类网格边长。"""
    obj_min_points: int = 80
    """少于这么多点的聚类丢弃。"""

    # --- 测量 ---
    plateau_tol_m: float = 0.006
    """顶面平台厚度。"""
    plateau_min_points: int = 30
    """顶面平台最少点数。"""

    # --- 可复现性 ---
    random_seed: int = 0
    """RANSAC 随机种子。1.0 硬编码为 0；暴露出来便于调用方做多种子稳定性测试。"""


DEFAULT_CONFIG = Config()
"""默认参数，等价于 1.0 的行为。"""

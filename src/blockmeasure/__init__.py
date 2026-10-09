"""blockmeasure —— 从深度相机数据测量托盘上物块的颜色、长×宽×高与托盘坐标系位置。

公开 API 都从这里导出，子模块路径不属于稳定契约。

目标用法（``measure_blocks`` 随 measure 层落地，见 README 状态说明）::

    from blockmeasure import measure_blocks, CameraProfile, Config

    scene = measure_blocks("scan.ply")
    for b in scene.blocks:
        print(b.color, b.height_mm, b.length_mm, b.width_mm, b.center_xyz_mm)

核心依赖只有 numpy；读取二进制 ``.ply`` 需要 ``trimesh``（``pip install blockmeasure[ply]``），
出图需要 ``pillow``（``[render]``）。
"""

from __future__ import annotations

from .camera import CameraProfile
from .config import DEFAULT_CONFIG, Config
from .exceptions import (
    BlockMeasureError,
    InvalidDepthError,
    NoBlocksFoundError,
    PlaneFitError,
    UnsupportedFormatError,
)
from .frame import TrayFrame
from .results import Block, SceneResult

__version__ = "2.0.0"

# 注意：measure_blocks 尚未实现（2.0 开发中，io 与 measure 层待移植）。
# 这里刻意不定义占位符——一个"存在但一调用就抛"的假函数会骗过 hasattr/工具链，
# 比干脆没有更糟。
__all__ = [
    "__version__",
    # 参数与相机
    "Config",
    "DEFAULT_CONFIG",
    "CameraProfile",
    # 结果
    "Block",
    "SceneResult",
    "TrayFrame",
    # 异常
    "BlockMeasureError",
    "UnsupportedFormatError",
    "InvalidDepthError",
    "PlaneFitError",
    "NoBlocksFoundError",
]

"""blockmeasure —— 从深度相机数据测量托盘上物块的颜色、长×宽×高与托盘坐标系位置。

公开 API 都从这里导出，子模块路径不属于稳定契约。

用法::

    from blockmeasure import measure_blocks, CameraProfile, Config

    scene = measure_blocks("scan.ply")
    for b in scene.blocks:
        print(b.color, b.height_mm, b.length_mm, b.width_mm, b.center_xyz_mm)

    # 或给 numpy 数组 + 自己的相机参数
    scene = measure_blocks(
        points_xyz,                       # (N, 3) float，单位米
        colors=rgb,                       # (N, 3) uint8，可选
        camera=CameraProfile(intel_d415()),
    )

核心依赖只有 numpy；读取二进制 ``.ply`` 需要 ``trimesh``（``pip install blockmeasure[ply]``），
出图需要 ``pillow``（``[render]``）。
"""

from __future__ import annotations

import os
from typing import Optional, Union

import numpy as np

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
from .io import discover_metadata, load_depth, load_ply
from .measure import measure
from .results import Block, SceneResult

__version__ = "2.0.0"

__all__ = [
    "__version__",
    # 入口
    "measure_blocks",
    # 参数与相机
    "Config",
    "DEFAULT_CONFIG",
    "CameraProfile",
    # 结果
    "Block",
    "SceneResult",
    "TrayFrame",
    # IO
    "load_ply",
    "load_depth",
    "discover_metadata",
    # 异常
    "BlockMeasureError",
    "UnsupportedFormatError",
    "InvalidDepthError",
    "PlaneFitError",
    "NoBlocksFoundError",
]


def measure_blocks(
    source: Union[str, np.ndarray],
    *,
    camera: Optional[CameraProfile] = None,
    cfg: Config = DEFAULT_CONFIG,
    frame: Optional[TrayFrame] = None,
    colors: Optional[np.ndarray] = None,
    outdir: Optional[str] = None,
) -> SceneResult:
    """包的主入口：测量一次场景，返回 :class:`~blockmeasure.results.SceneResult`。

    Args:
        source: ``.ply`` / ``.raw`` 文件路径，或 ``(N, 3)`` numpy 点云（单位米）。
        camera: 内参与深度尺度。**深度原帧必需**——未给出时自动在 ``.raw`` 旁找
            ``<name>_metadata.csv`` 并用 :meth:`CameraProfile.from_metadata_csv`
            构造（注意：元数据里不含深度尺度，此时用默认 ``0.001``）。点云不需要。
        cfg: 算法参数，默认与 1.0 完全一致。
        frame: 已标定的 :class:`~blockmeasure.TrayFrame`。给出时，块坐标表达在该
            固定坐标系（见 README「关于托盘坐标系」）。
        colors: ``source`` 为数组时的每点 RGB ``((N, 3))``。
        outdir: 非 ``None`` 时输出核对渲染图（需要 ``[render]`` extra）。

    Returns:
        :class:`~blockmeasure.results.SceneResult`。

    Raises:
        UnsupportedFormatError: 输入既不是可读点云也不是可解析的深度帧。
        InvalidDepthError: 深度帧缺少相机参数，或尺寸与分辨率不符。
        PlaneFitError: 台面或托盘平面拟合失败。
    """
    if isinstance(source, str):
        name = os.path.splitext(os.path.basename(source))[0]
        if source.endswith(".raw"):
            if camera is None:
                meta = discover_metadata(source)
                if meta is None:
                    raise InvalidDepthError(
                        f"{source}: 未提供相机参数，且旁边找不到 "
                        f"{os.path.basename(os.path.dirname(source))}/{name}_metadata.csv；"
                        "请传 camera=... 或提供内参文件"
                    )
                camera = CameraProfile.from_metadata_csv(meta)
            P, note = load_depth(source, camera)
            source_kind = "深度原帧"
            C = None
        elif source.endswith(".ply"):
            P, C, note = load_ply(source)
            source_kind = "点云"
        else:
            raise UnsupportedFormatError(
                f"无法识别的输入: {source}（支持 .ply / .raw / numpy 数组）"
            )
    elif isinstance(source, np.ndarray):
        P = np.asarray(source, dtype=np.float64)
        if P.ndim != 2 or P.shape[1] != 3:
            raise UnsupportedFormatError(
                f"点云数组必须是 (N, 3)，得到 {P.shape}"
            )
        C = None
        if colors is not None:
            C = np.asarray(colors)
            if C.shape != P.shape:
                raise UnsupportedFormatError(f"colors 必须与 points 同形状，得到 {C.shape}")
        name, note, source_kind = "array", "", "数组"
    else:
        raise UnsupportedFormatError(f"无法识别的输入类型: {type(source).__name__}")

    return measure(
        P,
        C,
        cfg=cfg,
        frame=frame,
        name=name,
        source=source_kind,
        note=note,
        outdir=outdir,
    )

"""输入/输出层：点云 ``.ply`` 与深度原帧 ``.raw``。

从 1.0 ``pipeline.py`` 逐句移植，数值行为一致；唯一区别是相机内参不再硬编码，
而是由 :class:`~blockmeasure.camera.CameraProfile` 注入。

.. note::
   二进制 ``.ply`` 走 trimesh（可选依赖 ``[ply]``）。trimesh 缺失时仍能用
   fallback 解析器读「ASCII 逐属性分行」写法（sc03 风格）的 PLY，但二进制
   PLY 没有 trimesh 就报 :class:`~blockmeasure.exceptions.UnsupportedFormatError`。
"""

from __future__ import annotations

import os
from typing import Optional, Tuple

import numpy as np

from .camera import CameraProfile
from .exceptions import InvalidDepthError, UnsupportedFormatError

__all__ = ["load_ply", "load_depth"]


def load_ply(path: str) -> Tuple[np.ndarray, Optional[np.ndarray], str]:
    """读 PLY 点云。

    Args:
        path: ``.ply`` 文件路径。

    Returns:
        ``(P, C, note)``:

        - ``P``: 点云 ``(N, 3)`` float64，单位米。
        - ``C``: 每点 RGB ``(N, 3)`` uint8；无彩色数据时 ``None``。
        - ``note``: 加载阶段的补充说明（如 ``ASCII 逐属性分行写法已适配``）。

    Raises:
        UnsupportedFormatError: 既非可读二进制 PLY，也非可自动修复的 ASCII PLY。
    """
    if not os.path.exists(path):
        raise UnsupportedFormatError(f"文件不存在: {path}")

    trimesh = None
    try:
        import trimesh
    except ImportError:
        pass
    else:
        trimesh = trimesh

    if trimesh is not None:
        try:
            m = trimesh.load(path, process=False)
            P = np.asarray(m.vertices, dtype=np.float64)
            C = None
            if hasattr(m.visual, "vertex_colors") and len(m.visual.vertex_colors):
                C = np.asarray(m.visual.vertex_colors)[:, :3].astype(int)
            if len(P) == 0:
                raise UnsupportedFormatError(f"{path}: 空点云")
            return P, C, ""
        except Exception:
            pass  # 落入 fallback 解析器

    return _load_ascii_ply(path)


def _load_ascii_ply(path: str) -> Tuple[np.ndarray, Optional[np.ndarray], str]:
    """fallback 解析器：读「ASCII 逐属性分行」写法的 PLY（1.0 ``data/sc03.ply`` 的怪癖）。

    该写法把每个顶点的 xyz / 法向 / rgb 各写一行，严格按行读会错位。这里把所有
    空白分隔的数值拉平后按 9 个属性一顶点重组，于是两种写法通用。

    独立成函数是为了能被直接测试——不依赖 trimesh 装没装、是 4.x 还是 5.x
    都走同一条路径。

    Raises:
        UnsupportedFormatError: 非 ASCII PLY、头无顶点数，或数据量与声明不符。
    """
    raw = open(path, "rb").read()
    try:
        pos = raw.index(b"end_header") + len(b"end_header")
    except ValueError:
        raise UnsupportedFormatError(f"{path}: 找不到 end_header，无法解析")
    head = raw[:pos].decode("ascii", "replace")
    if "format ascii" not in head:
        raise UnsupportedFormatError(
            f"{path}: 无法解析（既非可读二进制 PLY，也非 ASCII PLY；"
            f"二进制 PLY 需要 trimesh，装 [ply] extra）"
        )

    n_v = n_f = 0
    for line in head.splitlines():
        t = line.split()
        if len(t) >= 3 and t[0] == "element" and t[1] == "vertex":
            n_v = int(t[2])
        elif len(t) >= 3 and t[0] == "element" and t[1] == "face":
            n_f = int(t[2])
    if n_v == 0:
        raise UnsupportedFormatError(f"{path}: 头未声明顶点数")

    tok = raw[pos:].split()
    need = n_v * 9
    if len(tok) != need + n_f * 4:
        raise UnsupportedFormatError(f"{path}: 数据量不符，无法自动修复")
    arr = np.array(tok[:need], dtype=np.float64).reshape(n_v, 9)
    return (
        arr[:, 0:3],
        np.clip(arr[:, 6:9], 0, 255).astype(int),
        "ASCII 逐属性分行写法已适配",
    )


def load_depth(path_raw: str, camera: CameraProfile) -> Tuple[np.ndarray, str]:
    """读深度原帧（Z16）并反投影成三维点。

    依据 Z16 数据 + 内参反投影::

        X = (u - ppx) * Z / fx
        Y = (v - ppy) * Z / fy
        Z = depth * depth_scale_m

    输出是**标准相机坐标系**（Z 为正、朝向被摄物），与 RealSense Viewer 导出的
    ``.ply``（Z 为负）约定相反——后续由「法向量必须指向相机（坐标原点）」这条
    规则统一抹平。

    Args:
        path_raw: ``.raw`` 文件路径（uint16 小端）。
        camera: 内参与深度尺度。分辨率优先取 ``camera.width`` / ``camera.height``；
            两者缺失时按 16:9 从像素总数反推。

    Returns:
        ``(P, note)``：点云 ``(N, 3)`` 米 + 加载说明（含实际分辨率）。

    Raises:
        InvalidDepthError: 尺寸与像素数不符，或无法确定分辨率。
    """
    if not os.path.exists(path_raw):
        raise InvalidDepthError(f"深度帧文件不存在: {path_raw}")

    buf = np.fromfile(path_raw, dtype="<u2").astype(np.float64)
    if len(buf) == 0:
        raise InvalidDepthError(f"{path_raw}: 空文件")

    w, h = camera.width, camera.height
    if w is None or h is None:
        h_inferred = int(round((len(buf) * 9 / 16) ** 0.5))
        if h_inferred <= 0 or len(buf) % h_inferred != 0:
            raise InvalidDepthError(
                f"{path_raw}: 无法确定分辨率，请在 camera 里给出 width/height"
            )
        w, h = len(buf) // h_inferred, h_inferred
        note = f"分辨率按 16:9 反推为 {w}x{h}"
    else:
        note = f"分辨率 {w}x{h} 来自 camera"

    if w * h != len(buf):
        raise InvalidDepthError(
            f"{path_raw}: 尺寸 {w}x{h} 与像素数 {len(buf)} 不符"
        )

    fx, fy, ppx, ppy = camera.fx, camera.fy, camera.ppx, camera.ppy
    scale = camera.depth_scale_m
    Z = buf.reshape(h, w) * scale
    ys, xs = np.mgrid[0:h, 0:w]
    P = np.stack(
        [(xs - ppx) * Z / fx, (ys - ppy) * Z / fy, Z], axis=-1
    ).reshape(-1, 3)
    return P, note


def discover_metadata(path_raw: str) -> Optional[str]:
    """按 1.0 的约定在 ``.raw`` 旁找内参 CSV：同名 ``_metadata.csv``。

    Args:
        path_raw: ``.raw`` 文件路径。

    Returns:
        元数据 CSV 路径；不存在时 ``None``。
    """
    base = os.path.splitext(os.path.basename(path_raw))[0]
    candidate = os.path.join(os.path.dirname(path_raw), f"{base}_metadata.csv")
    return candidate if os.path.exists(candidate) else None

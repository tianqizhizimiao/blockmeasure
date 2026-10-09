"""IO 层测试：PLY 两种写法、深度帧反投影、错误路径。"""

import os
import tempfile
from pathlib import Path

import numpy as np
import pytest

from blockmeasure import (
    CameraProfile,
    InvalidDepthError,
    UnsupportedFormatError,
    discover_metadata,
    load_depth,
    load_ply,
)

HERE = Path(__file__).parent
FIXTURE_PLY = HERE / "data" / "ascii_per_attribute.ply"


def test_load_ply_ascii_per_attribute():
    """tests/data 的合成 4 顶点 PLY：锁定「逐属性分行」适配逻辑。"""
    P, C, note = load_ply(str(FIXTURE_PLY))
    assert P.shape == (4, 3)
    assert C.shape == (4, 3)
    assert C.dtype in (np.int64, np.int32)
    assert note == "ASCII 逐属性分行写法已适配"
    assert np.isfinite(P).all()
    # RGB 是 uint8 量级，clip 后不会越界
    assert C.min() >= 0 and C.max() <= 255


def test_load_ply_missing_file():
    with pytest.raises(UnsupportedFormatError, match="文件不存在"):
        load_ply("/nonexistent.ply")


def test_load_ply_unparseable():
    """既非 trimesh 可读二进制，也非合法 ASCII：必须报 UnsupportedFormatError。"""
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "bad.ply")
        with open(p, "wb") as f:
            f.write(b"ply\nformat binary 1.0\nend_header\ngarbage")
        with pytest.raises(UnsupportedFormatError):
            load_ply(p)


def _raw_path(tmp_path, name: str, buf: np.ndarray) -> str:
    """在 pytest tmp_path 里写出一个 .raw 文件并返回路径（tmp_path 自动清理）。"""
    p = os.path.join(tmp_path, name)
    with open(p, "wb") as f:
        f.write(buf.tobytes())
    return p


def test_load_depth_explicit_resolution(tmp_path):
    """camera 给 w/h 时用实际分辨率；Z = counts * scale。"""
    cam = CameraProfile(
        fx=445.578094, fy=445.578094, ppx=316.125519, ppy=172.919312,
        depth_scale_m=0.000694, width=2, height=2,
    )
    buf = np.array([1000, 1000, 1000, 1000], dtype="<u2")  # 2x2 帧
    P, note = load_depth(_raw_path(tmp_path, "x_Depth.raw", buf), cam)
    assert P.shape == (4, 3)
    assert np.allclose(P[:, 2], 0.000694 * 1000)
    assert "2x2" in note


def test_load_depth_infer_16_9(tmp_path):
    """camera 无 w/h 时按 16:9 反推分辨率。"""
    cam = CameraProfile(fx=450.0, fy=450.0, ppx=240.0, ppy=135.0)
    n = 1920 * 1080
    buf = np.zeros(n, dtype="<u2")
    P, note = load_depth(_raw_path(tmp_path, "x_Depth.raw", buf), cam)
    assert P.shape == (n, 3)
    assert "16:9" in note


def test_load_depth_size_mismatch(tmp_path):
    """声明分辨率与像素数不符必须报 InvalidDepthError。"""
    cam = CameraProfile.intel_d415()  # 640x360 = 230400 px
    buf = np.zeros(100, dtype="<u2")
    with pytest.raises(InvalidDepthError, match="尺寸.*不符"):
        load_depth(_raw_path(tmp_path, "x_Depth.raw", buf), cam)


def test_discover_metadata():
    with tempfile.TemporaryDirectory() as d:
        raw = os.path.join(d, "x_Depth.raw")
        open(raw, "w").close()
        open(os.path.join(d, "x_Depth_metadata.csv"), "w").close()
        found = discover_metadata(raw)
        assert found == os.path.join(d, "x_Depth_metadata.csv")
        assert discover_metadata(os.path.join(d, "y_Depth.raw")) is None


def test_measure_blocks_raw_requires_camera_or_meta():
    """无 camera 且旁边无元数据：必须报 InvalidDepthError。"""
    from blockmeasure import measure_blocks

    with tempfile.TemporaryDirectory() as d:
        raw = os.path.join(d, "x_Depth.raw")
        with open(raw, "wb") as f:
            f.write(np.zeros(640 * 360, dtype="<u2").tobytes())
        with pytest.raises(InvalidDepthError):
            measure_blocks(raw)

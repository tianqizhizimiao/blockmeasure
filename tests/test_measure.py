"""测量核心测试：颜色规则、合成场景、坐标契约、固定帧往返。

真实场景的逐值验证在 test_golden.py（slow，需要 ../1.0/data）。
"""

import os

import numpy as np
import pytest

from blockmeasure import (
    Config,
    PlaneFitError,
    TrayFrame,
    measure,
    measure_blocks,
)
from blockmeasure.measure import color_name

HERE = os.path.dirname(__file__)
TU1_RAW = os.path.join(HERE, "data", "tu1_Depth.raw")


# ---------------------------------------------------------------- 颜色规则
def test_color_name_rules():
    assert color_name(None) == "-"
    assert color_name((100, 100, 100)) == "白/灰"   # 色差 < 40
    assert color_name((20, 40, 200)) == "蓝"
    assert color_name((200, 30, 20)) == "红"
    assert color_name((30, 200, 40)) == "绿"
    assert color_name((200, 200, 50)) == "其他"
    assert color_name((10, 10, 250)) == "蓝"


# ---------------------------------------------------------- 合成场景
def _scene_points(seed: int = 0) -> np.ndarray:
    """合成场景，三层结构与真实数据一致（相机在上方俯视，.raw 约定）：

    - 台面（bench）：z=0.762m（离相机最远），9000 点，RANSAC 一级拟合的内点来源；
    - 托盘（tray）：z=0.750m，6000 点，二级拟合；
    - 两个物块：顶面相对托盘 20mm / 50mm（更靠近相机），各 600 点
      （底面贴托盘 + 顶面平台）。obj 门限只计高出托盘 8mm 的点，
      底面贴托盘的 300 点不计入。

    带符号高度「朝相机为正」：顶面 h = +20mm / +50mm，台面 h = -12mm。
    |z|>=0.70m 避开 remove_invalid 的 |z|<0.05m 剔除（真实台面距相机 ~0.75m）。
    """
    rng = np.random.default_rng(seed)

    bench = rng.uniform(-0.20, 0.20, size=(9000, 2))
    tray = rng.uniform(-0.125, 0.125, size=(6000, 2))

    def block(cx: float, top_z: float) -> np.ndarray:
        n = 300
        base = rng.uniform(-0.01, 0.01, size=(n, 2)) + np.array([cx, 0.05])
        base_pts = np.column_stack([base, np.full(n, 0.750)])  # 贴托盘面
        top = rng.uniform(-0.01, 0.01, size=(n, 2)) + np.array([cx, 0.05])
        top_pts = np.column_stack([top, np.full(n, top_z)])
        return np.vstack([base_pts, top_pts])

    A = block(0.03, 0.730)   # 顶面 h = +20mm
    B = block(0.08, 0.700)   # 顶面 h = +50mm

    P = np.vstack([
        np.column_stack([bench, np.full(9000, 0.762)]),
        np.column_stack([tray, np.full(6000, 0.750)]),
        A,
        B,
    ])

    # 绕 x 轴倾 3°：避免托盘面恰好水平导致 e1 = cross(n_t, z) = 0 的退化
    # （真实场景托盘对光轴倾斜 ~27°）。带符号高度对旋转不变。
    theta = np.radians(3.0)
    c, s = np.cos(theta), np.sin(theta)
    rot = np.array([[1.0, 0.0, 0.0], [0.0, c, -s], [0.0, s, c]])
    return P @ rot.T


def test_synthetic_two_blocks_order_and_heights():
    P = _scene_points()
    r = measure(P, cfg=Config(denoise_radius_m=0.0))
    assert len(r.blocks) == 2
    # 按高度降序，id 从 1 开始
    assert r.blocks[0].block_id == 1 and r.blocks[1].block_id == 2
    assert r.blocks[0].height_mm > r.blocks[1].height_mm
    # 高度 = 顶面平台中心（50mm 块 -> 50.0mm，误差 < 平台门限）
    assert abs(r.blocks[0].height_mm - 50.0) < 10
    assert abs(r.blocks[1].height_mm - 20.0) < 10
    # 顶面水平 -> 倾斜 0，平整度 ~0
    assert r.blocks[0].tilt_deg is not None and abs(r.blocks[0].tilt_deg) < 0.01
    assert r.blocks[1].flatness_mm is not None and r.blocks[1].flatness_mm < 1.0
    # obj 门限只计高出托盘 8mm 的点：底面贴托盘的 300 点不计入
    assert r.blocks[0].points == 300 and r.blocks[1].points == 300


def test_synthetic_scene_no_color():
    P = _scene_points()
    r = measure(P, cfg=Config(denoise_radius_m=0.0))
    assert all(b.color == "-" for b in r.blocks)
    assert all(b.rgb is None for b in r.blocks)


def test_small_scene_plane_fit_failure():
    """点太少拟合不出台面 -> PlaneFitError（不是裸 RuntimeError）。"""
    P = np.zeros((5, 3))
    with pytest.raises(PlaneFitError):
        measure(P)


def test_fixed_frame_roundtrip():
    """同一扫描的帧作为参考帧复用：块坐标不变。"""
    P = _scene_points()
    r1 = measure(P, cfg=Config(denoise_radius_m=0.0))
    r2 = measure(P, cfg=Config(denoise_radius_m=0.0), frame=r1.frame)
    assert r2.frame.reference == "scan"
    for b1, b2 in zip(r1.blocks, r2.blocks):
        assert pytest.approx(b1.u_mm, abs=1e-6) == b2.u_mm
        assert pytest.approx(b1.v_mm, abs=1e-6) == b2.v_mm
        assert pytest.approx(b1.height_mm, abs=1e-6) == b2.height_mm


def test_tray_frame_save_creates_parent_dir(tmp_path):
    """save() 自动创建父目录——标定产物常写到 calib/ 这类还不存在的目录。"""
    r = measure(_scene_points(), cfg=Config(denoise_radius_m=0.0))
    p = tmp_path / "calib" / "tray.json"
    TrayFrame.from_reference(r).save(str(p))
    assert p.exists()
    loaded = TrayFrame.load(str(p))
    assert loaded.reference == "reference"
    assert loaded.origin == pytest.approx(r.frame.origin)


def test_fixed_frame_from_real_scan():
    """tests/data 的真实 tu1 帧：用自身现算帧复用，坐标不变。"""
    from blockmeasure import CameraProfile

    cam = CameraProfile.intel_d415()
    r1 = measure_blocks(TU1_RAW, camera=cam)
    r2 = measure_blocks(TU1_RAW, camera=cam, frame=r1.frame)
    for b1, b2 in zip(r1.blocks, r2.blocks):
        assert pytest.approx(b1.u_mm, abs=1e-6) == b2.u_mm
        assert pytest.approx(b1.v_mm, abs=1e-6) == b2.v_mm
        assert pytest.approx(b1.height_mm, abs=1e-6) == b2.height_mm


# ---------------------------------------------------------- 结果契约
def test_block_center_xyz_contract():
    P = _scene_points()
    r = measure(P, cfg=Config(denoise_radius_m=0.0))
    for b in r.blocks:
        assert b.center_xyz_mm == (b.u_mm, b.v_mm, b.height_mm)


def test_scene_result_contract():
    P = _scene_points()
    r = measure(P, cfg=Config(denoise_radius_m=0.0))
    assert len(r) == len(r.blocks)
    assert list(iter(r)) == list(r.blocks)
    assert isinstance(r.log, tuple)
    assert all(isinstance(e, tuple) and len(e) == 2 for e in r.log)
    assert r.plane_rms_mm >= 0  # 合成平面完美平整，rms 可恰为 0
    assert r.points > 0


def test_empty_scene_is_not_error():
    """台面 + 托盘、没有物块：合法，空 SceneResult（README 契约）。"""
    rng = np.random.default_rng(1)
    bench = rng.uniform(-0.20, 0.20, size=(9000, 2))
    tray = rng.uniform(-0.125, 0.125, size=(6000, 2))
    P = np.vstack([
        np.column_stack([bench, np.full(9000, 0.762)]),
        np.column_stack([tray, np.full(6000, 0.750)]),
    ])
    # 同 _scene_points：避免完全水平面的 e1 退化
    theta = np.radians(3.0)
    c, s = np.cos(theta), np.sin(theta)
    rot = np.array([[1.0, 0.0, 0.0], [0.0, c, -s], [0.0, s, c]])
    P = P @ rot.T
    r = measure(P, cfg=Config(denoise_radius_m=0.0))
    assert len(r.blocks) == 0


def test_measure_blocks_array_input():
    P = _scene_points()
    r = measure_blocks(P, cfg=Config(denoise_radius_m=0.0))
    assert r.name == "array"
    assert r.source == "数组"

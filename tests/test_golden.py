"""黄金回归：2.0 必须逐值复现 1.0 已实测验证的 19 条结果。

- ``pytest -m slow``：本机有 ``../1.0/data/`` 时跑全量 6 组；
- CI：没有该目录，自动 skip（CI 用 tests/data 的小夹具做冒烟）。
- 判定容差按 CSV 的舍入位：2 位 -> 0.005，1 位 -> 0.05，3 位 -> 0.0005。
"""

import csv
import os

import numpy as np
import pytest

from blockmeasure import CameraProfile, measure_blocks
from conftest import DATA1, data1

# tu1/tu4 的黄金值依赖 D415 专属深度尺度 0.000694，
# 必须显式使用 intel_d415()（默认 0.001 会让高度差 ~1.44 倍）。
D415 = CameraProfile.intel_d415()

JOBS = [
    (data1("cs04.ply"), {}),
    (data1("cs05.ply"), {}),
    (data1("cs06.ply"), {}),
    (data1("sc03.ply"), {}),
    (data1("tu1_Depth.raw"), dict(camera=D415)),
    (data1("tu4_Depth.raw"), dict(camera=D415)),
]

TOL = {
    "height_mm": 0.005,
    "height_max_mm": 0.005,
    "length_mm": 0.05,
    "width_mm": 0.05,
    "tilt_deg": 0.005,
    "flatness_mm": 0.0005,
    "u_mm": 0.05,
    "v_mm": 0.05,
    "tray_w_mm": 0.05,
    "tray_h_mm": 0.05,
    "plane_rms_mm": 0.005,
}


def _load_golden() -> dict:
    path = os.path.join(os.path.dirname(__file__), "data", "golden_1.0_measurements.csv")
    with open(path, encoding="utf-8-sig") as f:
        return {(r["file"], r["block_id"]): r for r in csv.DictReader(f)}


def _block_fields(b, scene) -> dict:
    return {
        "color": b.color,
        "height_mm": b.height_mm,
        "height_max_mm": b.height_max_mm,
        "length_mm": b.length_mm,
        "width_mm": b.width_mm,
        "tilt_deg": b.tilt_deg,
        "flatness_mm": b.flatness_mm,
        "u_mm": b.u_mm,
        "v_mm": b.v_mm,
        "points": b.points,
        "tray_w_mm": scene.tray_size_mm[0],
        "tray_h_mm": scene.tray_size_mm[1],
        "plane_rms_mm": scene.plane_rms_mm,
        "rgb": b.rgb,
    }


def _compare_row(fields: dict, row: dict) -> list:
    """返回不符的 [(col, got, expected), ...]。"""
    bad = []
    for col in ["color", "height_mm", "height_max_mm", "length_mm",
                "width_mm", "tilt_deg", "flatness_mm", "u_mm", "v_mm",
                "points", "tray_w_mm", "tray_h_mm", "plane_rms_mm", "rgb"]:
        got = fields[col]
        cell = row[col]
        if col == "rgb":
            exp = None if not cell or cell == "None" else \
                tuple(int(x) for x in cell.strip("()").split(", "))
            if got != exp:
                bad.append((col, got, exp))
        elif col in ("color", "points"):
            exp = int(cell) if col == "points" else cell
            if got != exp:
                bad.append((col, got, cell))
        elif cell == "NA":
            if got is not None:
                bad.append((col, got, None))
        elif abs(got - float(cell)) > TOL[col]:
            bad.append((col, got, cell))
    return bad


def _check_job(job: tuple, golden: dict) -> None:
    path, kw = job
    scene = measure_blocks(path, **kw)
    rows = {k: v for k, v in golden.items() if k[0] == scene.name}
    assert len(rows) == len(scene.blocks), \
        f"{scene.name}: 块数不符 golden={len(rows)} got={len(scene.blocks)}"
    for b in scene.blocks:
        row = rows[(scene.name, str(b.block_id))]
        bad = _compare_row(_block_fields(b, scene), row)
        assert not bad, f"{scene.name} #{b.block_id} 不符: {bad}"


@pytest.mark.slow
def test_golden_all_six_datasets():
    """全量 6 组 x 19 条记录逐值比对。"""
    if not os.path.isdir(DATA1):
        pytest.skip("需要 ../1.0/data（全量回归数据不进仓库）")
    golden = _load_golden()
    for job in JOBS:
        _check_job(job, golden)


@pytest.mark.slow
def test_golden_tu1_smoke_on_repo_fixture():
    """不依赖 ../1.0/data：用仓库自带 tu1 夹具（已验证过 1.0）。"""
    import os.path as _p

    here = os.path.dirname(__file__)
    raw = _p.join(here, "data", "tu1_Depth.raw")
    if not os.path.exists(raw):
        pytest.skip("缺少 tests/data/tu1_Depth.raw")
    golden = _load_golden()
    scene = measure_blocks(raw, camera=D415)
    rows = {k: v for k, v in golden.items() if k[0] == "tu1_Depth"}
    assert len(rows) == len(scene.blocks)
    for b in scene.blocks:
        row = rows[("tu1_Depth", str(b.block_id))]
        bad = _compare_row(_block_fields(b, scene), row)
        assert not bad, f"tu1_Depth #{b.block_id} 不符: {bad}"

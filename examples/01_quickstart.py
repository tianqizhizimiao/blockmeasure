#!/usr/bin/env python3
"""示例 1：最小可用 —— 从深度原帧测量托盘上的物块。

运行::

    python examples/01_quickstart.py

用仓库自带的小夹具 `tests/data/tu1_Depth.raw`（640x360 Z16，450 KB），
所以**开箱即可运行**，不需要额外准备数据。

要点：D415 必须显式使用 `CameraProfile.intel_d415()`，它的
`depth_scale_m = 0.000694`；若用默认的 0.001，所有高度会整体缩放约 1.44 倍。
"""

from pathlib import Path

from blockmeasure import CameraProfile, measure_blocks

DATA = Path(__file__).resolve().parent.parent / "tests" / "data"
RAW = DATA / "tu1_Depth.raw"


def main() -> int:
    if not RAW.exists():
        print(f"找不到夹具: {RAW}")
        return 1

    scene = measure_blocks(str(RAW), camera=CameraProfile.intel_d415())

    print(f"来源      : {scene.source}   {scene.note}")
    print(f"参与点数  : {scene.points}")
    print(f"基准面尺寸: {scene.tray_size_mm[0]:.0f} x {scene.tray_size_mm[1]:.0f} mm")
    print(f"拟合残差  : {scene.plane_rms_mm:.1f} mm  （精度自检）")
    print(f"检出物块  : {len(scene.blocks)}")
    print()

    if not scene.blocks:
        print("未检出物块（这不是错误）")
        return 0

    print(f"{'#':<3}{'颜色':<8}{'高度mm':>8}{'长x宽mm':>12}{'倾斜°':>8}"
          f"{'平整度mm':>10}{'点数':>7}   中心(u, v, h) mm")
    for b in scene.blocks:
        tilt = f"{b.tilt_deg:.2f}" if b.tilt_deg is not None else "NA"
        flat = f"{b.flatness_mm:.3f}" if b.flatness_mm is not None else "NA"
        cx, cy, cz = (round(v, 1) for v in b.center_xyz_mm)
        print(f"{b.block_id:<3}{b.color:<8}{b.height_mm:>8.1f}"
              f"{b.length_mm:>7.0f}x{b.width_mm:<5.0f}{tilt:>8}"
              f"{flat:>10}{b.points:>7}   ({cx}, {cy}, {cz})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""示例 2：直接传 numpy 数组 —— 用自己的相机与自己的反投影。

运行::

    python examples/02_array_input.py

`measure_blocks()` 除了文件路径，也接受 ``(N, 3)`` 的 numpy 点云（单位**米**），
并可选附上每点 RGB。典型场景：你在别处已经拿到了点云（ROS 话题、自研采集程序、
仿真器输出），只想借这个库做平面拟合与物块分割。

本示例先用 `load_depth()` 把夹具反投影成点云，再**当数组传回去**，
以演示数组入口与文件入口等价。你自己的场景里换成自己的 P / C 即可。
"""

from pathlib import Path

import numpy as np

from blockmeasure import CameraProfile, load_depth, measure_blocks

DATA = Path(__file__).resolve().parent.parent / "tests" / "data"
RAW = DATA / "tu1_Depth.raw"


def main() -> int:
    if not RAW.exists():
        print(f"找不到夹具: {RAW}")
        return 1

    camera = CameraProfile.intel_d415()

    # ① 自己反投影（你的场景里换成你自己的点云）
    points, note = load_depth(str(RAW), camera)          # (N, 3) float64，米
    print(f"反投影得到点云: {points.shape}   {note}")

    # ② 没有任何颜色数据，colors 传 None 即可
    colors: np.ndarray | None = None

    # ③ 当数组传进去 —— 与 measure_blocks(路径) 结果一致
    scene = measure_blocks(points, colors=colors, camera=camera)

    print(f"来源标识  : {scene.source}  （应为『数组』）")
    print(f"检出物块  : {len(scene.blocks)}")
    for b in scene.blocks:
        print(f"  #{b.block_id} {b.color}  高 {b.height_mm:.1f} mm  "
              f"{b.length_mm:.0f} x {b.width_mm:.0f} mm  "
              f"点数 {b.points}  rgb={b.rgb}")
    print()
    print("提示：没有彩色点时 color 为 '-'、rgb 为 None，其余测量照常。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

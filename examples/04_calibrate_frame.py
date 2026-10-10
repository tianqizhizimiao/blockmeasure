#!/usr/bin/env python3
"""示例 4：标定一次托盘坐标系，之后反复复用。

运行::

    python examples/04_calibrate_frame.py

**为什么需要这个**：`measure_blocks()` 默认每次现算托盘坐标系，其原点取托盘平面内
点的质心，会随「这次扫到了托盘的哪一块」而漂移。实测同一物块在六次采集中的现算
坐标散布在约 124 x 130 mm 范围内。

所以：若你只关心**同一次扫描内**物块之间的相对位置，用默认的现算坐标系即可；
若你要「物体在托盘上的位置」在**多次采集之间可比**（或要喂给机械臂），
就必须标定一次固定坐标系并复用它。本示例演示这条流程。
"""

from pathlib import Path

import numpy as np

from blockmeasure import CameraProfile, TrayFrame, measure_blocks

DATA = Path(__file__).resolve().parent.parent / "tests" / "data"
RAW = DATA / "tu1_Depth.raw"
OUT_JSON = Path(__file__).resolve().parent / "_output" / "tray_frame.json"


def main() -> int:
    if not RAW.exists():
        print(f"找不到夹具: {RAW}")
        return 1

    camera = CameraProfile.intel_d415()

    # ① 用一次「干净扫描」标定坐标系
    calib_scene = measure_blocks(str(RAW), camera=camera)
    print(f"标定扫描用的坐标系 : reference = {calib_scene.frame.reference!r}（现算，跨次不可比）")

    frame = TrayFrame.from_reference(calib_scene)
    frame.save(str(OUT_JSON))          # 父目录不存在会自动创建
    print(f"已标定为固定参考     : reference = {frame.reference!r}")
    print(f"坐标系已保存到       : {OUT_JSON}")
    print()

    # ② 之后每次测量都加载同一套坐标系
    loaded = TrayFrame.load(str(OUT_JSON))
    scene = measure_blocks(str(RAW), camera=camera, frame=loaded)

    print(f"复用固定坐标系后，物块坐标表达在该系里（reference={scene.frame.reference!r}）:")
    for b in scene.blocks:
        u, v, h = b.center_xyz_mm          # 毫米，托盘系
        # to_camera 接收的是「米」（TrayFrame 内部单位是米），所以先 /1000
        cam = scene.frame.to_camera(np.array([u, v, h]) / 1000.0)
        print(f"  #{b.block_id} {b.color:<8}"
              f"托盘系 (u,v,h) = ({u:7.1f}, {v:7.1f}, {h:6.1f}) mm"
              f"   ->  相机系 (x,y,z) = ({cam[0]:.3f}, {cam[1]:.3f}, {cam[2]:.3f}) m")

    print()
    print("提示：单位约定 —— 对外的 Block 字段是**毫米**，"
          "而 TrayFrame 的换算方法是**米**，跨用时要 /1000。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

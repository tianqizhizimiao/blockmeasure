"""blockmeasure —— 从深度相机数据测量托盘上物块的颜色、长×宽×高与托盘坐标系位置。

对外只暴露稳定接口；内部实现分模块组织，见 README。

用法概览（随 2.0 开发推进逐项落地）::

    from blockmeasure import measure_blocks, CameraProfile

    # ① 直接给文件路径
    scene = measure_blocks("scan.ply")

    # ② 给 numpy 数组 + 调用方自己的相机参数
    scene = measure_blocks(points_xyz, colors=rgb, camera=CameraProfile(
        fx=445.578094, fy=445.578094, ppx=316.125519, ppy=172.919312,
        depth_scale_m=0.001,
    ))

    for b in scene.blocks:
        print(b.color, b.height_mm, b.length_mm, b.width_mm, b.center_xyz_mm)
"""

__version__ = "2.0.0"

__all__ = ["__version__"]

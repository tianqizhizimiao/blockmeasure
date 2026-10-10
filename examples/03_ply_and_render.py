#!/usr/bin/env python3
"""示例 3：从 .ply 点云测量，并导出核对渲染图。

运行::

    python examples/03_ply_and_render.py

    # 或指定自己的点云
    python examples/03_ply_and_render.py /path/to/scan.ply

`.ply` 走可选依赖 ``[ply]``（trimesh）。若只装了核心（仅 numpy），
二进制 PLY 会报 `UnsupportedFormatError`——装上即可::

    pip install "blockmeasure[ply]"

出图走 ``[render]``（pillow），只有在给出 ``outdir`` 时才惰性加载。

注意：真实点云（40 MB 级）不进仓库。默认路径指向同目录下的 1.0 数据集，
若你只克隆了 2.0，请用命令行参数传入自己的 .ply。
"""

import sys
from pathlib import Path

from blockmeasure import measure_blocks

# 仓库内的 1.0 数据集（本地开发时有；单独克隆 2.0 时不存在）
DEFAULT_PLY = Path(__file__).resolve().parent.parent.parent / "1.0" / "data" / "cs04.ply"
OUTDIR = Path(__file__).resolve().parent / "_output"


def main(argv: list[str]) -> int:
    ply = Path(argv[1]).expanduser() if len(argv) > 1 else DEFAULT_PLY

    if not ply.exists():
        print(f"找不到点云: {ply}")
        print()
        print("用法: python examples/03_ply_and_render.py <你的点云.ply>")
        print("（仓库只带小体积夹具，真实 .ply 需要你自己提供）")
        return 1

    scene = measure_blocks(str(ply), outdir=str(OUTDIR))

    print(f"文件      : {ply.name}")
    print(f"来源      : {scene.source}")
    print(f"参与点数  : {scene.points}")
    print(f"拟合残差  : {scene.plane_rms_mm:.1f} mm")
    print(f"检出物块  : {len(scene.blocks)}")
    for b in scene.blocks:
        print(f"  #{b.block_id} {b.color:<8} rgb={b.rgb}  "
              f"高 {b.height_mm:.1f} mm  {b.length_mm:.0f} x {b.width_mm:.0f} mm")

    if scene.blocks:
        print()
        print(f"核对图已输出到: {OUTDIR}")
        print(f"  {ply.stem}_height.png   高度图（颜色越红越高）")
        print(f"  {ply.stem}_seg.png      分割图（每块一色）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

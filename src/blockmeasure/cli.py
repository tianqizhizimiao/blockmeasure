"""命令行入口。

存在的两个理由：
1. 使用方拿到包后能立刻自检（`blockmeasure --version`）；
2. 开发时作为黄金回归的入口（见 tests/）。

算法逻辑不写在这里——这里只做参数解析与调用。
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from typing import List, Optional, Tuple

from . import __version__, DEFAULT_CONFIG, measure_blocks
from .camera import CameraProfile
from .exceptions import BlockMeasureError
from .frame import TrayFrame
from .results import SceneResult

__all__ = ["main", "build_parser"]


_EPILOG = """\
示例:
  # 单个点云
  blockmeasure data/cs04.ply

  # 深度原帧 + 内参（D415 必须给对深度尺度）
  blockmeasure data/tu1_Depth.raw --meta data/tu1_Depth_metadata.csv --depth-scale 0.000694

  # 批量处理 data/ 下全部素材
  blockmeasure --all -o output

  # 标定一次托盘坐标系，之后反复复用（这样跨次坐标才可比）
  blockmeasure data/clean_scan.ply --save-frame tray_frame.json
  blockmeasure data/scan_001.ply --frame tray_frame.json

输出:
  <out>/measurements.csv        每个物块一行（字段与 1.0 一致）
  <out>/<name>_height.png       高度图（颜色越红越高）
  <out>/<name>_seg.png          分割图（每块一色）
  后两张图需 [render] extra，可用 --no-render 关闭。

注意:
  --depth-scale 取错会让所有高度整体缩放，且不报任何错。Intel D415 为 0.000694。
  单个文件失败不会中断整批：错误打到 stderr，其余文件继续处理。

更多用法见仓库 docs/ 目录，或 Python 里 help(blockmeasure.measure_blocks)。
"""


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="blockmeasure",
        description=(
            "从深度相机点云（.ply）或深度原帧（.raw）测量托盘上物块的"
            "颜色、长×宽×高，以及物块在托盘坐标系中的位置。"
        ),
        epilog=_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=False,
    )
    ap.add_argument("-h", "--help", action="help", help="显示本帮助并退出")
    ap.add_argument("--version", action="version",
                    version=f"blockmeasure {__version__}",
                    help="显示版本号并退出")

    g_in = ap.add_argument_group("输入")
    g_in.add_argument("inputs", nargs="*", metavar="FILE",
                      help="一个或多个 .ply 点云 / .raw 深度原帧")
    g_in.add_argument("--all", action="store_true",
                      help="处理当前目录 data/ 下的全部素材（.ply 与 *_Depth.raw）")
    g_in.add_argument("--meta", metavar="CSV",
                      help="深度原帧的内参 CSV；缺省时自动在 .raw 旁找 "
                           "<name>_metadata.csv（注意其中不含深度尺度）")
    g_in.add_argument("--depth-scale", type=float, default=None, metavar="M",
                      help="深度单位（米/计数），与 --meta 一起用；"
                           "Intel D415 实测 0.000694，缺省 0.001")

    g_out = ap.add_argument_group("输出")
    g_out.add_argument("-o", "--out", default="output", metavar="DIR",
                       help="输出目录（默认 output），会写出 measurements.csv")
    g_out.add_argument("--no-render", action="store_true",
                       help="不输出核对渲染图（只要 CSV 时更快；出图需 [render] extra）")

    g_alg = ap.add_argument_group("算法")
    g_alg.add_argument("--voxel", type=float, default=0.0, metavar="M",
                       help="体素下采样边长（米），0=不下采样；调大可提速")

    g_frame = ap.add_argument_group("托盘坐标系")
    g_frame.add_argument("--frame", metavar="JSON",
                         help="使用已标定的托盘坐标系，让每次测量的块坐标可比")
    g_frame.add_argument("--save-frame", metavar="JSON",
                         help="把本次现算的托盘坐标系存成 JSON，供以后 --frame 复用")
    return ap


def _write_csv(results: List[SceneResult], path: str) -> int:
    """按 1.0 的字段顺序/舍入写 measurements.csv。"""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    fields = ["file", "source", "block_id", "color", "height_mm", "height_max_mm",
              "length_mm", "width_mm", "tilt_deg", "flatness_mm",
              "u_mm", "v_mm", "points", "tray_w_mm", "tray_h_mm",
              "plane_rms_mm", "rgb"]
    with open(path, "w", newline="", encoding="utf-8-sig") as fp:
        w = csv.DictWriter(fp, fieldnames=fields)
        w.writeheader()
        count = 0
        for r in results:
            for b in r.blocks:
                w.writerow({
                    "file": r.name, "source": r.source,
                    "block_id": b.block_id, "color": b.color,
                    "height_mm": round(b.height_mm, 2),
                    "height_max_mm": round(b.height_max_mm, 2),
                    "length_mm": round(b.length_mm, 1),
                    "width_mm": round(b.width_mm, 1),
                    "tilt_deg": "NA" if b.tilt_deg is None else round(b.tilt_deg, 2),
                    "flatness_mm": "NA" if b.flatness_mm is None else round(b.flatness_mm, 3),
                    "u_mm": round(b.u_mm, 1), "v_mm": round(b.v_mm, 1),
                    "points": b.points,
                    "tray_w_mm": round(r.tray_size_mm[0], 1),
                    "tray_h_mm": round(r.tray_size_mm[1], 1),
                    "plane_rms_mm": round(r.plane_rms_mm, 2),
                    "rgb": b.rgb,
                })
                count += 1
    return count


def _run_task(path: str, meta: Optional[str], args) -> SceneResult:
    """单个输入任务。meta 为 None 时：.raw 走 measure_blocks 的自动发现。"""
    outdir = None if args.no_render else args.out

    if path.endswith(".raw"):
        camera = None
        if meta:
            camera = CameraProfile.from_metadata_csv(
                meta, depth_scale_m=args.depth_scale or 0.001
            )
        elif args.depth_scale is not None:
            raise RuntimeError(
                f"{path}: 用了 --depth-scale 但没有 --meta，"
                "反投影缺内参；请同时提供 --meta"
            )
        return measure_blocks(
            path, camera=camera, cfg=args.cfg,
            frame=args.frame, outdir=outdir,
        )
    return measure_blocks(
        path, cfg=args.cfg, frame=args.frame, outdir=outdir
    )


def main(argv: Optional[List[str]] = None) -> int:
    ap = build_parser()
    args = ap.parse_args(argv)

    tasks: List[Tuple[str, Optional[str]]] = []
    if args.all:
        d = "data"
        if not os.path.isdir(d):
            ap.error("找不到 data/ 目录；请在素材根目录下运行，或给出文件路径")
        for f in sorted(os.listdir(d)):
            if f.endswith(".ply"):
                tasks.append((os.path.join(d, f), None))
            elif f.endswith("_Depth.raw"):
                meta = os.path.join(d, f.replace(".raw", "_metadata.csv"))
                tasks.append((os.path.join(d, f),
                              meta if os.path.exists(meta) else None))
    else:
        if not args.inputs:
            ap.print_help()
            return 0
        for p in args.inputs:
            tasks.append((p, args.meta if p.endswith(".raw") else None))
    if not tasks:
        ap.error("未指定输入；用 --all 或给出文件路径")

    args.cfg = Config(voxel_m=args.voxel) if args.voxel else DEFAULT_CONFIG
    if args.frame:
        try:
            args.frame = TrayFrame.load(args.frame)
        except (FileNotFoundError, ValueError, OSError) as e:
            ap.error(f"--frame 无法加载 {args.frame}: {e}")

    results: List[SceneResult] = []
    for path, meta in tasks:
        name = os.path.splitext(os.path.basename(path))[0]
        try:
            scene = _run_task(path, meta, args)
        except BlockMeasureError as e:
            print(f"\n[{name}] 处理失败: {type(e).__name__}: {e}", file=sys.stderr)
            continue

        print(f"\n{'='*62}\n[{name}]  来源: {scene.source}  {scene.note or '无'}\n{'='*62}")
        for stage, msg in scene.log:
            print(f"  {stage:<12} {msg}")
        print(f"  基准面尺寸   {scene.tray_size_mm[0]:.0f} x {scene.tray_size_mm[1]:.0f} mm"
              f"   拟合残差 {scene.plane_rms_mm:.1f} mm")
        if not scene.blocks:
            print("  未检出目标")
        else:
            print(f"  {'#':<3}{'颜色':<7}{'高度mm':>8}{'尺寸 长×宽 mm':>16}"
                  f"{'倾斜°':>9}{'平整度mm':>10}{'点数':>7}")
            for b in scene.blocks:
                tl = f"  {b.tilt_deg:.2f}" if b.tilt_deg is not None else "  NA"
                fl = f"  {b.flatness_mm:.3f}" if b.flatness_mm is not None else "    NA"
                print(f"  {b.block_id:<3}{b.color:<7}"
                      f"{b.height_mm:>8.1f}"
                      f"{b.length_mm:>9.0f}×{b.width_mm:<6.0f}"
                      f"{tl}{fl}{b.points:>7}")
        results.append(scene)
        if args.save_frame and args.frame is None:
            scene.frame.save(args.save_frame)
            print(f"  托盘坐标系已保存: {args.save_frame}")

    if results:
        out = os.path.join(args.out, "measurements.csv")
        n = _write_csv(results, out)
        print(f"\n{'='*62}\n已输出: {out}   (共 {n} 条记录)")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

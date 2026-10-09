"""命令行入口。

存在的两个理由：
1. 使用方拿到包后能立刻自检（`blockmeasure --version`）；
2. 开发时作为黄金回归的入口（见 tests/）。

算法逻辑不写在这里——这里只做参数解析与调用。
"""

from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from . import __version__


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="blockmeasure",
        description="从深度相机点云或深度帧测量托盘上物块的颜色、长宽高与托盘坐标系位置",
    )
    ap.add_argument("--version", action="version", version=f"blockmeasure {__version__}")
    ap.add_argument("inputs", nargs="*", help="点云 .ply 或深度帧 .raw")
    return ap


def main(argv: Optional[List[str]] = None) -> int:
    ap = build_parser()
    args = ap.parse_args(argv)
    if not args.inputs:
        ap.print_help()
        return 0
    ap.error("测量功能尚未实现（2.0 开发中，见 README 状态说明）")
    return 2  # pragma: no cover  —— ap.error 已抛出 SystemExit


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

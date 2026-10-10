#!/usr/bin/env bash
# 示例 5：命令行用法
#
# 这个脚本只做演示，不会自动执行任何测量步骤之外的事；逐条复制即可。
# 前置：pip install "blockmeasure[all]"
#
#   bash examples/05_cli_usage.sh

set -euo pipefail

# 定位仓库内的夹具（示例都能开箱跑）
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RAW="$HERE/../tests/data/tu1_Depth.raw"
META="$HERE/../tests/data/tu1_Depth_metadata.csv"
OUT="$HERE/_output/cli"

echo "=== ① 自检：版本 ==="
blockmeasure --version
echo

echo "=== ② 深度原帧 + 内参（D415 必须给 --depth-scale 0.000694）==="
blockmeasure "$RAW" --meta "$META" --depth-scale 0.000694 -o "$OUT"
echo

echo "=== ③ 标定：把本次现算的坐标系存下来，供以后复用 ==="
blockmeasure "$RAW" --meta "$META" --depth-scale 0.000694 \
    --save-frame "$OUT/tray_frame.json" -o "$OUT"
echo

echo "=== ④ 复用固定坐标系（坐标表达在同一套系里）==="
blockmeasure "$RAW" --meta "$META" --depth-scale 0.000694 \
    --frame "$OUT/tray_frame.json" -o "$OUT"
echo

echo "=== ⑤ 点云（.ply）批量处理 ==="
# 真实点云不进仓库；有 1.0 数据集时可直接：blockmeasure ../1.0/data/*.ply -o "$OUT"
echo "  blockmeasure data/*.ply -o $OUT"
echo

echo "=== ⑥ 提速：体素下采样（0.005 m = 5 mm）==="
echo "  blockmeasure scan.ply --voxel 0.005 -o $OUT"
echo

echo "=== ⑦ 只要数值不要出图 ==="
echo "  blockmeasure scan.ply --no-render -o $OUT"
echo

echo "=== ⑧ 在素材根目录一次性跑完 data/ 下全部素材 ==="
echo "  blockmeasure --all -o $OUT"
echo
echo "每次运行都会写出 $OUT/measurements.csv（字段与 1.0 一致）"

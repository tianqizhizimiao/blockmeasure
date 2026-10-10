# 示例

可直接运行的最小示例。**前 4 个开箱即可跑**——它们用仓库自带的夹具
`../tests/data/tu1_Depth.raw`（640x360 Z16，450 KB），不需要额外准备数据。

```bash
# 先装好（示例 3 的出图需要 [render]）
pip install "blockmeasure[all]"

# 或从仓库根目录直接用源码运行
PYTHONPATH=src python examples/01_quickstart.py
```

| 示例 | 内容 | 依赖数据 |
|---|---|---|
| [`01_quickstart.py`](01_quickstart.py) | 最小可用：深度原帧 → 物块尺寸 | 仓库自带夹具 |
| [`02_array_input.py`](02_array_input.py) | 传 numpy 数组（自己的点云/反投影） | 仓库自带夹具 |
| [`03_ply_and_render.py`](03_ply_and_render.py) | `.ply` 点云 + 导出核对渲染图 | 需自备 `.ply` |
| [`04_calibrate_frame.py`](04_calibrate_frame.py) | 标定并复用托盘坐标系 | 仓库自带夹具 |
| [`05_cli_usage.sh`](05_cli_usage.sh) | 命令行用法合集 | 仓库自带夹具 |

## 示例 3 的数据从哪来

真实点云（40 MB 级）不进仓库。示例 3 默认找同目录上层的 1.0 数据集
（`../1.0/data/cs04.ply`，本地开发时有）；单独克隆 2.0 时请自己传路径：

```bash
python examples/03_ply_and_render.py /path/to/your/scan.ply
```

## 两个最容易踩的坑

1. **`depth_scale_m`**：D415 是 `0.000694`，不是默认的 `0.001`。
   取错会让所有高度整体缩放（约 1.44 倍）**且不报错**。
   深度原帧一律用 `CameraProfile.intel_d415()`。
2. **托盘坐标系跨次不可比**：默认每次现算，原点会漂移。
   要跨次比较位置，先按示例 4 标定一次固定坐标系。

更多说明见仓库根目录的 [README](../README.md) 与 [docs/](../docs/)。

## 输出物

示例 3 与 4 会在 `examples/_output/` 下写文件（渲染图、坐标系 JSON、CSV），
该目录已在 `.gitignore` 中忽略。

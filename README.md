# blockmeasure

从深度相机（点云或深度帧）测量托盘上物块的颜色、长×宽×高，以及物块在托盘坐标系中的位置。

面向"需要拿到物块三维尺寸与位置，但不想自己实现平面拟合与分割"的使用方：装上一个包，传进去数据，拿到结构化结果。

> **状态：2.0 核心已完成。** IO、测量、渲染、CLI 全部实现；`tests/` 的 pytest 套件
> 含对 1.0 全部 19 条确定性结果的逐值黄金回归（`pytest -m slow`，需要 `../1.0/data`）。
> 接口尚未冻结，本 README 会随实现更新。
> 1.0（`../1.0/`）是已验证可用的脚本版本，其输出的 19 条确定性结果被 2.0 用作黄金回归基准。

## 安装

```bash
# 方式一：直接从 GitHub 安装（推荐，可指定 tag 锁定版本）
pip install "blockmeasure[all] @ git+https://github.com/tianqizhizimiao/blockmeasure@v2.0.0"

# 方式二：安装发布的 wheel
pip install blockmeasure-2.0.0-py3-none-any.whl

# 只装核心（不需要读 .ply、不需要出图时）
pip install blockmeasure
```

依赖策略：**核心只依赖 numpy**。读取二进制 `.ply` 需要 `trimesh`（`[ply]`），输出核对图需要 `pillow`（`[render]`），`[all]` 两者都装。装不上 extras 不影响核心测量功能。

## 快速开始

```python
from blockmeasure import measure_blocks, CameraProfile

# ① 给文件路径
scene = measure_blocks("scan.ply")

# ② 给 numpy 数组 + 你自己的相机参数
scene = measure_blocks(
    points_xyz,                      # (N, 3) float，单位米
    colors=rgb,                      # (N, 3) uint8，可选
    camera=CameraProfile(
        fx=445.578094, fy=445.578094,
        ppx=316.125519, ppy=172.919312,
        depth_scale_m=0.001,
    ),
)

for b in scene.blocks:
    print(b.color,          # '蓝' / '红' / '绿' / '白/灰' / '其他'
          b.rgb,            # (r, g, b) 平均色
          b.height_mm,      # 高度（顶面平台）
          b.length_mm, b.width_mm,
          b.center_xyz_mm)  # 托盘坐标系下的 X/Y/Z
```

## 关于"托盘坐标系"（重要）

`measure_blocks()` 每次都会现算一个托盘坐标系，并可通过 `scene.frame` 拿到：

```python
scene.frame.to_camera(b.center_xyz_mm)     # 托盘系 → 相机系
scene.frame.from_camera(their_points)      # 相机系 → 托盘系
```

但**每次现算的坐标系不能跨次比较**：实测同一物块在六次采集中的现算坐标散布在约 124×130 mm 范围内，因为不同视角只能扫到托盘的一部分（可见范围 215×249 ~ 307×302 mm）。

若你需要"物体在托盘上的位置"在多次采集之间可比，请**标定一次固定坐标系并复用它**：

```python
from blockmeasure import TrayFrame

frame = TrayFrame.from_reference(measure_blocks("clean_scan.ply"))
frame.save("tray_frame.json")

# 之后每次测量都表达在同一套坐标系里
scene = measure_blocks("scan_001.ply", frame=TrayFrame.load("tray_frame.json"))
```

## 返回值

`measure_blocks()` 返回冻结 dataclass `SceneResult`（`from blockmeasure import SceneResult`）：

| 字段 | 含义 |
|---|---|
| `blocks` | 检出的物块，按高度降序，`block_id` 从 1 开始；可能为空元组（未检出物块，这不是错误） |
| `frame` | 本次使用的托盘坐标系（`reference="scan"` 现算，或传入的固定参考） |
| `plane_rms_mm` | 基准面拟合残差 std —— 精度自检，本数据集为 1.0~2.7 mm |
| `tray_size_mm` | 基准面足迹尺寸 (u 跨度, v 跨度)，启发式，只用于限定测量范围 |
| `points` | 预处理后参与计算的点数 |
| `source` | `点云` / `深度原帧` / `数组` |
| `name` / `note` / `log` | 输入名、加载说明、各阶段摘要 |

`SceneResult.blocks` 里每个 `Block`（`from blockmeasure import Block`）：

| 字段 | 含义 |
|---|---|
| `block_id` / `color` / `rgb` | 序号、颜色归类、平均 RGB（无彩色时为 `None`） |
| `height_mm` / `height_max_mm` | 顶面平台高度 / 块内最大高度 |
| `length_mm` / `width_mm` | 顶面平台在托盘 u / v 方向的跨度 |
| `u_mm` / `v_mm` / `center_xyz_mm` | 底面投影中心与顶面中心（`(u, v, height)`） |
| `tilt_deg` / `flatness_mm` | 顶面倾角 / 平整度；覆盖不足时为 `None`（NA） |
| `points` | 属于该块、计入分割的点数 |

字段名即契约；各字段的精确语义见 `src/blockmeasure/results.py` 的 docstring。

## 命令行

```bash
# 单个点云
blockmeasure data/cs04.ply

# 深度原帧 + 内参（D415 必须给深度尺度）
blockmeasure data/tu1_Depth.raw --meta data/tu1_Depth_metadata.csv --depth-scale 0.000694

# 批量 + 固定坐标系复用
blockmeasure data/scan_001.ply data/scan_002.ply --frame tray_frame.json
blockmeasure data/clean_scan.ply --save-frame tray_frame.json
```

## 兼容性

- Python **>= 3.9**；CI 矩阵 `3.9 / 3.10 / 3.11 / 3.12 / 3.13 / 3.14`（[.github/workflows/ci.yml](.github/workflows/ci.yml)）
- 依赖 `numpy>=1.21`
- CI 每次 push / PR 执行：装 `[all,dev]` → `pytest` → `python -m build` 并验证 wheel 可装可导入

> 本机只有 Python 3.11 与 3.14，其余版本**由 CI 矩阵担保**，不是本地实测。
> 全量黄金回归需要 `../1.0/data`（46 MB，不进仓库），CI 里自动 skip；但 CI 仍会用
> 仓库自带的 `tests/data/tu1_Depth.raw` 跑真实端到端数值校验，不是只有单元测试。

## 许可

MIT，见 [LICENSE](LICENSE)。

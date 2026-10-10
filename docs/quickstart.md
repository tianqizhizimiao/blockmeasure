# 快速开始

## 三种输入

`measure_blocks()` 是包的唯一入口，接受三类输入。

### ① 点云文件 `.ply`

```python
from blockmeasure import measure_blocks

scene = measure_blocks("scan.ply")
```

二进制 PLY 需要可选依赖 `trimesh`：

```bash
pip install "blockmeasure[ply]"
```

没有 trimesh 时，仍可读"ASCII 逐属性分行"写法的 PLY（内置 fallback 解析器），
但二进制 PLY 会抛 `UnsupportedFormatError`。

### ② 深度原帧 `.raw`

```python
from blockmeasure import CameraProfile, measure_blocks

scene = measure_blocks(
    "tu1_Depth.raw",
    camera=CameraProfile.intel_d415(),   # 内参 + 深度尺度
)
```

!!! warning "深度原帧必须给对 `depth_scale_m`"
    这是最容易出错的一项，取错会让**所有高度整体缩放**且不报任何错。
    Intel D415 实测值为 `0.000694`；别的机型请重新标定，或使用默认的 `0.001`。

若 `.raw` 旁边存在同名元数据 `<name>_metadata.csv`，不传 `camera` 也会自动发现内参
——但**元数据里不含深度尺度**，此时用的是默认 `0.001`：

```python
# 自动发现内参，但深度尺度仍用默认 0.001
scene = measure_blocks("tu1_Depth.raw")

# 显式指定深度尺度（D415）
from blockmeasure import discover_metadata
meta = discover_metadata("tu1_Depth.raw")
camera = CameraProfile.from_metadata_csv(meta, depth_scale_m=0.000694)
scene = measure_blocks("tu1_Depth.raw", camera=camera)
```

### ③ numpy 数组

```python
import numpy as np
from blockmeasure import CameraProfile, measure_blocks

scene = measure_blocks(
    points_xyz,                        # (N, 3) float，单位**米**
    colors=rgb,                        # (N, 3) uint8，可选
    camera=CameraProfile(
        fx=445.578094, fy=445.578094,
        ppx=316.125519, ppy=172.919312,
        depth_scale_m=0.001,
    ),
)
```

点云数组必须是 `(N, 3)`；`colors` 给定时形状必须与之一致。

## 读结果

返回值是冻结 dataclass `SceneResult`：

| 字段 | 含义 |
|---|---|
| `blocks` | 检出的物块，按高度降序，`block_id` 从 1 开始；可能为空元组（**不是错误**） |
| `frame` | 本次使用的托盘坐标系 |
| `plane_rms_mm` | 基准面拟合残差 std —— 精度自检 |
| `tray_size_mm` | 基准面足迹尺寸 `(u 跨度, v 跨度)`，仅用于限定测量范围 |
| `points` | 预处理后参与计算的点数 |
| `source` | `点云` / `深度原帧` / `数组` |
| `name` / `note` / `log` | 输入名、加载说明、各阶段摘要 |

每个 `Block` 的字段：

| 字段 | 单位 | 含义 |
|---|---|---|
| `block_id` | — | 序号，按高度降序 |
| `color` / `rgb` | — | 颜色归类 / 平均 RGB（无彩色时 `-` 与 `None`） |
| `height_mm` | mm | 顶面平台高度 |
| `height_max_mm` | mm | 块内最大高度 |
| `length_mm` / `width_mm` | mm | 顶面平台在托盘 u / v 方向的跨度 |
| `u_mm` / `v_mm` | mm | 底面投影中心 |
| `center_xyz_mm` | mm | 顶面中心 `(u, v, height)`（派生属性） |
| `tilt_deg` / `flatness_mm` | 度 / mm | 顶面倾角 / 平整度；覆盖不足时为 `None` |
| `points` | — | 属于该块的点数 |

```python
for b in scene.blocks:
    print(f"#{b.block_id} {b.color} {b.height_mm:.1f}mm "
          f"{b.length_mm:.0f}x{b.width_mm:.0f}mm {b.center_xyz_mm}")
```

!!! tip "精度自检"
    `scene.plane_rms_mm` 是本数据集的 1.0~2.7 mm 量级。若它明显偏大，
    说明台面拟合质量差，结果可信度下降。

## 关于托盘坐标系（重要）

`measure_blocks()` 每次都会**现算**一个托盘坐标系，可通过 `scene.frame` 拿到：

```python
scene.frame.to_camera(b.center_xyz_mm)   # 托盘系 → 相机系
scene.frame.from_camera(their_points)    # 相机系 → 托盘系
```

!!! danger "每次现算的坐标系不能跨次比较"
    实测同一物块在六次采集中的现算坐标散布在约 **124×130 mm** 范围内，
    因为不同视角只能扫到托盘的一部分（可见范围 215×249 ~ 307×302 mm）。

若需要"物体在托盘上的位置"在多次采集之间可比，请**标定一次固定坐标系并复用它**：

```python
from blockmeasure import TrayFrame, measure_blocks

# ① 用一次干净扫描标定
frame = TrayFrame.from_reference(measure_blocks("clean_scan.ply"))
frame.save("tray_frame.json")        # 父目录不存在会自动创建

# ② 之后每次测量都表达在同一套坐标系里
scene = measure_blocks("scan_001.ply", frame=TrayFrame.load("tray_frame.json"))
```

!!! note "单位约定"
    对外的 `Block` 字段一律是**毫米**，而 `TrayFrame` 的换算方法
    （`to_camera` / `from_camera` / `height`）用的是**米**，跨用时要 `/1000`。

## 调参

算法参数集中在 `Config`，默认值与 1.0 完全一致：

```python
from blockmeasure import Config, measure_blocks

cfg = Config(
    plane_thresh_m=0.006,   # RANSAC 内点距离门限
    obj_min_h_m=0.008,      # 高出基准面多少算目标
    denoise_radius_m=0.006, # 降噪邻域半径（<= 0 跳过）
    voxel_m=0.005,          # 体素下采样边长（0 = 不下采样，可提速）
    random_seed=0,          # RANSAC 种子，便于多种子稳定性测试
)
scene = measure_blocks("scan.ply", cfg=cfg)
```

所有长度参数单位均为**米**。完整字段见 [API 参考 · Config](api.md#blockmeasure.Config)。

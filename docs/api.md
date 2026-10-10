# API 参考

本页是公开 API 的索引。稳定契约是 **`blockmeasure.__all__` 导出的这些名字**
（子模块路径不属于稳定契约）。

!!! note "离线怎么读"
    本页是普通 Markdown，直接在本地编辑器或 GitHub 上读即可，不需要任何构建工具。

    更详细的一手信息始终在源码 docstring 里，随时可查：

    ```python
    import blockmeasure
    help(blockmeasure)                        # 包总览
    help(blockmeasure.measure_blocks)         # 主入口：参数、返回、异常
    help(blockmeasure.Block)                  # 每个字段的精确语义
    ```

    CLI 的用法见 `blockmeasure --help`。

## 入口

### `measure_blocks()`

```python
measure_blocks(
    source,               # str 文件路径 或 (N, 3) ndarray，单位米
    *,
    camera=None,          # CameraProfile；深度原帧必需
    cfg=Config(...),      # 算法参数，默认与 1.0 一致
    frame=None,           # TrayFrame；给出则把块坐标表达在该固定坐标系
    colors=None,          # (N, 3) uint8；source 为数组时可用
    outdir=None,          # 非 None 时输出核对渲染图（需 [render]）
) -> SceneResult
```

包的主入口：测量一次场景。

| 参数 | 说明 |
|---|---|
| `source` | `.ply` / `.raw` 文件路径，或 `(N, 3)` numpy 点云（**米**） |
| `camera` | 内参与深度尺度。`.raw` 必需；未给出时自动找旁边同名 `_metadata.csv`（**但不含深度尺度**，此时用默认 `0.001`） |
| `cfg` | 算法参数，见下方 `Config` |
| `frame` | 已标定的托盘坐标系；跨次比较坐标时必须传 |
| `colors` | 每点 RGB，仅 `source` 为数组时有效 |
| `outdir` | 输出渲染图的目录；需要 `[render]` extra |

**异常**：`UnsupportedFormatError`（无法识别的输入）、`InvalidDepthError`
（深度帧缺内参或尺寸不符）、`PlaneFitError`（台面/托盘拟合失败）。

## 参数与相机

### `Config`

冻结 dataclass，测量管线全部可调参数，**单位一律为米**，默认值与 1.0 完全一致：

```python
Config(
    # 预处理
    invalid_min_m=0.05,          # 有效深度下限
    invalid_max_m=5.00,          # 有效深度上限
    denoise_radius_m=0.006,      # 统计降噪邻域半径；<= 0 跳过
    denoise_min_neighbors=8,     # 邻域内少于此数判为离群点
    voxel_m=0.0,                 # 体素下采样边长；0 = 不下采样
    # 平面拟合
    plane_thresh_m=0.006,        # RANSAC 内点距离门限
    plane_min_inliers=3000,      # 平面最少内点数
    ransac_iters=800,            # RANSAC 迭代次数
    # 基准面
    face_cell_m=0.004,           # 基准面连通域网格边长
    # 目标分割
    obj_min_h_m=0.008,           # 高出基准面多少算目标
    obj_max_h_m=0.30,            # 超过此高度视为干扰（机械臂等）
    obj_cell_m=0.004,            # 物块聚类网格边长
    obj_min_points=80,           # 少于这么多点的聚类丢弃
    # 测量
    plateau_tol_m=0.006,         # 顶面平台厚度
    plateau_min_points=30,       # 顶面平台最少点数
    # 可复现性
    random_seed=0,               # RANSAC 随机种子
)
```

`DEFAULT_CONFIG` 即 `Config()`，等价于 1.0 的行为。

### `CameraProfile`

```python
CameraProfile(
    fx, fy,                      # 焦距（像素）
    ppx, ppy,                    # 主点（像素）
    depth_scale_m=0.001,         # 深度单位（米/计数）
    width=None, height=None,     # 深度分辨率；None = 由数据推断
    distortion_model=None,       # 仅作记录，测量不依赖
)
```

!!! warning "`depth_scale_m` 是最容易错的一项"
    取错会让**所有高度整体缩放**且不报任何错。

- `CameraProfile.intel_d415()` —— 本机实测标定的 D415 参数（`depth_scale_m=0.000694`）
- `CameraProfile.from_metadata_csv(path, depth_scale_m=0.001)` —— 从 RealSense
  Viewer 导出的元数据 CSV 读内参（**元数据里不含深度尺度**，须由调用方提供）

## 结果类型

### `SceneResult`

冻结 dataclass，一次测量的完整结果。

| 字段 | 含义 |
|---|---|
| `blocks` | `Tuple[Block, ...]`，按高度降序；可能为空元组（**不是错误**） |
| `frame` | 本次使用的 `TrayFrame` |
| `plane_rms_mm` | 基准面拟合残差 std —— 精度自检 |
| `tray_size_mm` | 基准面足迹 `(u 跨度, v 跨度)`，仅用于限定测量范围 |
| `points` | 预处理后参与计算的点数 |
| `source` | `点云` / `深度原帧` / `数组` |
| `name` / `note` / `log` | 输入名、加载说明、各阶段摘要 |

支持 `len(scene)` 与迭代（直接遍历 `blocks`）。

### `Block`

冻结 dataclass，单个物块的测量结果，**长度单位全部为毫米**。

| 字段 | 类型 | 含义 |
|---|---|---|
| `block_id` | `int` | 序号，按高度降序从 1 开始 |
| `color` | `str` | `蓝` / `红` / `绿` / `白/灰` / `其他`；无彩色为 `-` |
| `rgb` | `(int,int,int) \| None` | 平均 RGB；无彩色为 `None` |
| `height_mm` | `float` | 高度 = 顶面平台（高度直方图最靠上的显著峰） |
| `height_max_mm` | `float` | 块内最大高度 |
| `length_mm` / `width_mm` | `float` | 顶面平台在托盘 u / v 方向的跨度 |
| `u_mm` / `v_mm` | `float` | 底面投影中心（托盘坐标均值） |
| `tilt_deg` | `float \| None` | 顶面法向与基准面法向夹角；覆盖不足为 `None` |
| `flatness_mm` | `float \| None` | 顶面点到拟合平面的 RMS，比倾角稳健 |
| `points` | `int` | 属于该块、计入分割的点数 |

派生属性 `center_xyz_mm` → `(u_mm, v_mm, height_mm)`，即托盘系下的 `(X, Y, Z)`。

### `TrayFrame`

托盘坐标系，**长度单位统一为米**（与相机坐标系一致）。

```python
TrayFrame(origin, axis_u, axis_v, normal, reference="scan")
```

| 方法/属性 | 说明 |
|---|---|
| `from_reference(scene)` | 把一次实测场景的现算坐标系标为固定参考（`reference="reference"`） |
| `save(path)` / `load(path)` | JSON 持久化；`save` 会自动创建父目录 |
| `from_camera(points)` | 相机系 `(N,3)` 米 → 托盘系 `(u, v, h)` 米 |
| `to_camera(uvh)` | 托盘系单点 → 相机系 |
| `height(points)` | 相机系点 → 沿法向的带符号高度（朝相机为正） |
| `to_tray_mm(uvh)` | 托盘系米 → 毫米 |

!!! danger "现算的坐标系不能跨次比较"
    默认每次现算，原点取托盘平面内点质心，随可见区域漂移。要跨次可比必须
    标定一次并复用，见 [快速开始](quickstart.md)。

## IO

| 函数 | 返回 | 说明 |
|---|---|---|
| `load_ply(path)` | `(P, C, note)` | 读 PLY 点云。`P` 为 `(N,3)` float64 米；`C` 为 `(N,3)` uint8 或 `None`。二进制 PLY 需 `[ply]` |
| `load_depth(path_raw, camera)` | `(P, note)` | 读 Z16 深度原帧并反投影成点云 |
| `discover_metadata(path_raw)` | `str \| None` | 在 `.raw` 旁找同名 `_metadata.csv` |

## 异常

全部继承自 `BlockMeasureError`，调用方 `except BlockMeasureError` 即可捕获所有预期失败。

| 异常 | 触发场景 |
|---|---|
| `BlockMeasureError` | 基类 |
| `UnsupportedFormatError` | 输入无法解析（二进制 PLY 缺 trimesh、形状不对等） |
| `InvalidDepthError` | 深度数据不自洽（缺内参、尺寸与分辨率不符、`depth_scale_m <= 0`） |
| `PlaneFitError` | 台面或托盘平面拟合失败（`str(e)` 说明是哪一级） |
| `NoBlocksFoundError` | 流程跑通但未检出物块。**注意**：默认不抛，只返回空 `blocks` |

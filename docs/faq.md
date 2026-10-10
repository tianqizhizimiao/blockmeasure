# 常见问题

## 高度整体不对（差一个固定倍数）

**几乎总是 `depth_scale_m` 取错。** 深度原帧的深度值是整数计数，乘上深度单位才是米；
取错会让所有高度整体缩放，而且**不会报任何错**。

- Intel D415 实测为 `0.000694` → 用 `CameraProfile.intel_d415()`
- 别的机型请重新标定；不确定时用默认 `0.001`（RealSense 系通用值）
- 从元数据 CSV 读内参时注意：**元数据里不含深度尺度**：

```python
CameraProfile.from_metadata_csv("meta.csv", depth_scale_m=0.000694)
```

本数据集里 D415 用错值会差约 **1.44 倍**（0.001 / 0.000694）。

## 同一个物块，两次测量的坐标对不上

正常现象。默认的托盘坐标系是**每次现算**的，原点取托盘平面内点的质心，
随"这次扫到了托盘的哪一块"而漂移——实测散布可达 124×130 mm。

**解法**：标定一次固定坐标系并复用，见[快速开始 · 关于托盘坐标系](quickstart.md)。

```python
frame = TrayFrame.from_reference(measure_blocks("clean_scan.ply"))
frame.save("tray_frame.json")
scene = measure_blocks("scan_001.ply", frame=TrayFrame.load("tray_frame.json"))
```

## 没检出物块，是出错了吗

**不是。** `scene.blocks` 为空元组是合法结果，`measure_blocks()` 不会因此抛异常
（`NoBlocksFoundError` 只是给显式检查用的）。

可以看看这些线索：

- `scene.tray_size_mm` —— 基准面是否被正确识别（尺寸应接近托盘实际大小）
- `scene.plane_rms_mm` —— 明显偏大说明台面拟合质量差
- `scene.log` —— 各阶段摘要，能看出卡在哪一步
- 调 `Config.obj_min_h_m` —— 物块太矮可能被当噪声滤掉

## `color` 是 `-`、`rgb` 是 `None`

说明输入**没有彩色数据**（比如深度原帧、或纯几何点云）。其余测量照常。

## `tilt_deg` 或 `flatness_mm` 是 `None`

顶面覆盖不足、拟合病态（判据：顶面两方向跨度之一 < 15 mm）。这类物块通常
只被扫到了一个角。`flatness_mm` 比 `tilt_deg` 稳健得多——倾角对"顶面扫到多少"
非常敏感，本数据集立方体在 6 次采集中报出 14.9°~23.4° 的波动。

## 报 `PlaneFitError: 未能拟合出基准面（台面）`

场景里没有足够大、足够平的平面。检查：

- 托盘是否真的出现在视野里
- `Config.invalid_min_m` / `invalid_max_m` 是否把有效深度裁掉了
- `Config.plane_min_inliers`（默认 3000）对点太少的输入是否过高

## 报 `InvalidDepthError`

- 没给 `camera`，且旁边找不到 `<name>_metadata.csv`
- 深度帧尺寸与内参分辨率不符
- `depth_scale_m <= 0`，或 `fx`/`fy` 为 0

## 报 `UnsupportedFormatError`（读 `.ply` 时）

二进制 PLY 需要 `trimesh`：

```bash
pip install "blockmeasure[ply]"
```

ASCII PLY 有内置 fallback 解析器，不需要 trimesh。输入形状不是 `(N, 3)` 时也报这个。

## 出图报错 / 没有 PNG

渲染需要 `pillow`，且只在给出 `outdir` 时才惰性加载：

```bash
pip install "blockmeasure[render]"
```

## 怎么提速

体素下采样，代价是精度：

```python
measure_blocks("scan.ply", cfg=Config(voxel_m=0.005))   # 5 mm
```

命令行对应 `--voxel 0.005`。只要数值不要图时加 `--no-render`。

## 支持哪些 Python 版本

Python **>= 3.9**。CI 矩阵覆盖 3.9 / 3.10 / 3.11 / 3.12 / 3.13 / 3.14；
本机实测环境为 3.11 与 3.14，其余由 CI 担保。

## 能 `import blockmeasure.measure` 直接用子模块吗

可以，但**子模块路径不属于稳定契约**。稳定的是 `blockmeasure.__all__` 导出的
公开 API（`measure_blocks`、`Config`、`CameraProfile`、`Block`、`SceneResult`、
`TrayFrame`、三个 IO 函数、五个异常）。接口已冻结（Beta），
破坏性变更会先警告、隔版本再移除。

## 结果与 1.0 一致吗

默认参数下**逐值一致**。1.0 输出的 19 条确定性结果被冻结为黄金回归基准
（`tests/data/golden_1.0_measurements.csv`），`pytest -m slow` 会逐值比对。

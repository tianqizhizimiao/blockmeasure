# 更新日志

本文件记录 blockmeasure 的所有重要变更。

格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [未发布]

### 修复

- `fit_plane_svd()` 改用薄 SVD（`full_matrices=False`）。原先用默认的
  `full_matrices=True` 会为 `(N, 3)` 的长条点集分配 `N×N` 的 `U` 矩阵：
  3 万点的基准面内点就要 5 GB 内存，点云更大时直接 `MemoryError`；
  部分 LAPACK 实现（实测 numpy 2.3.0 / Windows）在该路径上还会静默返回错误法向，
  表现为基准面残差从 2.7 mm 劣化到 28.3 mm、检出物块数与高度全错。
  只取最小奇异向量不需要完整 `U`，改薄 SVD 后结果与 1.0 黄金基准逐值一致。

## [2.0.0] - 2026-10-10

首个正式发布版本。把 1.0 的脚本版本重构为可安装、可复用的库，
**接口已冻结（Beta）**：后续破坏性变更将遵循弃用流程，先警告、隔版本再移除。

默认参数下与 1.0 **数值行为完全一致**——1.0 输出的 19 条确定性结果被逐值用作黄金回归基准。

### 新增

- **公开入口 `measure_blocks()`**：一次调用完成测量，支持三种输入——
  `.ply` 点云、`.raw` 深度原帧、裸 `(N, 3)` numpy 数组（可附颜色）。
- **`CameraProfile`**：相机内参与深度尺度独立成对象，默认值与具体机型解耦。
  提供 `intel_d415()`（本机实测标定）与 `from_metadata_csv()`。
  这一改动修掉了 1.0 把内参和 `depth_scale_m` 硬编码在 `CFG` 里的隐患——
  换相机会让所有高度整体缩放却不报错。
- **`TrayFrame`**：托盘坐标系成为可传递、可保存（JSON）、可复用的对象。
  标定一次即可让多次采集的物块坐标表达在同一套坐标系里，
  解决 1.0 只能拿到两个标量、且现算坐标系跨次不可比的问题。
- **结构化返回值**：冻结 dataclass `SceneResult` 与 `Block`，字段名即契约，
  有类型、有文档、可自动补全，替代 1.0 的裸 dict。
- **`Config` 参数对象**：算法参数按调用注入，替代 1.0 的模块级可变 `CFG`
  （后者被 `main()` 就地修改，污染全局、不可重入）。
- **类型化异常体系**：`BlockMeasureError` 基类及 `UnsupportedFormatError`、
  `InvalidDepthError`、`PlaneFitError`、`NoBlocksFoundError` 四个子类，
  调用方可按类型区分失败原因。
- **命令行 `blockmeasure`**：支持单文件测量、批量 `--all`、固定坐标系 `--frame`、
  标定导出 `--save-frame`、体素下采样 `--voxel`，并输出 `measurements.csv`。
- **核对渲染**：`outdir` 参数输出高度图与分割图（需 `[render]` extra）。
- **可选依赖拆分**：`[ply]`（trimesh，读二进制 PLY）、`[render]`（pillow，出图）、
  `[all]`、`[dev]`；核心只依赖 numpy，装不上 extras 不影响测量。

### 变更

- 二进制 `.ply` 改由 trimesh 读取（可选依赖），不再强制依赖；
  新增针对「ASCII 逐属性分行」写法的 fallback 解析器，两种写法通用。
- 项目结构从单文件脚本改为 `src/blockmeasure/` 包，附带 `pyproject.toml`。

### 修复

- `TrayFrame.save()` 在父目录不存在时自动创建，`save("calib/tray.json")` 可直接使用。

### 测试与持续集成

- 对 1.0 全部 19 条确定性结果的逐值黄金回归（`pytest -m slow`，需 `../1.0/data`）。
- 仓库自带小体积 fixture（`tests/data/tu1_Depth.raw` 等），CI 中跑真实端到端数值校验。
- GitHub Actions 矩阵：Python 3.9 / 3.10 / 3.11 / 3.12 / 3.13 / 3.14，
  执行安装 `[all,dev]` → `pytest` → `python -m build` 并验证 wheel 可装可导入。

### 说明

- 需要 Python >= 3.9；本机实测环境为 3.11 与 3.14，
  其余版本由 CI 矩阵担保，非本地实测。
- 子模块路径（如 `blockmeasure.measure.measure`）不属于稳定契约，
  公开 API 以 `blockmeasure.__all__` 为准。

[未发布]: https://github.com/tianqizhizimiao/blockmeasure/compare/v2.0.0...HEAD
[2.0.0]: https://github.com/tianqizhizimiao/blockmeasure/releases/tag/v2.0.0

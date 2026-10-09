# blockmeasure

从深度相机（点云或深度帧）测量托盘上物块的颜色、长×宽×高，以及物块在托盘坐标系中的位置。

面向"需要拿到物块三维尺寸与位置，但不想自己实现平面拟合与分割"的使用方：装上一个包，传进去数据，拿到结构化结果。

> **状态：2.0 开发中。** 接口尚未冻结，本 README 会随实现更新。
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

会随实现补全。计划包含 `SceneResult`（`blocks` / `frame` / `plane_rms_mm` / `tray_size_mm`）与 `Block`（颜色、RGB、高、宽、长、托盘系坐标、倾角、平整度、点数）。

## 兼容性

- Python **>= 3.9**
- 依赖 `numpy>=1.21`
- 已在 CI 中验证的版本矩阵：见 `.github/workflows/ci.yml`

> 本机只有 Python 3.11 与 3.14，其余版本**由 CI 矩阵担保**，不是本地实测。

## 许可

MIT，见 [LICENSE](LICENSE)。

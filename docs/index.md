# blockmeasure

从深度相机（点云或深度帧）测量托盘上物块的**颜色、长×宽×高**，以及物块在
**托盘坐标系**中的位置。

面向"需要拿到物块三维尺寸与位置，但不想自己实现平面拟合与分割"的使用方：
装上一个包，传进去数据，拿到结构化结果。

!!! success "版本状态"
    **2.0.0 核心已完成，接口已冻结（Beta）**。IO、测量、渲染、CLI 全部实现，
    并对 1.0 已验证的 19 条确定性结果做逐值黄金回归。

## 特点

- **一个入口**：`measure_blocks()` 接受 `.ply` 点云、`.raw` 深度原帧、
  或裸 `(N, 3)` numpy 数组。
- **核心只依赖 numpy**：读 `.ply`（`[ply]`）与出图（`[render]`）是可选 extras，
  装不上也不影响测量。
- **结构化返回**：冻结 dataclass `SceneResult` / `Block`，字段名即契约。
- **坐标系可标定复用**：解决"现算坐标系跨次不可比"的问题。
- **与 1.0 数值等价**：默认参数下逐值复现 1.0 的结果。

## 安装

```bash
# 核心（只需 numpy）
pip install blockmeasure

# 需要读 .ply 点云 → 加 trimesh
pip install "blockmeasure[ply]"

# 需要输出核对图 → 加 pillow
pip install "blockmeasure[render]"

# 两者都要
pip install "blockmeasure[all]"
```

也可从源码安装：

```bash
git clone https://github.com/tianqizhizimiao/blockmeasure.git
cd blockmeasure
pip install -e ".[all,dev]"
```

## 30 秒上手

```python
from blockmeasure import CameraProfile, measure_blocks

# 给文件路径即可；D415 深度原帧要显式带内参
scene = measure_blocks("scan.ply")
scene = measure_blocks("tu1_Depth.raw", camera=CameraProfile.intel_d415())

for b in scene.blocks:
    print(b.color,               # '蓝' / '红' / '绿' / '白/灰' / '其他'
          b.height_mm,           # 高度（顶面平台）
          b.length_mm, b.width_mm,
          b.center_xyz_mm)       # 托盘坐标系下的 (X, Y, Z)，毫米
```

## 下一步

- [快速开始](quickstart.md) —— 三种输入、返回值、坐标系，逐个讲清
- [命令行](cli.md) —— 不想写代码时的用法
- [常见问题](faq.md) —— 最容易踩的几个坑（深度尺度、坐标系）
- [API 参考](api.md) —— 公开 API 索引、字段语义与异常
- [更新日志](../CHANGELOG.md)

> 更细的一手信息在源码 docstring 里：`help(blockmeasure.measure_blocks)`。
> 命令行选项与示例见 `blockmeasure --help`。

## 许可

MIT，见 [LICENSE](https://github.com/tianqizhizimiao/blockmeasure/blob/main/LICENSE)。

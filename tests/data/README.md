# tests/data —— 测试夹具与黄金基准

这些文件是 **2.0 重构的安全网**：2.0 的算法必须复现 1.0 已实测验证过的结果。

## 文件

| 文件 | 来源 | 用途 |
|---|---|---|
| `golden_1.0_measurements.csv` | 1.0 的 `output/measurements.csv` **冻结副本**（19 条记录） | 完整 6 组数据的黄金基准 |
| `tu1_Depth.raw` | 1.0 的 `data/tu1_Depth.raw` 副本（640×360 Z16，450 KB） | CI 用的真实端到端夹具 |
| `tu1_Depth_metadata.csv` | 1.0 的 `data/tu1_Depth_metadata.csv` 副本（内参） | 同上 |
| `ascii_per_attribute.ply` | **手工合成**，4 顶点 | 锁定"ASCII PLY 逐属性分行"修复逻辑 |

## 为什么冻结一份 CSV 而不直接读 1.0 的 output/

因为 1.0 的 `output/measurements.csv` 是可被重新生成的产物，不是不可变的基准。
冻结成副本后，即使 1.0 目录被改动或删除，2.0 的回归判据依然稳定。

## 夹具已验证

`tu1_Depth.raw` + 元数据经 1.0 的 `pipeline.py` 实跑，产出与
`golden_1.0_measurements.csv` 中 `tu1_Depth` 的 3 行**逐字段完全一致**：

| block | height_mm | length×width | points |
|---|---|---|---|
| 1 | 57.0 | 42×25 | 1040 |
| 2 | 31.0 | 40×41 | 1736 |
| 3 | 15.0 | 45×40 | 954 |

`ascii_per_attribute.ply` 经 1.0 的 `load_ply` 实跑，得到预期的 4 个顶点与
RGB，并触发 `ASCII 逐属性分行写法已适配` 分支。

> 注意：`tu1` 的黄金值依赖 **`depth_scale_m = 0.000694`**（Intel D415 专属值）。
> 2.0 的默认值是通用的 `0.001`，因此**回归测试必须显式使用
> `CameraProfile.intel_d415()`**，否则高度会整体缩放 ~1.44 倍。

## 需要更多数据时

完整的 6 组数据共 46 MB，不进仓库。需要跑全量回归时，把
`../1.0/data/` 放到约定位置（见 `tests/conftest.py`），并运行
`pytest -m slow`。

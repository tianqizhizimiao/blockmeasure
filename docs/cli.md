# 命令行

不想写代码时，用 `blockmeasure` 命令。安装后即可用：

```bash
blockmeasure --version
```

## 基本用法

```bash
# 单个点云
blockmeasure data/cs04.ply

# 深度原帧 + 内参（D415 必须给 --depth-scale 0.000694）
blockmeasure data/tu1_Depth.raw \
    --meta data/tu1_Depth_metadata.csv \
    --depth-scale 0.000694

# 多个文件一起
blockmeasure data/scan_001.ply data/scan_002.ply
```

每次运行都会写出 `<out>/measurements.csv`（字段顺序与舍入和 1.0 一致）。

## 固定坐标系复用

```bash
# 标定一次：把本次现算的坐标系存下来
blockmeasure data/clean_scan.ply --save-frame tray_frame.json

# 之后每次测量都表达在同一套坐标系里
blockmeasure data/scan_001.ply --frame tray_frame.json
```

## 批量处理

在素材根目录（含 `data/`）执行：

```bash
blockmeasure --all -o output
```

会处理 `data/` 下全部 `.ply` 与 `*_Depth.raw`，自动配对同名 `_metadata.csv`。

## 常用选项

| 选项 | 说明 |
|---|---|
| `inputs` | 一个或多个 `.ply` / `.raw` 路径 |
| `--meta PATH` | 深度原帧对应的内参 CSV |
| `--depth-scale F` | 深度单位（米/计数）；与 `--meta` 一起用，D415 为 `0.000694` |
| `-o, --out DIR` | 输出目录，默认 `output` |
| `--all` | 处理 `data/` 下全部素材 |
| `--no-render` | 不输出核对渲染图（只要 CSV 时更快） |
| `--voxel F` | 体素下采样边长（米），`0` = 不下采样，可用于提速 |
| `--frame PATH` | 使用已标定的托盘坐标系 JSON |
| `--save-frame PATH` | 把本次现算的托盘坐标系保存为 JSON |
| `--version` | 打印版本 |

## 输出

- `<out>/measurements.csv` —— 每个物块一行，含
  `file` / `source` / `block_id` / `color` / `height_mm` / `height_max_mm` /
  `length_mm` / `width_mm` / `tilt_deg` / `flatness_mm` /
  `u_mm` / `v_mm` / `points` / `tray_w_mm` / `tray_h_mm` /
  `plane_rms_mm` / `rgb`
- `<out>/<name>_height.png`、`<out>/<name>_seg.png` —— 核对渲染图
  （除非给 `--no-render`，需要 `[render]` extra）

## 出错时

单个文件失败不会中断整批：错误以 `[文件名] 处理失败: 异常类型: 说明` 打到 stderr，
其余文件继续处理。

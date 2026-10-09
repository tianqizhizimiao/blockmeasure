"""结构化返回值。

1.0 的 ``process()`` 返回裸 dict：内部键叫 ``h_max_mm``，导出 CSV 时字段又叫
``height_max_mm``，``tray_mm`` 还是个 tuple。调用方只能靠翻源码猜字段名，改一次就破坏兼容。

这里换成冻结 dataclass：字段名即契约，有类型、有文档、可自动补全。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Tuple

from .frame import TrayFrame

__all__ = ["Block", "SceneResult"]


@dataclass(frozen=True)
class Block:
    """单个物块的测量结果。长度单位全部为**毫米**。"""

    block_id: int
    """序号，按高度**降序**重排后从 1 开始。"""

    color: str
    """颜色归类：``蓝``/``红``/``绿``/``白/灰``/``其他``；无彩色数据时为 ``-``。"""

    rgb: Optional[Tuple[int, int, int]]
    """该物块点云的平均 RGB；无彩色数据时为 ``None``。"""

    height_mm: float
    """高度 = 顶面平台（高度直方图最靠上的显著峰）。"""

    height_max_mm: float
    """该物块点的最大高度。"""

    length_mm: float
    """顶面平台在托盘坐标 u 方向的跨度。"""

    width_mm: float
    """顶面平台在托盘坐标 v 方向的跨度。"""

    u_mm: float
    """物块全部点的托盘坐标 u 均值（底面投影中心）。"""

    v_mm: float
    """物块全部点的托盘坐标 v 均值。"""

    tilt_deg: Optional[float]
    """顶面法向与基准面法向的夹角。

    ``None`` 表示顶面覆盖不足、拟合病态（判据：两方向跨度之一 < 15 mm）。
    该量对"顶面被扫到多少"很敏感——本数据集立方体在 6 次采集中报出 14.9°~23.4°。
    """

    flatness_mm: Optional[float]
    """顶面点到其拟合平面的 RMS，即平整度/凹凸指标。比倾角稳健。"""

    points: int
    """属于该物块的点数。"""

    @property
    def center_xyz_mm(self) -> Tuple[float, float, float]:
        """物块在**托盘坐标系**中的位置 ``(X, Y, Z)``，单位毫米。

        ``X`` / ``Y`` 是物块底面投影中心（``u_mm``/``v_mm``），
        ``Z`` 是顶面高度（``height_mm``）。

        注意：该坐标的**原点取决于** :class:`~blockmeasure.frame.TrayFrame`
        ——若用的是每次现算的 frame，则只能做同一次扫描内的相对比较，
        详见 README「关于托盘坐标系」。
        """
        return (self.u_mm, self.v_mm, self.height_mm)


@dataclass(frozen=True)
class SceneResult:
    """一次测量的完整结果。"""

    blocks: Tuple[Block, ...]
    """检出的物块，按高度降序。可能为空元组（未检出物块，这不是错误）。"""

    frame: TrayFrame
    """本次使用的托盘坐标系。用它可在相机系与托盘系之间换算。"""

    plane_rms_mm: float
    """基准面拟合残差 std——**精度自检**，本数据集为 1.0~2.7 mm。"""

    tray_size_mm: Tuple[float, float]
    """基准面足迹尺寸（启发式，见 README），仅用于限定测量范围。"""

    points: int
    """预处理后参与计算的点数。"""

    source: str
    """数据来源标识，如 ``点云`` / ``深度原帧`` / ``数组``。"""

    name: str = ""
    """输入名（通常是文件名，不含扩展名）。"""

    note: str = ""
    """加载阶段的补充说明（如内参来源、分辨率、ASCII 修复提示）。"""

    log: Tuple[Tuple[str, str], ...] = field(default=())
    """各阶段摘要，供日志/自检使用。"""

    def __len__(self) -> int:
        return len(self.blocks)

    def __iter__(self):
        return iter(self.blocks)

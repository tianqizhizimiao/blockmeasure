"""类型化异常。

1.0 里失败时抛的是裸 ``RuntimeError``/``ValueError``，而 CLI 又 ``except Exception``
把它吞成一行 stderr 打印。作为被别人 ``import`` 的库，调用方必须能按类型区分失败原因，
所以这里给每种可预期的失败一个类型。
"""

from __future__ import annotations

__all__ = [
    "BlockMeasureError",
    "UnsupportedFormatError",
    "InvalidDepthError",
    "PlaneFitError",
    "NoBlocksFoundError",
]


class BlockMeasureError(Exception):
    """本库所有异常的基类。调用方 ``except BlockMeasureError`` 即可捕获全部预期失败。"""


class UnsupportedFormatError(BlockMeasureError):
    """输入文件无法解析（既不是可读的二进制 PLY，也不是可修复的 ASCII PLY 等）。"""


class InvalidDepthError(BlockMeasureError):
    """深度数据本身不自洽（分辨率与像素数不符、缺少内参等）。"""


class PlaneFitError(BlockMeasureError):
    """基准面拟合失败——通常意味着场景里没有足够大的平面。

    台面拟合失败与托盘拟合失败都抛这个类型，``str(e)`` 里会说明是哪一级。
    """


class NoBlocksFoundError(BlockMeasureError):
    """流程跑通但一个物块都没检出。

    注意：这**不是**致命错误。默认情况下测量函数不会抛它，而是返回
    ``SceneResult(blocks=[])``；只有显式要求必须有结果时才由调用方检查。
    """

"""conftest —— 测试共享路径与数据位置。

全量回归数据（6 组、46 MB）在 ``../1.0/data/``，不进仓库。本机缺该目录时，
``slow`` 标记的测试自动 skip；CI 环境没有该目录，同样跳过（CI 用
tests/data 里的合成/真实小夹具）。
"""

import os

HERE = os.path.dirname(__file__)
DATA1 = os.path.abspath(os.path.join(HERE, "..", "..", "1.0", "data"))


def data1(*parts: str) -> str:
    return os.path.join(DATA1, *parts)

"""相机内参与深度尺度。

这是 1.0 作为库时**最危险的一处**：内参与 ``depth_scale_m=0.000694``（D415 专属值）
直接写死在 ``CFG`` 里。别的队伍若用 D435/L515 或别的深度单位，**全部高度会被整体缩放**
却不会报任何错——1.0 文档自己都写了"换相机必须重新标定这个系数"。

因此这里把相机参数独立成对象，并让默认值与具体机型解耦：

* :attr:`CameraProfile.depth_scale_m` 默认 **0.001**（RealSense 系通用默认），
  对"别人的相机"是安全值；
* 本机实测的 D415 参数通过 :meth:`CameraProfile.intel_d415` 显式取得。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from .exceptions import InvalidDepthError

__all__ = ["CameraProfile"]


@dataclass(frozen=True)
class CameraProfile:
    """深度相机内参与深度单位。

    Args:
        fx: 焦距 x（像素）。
        fy: 焦距 y（像素）。
        ppx: 主点 x（像素）。
        ppy: 主点 y（像素）。
        depth_scale_m: **深度单位，米/计数**。默认 ``0.001``。
            这是最容易搞错的一项：取错会让所有高度整体缩放。
        width: 深度分辨率宽；``None`` 表示由数据推断。
        height: 深度分辨率高；``None`` 表示由数据推断。
        distortion_model: 畸变模型名，仅作记录（测量不依赖它）。
    """

    fx: float
    fy: float
    ppx: float
    ppy: float
    depth_scale_m: float = 0.001
    width: Optional[int] = None
    height: Optional[int] = None
    distortion_model: Optional[str] = None

    def __post_init__(self) -> None:
        if self.depth_scale_m <= 0:
            raise InvalidDepthError(
                f"depth_scale_m 必须为正，得到 {self.depth_scale_m!r}"
            )
        if self.fx == 0 or self.fy == 0:
            raise InvalidDepthError("fx/fy 不能为 0")

    @classmethod
    def intel_d415(cls) -> "CameraProfile":
        """本机实测标定过的 Intel RealSense D415 参数。

        ``depth_scale_m=0.000694`` 是与点云交叉标定得到的，并与相机参数转储
        （``cs10.8.json`` 的 ``param-depthunits: 694``）一致。

        1.0 的黄金基准值依赖这个 profile——回归测试必须显式使用它，
        否则高度会整体差约 1.44 倍。
        """
        return cls(
            fx=445.578094,
            fy=445.578094,
            ppx=316.125519,
            ppy=172.919312,
            depth_scale_m=0.000694,
            width=640,
            height=360,
            distortion_model="Brown-Conrady",
        )

    @classmethod
    def from_metadata_csv(
        cls,
        path: str,
        depth_scale_m: float = 0.001,
    ) -> "CameraProfile":
        """从 RealSense Viewer 导出的元数据 CSV 读取内参。

        兼容 1.0 ``load_depth`` 的解析方式：逐行按逗号切分，取前两个字段做键值对；
        键名匹配 ``Fx`` / ``Fy`` / ``PPx`` / ``PPy`` / ``Resolution x`` /
        ``Resolution y`` / ``Distorsion``。

        Args:
            path: 元数据 CSV 路径。
            depth_scale_m: 深度单位。**元数据里不含这一项**，必须由调用方提供；
                默认 0.001，D415 请用 :meth:`intel_d415` 或显式传 0.000694。
        """
        if not os.path.exists(path):
            raise InvalidDepthError(f"内参文件不存在: {path}")

        vals = {}
        for line in open(path, encoding="utf-8-sig"):
            parts = [s.strip() for s in line.split(",")]
            if len(parts) < 2:
                continue
            key, val = parts[0], parts[1]
            if key in ("Resolution x", "Resolution y", "Bytes per pixel"):
                try:
                    vals[key] = int(float(val))
                except ValueError:
                    continue
            elif key in ("Fx", "Fy", "PPx", "PPy"):
                try:
                    vals[key] = float(val)
                except ValueError:
                    continue
            elif key == "Distorsion":
                vals[key] = val

        missing = [k for k in ("Fx", "Fy", "PPx", "PPy") if k not in vals]
        if missing:
            raise InvalidDepthError(
                f"{os.path.basename(path)} 缺少内参字段: {', '.join(missing)}"
            )

        return cls(
            fx=vals["Fx"],
            fy=vals["Fy"],
            ppx=vals["PPx"],
            ppy=vals["PPy"],
            depth_scale_m=depth_scale_m,
            width=vals.get("Resolution x"),
            height=vals.get("Resolution y"),
            distortion_model=vals.get("Distorsion") or None,
        )

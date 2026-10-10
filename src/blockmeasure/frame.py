"""托盘坐标系。

1.0 把 ``cen0`` / ``n_t`` / ``e1`` / ``e2`` 在 ``process()`` 里算出来，却**没有对外返回**
——调用方只拿到两个标量 ``u_mm``/``v_mm``，连自己换算回相机坐标都做不到。
这里把它做成一个可传递、可保存的对象。

坐标系约定（与 1.0 一致）：

* 原点 ``origin``：1.0 取托盘平面内点的质心（**随扫描漂移**，见 README 的说明）；
* ``normal``：托盘平面法向，**指向相机**；
* ``axis_u`` / ``axis_v``：平面内正交基，满足 ``axis_u × axis_v == normal``（右手系）。

任意点的托盘坐标即 ``(u, v, h)``，其中 ``h`` 是沿 ``normal`` 的带符号距离，
朝向相机为正。
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, Sequence, Tuple

import numpy as np

if TYPE_CHECKING:  # 仅为类型标注，避免与 results.py 形成循环导入
    from .results import SceneResult

__all__ = ["TrayFrame"]

Vec3 = Tuple[float, float, float]


def _as_vec3(v: Sequence[float]) -> Vec3:
    return (float(v[0]), float(v[1]), float(v[2]))


@dataclass(frozen=True)
class TrayFrame:
    """托盘坐标系（长度单位统一为**米**，与相机坐标系一致）。"""

    origin: Vec3
    axis_u: Vec3
    axis_v: Vec3
    normal: Vec3
    reference: str = "scan"
    """``"scan"`` 表示按本次扫描现算（跨次不可比）；
    ``"reference"`` 表示来自一次性标定的固定基准。"""

    # ------------------------- 坐标换算 -------------------------
    def from_camera(self, points: np.ndarray) -> np.ndarray:
        """相机系 ``(N,3)`` 米 → 托盘系 ``(N,3)`` 米，列顺序为 ``(u, v, h)``。"""
        pts = np.asarray(points, dtype=np.float64).reshape(-1, 3)
        rel = pts - np.asarray(self.origin, dtype=np.float64)
        return np.stack(
            [
                rel @ np.asarray(self.axis_u, dtype=np.float64),
                rel @ np.asarray(self.axis_v, dtype=np.float64),
                rel @ np.asarray(self.normal, dtype=np.float64),
            ],
            axis=-1,
        )

    def to_camera(self, uvh: Sequence[float]) -> Vec3:
        """托盘系单点 ``(u, v, h)`` 米 → 相机系米。"""
        p = (
            np.asarray(self.origin, dtype=np.float64)
            + float(uvh[0]) * np.asarray(self.axis_u, dtype=np.float64)
            + float(uvh[1]) * np.asarray(self.axis_v, dtype=np.float64)
            + float(uvh[2]) * np.asarray(self.normal, dtype=np.float64)
        )
        return _as_vec3(p)

    def height(self, points: np.ndarray) -> np.ndarray:
        """相机系 ``(N,3)`` 米 → 沿 ``normal`` 的带符号高度 ``(N,)`` 米（朝相机为正）。"""
        pts = np.asarray(points, dtype=np.float64).reshape(-1, 3)
        return (pts - np.asarray(self.origin, dtype=np.float64)) @ np.asarray(
            self.normal, dtype=np.float64
        )

    def to_tray_mm(self, uvh: Sequence[float]) -> Vec3:
        """托盘系米 → 毫米（对外返回给调用方的单位）。"""
        return (float(uvh[0]) * 1000.0, float(uvh[1]) * 1000.0, float(uvh[2]) * 1000.0)

    # ------------------------- 持久化 -------------------------
    def to_dict(self) -> dict:
        return {
            "origin": list(self.origin),
            "axis_u": list(self.axis_u),
            "axis_v": list(self.axis_v),
            "normal": list(self.normal),
            "reference": self.reference,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "TrayFrame":
        return cls(
            origin=_as_vec3(d["origin"]),
            axis_u=_as_vec3(d["axis_u"]),
            axis_v=_as_vec3(d["axis_v"]),
            normal=_as_vec3(d["normal"]),
            reference=str(d.get("reference", "reference")),
        )

    @classmethod
    def from_reference(cls, scene: SceneResult) -> "TrayFrame":
        """把一次实测场景的现算坐标系标为固定参考。

        Args:
            scene: 一个 :class:`~blockmeasure.results.SceneResult`（通常用一次
                专门"校准用"的干净扫描）。

        Returns:
            同参数的 :class:`TrayFrame`，但 ``reference="reference"``——之后传给
            ``measure_blocks(frame=...)`` 即可把每次测量表达在这套固定坐标系里。
        """
        f = scene.frame
        return cls(
            origin=f.origin,
            axis_u=f.axis_u,
            axis_v=f.axis_v,
            normal=f.normal,
            reference="reference",
        )

    def save(self, path: str) -> None:
        """保存为 JSON，便于"标定一次、反复复用"。

        父目录不存在时自动创建（``save("calib/tray.json")`` 直接可用）。
        """
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(path, "w", encoding="utf-8") as fp:
            json.dump(self.to_dict(), fp, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, path: str) -> "TrayFrame":
        with open(path, encoding="utf-8") as fp:
            return cls.from_dict(json.load(fp))

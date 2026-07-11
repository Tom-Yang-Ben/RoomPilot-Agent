#!/usr/bin/env python3
"""build_glb_scene.py — 由 architecture.json + furniture.json 組出 3D 場景並輸出 scene.glb。

- 依 architecture 的牆建立牆體方塊（可選是否含牆）。
- 依 furniture 每件的 glb_path 載入模型，套用位置與旋轉擺入場景；
  找不到 GLB 時以 dimensions 大小的佔位方塊替代並警告，不中斷輸出。

座標對應：平面 (x, y) → 3D (x, 0, y)，Y 軸朝上（cm）。rotation 為繞垂直軸的角度。
若你的 GLB 正面朝向與本管線「0 度朝 +Y」不同，用 --model-yaw-offset 統一補償。

用法：
  python build_glb_scene.py --architecture architecture.json --furniture furniture.json \
      --out scene.glb [--assets-root .] [--no-walls] [--model-yaw-offset 0]
"""
from __future__ import annotations
import argparse, math, os, sys

try:
    import numpy as np
    import trimesh
except ImportError:
    np = trimesh = None


def _yaw_matrix(angle_deg: float):
    """繞 Y 軸（垂直）旋轉。平面 CCW 對應繞 Y 的負向，這裡統一取負號。"""
    a = -math.radians(angle_deg)
    c, s = math.cos(a), math.sin(a)
    m = np.eye(4)
    m[0, 0], m[0, 2] = c, s
    m[2, 0], m[2, 2] = -s, c
    return m


def _translate(x, y, z):
    m = np.eye(4)
    m[0, 3], m[1, 3], m[2, 3] = x, y, z
    return m


def _box(w, d, h, color=(180, 180, 180, 255)):
    b = trimesh.creation.box(extents=(w, h, d))  # 注意：Y 為高
    b.visual.face_colors = color
    return b


def _add_walls(scene, architecture):
    walls = architecture.get("walls", [])
    for w in walls:
        length = w["width"]
        thick = w.get("thickness", 15.0)
        height = w.get("height", 280.0)
        box = _box(length, thick, height, color=(210, 205, 195, 255))
        T = _translate(w["position"]["x"], height / 2.0, w["position"]["y"]) @ _yaw_matrix(w.get("rotation", 0.0))
        scene.add_geometry(box, transform=T, geom_name=w["id"])


def _load_model(path, dims):
    """載入 GLB；失敗回傳佔位方塊。回傳 (mesh_or_scene, is_placeholder)。"""
    if path and os.path.exists(path):
        try:
            loaded = trimesh.load(path, force="scene")
            return loaded, False
        except Exception as e:  # noqa: BLE001
            print(f"[build_glb] 載入失敗 {path}: {e}；改用佔位方塊", file=sys.stderr)
    else:
        print(f"[build_glb] 找不到 GLB：{path}；改用佔位方塊", file=sys.stderr)
    ph = _box(dims["width"], dims["depth"], dims["height"], color=(150, 170, 200, 255))
    return ph, True


def build(architecture, furniture, assets_root=".", include_walls=True, yaw_offset=0.0):
    if trimesh is None:
        raise RuntimeError("需要 trimesh 與 numpy：pip install trimesh numpy pygltflib")
    scene = trimesh.Scene()
    if include_walls:
        _add_walls(scene, architecture)

    for f in furniture["furniture"]:
        dims = f["dimensions"]
        path = f.get("glb_path", "")
        if path and not os.path.isabs(path):
            path = os.path.join(assets_root, path)
        model, is_ph = _load_model(path, dims)
        z = f["position"].get("z", 0.0)
        # 模型底部貼地：抬升到 height/2（假設模型/方塊以中心為原點）
        lift = dims["height"] / 2.0 if is_ph else 0.0
        T = _translate(f["position"]["x"], z + lift, f["position"]["y"]) \
            @ _yaw_matrix(f.get("rotation", 0.0) + yaw_offset)
        if isinstance(model, trimesh.Scene):
            for name, geom in model.geometry.items():
                scene.add_geometry(geom, transform=T @ model.graph.get(name)[0],
                                   geom_name=f'{f["id"]}_{name}')
        else:
            scene.add_geometry(model, transform=T, geom_name=f["id"])
    return scene


def _load(path):
    import json
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def main(argv=None):
    ap = argparse.ArgumentParser(description="組出 3D 場景 scene.glb")
    ap.add_argument("--architecture", required=True)
    ap.add_argument("--furniture", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--assets-root", default=".", help="glb_path 的相對根目錄")
    ap.add_argument("--no-walls", action="store_true")
    ap.add_argument("--model-yaw-offset", type=float, default=0.0)
    args = ap.parse_args(argv)

    scene = build(_load(args.architecture), _load(args.furniture),
                  assets_root=args.assets_root, include_walls=not args.no_walls,
                  yaw_offset=args.model_yaw_offset)
    scene.export(args.out)
    print(f"[build_glb] geometries={len(scene.geometry)} → {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

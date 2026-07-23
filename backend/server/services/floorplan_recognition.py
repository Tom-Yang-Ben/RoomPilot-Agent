"""平面圖位元組 → 樓面 JSON 辨識服務(原 main.py 辨識區塊)。

DXF 直接解析;PNG/JPG/BMP 走 floorplan2dxf 影像管線再以 dxf_parser 升維,
並附掛影像管線的門偵測與(選配,allow_openrouter)VLM 房間語意標註。
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import HTTPException

from ...floorplan.room_analysis import ROOM_TYPE_OPTIONS, attach_room_regions
from ...upgrade3d.dxf_parser import parse_dxf_bytes
from ...upgrade3d.wall_openings import build_opening_wall_geometry
from . import floorplan_vlm
from .scene_service import _flip_parsed_z, load_local_env


def _attach_recognized_doors(floorplan: dict, handoff: dict) -> None:
    """把 floorplan2dxf 交接 JSON 的門(影像管線偵測,DXF 圖層沒有)補進 floorplan。

    交接 cm 座標與 dxf_scale/ 同框(原點左下、y 向上);dxf_parser 把幾何平移到
    平面中心後輸出公尺,所以這裡用「牆 cm bbox 中心」做同一個平移,z 再取負
    (與 _flip_parsed_z 一致)。門只有中心點+寬度,方向取最近牆矩形的長軸。
    """
    # 只收高信心門(≥0.85,同管線交叉檢核門檻)——低分多是家具/淋浴間弧線拼的假門,
    # 顯示假門比漏門更誤導使用者確認流程
    doors_cm = [
        d.get("cm")
        for d in handoff.get("doors") or []
        if d.get("cm") and float(d.get("score") or 0) >= 0.85
    ]
    walls_cm = [w.get("cm") for w in handoff.get("walls") or [] if w.get("cm")]
    if not doors_cm or not walls_cm:
        return
    ccx = (min(w[0] for w in walls_cm) + max(w[2] for w in walls_cm)) / 2.0
    ccy = (min(w[1] for w in walls_cm) + max(w[3] for w in walls_cm)) / 2.0

    def nearest_wall_horizontal(cx: float, cy: float) -> bool:
        best, horiz = None, True
        for x0, y0, x1, y1 in walls_cm:
            dx = max(x0 - cx, 0, cx - x1)
            dy = max(y0 - cy, 0, cy - y1)
            d2 = dx * dx + dy * dy
            if best is None or d2 < best:
                best, horiz = d2, (x1 - x0) >= (y1 - y0)
        return horiz

    doors_m: list[dict] = []
    door_segments: list[dict] = []
    for d in doors_cm:
        cx, cy, width = float(d["cx"]), float(d["cy"]), float(d["width"])
        x_m = (cx - ccx) / 100.0
        z_m = -(cy - ccy) / 100.0          # y 向上 → z 向南(同 _flip_parsed_z)
        half = width / 200.0
        if nearest_wall_horizontal(cx, cy):
            seg = {"x1": x_m - half, "z1": z_m, "x2": x_m + half, "z2": z_m}
        else:
            seg = {"x1": x_m, "z1": z_m - half, "x2": x_m, "z2": z_m + half}
        doors_m.append({k: round(v, 3) for k, v in seg.items()})
        door_segments.append(
            {
                "start": {"x": round(seg["x1"] * 100, 2), "z": round(seg["z1"] * 100, 2)},
                "end": {"x": round(seg["x2"] * 100, 2), "z": round(seg["z2"] * 100, 2)},
            }
        )
    floorplan["doors"] = doors_m
    floorplan["door_segments"] = door_segments
    floorplan.update(build_opening_wall_geometry(floorplan))
    if isinstance(floorplan.get("stats"), dict):
        floorplan["stats"]["doors"] = len(doors_m)


def _attach_vlm_rooms(floorplan: dict, vlm: dict, handoff: dict) -> None:
    """VLM 房間標註(0~1000 正規化 bbox)→ 與牆同框的公尺座標(平面中心原點、z 翻轉)。

    fixed_utility(廚房/浴室)= 管線固定不可移動;outdoor(露台/陽台)不擺室內家具
    ——這兩類之後交給擺位邊界剔除。px bbox 也保留,前端疊回原圖用。
    """
    image = handoff.get("image") or {}
    scale = handoff.get("scale") or {}
    walls_cm = [w.get("cm") for w in handoff.get("walls") or [] if w.get("cm")]
    img_w, img_h = image.get("width_px"), image.get("height_px")
    cm_per_px = scale.get("cm_per_px")
    if not (img_w and img_h and cm_per_px and walls_cm):
        return
    ccx = (min(w[0] for w in walls_cm) + max(w[2] for w in walls_cm)) / 2.0
    ccy = (min(w[1] for w in walls_cm) + max(w[3] for w in walls_cm)) / 2.0

    def to_m(px_x: float, px_y: float) -> tuple[float, float]:
        cm_x = px_x * cm_per_px
        cm_y = (img_h - px_y) * cm_per_px          # 影像 y 向下 → cm 座標 y 向上
        return (cm_x - ccx) / 100.0, -(cm_y - ccy) / 100.0  # z 翻轉,同 _flip_parsed_z

    rooms = []
    for room in vlm.get("rooms") or []:
        n = room["bbox_norm"]
        px = [n[0] / 1000 * img_w, n[1] / 1000 * img_h, n[2] / 1000 * img_w, n[3] / 1000 * img_h]
        x0, z0 = to_m(px[0], px[1])
        x1, z1 = to_m(px[2], px[3])
        rooms.append({
            "label": room["label"],
            "label_zh": room["label_zh"],
            "kind": room["kind"],
            "evidence": room["evidence"],
            "bbox_px": [round(v, 1) for v in px],
            "bbox": [round(x0, 3), round(z0, 3), round(x1, 3), round(z1, 3)],
        })
    floorplan["rooms"] = rooms
    if isinstance(floorplan.get("stats"), dict):
        floorplan["stats"]["rooms"] = len(rooms)


def recognize_floorplan_bytes(
    raw: bytes,
    name: str,
    scale_m: float | None = None,
    thickness: float = 0.18,
    height: float = 2.7,
    allow_openrouter: bool = False,
) -> dict:
    """平面圖影像(PNG/JPG/BMP)→ 牆/門/窗辨識(floorplan2dxf 管線)→ 3D 樓面 JSON。

    回傳:floorplan(dxf_parser 輸出,公尺、平面中心原點)、dxf_text(可直接餵
    /api/scene/generate 的 floorplan_dxf_text)、scale(比例尺推斷資訊)。
    DXF 檔直接解析不走影像管線。需要 vision extra(cv2);未安裝回 503。
    """
    import tempfile

    suffix = Path(name).suffix.lower()

    if suffix == ".dxf":
        dxf_text = raw.decode("utf-8", errors="ignore")
        try:
            # _flip_parsed_z:DXF y 朝北、three.js +z 朝南,不翻轉畫面會上下鏡像
            floorplan = _flip_parsed_z(
                parse_dxf_bytes(raw, name, scale_m, thickness, height)
            )
        except Exception as e:
            raise HTTPException(422, f"DXF 解析失敗: {e}")
        attach_room_regions(floorplan)
        floorplan["room_type_options"] = [dict(item) for item in ROOM_TYPE_OPTIONS]
        return {
            "floorplan": floorplan,
            "dxf_text": dxf_text,
            "scale": None,
            "source": "dxf",
            "openrouter": {
                "provider": "openrouter",
                "requested": bool(allow_openrouter),
                "sent": False,
                "status": "not_applicable_to_dxf",
            },
        }

    try:
        from ...floorplan import floorplan2dxf as fp
    except Exception:
        raise HTTPException(503, "影像辨識需要 vision 依賴:請以 `uv run --extra vision uvicorn ...` 啟動")

    with tempfile.TemporaryDirectory(prefix="rp_recognize_") as tmp:
        tmp_dir = Path(tmp)
        img_path = tmp_dir / f"input{suffix or '.png'}"
        img_path.write_bytes(raw)
        out_dxf = tmp_dir / "dxf" / "input.dxf"
        out_dxf.parent.mkdir(parents=True)
        cfg = fp.load_config(str(Path(fp.__file__).parent / "config.ini"))
        cfg.input = str(img_path)
        cfg.output = str(out_dxf)
        cfg.preview = str(tmp_dir / "chk.png")
        try:
            fp.run(cfg)
        except SystemExit as e:  # 管線內部以 sys.exit 報錯
            raise HTTPException(422, f"影像辨識失敗: {e}")
        except Exception as e:
            raise HTTPException(422, f"影像辨識失敗: {e}")

        # 優先用 dxf_scale/(牆厚錨定修正比例、公分單位 $INSUNITS=5):
        # dxf/ 是 config 固定比例,遇到需要 wall_min 修正的圖(如 floor08)
        # 尺寸會差到 2 倍;dxf_scale/ 才是交給引擎/前端的真實尺寸。
        scale_dxf = tmp_dir / "dxf_scale" / "input.dxf"
        dxf_source = scale_dxf if scale_dxf.is_file() else out_dxf
        dxf_text = dxf_source.read_text(encoding="utf-8", errors="ignore")

        scale_info = None
        handoff_data: dict | None = None
        handoff = tmp_dir / "json" / "input.json"
        if handoff.is_file():
            try:
                handoff_data = json.loads(handoff.read_text(encoding="utf-8"))
                scale_info = handoff_data.get("scale")
            except Exception:
                handoff_data = None
        preview_b64 = None
        preview_path = Path(cfg.preview)
        if preview_path.is_file():
            import base64
            preview_b64 = base64.b64encode(preview_path.read_bytes()).decode("ascii")
        try:
            # _flip_parsed_z:DXF y 朝北、three.js +z 朝南,不翻轉畫面會上下鏡像
            floorplan = _flip_parsed_z(
                parse_dxf_bytes(
                    dxf_text.encode("utf-8"),
                    "recognized.dxf",
                    scale_m,
                    thickness,
                    height,
                )
            )
        except Exception as e:
            raise HTTPException(422, f"辨識結果升維失敗: {e}")
        if handoff_data and dxf_source is scale_dxf:
            _attach_recognized_doors(floorplan, handoff_data)

        # VLM 語意層(選配):房間標籤/固定機能空間 + 門窗數第二意見。
        # 失敗回 None,不影響幾何辨識結果。
        vlm_info = None
        if allow_openrouter:
            load_local_env()
        provider_ready = bool(allow_openrouter and floorplan_vlm.vlm_enabled())
        image_subtype = "jpeg" if suffix in (".jpg", ".jpeg") else ("bmp" if suffix == ".bmp" else "png")
        vlm = (
            floorplan_vlm.annotate_floorplan(raw, mime=f"image/{image_subtype}")
            if allow_openrouter
            else None
        )
        if vlm:
            if handoff_data:
                _attach_vlm_rooms(floorplan, vlm, handoff_data)
            stats = floorplan.get("stats") or {}
            vlm_info = {
                "model": vlm["model"],
                "door_count": vlm["door_count"],
                "window_count": vlm["window_count"],
                "printed_dimensions": vlm["printed_dimensions"],
                # 交叉檢核:VLM 與 CV 管線的門窗數差距大 → 值得人工確認
                "counts_agree": (
                    vlm["window_count"] is not None
                    and abs(vlm["window_count"] - int(stats.get("windows") or 0)) <= 1
                ),
            }
        attach_room_regions(floorplan)
        floorplan["room_type_options"] = [dict(item) for item in ROOM_TYPE_OPTIONS]
        openrouter_info = {
            "provider": "openrouter",
            "requested": bool(allow_openrouter),
            "sent": provider_ready,
            "status": (
                "suggested"
                if vlm
                else ("unavailable" if allow_openrouter else "not_requested")
            ),
            "model": vlm.get("model") if vlm else None,
        }
        return {
            "floorplan": floorplan,
            "dxf_text": dxf_text,
            "scale": scale_info,
            "source": "image",
            "preview_png_base64": preview_b64,
            "vlm": vlm_info,
            "openrouter": openrouter_info,
        }

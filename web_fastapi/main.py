from __future__ import annotations

import io
import json
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from PIL import Image

from .scene_pipeline import build_scene_payload, get_openrouter_status


BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
STATIC_DIR = BASE_DIR / "static"
MOODBOARD_DIR = PROJECT_DIR / "docs" / "moodboard_assets"
STYLE_DB_PATH = PROJECT_DIR / "sf3d" / "metadata" / "ikea_furniture_style_database.json"

app = FastAPI(title="AI 室內風格與家具配置展示系統")

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.mount("/docs-assets", StaticFiles(directory=MOODBOARD_DIR), name="docs-assets")


def _normalize_posix_path(path_text: str) -> str:
    return path_text.replace("\\", "/").lstrip("/")


def _safe_relative_url(path_text: str | None, mount_prefix: str) -> str | None:
    if not path_text:
        return None
    return f"{mount_prefix}/{_normalize_posix_path(path_text)}"


def _model_status(model_path_text: str | None) -> tuple[bool, str]:
    if not model_path_text:
        return False, "這件家具沒有設定 GLB 路徑。"

    model_path = Path(model_path_text)
    if model_path.exists():
        return True, "GLB 可用"

    return False, "資料有記錄，但目前專案資料夾中找不到對應的 GLB 檔案。"


def load_style_database() -> dict:
    return json.loads(STYLE_DB_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=2048)
def _parse_glb(model_path_text: str) -> tuple[dict, bytes]:
    model_path = Path(model_path_text)
    buffer = model_path.read_bytes()

    if buffer[0:4] != b"glTF":
        raise ValueError("The input file is not a binary glTF (.glb) file.")

    declared_length = int.from_bytes(buffer[8:12], "little")
    if declared_length != len(buffer):
        raise ValueError("GLB length mismatch.")

    offset = 12
    json_payload = None
    binary_payload = None

    while offset + 8 <= len(buffer):
        chunk_length = int.from_bytes(buffer[offset : offset + 4], "little")
        chunk_type = int.from_bytes(buffer[offset + 4 : offset + 8], "little")
        chunk_start = offset + 8
        chunk_end = chunk_start + chunk_length
        chunk = buffer[chunk_start:chunk_end]

        if chunk_type == 0x4E4F534A:
            json_payload = json.loads(chunk.rstrip(b"\x00").decode("utf-8"))
        elif chunk_type == 0x004E4942:
            binary_payload = bytes(chunk)

        offset = chunk_end

    if json_payload is None or binary_payload is None:
        raise ValueError("The GLB does not contain both JSON and BIN chunks.")

    return json_payload, binary_payload


def _get_furniture_by_id(furniture_id: str) -> dict:
    data = load_style_database()
    furniture = next((item for item in data.get("furniture", []) if item.get("furniture_id") == furniture_id), None)
    if not furniture:
        raise HTTPException(status_code=404, detail="找不到這件家具資料。")
    return furniture


def _get_model_path_for_furniture(furniture: dict) -> str:
    model_path_text = furniture.get("glb_absolute_path")
    if not model_path_text:
        raise HTTPException(status_code=404, detail="這件家具沒有 GLB 路徑。")

    if not Path(model_path_text).exists():
        raise HTTPException(status_code=404, detail="找不到這件家具對應的 GLB 檔案。")

    return model_path_text


def _gltf_payload_for_web(model_path_text: str, furniture_id: str) -> dict:
    gltf_json, binary_payload = _parse_glb(model_path_text)
    gltf_copy = json.loads(json.dumps(gltf_json))

    if gltf_copy.get("buffers"):
        gltf_copy["buffers"][0]["uri"] = "buffer.bin"
        gltf_copy["buffers"][0]["byteLength"] = len(binary_payload)

    for index, image in enumerate(gltf_copy.get("images", [])):
        if image.get("bufferView") is not None:
            image["uri"] = f"images/{index}"
            image.pop("bufferView", None)
            image.pop("mimeType", None)

    for texture in gltf_copy.get("textures", []):
        ext_webp = texture.get("extensions", {}).get("EXT_texture_webp")
        if ext_webp and ext_webp.get("source") is not None:
            texture["source"] = ext_webp["source"]
        texture.pop("extensions", None)

    gltf_copy["extensionsUsed"] = [
        ext for ext in gltf_copy.get("extensionsUsed", [])
        if ext != "EXT_texture_webp"
    ]
    gltf_copy["extensionsRequired"] = [
        ext for ext in gltf_copy.get("extensionsRequired", [])
        if ext != "EXT_texture_webp"
    ]

    return gltf_copy


def _image_bytes_from_glb(model_path_text: str, image_index: int) -> tuple[bytes, str]:
    gltf_json, binary_payload = _parse_glb(model_path_text)
    images = gltf_json.get("images", [])
    buffer_views = gltf_json.get("bufferViews", [])

    if image_index < 0 or image_index >= len(images):
        raise HTTPException(status_code=404, detail="找不到這張貼圖。")

    image = images[image_index]
    buffer_view_index = image.get("bufferView")
    if buffer_view_index is None:
        raise HTTPException(status_code=404, detail="這張貼圖沒有內嵌 bufferView。")

    if buffer_view_index < 0 or buffer_view_index >= len(buffer_views):
        raise HTTPException(status_code=404, detail="這張貼圖的 bufferView 無效。")

    view = buffer_views[buffer_view_index]
    start = view.get("byteOffset", 0)
    end = start + view.get("byteLength", 0)
    mime_type = image.get("mimeType", "application/octet-stream")
    payload = binary_payload[start:end]

    if mime_type == "image/webp":
        with Image.open(io.BytesIO(payload)) as source:
            output = io.BytesIO()
            source.save(output, format="PNG")
            return output.getvalue(), "image/png"

    return payload, mime_type


def build_site_payload() -> dict:
    raw = load_style_database()
    furniture_items = raw.get("furniture", [])
    furniture_by_id = {item["furniture_id"]: item for item in furniture_items}

    styles = []
    for style in raw.get("styles", []):
        representative_cards = []
        for furniture_id, card_path in zip(
            style.get("representative_furniture_ids", []),
            style.get("representative_furniture_cards", []),
        ):
            furniture = furniture_by_id.get(furniture_id)
            if not furniture:
                continue

            has_model, model_reason = _model_status(furniture.get("glb_absolute_path"))
            representative_cards.append(
                {
                    "furniture_id": furniture_id,
                    "name_en": furniture.get("name_en"),
                    "name_zh_raw": furniture.get("name_zh_raw"),
                    "normalized_type": furniture.get("normalized_type"),
                    "primary_style": furniture.get("primary_style"),
                    "color": furniture.get("color"),
                    "material": furniture.get("material"),
                    "size_cm": furniture.get("size_cm"),
                    "card_image_url": _safe_relative_url(
                        card_path.replace("docs/moodboard_assets/", "", 1)
                        if card_path.startswith("docs/moodboard_assets/")
                        else card_path,
                        "/docs-assets",
                    ),
                    "has_model": has_model,
                    "missing_model_reason": None if has_model else model_reason,
                    "model_url": f"/api/furniture/{furniture_id}/model.gltf" if has_model else None,
                }
            )

        styles.append(
            {
                "style_id": style.get("style_id"),
                "style_name_zh": style.get("style_name_zh"),
                "style_name_en": style.get("style_name_en"),
                "core_description_zh": style.get("core_description_zh"),
                "keywords_zh": style.get("keywords_zh", []),
                "main_colors_zh": style.get("main_colors_zh", []),
                "materials_zh": style.get("materials_zh", []),
                "shape_features_zh": style.get("shape_features_zh", []),
                "avoid_elements_zh": style.get("avoid_elements_zh", []),
                "scene_background": style.get("scene_background", {}),
                "wall_recommendations": style.get("wall_recommendations", []),
                "floor_recommendations": style.get("floor_recommendations", []),
                "recommended_wall_floor_pairs_zh": style.get("recommended_wall_floor_pairs_zh", []),
                "visual_theme": style.get("visual_theme", {}),
                "palette_hex": style.get("palette_hex", []),
                "stats": style.get("stats", {}),
                "moodboard_image_url": _safe_relative_url(
                    (style.get("moodboard_card_path") or "").replace("docs/moodboard_assets/", "", 1),
                    "/docs-assets",
                ),
                "representative_furniture": representative_cards,
            }
        )

    furniture_payload = []
    for item in furniture_items:
        has_model, model_reason = _model_status(item.get("glb_absolute_path"))
        furniture_payload.append(
            {
                "furniture_id": item.get("furniture_id"),
                "name_en": item.get("name_en"),
                "name_zh_raw": item.get("name_zh_raw"),
                "category_label": item.get("category_label"),
                "normalized_type": item.get("normalized_type"),
                "primary_style": item.get("primary_style"),
                "style_candidates": item.get("style_candidates", []),
                "style_confidence": item.get("style_confidence"),
                "style_assignment_source": item.get("style_assignment_source"),
                "color": item.get("color"),
                "material": item.get("material"),
                "size_cm": item.get("size_cm"),
                "must_against_wall": item.get("must_against_wall"),
                "can_rotate": item.get("can_rotate"),
                "has_model": has_model,
                "missing_model_reason": None if has_model else model_reason,
                "model_url": f"/api/furniture/{item.get('furniture_id')}/model.gltf" if has_model else None,
            }
        )

    featured_models = [item for item in furniture_payload if item["has_model"]][:24]

    return {
        "project": {
            "title": "AI 室內風格與家具配置展示系統",
            "subtitle": "以平面圖、風格條件與既有 GLB 家具資料庫，自動配置並展示 3D 室內場景。",
            "scope": [
                "上傳平面圖與需求文字",
                "由風格規則與家具資料庫挑選合適模型",
                "輸出可在網頁瀏覽的 Three.js 3D 場景",
            ],
            "not_scope": "本專題不是直接生成全新 3D 家具模型，而是用既有 GLB 資料庫做風格化配置。",
        },
        "summary": raw.get("summary", {}),
        "styles": styles,
        "furniture": furniture_payload,
        "featured_models": featured_models,
        "missing_model_count": sum(1 for item in furniture_payload if not item["has_model"]),
    }


def _page(name: str) -> FileResponse:
    return FileResponse(STATIC_DIR / name)


@app.get("/")
def home() -> FileResponse:
    return _page("index.html")


@app.get("/styles")
def styles_page() -> FileResponse:
    return _page("styles.html")


@app.get("/library")
def library_page() -> FileResponse:
    return _page("library.html")


@app.get("/scene")
def scene_page() -> FileResponse:
    return _page("scene.html")


@app.get("/compare")
def compare_page() -> FileResponse:
    return _page("scene.html")


@app.get("/api/site-data")
def site_data() -> dict:
    return build_site_payload()


@app.get("/api/scene/provider-status")
def scene_provider_status() -> dict:
    return get_openrouter_status()


@app.post("/api/scene/generate")
async def generate_scene(payload: dict) -> dict:
    site_payload = build_site_payload()

    questionnaire = {
        "space_type": payload.get("space_type", "living_room"),
        "style_preference": payload.get("style_preference", "auto"),
        "required_furniture": payload.get("required_furniture", []),
        "custom_furniture": payload.get("custom_furniture", []),
        "preferred_colors": payload.get("preferred_colors", []),
        "custom_colors": payload.get("custom_colors", []),
        "personal_notes": payload.get("personal_notes", ""),
        "keep_window_clear": bool(payload.get("keep_window_clear", False)),
        "keep_door_clear": bool(payload.get("keep_door_clear", False)),
        "need_storage": bool(payload.get("need_storage", False)),
        "prefer_low_saturation": bool(payload.get("prefer_low_saturation", False)),
        "floorplan_filename": payload.get("floorplan_filename"),
        "floorplan_dxf_text": payload.get("floorplan_dxf_text"),
        "wall_option": payload.get("wall_option", "auto"),
        "floor_option": payload.get("floor_option", "auto"),
        "furniture_random_seed": payload.get("furniture_random_seed"),
    }

    return build_scene_payload(
        site_payload=site_payload,
        questionnaire=questionnaire,
        floorplan_path=payload.get("floorplan_filename"),
        room_width_cm=float(payload.get("room_width_cm", 420)),
        room_depth_cm=float(payload.get("room_depth_cm", 360)),
    )


@app.get("/api/furniture/{furniture_id}/model")
def furniture_model(furniture_id: str) -> FileResponse:
    furniture = _get_furniture_by_id(furniture_id)
    model_path_text = _get_model_path_for_furniture(furniture)
    model_path = Path(model_path_text)
    return FileResponse(model_path, media_type="model/gltf-binary", filename=model_path.name)


@app.get("/api/furniture/{furniture_id}/model.gltf")
def furniture_model_gltf(furniture_id: str) -> JSONResponse:
    furniture = _get_furniture_by_id(furniture_id)
    model_path_text = _get_model_path_for_furniture(furniture)
    return JSONResponse(_gltf_payload_for_web(model_path_text, furniture_id))


@app.get("/api/furniture/{furniture_id}/buffer.bin")
def furniture_model_buffer(furniture_id: str) -> Response:
    furniture = _get_furniture_by_id(furniture_id)
    model_path_text = _get_model_path_for_furniture(furniture)
    _, binary_payload = _parse_glb(model_path_text)
    return Response(content=binary_payload, media_type="application/octet-stream")


@app.get("/api/furniture/{furniture_id}/images/{image_index}")
def furniture_model_image(furniture_id: str, image_index: int) -> Response:
    furniture = _get_furniture_by_id(furniture_id)
    model_path_text = _get_model_path_for_furniture(furniture)
    image_bytes, mime_type = _image_bytes_from_glb(model_path_text, image_index)
    return Response(content=image_bytes, media_type=mime_type)

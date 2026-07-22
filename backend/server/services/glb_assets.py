"""GLB 模型資產定位與回應(原 main.py GLB 區塊)。

負責:data/dataset/ 與外部 zip 內的 GLB 檔定位、遠端 GLB 代理、GLB 拆解為
gltf+bin+貼圖,供 /api/furniture/*/model* 端點與型錄 has_model 判定使用。
"""
from __future__ import annotations

import io
import json
import os
import unicodedata
import urllib.error
import urllib.request
import zipfile
from functools import lru_cache
from pathlib import Path

from fastapi import HTTPException
from fastapi.responses import FileResponse, Response
from PIL import Image

from ..config import DATASET_DIR, PROJECT_DIR


_EXTERNAL_GLB_ZIP_SEARCH_DIRS = (
    DATASET_DIR,
    PROJECT_DIR / "data" / "dataset" / "style_rag",
    Path.home() / "Downloads",
)
_EXTERNAL_GLB_ZIP_PATTERNS = (
    "downloaded-files*.zip",
    "ABO*.zip",
    "補缺的GLB*.zip",
    "ikea抓取家具glb_中文命名版*.zip",
    "drive-download-202607*.zip",
)

# GLB 實檔可能在 data/dataset/ 的不同層(依組員從雲端下載後的擺法)
_DATASET_GLB_ROOTS = [
    DATASET_DIR,
    DATASET_DIR / "ikea_glb_db" / "ikea抓取家具glb_中文命名版",
]


def _normalize_posix_path(path_text: str) -> str:
    return path_text.replace("\\", "/").lstrip("/")


def _is_remote_glb_url(path_text: object) -> bool:
    text = str(path_text or "").strip()
    return text.startswith(("https://", "http://")) and (
        ".glb" in text.lower()
        or "/glb/" in text.lower()
        or "/glb_draco/" in text.lower()
        or "/simple/" in text.lower()
    )


def _remote_glb_url(furniture: dict) -> str | None:
    for key in ("glb_absolute_path", "model_url", "glb_url", "model_path", "glb_path"):
        url = str(furniture.get(key) or "").strip()
        if _is_remote_glb_url(url):
            return url
    return None


def _glb_lookup_keys(path_text: str) -> list[str]:
    normalized = unicodedata.normalize("NFKC", _normalize_posix_path(path_text)).casefold()
    parts = [part for part in normalized.split("/") if part]
    keys: list[str] = []
    for count in (5, 4, 3, 2, 1):
        if len(parts) >= count:
            keys.append("/".join(parts[-count:]))
    keys.append(normalized)
    return list(dict.fromkeys(keys))


@lru_cache(maxsize=1)
def _dataset_glb_lookup() -> dict[str, Path]:
    lookup: dict[str, Path] = {}
    conflicts: set[str] = set()
    if not DATASET_DIR.exists():
        return lookup

    def remember(key: str, path: Path) -> None:
        existing = lookup.get(key)
        if existing is not None and existing != path:
            conflicts.add(key)
            return
        lookup[key] = path

    for path in DATASET_DIR.rglob("*.glb"):
        if not path.is_file():
            continue
        for key in _glb_lookup_keys(path.name):
            remember(key, path)
        for root in _DATASET_GLB_ROOTS:
            try:
                relative = path.relative_to(root)
            except ValueError:
                continue
            for key in _glb_lookup_keys(relative.as_posix()):
                remember(key, path)

    for key in conflicts:
        lookup.pop(key, None)
    return lookup


def _iter_external_zip_paths() -> list[Path]:
    roots: list[Path] = []
    env_roots = os.environ.get("ROOMPILOT_EXTERNAL_GLB_ZIP_DIRS", "")
    for raw_root in env_roots.split(os.pathsep):
        raw_root = raw_root.strip()
        if raw_root:
            roots.append(Path(raw_root))
    roots.extend(_EXTERNAL_GLB_ZIP_SEARCH_DIRS)

    found: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        candidates: list[Path] = []
        if root.is_file() and root.suffix.lower() == ".zip":
            candidates = [root]
        elif root.is_dir():
            for pattern in _EXTERNAL_GLB_ZIP_PATTERNS:
                candidates.extend(root.glob(pattern))

        for candidate in candidates:
            key = str(candidate.resolve()).casefold()
            if key in seen or not candidate.is_file():
                continue
            seen.add(key)
            found.append(candidate)
    return found


@lru_cache(maxsize=1)
def _external_zip_entry_lookup() -> dict[str, tuple[Path, str]]:
    lookup: dict[str, tuple[Path, str]] = {}
    conflicts: set[str] = set()

    def remember(key: str, archive_path: Path, entry_name: str) -> None:
        existing = lookup.get(key)
        if existing is not None and existing[1] != entry_name:
            conflicts.add(key)
            return
        lookup[key] = (archive_path, entry_name)

    for archive_path in _iter_external_zip_paths():
        try:
            with zipfile.ZipFile(archive_path) as archive:
                for entry_name in archive.namelist():
                    if not entry_name.lower().endswith(".glb"):
                        continue
                    for key in _glb_lookup_keys(entry_name):
                        remember(key, archive_path, entry_name)
        except (OSError, zipfile.BadZipFile):
            continue

    for key in conflicts:
        lookup.pop(key, None)
    return lookup


def _external_zip_entry_variants(entry_name: object) -> list[str]:
    entry = _normalize_posix_path(str(entry_name or "").strip())
    if not entry:
        return []

    variants = [entry]
    if entry.startswith("downloaded-files/ABO/"):
        variants.append(entry.replace("downloaded-files/ABO/", "downloaded-files(furniture)/ABO/", 1))
    if entry.startswith("downloaded-files/"):
        variants.append(entry.replace("downloaded-files/", "downloaded-files(furniture)/", 1))
        variants.append(entry.replace("downloaded-files/", "downloaded-files(home apppliances)/", 1))
    if entry.startswith("ABO/"):
        variants.append(f"downloaded-files(furniture)/{entry}")
    variants.append(f"downloaded-files(furniture)/{entry}")
    variants.append(f"downloaded-files(home apppliances)/{entry}")
    return list(dict.fromkeys(variants))


def _resolve_external_zip_entry(furniture: dict) -> tuple[Path, str] | None:
    entry_name = furniture.get("zip_entry")
    if not entry_name:
        return None

    direct_archive = Path(str(furniture.get("source_archive_path") or ""))
    direct_candidates = [direct_archive]
    if not direct_archive.is_absolute():
        direct_candidates.extend(
            [
                PROJECT_DIR / direct_archive,
                DATASET_DIR / direct_archive,
                Path.home() / "Downloads" / direct_archive.name,
            ]
        )

    for archive_path in direct_candidates:
        if not (archive_path.is_file() and archive_path.suffix.lower() == ".zip"):
            continue
        try:
            with zipfile.ZipFile(archive_path) as archive:
                names = set(archive.namelist())
                for variant in _external_zip_entry_variants(entry_name):
                    if variant in names:
                        return archive_path, variant
        except (OSError, zipfile.BadZipFile):
            continue

    lookup = _external_zip_entry_lookup()
    for variant in _external_zip_entry_variants(entry_name):
        for key in _glb_lookup_keys(variant):
            resolved = lookup.get(key)
            if resolved is not None and resolved[0].exists():
                return resolved
    return None


def _resolve_glb_path(furniture: dict) -> Path | None:
    """依序嘗試:metadata 的絕對路徑 → 專案 data/dataset/ 下的相對路徑。"""
    absolute_text = furniture.get("glb_absolute_path")
    if absolute_text and Path(absolute_text).exists():
        return Path(absolute_text)

    relative_text = furniture.get("glb_relative_path")
    if relative_text:
        relative = _normalize_posix_path(relative_text)
        for root in _DATASET_GLB_ROOTS:
            candidate = root / relative
            if candidate.exists():
                return candidate
        lookup = _dataset_glb_lookup()
        for key in _glb_lookup_keys(relative):
            candidate = lookup.get(key)
            if candidate is not None and candidate.exists():
                return candidate

    return None


def _model_status(furniture: dict) -> tuple[bool, str]:
    if furniture.get("zip_entry"):
        if _resolve_external_zip_entry(furniture) is not None:
            return True, "外部 GLB zip 可用"
        return False, "外部家具有 zip_entry，但目前找不到對應 GLB zip 或 zip 內 entry。"

    if not furniture.get("glb_absolute_path") and not furniture.get("glb_relative_path"):
        return False, "這件家具沒有設定 GLB 路徑。"

    if _resolve_glb_path(furniture) is not None:
        return True, "GLB 可用"

    if _remote_glb_url(furniture):
        return False, "遠端 GLB 尚未驗證，暫不提供載入。"

    return False, "資料有記錄，但 data/dataset/ 中找不到對應的 GLB 檔案(請先從雲端下載 dataset)。"


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


def _external_glb_bytes(furniture: dict) -> bytes:
    resolved = _resolve_external_zip_entry(furniture)
    if resolved is None:
        raise HTTPException(status_code=404, detail="外部匯入模型來源不存在。")
    archive_path, entry_name = resolved
    try:
        with zipfile.ZipFile(archive_path) as archive:
            return archive.read(entry_name)
    except KeyError:
        raise HTTPException(status_code=404, detail="外部匯入模型在 zip 中不存在。")
    except zipfile.BadZipFile:
        raise HTTPException(status_code=422, detail="外部匯入 zip 無法讀取。")


def _remote_glb_response(url: str) -> Response:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "RoomPilot/1.0",
            "Accept": "model/gltf-binary,application/octet-stream,*/*",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = response.read()
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise HTTPException(status_code=502, detail=f"遠端 GLB 讀取失敗：{exc}") from exc

    if payload[:4] != b"glTF":
        raise HTTPException(status_code=502, detail="遠端模型不是可用的 GLB 檔案。")

    return Response(content=payload, media_type="model/gltf-binary")


def _model_response_for_merged_furniture(furniture: dict):
    if furniture.get("zip_entry"):
        payload = _external_glb_bytes(furniture)
        if payload[:4] == b"glTF":
            return Response(content=payload, media_type="model/gltf-binary")

    model_path_text = _get_model_path_for_furniture(furniture)
    try:
        _parse_glb(model_path_text)
        model_path = Path(model_path_text)
        return FileResponse(model_path, media_type="model/gltf-binary", filename=model_path.name)
    except (HTTPException, ValueError, OSError, json.JSONDecodeError):
        remote_url = _remote_glb_url(furniture)
        if remote_url:
            return _remote_glb_response(remote_url)
        raise HTTPException(status_code=404, detail="找不到可載入的 GLB 模型。")


def _get_model_path_for_furniture(furniture: dict) -> str:
    model_path = _resolve_glb_path(furniture)
    if model_path is None:
        raise HTTPException(status_code=404, detail="找不到這件家具對應的 GLB 檔案(data/dataset/ 未就緒?)。")

    return str(model_path)


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

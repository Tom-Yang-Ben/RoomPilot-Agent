"""驗證 IKEA 離線備援 zip 是否完整覆蓋隔離家具清單。"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import unicodedata
import zipfile
from collections import defaultdict
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CATALOG = (
    ROOT
    / "backend"
    / "catalog"
    / "data"
    / "furniture_catalog_6styles_zh.json"
)
EXPECTED_SHA256 = "5afb7b192bdcfe3bb4b303fa554aab30db01023318cb24661c22a78505e377a8"
EXPECTED_CATALOG_MODELS = 1508


def _normalized_basename(value: object) -> str:
    text = str(value or "").replace("\\", "/")
    basename = PurePosixPath(text).name
    return unicodedata.normalize("NFKC", basename).casefold()


def verify_backup(
    archive_path: Path,
    catalog_path: Path = DEFAULT_CATALOG,
    expected_sha256: str | None = EXPECTED_SHA256,
) -> dict[str, object]:
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    items = catalog.get("furniture") or catalog.get("items") or []

    catalog_by_basename: dict[str, list[dict]] = defaultdict(list)
    for item in items:
        relative_path = item.get("glb_relative_path")
        if relative_path:
            catalog_by_basename[_normalized_basename(relative_path)].append(item)

    with zipfile.ZipFile(archive_path) as archive:
        glb_entries = [
            name for name in archive.namelist() if name.casefold().endswith(".glb")
        ]

    matched_entries = 0
    matched_ids: set[str] = set()
    unmatched_entries: list[str] = []
    ambiguous: dict[str, list[str]] = {}
    for entry_name in glb_entries:
        candidates = catalog_by_basename.get(_normalized_basename(entry_name), [])
        if len(candidates) == 1:
            matched_entries += 1
            furniture_id = str(candidates[0].get("furniture_id") or "")
            if furniture_id:
                matched_ids.add(furniture_id)
        elif not candidates:
            unmatched_entries.append(entry_name)
        else:
            ambiguous[entry_name] = [
                str(candidate.get("furniture_id") or "") for candidate in candidates
            ]

    digest = hashlib.sha256()
    with archive_path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    sha256 = digest.hexdigest()

    return {
        "catalog_model_count": len(matched_ids),
        "matched_archive_entries": matched_entries,
        "unmatched_archive_entries": unmatched_entries,
        "ambiguous": ambiguous,
        "archive_glb_count": len(glb_entries),
        "sha256": sha256,
        "sha256_matches": expected_sha256 is None or sha256 == expected_sha256.casefold(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path, help="IKEA 離線備援 zip")
    parser.add_argument(
        "--catalog",
        type=Path,
        default=DEFAULT_CATALOG,
        help="RoomPilot 家具型錄 JSON",
    )
    args = parser.parse_args()

    try:
        result = verify_backup(args.archive, args.catalog)
    except (OSError, UnicodeError, json.JSONDecodeError, zipfile.BadZipFile) as exc:
        print(f"驗證失敗：{exc}", file=sys.stderr)
        return 2

    print(
        f"可用型錄家具：{result['catalog_model_count']}；"
        f"已對應 GLB：{result['matched_archive_entries']}；"
        f"zip 內 GLB：{result['archive_glb_count']}；"
        f"未入型錄 GLB：{len(result['unmatched_archive_entries'])}"
    )
    print(f"SHA-256：{result['sha256']}")
    if not result["sha256_matches"]:
        print("SHA-256 與已驗證備援包不符。", file=sys.stderr)
    if result["ambiguous"]:
        print(f"檔名歧義：{len(result['ambiguous'])}", file=sys.stderr)
    if result["catalog_model_count"] != EXPECTED_CATALOG_MODELS:
        print(
            f"可用型錄家具應為 {EXPECTED_CATALOG_MODELS} 件。",
            file=sys.stderr,
        )
    return (
        0
        if result["sha256_matches"]
        and not result["ambiguous"]
        and result["catalog_model_count"] == EXPECTED_CATALOG_MODELS
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())

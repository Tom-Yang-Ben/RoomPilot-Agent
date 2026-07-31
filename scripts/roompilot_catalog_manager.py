"""RoomPilot catalog manager：合併、驗證、檢查與清理 normalized catalog。

``merge`` 會把不同輸入結構轉成固定的 normalized JSON 與 JSONL；``validate``
檢查基本必填欄位；``check-glb`` 驗證本機模型路徑；``prune-missing`` 預設只預覽，
加入 ``--apply`` 後才會先備份並移除找不到 GLB 的項目。
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlparse


# 專案位置、公開 action 與報告檔排除規則。
SCRIPTS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPTS_DIR.parent

HELPERS = {
    "merge": "合併 JSON 為 catalog JSON 與 JSONL",
    "validate": "驗證 catalog JSON 的必要欄位",
    "check-glb": "檢查 glb_path 對應的本機檔案",
    "prune-missing": "預覽或移除找不到 GLB 的 items",
}

REPORT_NAME_PATTERNS = ("_report.json", "_validation.json")
# Downloader 與 catalog manager 共用的 normalized schema 與 item 欄位順序。
NORMALIZED_SCHEMA = "roompilot-rag normalized v1"
NORMALIZED_ITEM_FIELDS = (
    "id",
    "name_en",
    "name_zh",
    "category",
    "type",
    "role",
    "color",
    "material",
    "style_confidence",
    "style_source",
    "style_top",
    "width_cm",
    "depth_cm",
    "height_cm",
    "glb_path",
    "has_local_glb",
    "is_ikea",
    "source_group",
    "kind",
    "catalog",
    "source_dataset",
    "product_url",
)


class CatalogToolError(RuntimeError):
    """可預期的輸入或資料格式錯誤。"""


def json_files(input_path: Path, pattern: str = "*.json") -> list[Path]:
    """取得單一 JSON 或資料夾下符合 pattern 的 JSON，略過工具報告與備份。"""
    input_path = input_path.resolve()
    if input_path.is_file():
        return [input_path]
    if not input_path.is_dir():
        raise CatalogToolError(f"輸入路徑不存在：{input_path}")

    files = []
    for path in sorted(input_path.rglob(pattern)):
        lowered = path.name.casefold()
        relative_parts = {part.casefold() for part in path.relative_to(input_path).parts}
        if "backups" in relative_parts or any(lowered.endswith(value) for value in REPORT_NAME_PATTERNS):
            continue
        files.append(path)
    if not files:
        raise CatalogToolError(f"找不到符合 {pattern!r} 的 JSON：{input_path}")
    return files


def read_json(path: Path) -> Any:
    """以 UTF-8（可含 BOM）讀取 JSON，並把解析位置包成較清楚的工具錯誤。"""
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise CatalogToolError(f"JSON 格式錯誤：{path}（第 {exc.lineno} 行，第 {exc.colno} 欄）") from exc


def extract_items(payload: Any, path: Path) -> tuple[list[dict[str, Any]], str]:
    """支援 catalog 物件、物件陣列，以及單一 item 物件。"""
    if isinstance(payload, list):
        items = payload
        shape = "list"
    elif isinstance(payload, dict) and isinstance(payload.get("items"), list):
        items = payload["items"]
        shape = "catalog"
    elif isinstance(payload, dict) and any(key in payload for key in ("id", "sku", "glb_path")):
        items = [payload]
        shape = "item"
    else:
        raise CatalogToolError(f"不支援的 JSON 結構：{path}（需要 list、items list 或單一 item）")

    invalid_indexes = [index for index, item in enumerate(items) if not isinstance(item, dict)]
    if invalid_indexes:
        preview = ", ".join(str(value) for value in invalid_indexes[:5])
        raise CatalogToolError(f"items 內含非 object 資料：{path}（index: {preview}）")
    return items, shape


def write_json(path: Path, payload: Any) -> None:
    """先寫入同資料夾暫存檔，再原子取代目標 JSON，降低半寫入風險。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def record_identifier(item: dict[str, Any]) -> str:
    """依序以 sku、id、project_id 取得可用於查錯與去重的識別字串。"""
    return str(item.get("sku") or item.get("id") or item.get("project_id") or "").strip()


def common_value(values: list[Any], fallback: str) -> str:
    """只有一種非空 metadata 值時沿用；混合或缺少時使用 fallback。"""
    cleaned = {str(value).strip() for value in values if value not in (None, "")}
    return cleaned.pop() if len(cleaned) == 1 else fallback


def dimension_value(item: dict[str, Any], field: str) -> Any:
    """讀取 width_cm 等頂層欄位，缺少時相容舊版 size_cm 巢狀格式。"""
    value = item.get(field)
    if value not in (None, ""):
        return value
    size = item.get("size_cm")
    if isinstance(size, dict):
        return size.get(field.removesuffix("_cm"))
    return None


def normalize_item(
    item: dict[str, Any],
    source_catalog: str,
    source_group: str,
    kind: str,
    dataset_name: str,
) -> dict[str, Any]:
    """把任意支援的 item 映射成固定 22 欄，並補上來源、本機 GLB 與商品網址。"""
    identifier = str(item.get("id") or item.get("sku") or item.get("project_id") or "").strip()
    glb_path = str(item.get("glb_path") or "").strip().replace("\\", "/")
    local_path, path_error = safe_glb_path(PROJECT_ROOT, glb_path)
    explicit_local = item.get("has_local_glb")
    has_local_glb = (
        explicit_local
        if isinstance(explicit_local, bool)
        else not path_error and local_path is not None and local_path.is_file() and local_path.stat().st_size > 0
    )
    item_source_group = str(item.get("source_group") or source_group)
    explicit_ikea = item.get("is_ikea")
    confidence = item.get("style_confidence")
    if not isinstance(confidence, (int, float)):
        confidence = 0.0
    normalized = {
        "id": identifier,
        "name_en": str(item.get("name_en") or item.get("name") or ""),
        "name_zh": str(item.get("name_zh") or item.get("chinese_name") or ""),
        "category": str(item.get("category") or item.get("category_name_zh") or item.get("category_name_en") or ""),
        "type": str(item.get("type") or ""),
        "role": str(item.get("role") or ""),
        "color": str(item.get("color") or ""),
        "material": str(item.get("material") or ""),
        "style_confidence": confidence,
        "style_source": str(item.get("style_source") or ""),
        "style_top": str(item.get("style_top") or ""),
        "width_cm": dimension_value(item, "width_cm"),
        "depth_cm": dimension_value(item, "depth_cm"),
        "height_cm": dimension_value(item, "height_cm"),
        "glb_path": glb_path,
        "has_local_glb": has_local_glb,
        "is_ikea": explicit_ikea if isinstance(explicit_ikea, bool) else item_source_group.casefold() == "ikea",
        "source_group": item_source_group,
        "kind": str(item.get("kind") or kind),
        "catalog": str(item.get("catalog") or source_catalog),
        "source_dataset": str(item.get("source_dataset") or dataset_name),
        "product_url": str(item.get("product_url") or item.get("source_page") or "").strip(),
    }
    return {field: normalized[field] for field in NORMALIZED_ITEM_FIELDS}


def normalized_catalog(
    items: list[dict[str, Any]],
    source_catalog: str,
    source_group: str,
    kind: str,
    dataset_name: str,
) -> dict[str, Any]:
    """組成 normalized catalog 頂層結構並計算 count、空材質與空顏色數。"""
    return {
        "schema": NORMALIZED_SCHEMA,
        "source_catalog": source_catalog,
        "source_group": source_group,
        "kind": kind,
        "dataset_name": dataset_name,
        "count": len(items),
        "empty_material": sum(not str(item["material"]).strip() for item in items),
        "empty_color": sum(not str(item["color"]).strip() for item in items),
        "items": items,
    }


def refresh_catalog_counts(payload: dict[str, Any]) -> None:
    """在清理 items 後，就地更新 catalog 的三個統計欄位。"""
    items = payload.get("items")
    if not isinstance(items, list):
        return
    payload["count"] = len(items)
    payload["empty_material"] = sum(
        not str(item.get("material") or "").strip() for item in items if isinstance(item, dict)
    )
    payload["empty_color"] = sum(
        not str(item.get("color") or "").strip() for item in items if isinstance(item, dict)
    )


def merge_action(argv: list[str]) -> int:
    """合併來源 JSON，推斷 metadata，輸出 normalized JSON envelope 與 JSONL。"""
    parser = argparse.ArgumentParser(prog="roompilot_catalog_manager.py merge", description=HELPERS["merge"])
    parser.add_argument("--input", type=Path, required=True, help="來源 JSON 檔或資料夾。")
    parser.add_argument("--output", type=Path, required=True, help="輸出的 JSONL 路徑。")
    parser.add_argument("--json-output", type=Path, help="輸出的 JSON 路徑；預設由 --output 改副檔名。")
    parser.add_argument("--source-catalog", help="頂層 source_catalog；未指定時從輸入推斷。")
    parser.add_argument("--source-group", help="頂層 source_group；未指定時從輸入推斷。")
    parser.add_argument("--kind", help="頂層 kind；未指定時從輸入推斷。")
    parser.add_argument("--dataset-name", help="頂層 dataset_name；未指定時從輸入推斷。")
    parser.add_argument("--allow-duplicate-sku", action="store_true", help="允許重複的 sku/id。")
    args = parser.parse_args(argv)

    # 先蒐集所有來源列與 catalog metadata，稍後統一推斷頂層資訊。
    input_path = args.input.resolve()
    source_rows: list[dict[str, Any]] = []
    metadata: dict[str, list[Any]] = {
        "source_catalog": [],
        "source_group": [],
        "kind": [],
        "dataset_name": [],
    }
    seen: dict[str, Path] = {}
    for path in json_files(input_path):
        payload = read_json(path)
        if isinstance(payload, dict):
            for key in metadata:
                metadata[key].append(payload.get(key))
        items, _ = extract_items(payload, path)
        for item in items:
            row = dict(item)
            identifier = record_identifier(row)
            if identifier and identifier in seen and not args.allow_duplicate_sku:
                raise CatalogToolError(f"重複的 sku/id：{identifier}（{seen[identifier]}、{path}）")
            if identifier:
                seen[identifier] = path
            source_rows.append(row)

    # 命令列參數優先；其次沿用唯一來源值；混合資料則使用安全預設。
    default_catalog = input_path.stem if input_path.is_file() else "merged_catalog"
    source_catalog = args.source_catalog or common_value(
        metadata["source_catalog"] + [row.get("catalog") for row in source_rows],
        default_catalog,
    )
    source_group = args.source_group or common_value(
        metadata["source_group"] + [row.get("source_group") for row in source_rows],
        "mixed" if input_path.is_dir() else "non-IKEA",
    )
    kind = args.kind or common_value(
        metadata["kind"] + [row.get("kind") for row in source_rows],
        "mixed" if input_path.is_dir() else "furniture",
    )
    dataset_name = args.dataset_name or common_value(
        metadata["dataset_name"] + [row.get("source_dataset") for row in source_rows],
        source_catalog,
    )
    # 正規化會只保留固定欄位，避免不同來源的臨時欄位污染輸出 schema。
    rows = [
        normalize_item(row, source_catalog, source_group, kind, dataset_name)
        for row in source_rows
    ]
    catalog_payload = normalized_catalog(rows, source_catalog, source_group, kind, dataset_name)

    output = args.output.resolve()
    json_output = (args.json_output or args.output.with_suffix(".json")).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    write_json(json_output, catalog_payload)
    print(f"合併完成：{len(rows):,} 筆")
    print(f"JSONL：{output}")
    print(f"JSON： {json_output}")
    return 0


def item_validation_errors(item: dict[str, Any]) -> list[str]:
    """檢查識別碼、名稱、GLB 路徑，以及非空商品網址。"""
    errors: list[str] = []
    if not record_identifier(item):
        errors.append("缺少識別欄位 sku/id/project_id")
    if not any(str(item.get(key) or "").strip() for key in ("name", "name_en", "name_zh", "chinese_name")):
        errors.append("缺少名稱欄位")
    glb_path = str(item.get("glb_path") or "").strip()
    if not glb_path:
        errors.append("缺少 glb_path")
    elif Path(glb_path).suffix.casefold() != ".glb":
        errors.append("glb_path 不是 .glb")
    product_url = str(item.get("product_url") or item.get("source_page") or "").strip()
    if product_url:
        parsed = urlparse(product_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            errors.append("product_url 不是有效的 HTTP(S) 網址")
    return errors


def validate_action(argv: list[str]) -> int:
    """驗證一或多個 JSON，輸出彙總 JSON 與逐筆問題 CSV。"""
    parser = argparse.ArgumentParser(prog="roompilot_catalog_manager.py validate", description=HELPERS["validate"])
    parser.add_argument("--input", type=Path, required=True, help="要驗證的 JSON 檔或資料夾。")
    parser.add_argument("--report-dir", type=Path, required=True, help="驗證報告資料夾。")
    parser.add_argument("--pattern", default="*.json", help="資料夾搜尋樣式；預設 *.json。")
    args = parser.parse_args(argv)

    issues: list[dict[str, Any]] = []
    total = 0
    file_summaries = []
    for path in json_files(args.input, args.pattern):
        items, _ = extract_items(read_json(path), path)
        file_issue_count = 0
        for index, item in enumerate(items):
            total += 1
            errors = item_validation_errors(item)
            if errors:
                file_issue_count += 1
                issues.append({"file": str(path), "index": index, "identifier": record_identifier(item), "errors": errors})
        file_summaries.append({"file": str(path), "items": len(items), "invalid_items": file_issue_count})

    report_dir = args.report_dir.resolve()
    report_dir.mkdir(parents=True, exist_ok=True)
    report = {"total_items": total, "valid_items": total - len(issues), "invalid_items": len(issues), "files": file_summaries, "issues": issues}
    json_report = report_dir / "json_validation_report.json"
    csv_report = report_dir / "json_validation_issues.csv"
    write_json(json_report, report)
    with csv_report.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["file", "index", "identifier", "errors"])
        writer.writeheader()
        for issue in issues:
            writer.writerow({**issue, "errors": "；".join(issue["errors"])})
    print(f"驗證完成：{total:,} 筆，問題 {len(issues):,} 筆")
    print(f"報告：{json_report}")
    return 1 if issues else 0


def safe_glb_path(project_root: Path, value: Any) -> tuple[Path | None, str]:
    """驗證 glb_path 為安全相對路徑與 .glb 副檔名，並解析成本機路徑。"""
    text = str(value or "").strip().replace("\\", "/")
    if not text:
        return None, "missing_path"
    pure = PurePosixPath(text)
    if pure.is_absolute() or ".." in pure.parts or re.match(r"^[A-Za-z]:/", text):
        return None, "unsafe_path"
    if pure.suffix.casefold() != ".glb":
        return None, "invalid_extension"
    return project_root.joinpath(*pure.parts), ""


def glb_scan(input_path: Path, project_root: Path, pattern: str) -> tuple[list[dict[str, Any]], dict[Path, list[int]]]:
    """掃描 catalog 中的 GLB，回傳逐筆狀態與各檔案缺檔 item index。"""
    results: list[dict[str, Any]] = []
    missing_indexes: dict[Path, list[int]] = {}
    for path in json_files(input_path, pattern):
        items, _ = extract_items(read_json(path), path)
        for index, item in enumerate(items):
            local_path, error = safe_glb_path(project_root, item.get("glb_path"))
            if error:
                status = error
            elif not local_path.is_file():
                status = "missing_file"
            elif local_path.stat().st_size == 0:
                status = "empty_file"
            else:
                status = "ready"
            results.append({"file": str(path), "index": index, "identifier": record_identifier(item), "glb_path": item.get("glb_path", ""), "status": status})
            if status == "missing_file":
                missing_indexes.setdefault(path, []).append(index)
    return results, missing_indexes


def check_glb_action(argv: list[str]) -> int:
    """執行唯讀 GLB 一致性檢查，將非 ready 項目寫入 JSON 報告。"""
    parser = argparse.ArgumentParser(prog="roompilot_catalog_manager.py check-glb", description=HELPERS["check-glb"])
    parser.add_argument("--input", type=Path, default=PROJECT_ROOT / "JSON", help="JSON 檔或資料夾；預設 JSON。")
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT, help="glb_path 的基準資料夾。")
    parser.add_argument("--pattern", default="*.normalized.json", help="資料夾搜尋樣式。")
    parser.add_argument("--report", type=Path, default=PROJECT_ROOT / "JSON/reports/json_glb_consistency_report.json")
    args = parser.parse_args(argv)

    results, _ = glb_scan(args.input.resolve(), args.project_root.resolve(), args.pattern)
    counts: dict[str, int] = {}
    for row in results:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    report = {"project_root": str(args.project_root.resolve()), "input": str(args.input.resolve()), "total_items": len(results), "status_counts": counts, "issues": [row for row in results if row["status"] != "ready"]}
    write_json(args.report.resolve(), report)
    issue_count = len(report["issues"])
    print(f"GLB 檢查完成：{len(results):,} 筆，問題 {issue_count:,} 筆")
    print(f"報告：{args.report.resolve()}")
    return 1 if issue_count else 0


def relative_backup_path(path: Path, input_path: Path) -> Path:
    """計算檔案在備份資料夾內應保留的相對位置。"""
    if input_path.is_dir():
        return path.relative_to(input_path)
    return Path(path.name)


def prune_missing_action(argv: list[str]) -> int:
    """預覽缺檔項目；加 --apply 時先備份，再同步修改 JSON 與 JSONL。"""
    parser = argparse.ArgumentParser(prog="roompilot_catalog_manager.py prune-missing", description=HELPERS["prune-missing"])
    parser.add_argument("--input", type=Path, default=PROJECT_ROOT / "JSON", help="JSON 檔或資料夾；預設 JSON。")
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT, help="glb_path 的基準資料夾。")
    parser.add_argument("--pattern", default="*.normalized.json", help="資料夾搜尋樣式。")
    parser.add_argument("--backup-dir", type=Path, help="備份資料夾；未指定時自動建立時間戳目錄。")
    parser.add_argument("--report", type=Path, default=PROJECT_ROOT / "JSON/reports/prune_missing_report.json")
    parser.add_argument("--apply", action="store_true", help="實際備份並修改檔案；未加時只預覽。")
    args = parser.parse_args(argv)

    input_path = args.input.resolve()
    _, missing_indexes = glb_scan(input_path, args.project_root.resolve(), args.pattern)
    removal_count = sum(len(indexes) for indexes in missing_indexes.values())
    changed_files: list[dict[str, Any]] = []
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = (args.backup_dir or PROJECT_ROOT / "JSON/backups" / f"prune_missing_{timestamp}").resolve()

    # 預設不修改；只有明確指定 --apply 才建立備份並覆寫來源。
    if args.apply:
        for path, indexes in missing_indexes.items():
            payload = read_json(path)
            items, shape = extract_items(payload, path)
            remove = set(indexes)
            kept = [item for index, item in enumerate(items) if index not in remove]
            backup_path = backup_dir / relative_backup_path(path, input_path)
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, backup_path)
            if shape == "catalog":
                payload["items"] = kept
                refresh_catalog_counts(payload)
                output_payload = payload
            elif shape == "list":
                output_payload = kept
            else:
                output_payload = []
            write_json(path, output_payload)

            jsonl_path = path.with_suffix(".jsonl")
            if jsonl_path.is_file():
                jsonl_backup = backup_dir / relative_backup_path(jsonl_path, input_path)
                jsonl_backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(jsonl_path, jsonl_backup)
                jsonl_path.write_text("".join(json.dumps(item, ensure_ascii=False) + "\n" for item in kept), encoding="utf-8")
            changed_files.append({"file": str(path), "removed": len(indexes), "remaining": len(kept), "backup": str(backup_path)})

    report = {"mode": "apply" if args.apply else "preview", "input": str(input_path), "missing_items": removal_count, "affected_files": len(missing_indexes), "backup_dir": str(backup_dir) if args.apply else None, "files": changed_files or [{"file": str(path), "would_remove": len(indexes)} for path, indexes in missing_indexes.items()]}
    write_json(args.report.resolve(), report)
    verb = "已移除" if args.apply else "預計移除"
    print(f"{verb}：{removal_count:,} 筆，影響 {len(missing_indexes):,} 個 JSON")
    if not args.apply:
        print("目前是預覽模式；確認報告後加上 --apply 才會修改。")
    else:
        print(f"備份：{backup_dir}")
    print(f"報告：{args.report.resolve()}")
    return 0


ACTION_RUNNERS = {
    "merge": merge_action,
    "validate": validate_action,
    "check-glb": check_glb_action,
    "prune-missing": prune_missing_action,
}


def prompt_choice(title: str, choices: list[tuple[str, str]]) -> str:
    """顯示編號選單，反覆詢問直到使用者選到有效項目。"""
    print(f"\n{title}")
    for index, (_, label) in enumerate(choices, start=1):
        print(f"{index}. {label}")
    while True:
        value = input("Select: ").strip()
        if value.isdigit() and 1 <= int(value) <= len(choices):
            return choices[int(value) - 1][0]
        print("Invalid selection.")


def prompt_text(label: str, default: str | None = None) -> str:
    """讀取一段文字輸入；若使用者直接按 Enter，就回傳預設值。"""
    suffix = f" [{default}]" if default not in (None, "") else ""
    value = input(f"{label}{suffix}: ").strip()
    return value if value else (default or "")


def prompt_yes_no(label: str, default: bool = False) -> bool:
    """讀取 yes/no 問題，支援預設值，用於互動式布林選項。"""
    default_text = "Y/n" if default else "y/N"
    value = input(f"{label} ({default_text}): ").strip().casefold()
    if not value:
        return default
    return value in {"y", "yes", "true", "1"}


def run_helper(action: str, args: list[str]) -> int:
    """執行內建的 JSON/catalog action。"""
    return ACTION_RUNNERS[action](args)


def interactive_merge() -> int:
    """互動式收集合併 catalog 所需的輸入資料夾與輸出檔案路徑。"""
    args = [
        "--input",
        prompt_text("Input JSON folder", "data/raw_json"),
        "--output",
        prompt_text("Output JSONL", "data/processed/furniture_catalog.jsonl"),
    ]
    json_output = prompt_text("Output JSON, blank to derive from JSONL")
    if json_output:
        args.extend(["--json-output", json_output])
    if prompt_yes_no("Allow duplicate SKU", False):
        args.append("--allow-duplicate-sku")
    return run_helper("merge", args)


def interactive_validate() -> int:
    """互動式收集 JSON 驗證所需的輸入資料夾與報告輸出資料夾。"""
    args = [
        "--input",
        prompt_text("Input JSON folder", "data/raw_json"),
        "--report-dir",
        prompt_text("Report folder", "data/reports"),
    ]
    return run_helper("validate", args)


def interactive_main() -> int:
    """JSON/catalog 主選單；讓使用者選擇合併、驗證、檢查或清理功能。"""
    action = prompt_choice(
        "JSON/catalog tool",
        [
            ("merge", "Merge metadata JSON into furniture catalog"),
            ("validate", "Validate metadata JSON"),
            ("check-glb", "Check JSON/GLB file consistency"),
            ("prune-missing", "Remove JSON objects whose GLB files are missing"),
            ("exit", "Exit"),
        ],
    )
    if action == "merge":
        return interactive_merge()
    if action == "validate":
        return interactive_validate()
    if action == "prune-missing":
        print("預設只產生預覽報告；選擇實際套用時會先建立備份。")
        if prompt_yes_no("Apply changes", False):
            return run_helper(action, ["--apply"])
    if action == "exit":
        return 0
    return run_helper(action, [])


def parse_args() -> argparse.Namespace:
    """解析 `roompilot_catalog_manager.py` 的頂層命令列參數。"""
    parser = argparse.ArgumentParser(description="RoomPilot JSON/catalog maintenance tool.")
    parser.add_argument(
        "action",
        nargs="?",
        choices=sorted(HELPERS),
        help="Omit to use the interactive menu.",
    )
    parser.add_argument("args", nargs=argparse.REMAINDER, help="Arguments passed to the selected tool.")
    parser.add_argument("--list", action="store_true", help="List JSON/catalog actions and exit.")
    return parser.parse_args()


def print_actions() -> None:
    """列印目前公開的 JSON/catalog 維護功能清單。"""
    print("可用的 JSON/catalog 功能：")
    for action, description in HELPERS.items():
        print(f"- {action}: {description}")


def main() -> int:
    """程式進入點；處理 --list、直接 action，或啟動互動式選單。"""
    try:
        args = parse_args()
        if args.list:
            print_actions()
            return 0
        if args.action:
            forwarded = args.args[1:] if args.args and args.args[0] == "--" else args.args
            return run_helper(args.action, forwarded)
        print_actions()
        return interactive_main()
    except CatalogToolError as exc:
        print(f"[錯誤] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())

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


SCRIPTS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPTS_DIR.parent

HELPERS = {
    "merge": "合併 JSON 為 catalog JSON 與 JSONL",
    "validate": "驗證 catalog JSON 的必要欄位",
    "check-glb": "檢查 glb_path 對應的本機檔案",
    "prune-missing": "預覽或移除找不到 GLB 的 items",
}

REPORT_NAME_PATTERNS = ("_report.json", "_validation.json")


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
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def record_identifier(item: dict[str, Any]) -> str:
    return str(item.get("sku") or item.get("id") or item.get("project_id") or "").strip()


def merge_action(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="json_catalog_tool.py merge", description=HELPERS["merge"])
    parser.add_argument("--input", type=Path, required=True, help="來源 JSON 檔或資料夾。")
    parser.add_argument("--output", type=Path, required=True, help="輸出的 JSONL 路徑。")
    parser.add_argument("--json-output", type=Path, help="輸出的 JSON 路徑；預設由 --output 改副檔名。")
    parser.add_argument("--allow-duplicate-sku", action="store_true", help="允許重複的 sku/id。")
    args = parser.parse_args(argv)

    input_path = args.input.resolve()
    rows: list[dict[str, Any]] = []
    seen: dict[str, Path] = {}
    for path in json_files(input_path):
        items, _ = extract_items(read_json(path), path)
        for item in items:
            row = dict(item)
            if not row.get("source_json"):
                try:
                    row["source_json"] = path.relative_to(input_path).as_posix() if input_path.is_dir() else path.name
                except ValueError:
                    row["source_json"] = str(path)
            identifier = record_identifier(row)
            if identifier and identifier in seen and not args.allow_duplicate_sku:
                raise CatalogToolError(f"重複的 sku/id：{identifier}（{seen[identifier]}、{path}）")
            if identifier:
                seen[identifier] = path
            rows.append(row)

    output = args.output.resolve()
    json_output = (args.json_output or args.output.with_suffix(".json")).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    write_json(json_output, rows)
    print(f"合併完成：{len(rows):,} 筆")
    print(f"JSONL：{output}")
    print(f"JSON： {json_output}")
    return 0


def item_validation_errors(item: dict[str, Any]) -> list[str]:
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
    return errors


def validate_action(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="json_catalog_tool.py validate", description=HELPERS["validate"])
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
    parser = argparse.ArgumentParser(prog="json_catalog_tool.py check-glb", description=HELPERS["check-glb"])
    parser.add_argument("--input", type=Path, default=PROJECT_ROOT / "JSON", help="JSON 檔或資料夾；預設 JSON。")
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT, help="glb_path 的基準資料夾。")
    parser.add_argument("--pattern", default="*.normalized.json", help="資料夾搜尋樣式。")
    parser.add_argument("--report", type=Path, default=PROJECT_ROOT / "dataset/catalog_json/reports/json_glb_consistency_report.json")
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
    if input_path.is_dir():
        return path.relative_to(input_path)
    return Path(path.name)


def prune_missing_action(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="json_catalog_tool.py prune-missing", description=HELPERS["prune-missing"])
    parser.add_argument("--input", type=Path, default=PROJECT_ROOT / "JSON", help="JSON 檔或資料夾；預設 JSON。")
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT, help="glb_path 的基準資料夾。")
    parser.add_argument("--pattern", default="*.normalized.json", help="資料夾搜尋樣式。")
    parser.add_argument("--backup-dir", type=Path, help="備份資料夾；未指定時自動建立時間戳目錄。")
    parser.add_argument("--report", type=Path, default=PROJECT_ROOT / "dataset/catalog_json/reports/prune_missing_report.json")
    parser.add_argument("--apply", action="store_true", help="實際備份並修改檔案；未加時只預覽。")
    args = parser.parse_args(argv)

    input_path = args.input.resolve()
    _, missing_indexes = glb_scan(input_path, args.project_root.resolve(), args.pattern)
    removal_count = sum(len(indexes) for indexes in missing_indexes.values())
    changed_files: list[dict[str, Any]] = []
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = (args.backup_dir or PROJECT_ROOT / "dataset/catalog_json/backups" / f"prune_missing_{timestamp}").resolve()

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
                if "count" in payload:
                    payload["count"] = len(kept)
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
    """解析 `json_catalog_tool.py` 的頂層命令列參數。"""
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

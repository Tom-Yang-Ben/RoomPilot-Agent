from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parent
HELPER_DIR = SCRIPTS_DIR / "_tool_helpers"

HELPERS = {
    "merge": "merge_json_to_catalog.py",
    "validate": "validate_json.py",
    "check-glb": "check_json_glb_consistency.py",
    "prune-missing": "prune_json_to_existing_glbs.py",
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
    """載入 `_tool_helpers` 裡的 JSON/catalog 實作腳本並執行它的 main。"""
    path = HELPER_DIR / HELPERS[action]
    if not path.exists():
        raise FileNotFoundError(f"Missing helper: {path}")
    if str(HELPER_DIR) not in sys.path:
        sys.path.insert(0, str(HELPER_DIR))

    spec = importlib.util.spec_from_file_location(f"roompilot_json_{path.stem}", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load helper: {path}")

    module = importlib.util.module_from_spec(spec)
    old_argv = sys.argv[:]
    try:
        sys.argv = [str(path), *args]
        spec.loader.exec_module(module)
        result = module.main()
    finally:
        sys.argv = old_argv
    return result if isinstance(result, int) else 0


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
        print("This edits JSON files after creating backups.")
        if not prompt_yes_no("Continue", False):
            return 0
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
    print("Available JSON/catalog actions:")
    print("- merge: Merge metadata JSON into furniture_catalog.jsonl and .json")
    print("- validate: Validate required metadata JSON fields")
    print("- check-glb: Check JSON glb_path references against existing GLB files")
    print("- prune-missing: Back up JSON, then remove objects whose GLB files are missing")


def main() -> int:
    """程式進入點；處理 --list、直接 action，或啟動互動式選單。"""
    args = parse_args()
    if args.list:
        print_actions()
        return 0
    if args.action:
        forwarded = args.args[1:] if args.args and args.args[0] == "--" else args.args
        return run_helper(args.action, forwarded)
    print_actions()
    return interactive_main()


if __name__ == "__main__":
    sys.exit(main())

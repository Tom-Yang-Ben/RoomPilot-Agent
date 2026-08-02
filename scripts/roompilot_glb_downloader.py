"""RoomPilot GLB downloader：下載 IKEA／ABO 模型並輸出 normalized catalog。

檔案前半部保留舊版互動式 helper 介面；目前直接執行本檔時，實際入口是
``download_main``。下載器可接受直接 URL、URL 文字檔、JSON/JSONL manifest，
以及 IKEA 商品頁，成功下載後會驗證 GLB magic header，再輸出 normalized JSON、
JSONL 與獨立的下載報告。
"""

from __future__ import annotations

import argparse
import html
import importlib.util
import json
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


# 舊版互動式入口所使用的 helper 路徑與對應檔名。
SCRIPTS_DIR = Path(__file__).resolve().parent
HELPER_DIR = SCRIPTS_DIR / "_tool_helpers"
REGIONAL_HELPER_DIR = HELPER_DIR / "_merged_helpers"

HELPERS = {
    "ikea": "ikea_category_glb_downloader.py",
    "abo-furniture": "abo_needed_glb_downloader.py",
    "abo-home": "abo_home_appliances_accessories_downloader.py",
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
    """載入 `_tool_helpers` 裡的實作腳本，暫時轉發 argv 後執行它的 main。"""
    path = HELPER_DIR / HELPERS[action]
    if not path.exists():
        raise FileNotFoundError(f"Missing helper: {path}")

    for import_dir in (str(HELPER_DIR), str(REGIONAL_HELPER_DIR), str(SCRIPTS_DIR)):
        if import_dir not in sys.path:
            sys.path.insert(0, import_dir)

    spec = importlib.util.spec_from_file_location(f"roompilot_{path.stem}", path)
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


def interactive_ikea_args() -> list[str]:
    """互動式收集 IKEA 下載參數，支援家電家飾、一般分類、單品 URL。"""
    mode = prompt_choice(
        "IKEA download mode",
        [
            ("home", "Taiwan/Japan/Finland home appliances and accessories"),
            ("category", "General IKEA category download"),
            ("product", "Direct IKEA product URL download"),
        ],
    )
    site = prompt_text("IKEA site", "tw" if mode == "home" else "fi")
    output_root = prompt_text("Output root", "downloaded-files")
    timeout = prompt_text("Category timeout seconds", "600")
    args = ["--site", site, "--output-root", output_root, "--category-timeout-seconds", timeout]

    if mode == "home":
        group = prompt_choice(
            "Home batch group",
            [
                ("all", "All home appliances and accessories"),
                ("home-appliances", "Home appliances only"),
                ("home-accessories", "Home accessories only"),
            ],
        )
        args.extend(["--home-needed-batch", "--home-group", group])
        target_count = prompt_text("Target count per category, blank for all")
        if target_count:
            args.extend(["--target-count", target_count])
        only_category = prompt_text("Only category slug, blank for all")
        if only_category:
            args.extend(["--only-category", only_category])
        start_category = prompt_text("Start category slug, blank for beginning")
        if start_category:
            args.extend(["--start-category", start_category])
    elif mode == "category":
        category = prompt_text("IKEA category key or full URL")
        if not category:
            raise ValueError("Category is required.")
        args.extend(["--category", category])
        if prompt_yes_no("Download all products in category", False):
            args.append("--all")
        else:
            args.extend(["--target-count", prompt_text("Target count", "1")])
    else:
        product_url = prompt_text("Product URL")
        if not product_url:
            raise ValueError("Product URL is required.")
        product_category = prompt_text("Product category folder", "manual-products")
        args.extend(["--product-url", product_url, "--product-category", product_category])
    return args


def abo_help() -> None:
    """列印 ABO 下載器的簡化命令列用法與可用模式。"""
    print("usage: roompilot_glb_downloader.py abo -- [--mode all|furniture|home] [options]")
    print()
    print("ABO download modes:")
    print("  all        Download furniture, then home appliances/accessories. This is the default.")
    print("  furniture  Download main ABO furniture categories.")
    print("  home       Download ABO home appliances/accessories.")
    print()
    print("Options:")
    print("  --output-root PATH")
    print("  --raw-json-root PATH")
    print("  --cache-dir PATH")
    print("  --category-timeout-seconds N")
    print("  --workers N")
    print("  --skip-cache-download")
    print("  --dry-run")


def parse_abo_args(args: list[str]) -> argparse.Namespace:
    """解析 ABO 下載參數，讓命令列可選 all、furniture、home 三種模式。"""
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--help", action="store_true")
    parser.add_argument("--mode", choices=["all", "furniture", "home"], default="all")
    parser.add_argument("--output-root")
    parser.add_argument("--raw-json-root")
    parser.add_argument("--cache-dir")
    parser.add_argument("--category-timeout-seconds")
    parser.add_argument("--workers")
    parser.add_argument("--skip-cache-download", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parsed, unknown = parser.parse_known_args(args)
    parsed.unknown = unknown
    return parsed


def build_abo_furniture_args(args: argparse.Namespace) -> list[str]:
    """把共用 ABO 參數轉成 ABO 家具下載 helper 可接受的 argv。"""
    forwarded: list[str] = []
    for source, target in (
        ("output_root", "--output-root"),
        ("raw_json_root", "--raw-json-root"),
        ("category_timeout_seconds", "--category-timeout-seconds"),
        ("workers", "--workers"),
    ):
        value = getattr(args, source)
        if value:
            forwarded.extend([target, value])
    if args.skip_cache_download:
        forwarded.append("--skip-cache-download")
    if args.dry_run:
        forwarded.append("--dry-run")
    return forwarded


def build_abo_home_args(args: argparse.Namespace) -> list[str]:
    """把共用 ABO 參數轉成 ABO 家電/家飾下載 helper 可接受的 argv。"""
    forwarded: list[str] = []
    for source, target in (
        ("output_root", "--output-root"),
        ("cache_dir", "--cache-dir"),
        ("category_timeout_seconds", "--category-timeout-seconds"),
        ("workers", "--workers"),
    ):
        value = getattr(args, source)
        if value:
            forwarded.extend([target, value])
    forwarded.extend(["--group", "all"])
    if args.skip_cache_download:
        forwarded.append("--skip-cache-download")
    if args.dry_run:
        forwarded.append("--dry-run")
    return forwarded


def run_abo(args: list[str]) -> int:
    """依照 ABO 模式執行家具、家電/家飾，或兩者依序執行。"""
    parsed = parse_abo_args(args)
    if parsed.help:
        abo_help()
        return 0
    if parsed.unknown:
        raise ValueError(f"Unknown ABO arguments: {' '.join(parsed.unknown)}")

    if parsed.mode == "furniture":
        return run_helper("abo-furniture", build_abo_furniture_args(parsed))
    if parsed.mode == "home":
        return run_helper("abo-home", build_abo_home_args(parsed))

    furniture_code = run_helper("abo-furniture", build_abo_furniture_args(parsed))
    if furniture_code:
        return furniture_code
    return run_helper("abo-home", build_abo_home_args(parsed))


def interactive_abo_args() -> list[str]:
    """互動式收集 ABO 下載共用設定，例如輸出路徑、快取、timeout、worker。"""
    output_root = prompt_text("Output root", "downloaded-files/ABO")
    args = [
        "--output-root",
        output_root,
        "--raw-json-root",
        prompt_text("Raw JSON root", "data/raw_json/ABO"),
        "--cache-dir",
        prompt_text("Cache dir", f"{output_root}/_cache"),
        "--category-timeout-seconds",
        prompt_text("Category timeout seconds", "180"),
        "--workers",
        prompt_text("Workers", "6"),
    ]
    if prompt_yes_no("Skip cache download", False):
        args.append("--skip-cache-download")
    if prompt_yes_no("Dry run", False):
        args.append("--dry-run")
    return args


def interactive_abo() -> int:
    """互動式選擇 ABO 下載模式，並呼叫對應 helper 執行下載。"""
    mode = prompt_choice(
        "ABO download mode",
        [
            ("all", "All ABO furniture and home appliances/accessories"),
            ("furniture", "ABO furniture only"),
            ("home", "ABO home appliances/accessories only"),
        ],
    )
    args = interactive_abo_args()
    parsed = parse_abo_args(args)
    parsed.mode = mode
    if parsed.mode == "furniture":
        return run_helper("abo-furniture", build_abo_furniture_args(parsed))
    if parsed.mode == "home":
        return run_helper("abo-home", build_abo_home_args(parsed))
    furniture_code = run_helper("abo-furniture", build_abo_furniture_args(parsed))
    if furniture_code:
        return furniture_code
    return run_helper("abo-home", build_abo_home_args(parsed))


def interactive_main() -> int:
    """家具下載主選單；讓使用者選擇 IKEA 或 ABO 下載器。"""
    action = prompt_choice(
        "Furniture downloader",
        [
            ("ikea", "IKEA downloader"),
            ("abo", "ABO downloader"),
            ("exit", "Exit"),
        ],
    )
    if action == "ikea":
        return run_helper("ikea", interactive_ikea_args())
    if action == "abo":
        return interactive_abo()
    return 0


def parse_args() -> argparse.Namespace:
    """解析 `roompilot_glb_downloader.py` 的舊版頂層命令列參數。"""
    parser = argparse.ArgumentParser(description="RoomPilot furniture GLB downloader.")
    parser.add_argument("action", nargs="?", choices=["ikea", "abo"], help="Omit to use the interactive menu.")
    parser.add_argument("args", nargs=argparse.REMAINDER, help="Arguments passed to the selected downloader.")
    parser.add_argument("--list", action="store_true", help="List download actions and exit.")
    return parser.parse_args()


def print_actions() -> None:
    """列印目前公開的家具下載功能清單。"""
    print("Available download actions:")
    print("- ikea: IKEA downloader, including TW/JP/FI home appliances/accessories")
    print("- abo: ABO downloader, including furniture and home appliances/accessories")


def main() -> int:
    """程式進入點；處理 --list、直接 action，或啟動互動式選單。"""
    args = parse_args()
    if args.list:
        print_actions()
        return 0
    if args.action == "ikea":
        forwarded = args.args[1:] if args.args and args.args[0] == "--" else args.args
        return run_helper("ikea", forwarded)
    if args.action == "abo":
        forwarded = args.args[1:] if args.args and args.args[0] == "--" else args.args
        return run_abo(forwarded)
    print_actions()
    return interactive_main()


# 直接 GLB 下載器的固定路徑、可辨識 URL 欄位與 HTTP User-Agent。
MODEL_ROOT = SCRIPTS_DIR.parent / "downloaded-files" / "models"
MODEL_URL_KEYS = ("model_url", "glb_url", "download_url", "asset_url")
MODEL_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) RoomPilotModelDownloader/1.0"
NORMALIZED_SCHEMA = "roompilot-rag normalized v1"
# Downloader 與 catalog manager 共用的 normalized item 欄位順序。
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


def model_slug(value: str, fallback: str = "model") -> str:
    """把名稱轉成適合資料夾、檔名與 item id 使用的 ASCII slug。"""
    value = urllib.parse.unquote(value)
    value = re.sub(r"[^a-zA-Z0-9._-]+", "-", value).strip("-._").lower()
    return value[:120] or fallback


def normalize_model_url(value: str, base_url: str = "") -> str:
    """清理 HTML／跳脫字元並補齊相對網址，只接受 HTTP 或 HTTPS。"""
    value = html.unescape(value.strip().strip('"\''))
    value = value.replace("\\/", "/").replace("\\u0026", "&")
    if base_url:
        value = urllib.parse.urljoin(base_url, value)
    parsed = urllib.parse.urlparse(value)
    return value if parsed.scheme in {"http", "https"} and bool(parsed.netloc) else ""


def extract_model_urls(text: str, base_url: str = "") -> list[str]:
    """從網頁文字中找出所有 .glb URL，正規化後依出現順序去重。"""
    decoded = html.unescape(text).replace("\\/", "/").replace("\\u0026", "&")
    matches = re.findall(
        r"(?:https?:)?//[^\"'<>\s]+?\.glb(?:\?[^\"'<>\s]*)?|/[A-Za-z0-9_./%+~-]+\.glb(?:\?[^\"'<>\s]*)?",
        decoded,
        flags=re.IGNORECASE,
    )
    urls = [normalize_model_url(value, base_url) for value in matches]
    return list(dict.fromkeys(url for url in urls if url))


def iter_manifest_objects(value: Any) -> Iterable[dict[str, Any]]:
    """遞迴走訪巢狀 JSON，逐一產生其中所有 object。"""
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from iter_manifest_objects(child)
    elif isinstance(value, list):
        for child in value:
            yield from iter_manifest_objects(child)


def manifest_specs(path: Path, fallback_category: str) -> list[dict[str, Any]]:
    """從 JSON／JSONL manifest 讀取模型 URL、名稱、分類與 normalized metadata。"""
    if not path.exists():
        raise FileNotFoundError(f"找不到 manifest：{path}")
    if path.suffix.casefold() == ".jsonl":
        roots = [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    else:
        roots = [json.loads(path.read_text(encoding="utf-8-sig"))]
    specs: list[dict[str, Any]] = []
    for root in roots:
        root_metadata = root if isinstance(root, dict) else {}
        for item in iter_manifest_objects(root):
            url = next(
                (
                    normalize_model_url(str(item[key]))
                    for key in MODEL_URL_KEYS
                    if item.get(key) and normalize_model_url(str(item[key]))
                ),
                "",
            )
            if not url:
                continue
            name = next(
                (str(item[key]) for key in ("name_en", "name", "title", "sku", "product_id", "id") if item.get(key) not in (None, "")),
                Path(urllib.parse.urlparse(url).path).stem,
            )
            category = next(
                (str(item[key]) for key in ("category", "category_name_en", "group", "type") if item.get(key) not in (None, "")),
                fallback_category,
            )
            source_item = dict(item)
            for item_key, root_key in (
                ("catalog", "source_catalog"),
                ("source_group", "source_group"),
                ("kind", "kind"),
                ("source_dataset", "dataset_name"),
            ):
                if source_item.get(item_key) in (None, "") and root_metadata.get(root_key) not in (None, ""):
                    source_item[item_key] = root_metadata[root_key]
            source_page = normalize_model_url(
                str(item.get("product_url") or item.get("source_page") or "")
            )
            specs.append(
                {
                    "url": url,
                    "name": name,
                    "category": category,
                    "source_page": source_page,
                    "source_item": source_item,
                }
            )
    return specs


def url_file_specs(path: Path, category: str) -> list[dict[str, Any]]:
    """讀取一行一個 URL 的 UTF-8 文字檔，TAB 後方可提供自訂名稱。"""
    if not path.exists():
        raise FileNotFoundError(f"找不到網址清單：{path}")
    specs: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        value = line.strip()
        if not value or value.startswith("#"):
            continue
        parts = value.split("\t", 2)
        url = normalize_model_url(parts[0])
        if not url:
            raise ValueError(f"不是有效的 HTTP(S) 網址：{parts[0]}")
        default_name = Path(urllib.parse.urlparse(url).path).stem
        name = parts[1].strip() if len(parts) >= 2 and parts[1].strip() else default_name
        source_page = normalize_model_url(parts[2]) if len(parts) == 3 else ""
        if len(parts) == 3 and parts[2].strip() and not source_page:
            raise ValueError(f"不是有效的商品網址：{parts[2]}")
        specs.append(
            {
                "url": url,
                "name": name,
                "category": category,
                "source_page": source_page,
                "source_item": {},
            }
        )
    return specs


def ikea_page_specs(url: str, category: str, timeout: int) -> list[dict[str, Any]]:
    """下載 IKEA 商品頁並擷取公開 GLB URL，轉成待下載規格。"""
    request = urllib.request.Request(url, headers={"User-Agent": MODEL_USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        page = response.read().decode("utf-8", errors="ignore")
    model_urls = extract_model_urls(page, url)
    if not model_urls:
        raise RuntimeError(f"商品頁沒有公開的 .glb 網址：{url}")
    product = model_slug(Path(urllib.parse.urlparse(url).path).name, "ikea-product")
    return [
        {"url": model_url, "name": f"{product}-{index:02d}", "category": category, "source_page": url, "source_item": {}}
        for index, model_url in enumerate(model_urls, 1)
    ]


def nested_value(item: dict[str, Any], key: str) -> Any:
    """優先讀取頂層尺寸欄位，缺少時再從舊格式 size_cm 取值。"""
    value = item.get(key)
    if value not in (None, ""):
        return value
    size = item.get("size_cm")
    if isinstance(size, dict):
        return size.get(key.removesuffix("_cm"))
    return None


def normalized_download_item(
    spec: dict[str, Any],
    target: Path,
    project_root: Path,
    source: str,
    source_group: str,
    kind: str,
    catalog: str,
    dataset_name: str,
) -> dict[str, Any]:
    """把成功下載的模型與來源 metadata 組成固定 22 欄的 normalized item。"""
    original = spec.get("source_item")
    item = original if isinstance(original, dict) else {}
    category = str(item.get("category") or spec["category"])
    role_default = "家電" if kind == "appliance" else "家具"
    model_path = target.relative_to(project_root).as_posix() if target.is_relative_to(project_root) else str(target)
    confidence = item.get("style_confidence")
    if not isinstance(confidence, (int, float)):
        confidence = 0.0
    normalized = {
        "id": target.stem,
        "name_en": str(item.get("name_en") or item.get("name") or item.get("title") or spec["name"]),
        "name_zh": str(item.get("name_zh") or item.get("chinese_name") or ""),
        "category": category,
        "type": str(item.get("type") or model_slug(category, "unknown")),
        "role": str(item.get("role") or role_default),
        "color": str(item.get("color") or ""),
        "material": str(item.get("material") or ""),
        "style_confidence": confidence,
        "style_source": str(item.get("style_source") or "downloader_default"),
        "style_top": str(item.get("style_top") or "scandinavian:0.0;modern:0.0;minimalist_muji:0.0"),
        "width_cm": nested_value(item, "width_cm"),
        "depth_cm": nested_value(item, "depth_cm"),
        "height_cm": nested_value(item, "height_cm"),
        "glb_path": model_path,
        "has_local_glb": valid_glb(target),
        "is_ikea": item.get("is_ikea") if isinstance(item.get("is_ikea"), bool) else source == "ikea",
        "source_group": str(item.get("source_group") or source_group),
        "kind": str(item.get("kind") or kind),
        "catalog": str(item.get("catalog") or catalog),
        "source_dataset": str(item.get("source_dataset") or dataset_name),
        "product_url": normalize_model_url(
            str(item.get("product_url") or item.get("source_page") or spec.get("source_page") or "")
        ),
    }
    return {field: normalized[field] for field in NORMALIZED_ITEM_FIELDS}


def normalized_catalog(
    items: list[dict[str, Any]],
    source_catalog: str,
    source_group: str,
    kind: str,
    dataset_name: str,
) -> dict[str, Any]:
    """建立 normalized catalog envelope，並重新計算筆數與空材質／顏色數。"""
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


def common_spec_value(specs: list[dict[str, Any]], key: str) -> str:
    """若所有下載規格對某 metadata 只有一個非空值，就回傳該值。"""
    values = {
        str(item[key]).strip()
        for spec in specs
        if isinstance(spec.get("source_item"), dict)
        for item in [spec["source_item"]]
        if item.get(key) not in (None, "")
    }
    return values.pop() if len(values) == 1 else ""


def write_download_outputs(
    output_root: Path,
    catalog_payload: dict[str, Any],
    report: dict[str, Any],
) -> tuple[Path, Path, Path]:
    """寫出 normalized JSON、逐行 JSONL，以及含狀態與錯誤的下載報告。"""
    output_root.mkdir(parents=True, exist_ok=True)
    catalog_path = output_root / "download_catalog.normalized.json"
    jsonl_path = output_root / "download_catalog.normalized.jsonl"
    report_path = output_root / "download_report.json"
    catalog_path.write_text(json.dumps(catalog_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    jsonl_path.write_text(
        "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in catalog_payload["items"]),
        encoding="utf-8",
    )
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return catalog_path, jsonl_path, report_path


def valid_glb(path: Path) -> bool:
    """確認檔案存在、至少 12 bytes，且前四個 bytes 為 GLB 的 glTF 標記。"""
    if not path.is_file() or path.stat().st_size < 12:
        return False
    with path.open("rb") as file:
        return file.read(4) == b"glTF"


def fetch_glb(url: str, target: Path, timeout: int, overwrite: bool) -> str:
    """以暫存檔下載 GLB、驗證內容後原子取代目標，並回傳處理狀態。"""
    if not overwrite and valid_glb(target):
        return "skipped_existing"
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".glb.part")
    request = urllib.request.Request(url, headers={"User-Agent": MODEL_USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response, temporary.open("wb") as output:
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
        if not valid_glb(temporary):
            with temporary.open("rb") as file:
                header = file.read(16)
            raise ValueError(f"下載內容不是有效 GLB（header={header!r}）")
        temporary.replace(target)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return "downloaded"


def add_model_source_arguments(parser: argparse.ArgumentParser, source: str) -> None:
    """替 IKEA 或 ABO 子命令加入共同的來源、輸出與 catalog 參數。"""
    parser.set_defaults(model_source=source)
    parser.add_argument("--url", action="append", default=[], help="Direct GLB URL; may be repeated.")
    parser.add_argument(
        "--source-page",
        action="append",
        default=[],
        help="Product page for --url; repeat per URL, or provide once for all direct URLs.",
    )
    parser.add_argument(
        "--url-file",
        action="append",
        default=[],
        help="UTF-8 lines: GLB URL, optional tab-separated name and product URL.",
    )
    parser.add_argument("--manifest", action="append", default=[], help="JSON/JSONL containing model_url, glb_url, download_url, or asset_url.")
    parser.add_argument("--category", default="manual", help="Fallback output category.")
    parser.add_argument("--kind", choices=["furniture", "appliance"], help="Normalized catalog kind; inferred from manifest or defaults to furniture.")
    parser.add_argument("--catalog", help="Normalized source_catalog/catalog value; derived from source and kind by default.")
    parser.add_argument("--dataset-name", help="Normalized dataset_name/source_dataset value.")
    parser.add_argument("--source-group", help="Normalized source_group; defaults to IKEA or non-IKEA.")
    parser.add_argument("--output-root", help=f"Default: downloaded-files/models/{source}")
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--dry-run", action="store_true")


def build_model_parser() -> argparse.ArgumentParser:
    """建立目前直接執行入口使用的 IKEA／ABO 命令列解析器。"""
    parser = argparse.ArgumentParser(description="Download furniture GLB files into downloaded-files/models.")
    parser.add_argument("--list", action="store_true", help="List supported sources and exit.")
    sources = parser.add_subparsers(dest="model_source")
    ikea = sources.add_parser("ikea", help="IKEA direct GLB, manifest, or product-page download.")
    add_model_source_arguments(ikea, "ikea")
    ikea.add_argument("--product-url", action="append", default=[], help="IKEA product page to inspect for public GLB URLs.")
    abo = sources.add_parser("abo", help="ABO direct GLB or manifest download.")
    add_model_source_arguments(abo, "abo")
    return parser


def interactive_model_args() -> list[str]:
    """未提供命令列參數時，以簡易問答取得來源與單一下載 URL。"""
    print("Furniture GLB downloader")
    source = input("Source [ikea/abo] (ikea): ").strip().casefold() or "ikea"
    if source not in {"ikea", "abo"}:
        raise ValueError("Source must be ikea or abo.")
    if source == "ikea":
        product_url = input("IKEA product URL (blank to enter a direct GLB URL): ").strip()
        if product_url:
            return ["ikea", "--product-url", product_url]
    url = input("Direct GLB URL: ").strip()
    if not url:
        raise ValueError("A product URL or direct GLB URL is required.")
    return [source, "--url", url]


def download_main(argv: list[str] | None = None) -> int:
    """彙整下載來源、執行 GLB 下載，最後輸出 normalized catalog 與報告。"""
    parser = build_model_parser()
    values = list(sys.argv[1:] if argv is None else argv)
    if not values:
        values = interactive_model_args()
    args = parser.parse_args(values)
    if args.list:
        print("ikea -> downloaded-files/models/ikea")
        print("abo  -> downloaded-files/models/abo")
        return 0
    if not args.model_source:
        parser.error("請指定 ikea 或 abo")

    # 決定來源根目錄；相對路徑一律以專案根目錄解析。
    output_root = Path(args.output_root) if args.output_root else MODEL_ROOT / args.model_source
    if not output_root.is_absolute():
        output_root = SCRIPTS_DIR.parent / output_root
    specs: list[dict[str, Any]] = []
    # 將直接 URL、URL 檔、manifest 與 IKEA 商品頁統一轉成下載規格。
    if args.source_page and not args.url:
        parser.error("--source-page 必須搭配 --url")
    if args.source_page and len(args.source_page) not in {1, len(args.url)}:
        parser.error("--source-page 必須只提供一次，或與 --url 數量相同")
    direct_source_pages = [normalize_model_url(value) for value in args.source_page]
    if any(not value for value in direct_source_pages):
        parser.error("--source-page 必須是有效的 HTTP(S) 網址")
    for index, value in enumerate(args.url):
        url = normalize_model_url(value)
        if not url:
            parser.error(f"Invalid --url: {value}")
        source_page = (
            direct_source_pages[0]
            if len(direct_source_pages) == 1
            else direct_source_pages[index]
            if direct_source_pages
            else ""
        )
        specs.append(
            {
                "url": url,
                "name": Path(urllib.parse.urlparse(url).path).stem,
                "category": args.category,
                "source_page": source_page,
                "source_item": {},
            }
        )
    for value in args.url_file:
        specs.extend(url_file_specs(Path(value), args.category))
    for value in args.manifest:
        specs.extend(manifest_specs(Path(value), args.category))
    if args.model_source == "ikea":
        for value in args.product_url:
            specs.extend(ikea_page_specs(value, args.category, args.timeout))

    # 同一 URL 在單次執行只處理一次。
    unique: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    for spec in specs:
        if spec["url"] not in seen_urls:
            seen_urls.add(spec["url"])
            unique.append(spec)
    if not unique:
        parser.error("沒有下載項目；請提供 --url、--url-file、--manifest 或 IKEA --product-url")

    used_targets: set[Path] = set()
    records: list[dict[str, Any]] = []
    catalog_items: list[dict[str, Any]] = []
    failures = 0
    kind = args.kind or common_spec_value(unique, "kind") or "furniture"
    source_group = args.source_group or common_spec_value(unique, "source_group") or ("IKEA" if args.model_source == "ikea" else "non-IKEA")
    source_catalog = args.catalog or common_spec_value(unique, "catalog") or f"{args.model_source}_{kind}"
    dataset_name = args.dataset_name or common_spec_value(unique, "source_dataset") or f"{args.model_source.upper()} downloaded {kind}"
    # 逐筆決定目標檔名並下載；失敗資料只進報告，不進 normalized catalog。
    for spec in unique:
        category = model_slug(spec["category"], "manual")
        source_item = spec.get("source_item") if isinstance(spec.get("source_item"), dict) else {}
        stem_source = source_item.get("id") or spec["name"]
        stem = model_slug(str(stem_source), Path(urllib.parse.urlparse(spec["url"]).path).stem or "model")
        target = output_root / category / f"{stem}.glb"
        sequence = 2
        while target in used_targets:
            target = output_root / category / f"{stem}-{sequence:02d}.glb"
            sequence += 1
        used_targets.add(target)
        record: dict[str, Any] = {
            "source": args.model_source,
            "name": spec["name"],
            "category": spec["category"],
            "model_url": spec["url"],
            "product_url": spec["source_page"],
            "source_page": spec["source_page"],
            "model_path": target.relative_to(SCRIPTS_DIR.parent).as_posix() if target.is_relative_to(SCRIPTS_DIR.parent) else str(target),
        }
        if args.dry_run:
            record["status"] = "planned"
            print(f"PLAN {spec['url']} -> {target}")
        else:
            try:
                record["status"] = fetch_glb(spec["url"], target, args.timeout, args.overwrite)
                record["file_size"] = target.stat().st_size
                catalog_items.append(
                    normalized_download_item(
                        spec,
                        target,
                        SCRIPTS_DIR.parent,
                        args.model_source,
                        source_group,
                        kind,
                        source_catalog,
                        dataset_name,
                    )
                )
                print(f"OK {record['status']}: {target}")
            except Exception as exc:
                failures += 1
                record["status"] = "failed"
                record["error"] = str(exc)
                print(f"FAIL {spec['url']}: {exc}", file=sys.stderr)
        records.append(record)

    # Dry Run 只列印計畫；正式執行才寫 catalog、JSONL 與報告。
    if not args.dry_run:
        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source": args.model_source,
            "output_root": str(output_root),
            "total": len(records),
            "catalog_items": len(catalog_items),
            "failed": failures,
            "items": records,
        }
        catalog_payload = normalized_catalog(
            catalog_items,
            source_catalog,
            source_group,
            kind,
            dataset_name,
        )
        catalog_path, jsonl_path, report_path = write_download_outputs(output_root, catalog_payload, report)
        print(f"CATALOG {catalog_path}")
        print(f"JSONL   {jsonl_path}")
        print(f"REPORT  {report_path}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(download_main())

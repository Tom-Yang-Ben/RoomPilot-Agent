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
    print("usage: furniture_downloader.py abo -- [--mode all|furniture|home] [options]")
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
    """解析 `furniture_downloader.py` 的頂層命令列參數。"""
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


MODEL_ROOT = SCRIPTS_DIR.parent / "downloaded-files" / "models"
MODEL_URL_KEYS = ("model_url", "glb_url", "download_url", "asset_url")
MODEL_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) RoomPilotModelDownloader/1.0"


def model_slug(value: str, fallback: str = "model") -> str:
    value = urllib.parse.unquote(value)
    value = re.sub(r"[^a-zA-Z0-9._-]+", "-", value).strip("-._").lower()
    return value[:120] or fallback


def normalize_model_url(value: str, base_url: str = "") -> str:
    value = html.unescape(value.strip().strip('"\''))
    value = value.replace("\\/", "/").replace("\\u0026", "&")
    if base_url:
        value = urllib.parse.urljoin(base_url, value)
    parsed = urllib.parse.urlparse(value)
    return value if parsed.scheme in {"http", "https"} else ""


def extract_model_urls(text: str, base_url: str = "") -> list[str]:
    decoded = html.unescape(text).replace("\\/", "/").replace("\\u0026", "&")
    matches = re.findall(
        r"(?:https?:)?//[^\"'<>\s]+?\.glb(?:\?[^\"'<>\s]*)?|/[A-Za-z0-9_./%+~-]+\.glb(?:\?[^\"'<>\s]*)?",
        decoded,
        flags=re.IGNORECASE,
    )
    urls = [normalize_model_url(value, base_url) for value in matches]
    return list(dict.fromkeys(url for url in urls if url))


def iter_manifest_objects(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from iter_manifest_objects(child)
    elif isinstance(value, list):
        for child in value:
            yield from iter_manifest_objects(child)


def manifest_specs(path: Path, fallback_category: str) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"找不到 manifest：{path}")
    if path.suffix.casefold() == ".jsonl":
        roots = [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    else:
        roots = [json.loads(path.read_text(encoding="utf-8-sig"))]
    specs: list[dict[str, str]] = []
    for root in roots:
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
                (str(item[key]) for key in ("name", "title", "sku", "product_id", "id") if item.get(key) not in (None, "")),
                Path(urllib.parse.urlparse(url).path).stem,
            )
            category = next(
                (str(item[key]) for key in ("category", "category_name_en", "group", "type") if item.get(key) not in (None, "")),
                fallback_category,
            )
            specs.append(
                {
                    "url": url,
                    "name": name,
                    "category": category,
                    "source_page": str(item.get("product_url") or item.get("source_page") or ""),
                }
            )
    return specs


def url_file_specs(path: Path, category: str) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"找不到網址清單：{path}")
    specs: list[dict[str, str]] = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        value = line.strip()
        if not value or value.startswith("#"):
            continue
        parts = value.split("\t", 1)
        url = normalize_model_url(parts[0])
        if not url:
            raise ValueError(f"不是有效的 HTTP(S) 網址：{parts[0]}")
        name = parts[1].strip() if len(parts) == 2 else Path(urllib.parse.urlparse(url).path).stem
        specs.append({"url": url, "name": name, "category": category, "source_page": ""})
    return specs


def ikea_page_specs(url: str, category: str, timeout: int) -> list[dict[str, str]]:
    request = urllib.request.Request(url, headers={"User-Agent": MODEL_USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        page = response.read().decode("utf-8", errors="ignore")
    model_urls = extract_model_urls(page, url)
    if not model_urls:
        raise RuntimeError(f"商品頁沒有公開的 .glb 網址：{url}")
    product = model_slug(Path(urllib.parse.urlparse(url).path).name, "ikea-product")
    return [
        {"url": model_url, "name": f"{product}-{index:02d}", "category": category, "source_page": url}
        for index, model_url in enumerate(model_urls, 1)
    ]


def valid_glb(path: Path) -> bool:
    if not path.is_file() or path.stat().st_size < 12:
        return False
    with path.open("rb") as file:
        return file.read(4) == b"glTF"


def fetch_glb(url: str, target: Path, timeout: int, overwrite: bool) -> str:
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
    parser.set_defaults(model_source=source)
    parser.add_argument("--url", action="append", default=[], help="Direct GLB URL; may be repeated.")
    parser.add_argument("--url-file", action="append", default=[], help="UTF-8 file with one GLB URL per line; optional tab-separated name.")
    parser.add_argument("--manifest", action="append", default=[], help="JSON/JSONL containing model_url, glb_url, download_url, or asset_url.")
    parser.add_argument("--category", default="manual", help="Fallback output category.")
    parser.add_argument("--output-root", help=f"Default: downloaded-files/models/{source}")
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--dry-run", action="store_true")


def build_model_parser() -> argparse.ArgumentParser:
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

    output_root = Path(args.output_root) if args.output_root else MODEL_ROOT / args.model_source
    if not output_root.is_absolute():
        output_root = SCRIPTS_DIR.parent / output_root
    specs: list[dict[str, str]] = []
    for value in args.url:
        url = normalize_model_url(value)
        if not url:
            parser.error(f"Invalid --url: {value}")
        specs.append({"url": url, "name": Path(urllib.parse.urlparse(url).path).stem, "category": args.category, "source_page": ""})
    for value in args.url_file:
        specs.extend(url_file_specs(Path(value), args.category))
    for value in args.manifest:
        specs.extend(manifest_specs(Path(value), args.category))
    if args.model_source == "ikea":
        for value in args.product_url:
            specs.extend(ikea_page_specs(value, args.category, args.timeout))

    unique: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    for spec in specs:
        if spec["url"] not in seen_urls:
            seen_urls.add(spec["url"])
            unique.append(spec)
    if not unique:
        parser.error("沒有下載項目；請提供 --url、--url-file、--manifest 或 IKEA --product-url")

    used_targets: set[Path] = set()
    records: list[dict[str, Any]] = []
    failures = 0
    for spec in unique:
        category = model_slug(spec["category"], "manual")
        stem = model_slug(spec["name"], Path(urllib.parse.urlparse(spec["url"]).path).stem or "model")
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
                print(f"OK {record['status']}: {target}")
            except Exception as exc:
                failures += 1
                record["status"] = "failed"
                record["error"] = str(exc)
                print(f"FAIL {spec['url']}: {exc}", file=sys.stderr)
        records.append(record)

    if not args.dry_run:
        output_root.mkdir(parents=True, exist_ok=True)
        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source": args.model_source,
            "output_root": str(output_root),
            "total": len(records),
            "failed": failures,
            "items": records,
        }
        (output_root / "download_manifest.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(download_main())

import csv
import html
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import unquote

import requests
from tqdm import tqdm


BOOKCASE_CATEGORY_URLS = [
    "https://www.ikea.com/fi/en/cat/bookcases-10382/",
    "https://www.ikea.com/fi/en/cat/bookcases-shelving-units-st002/",
]
TARGET_COUNT = 10
TIME_LIMIT_SECONDS = 10 * 60
OUTPUT_DIR = Path("downloaded-files") / "bookcases"
METADATA_CSV = OUTPUT_DIR / "bookcase_glb_metadata.csv"
METADATA_JSON = OUTPUT_DIR / "bookcase_glb_metadata.json"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def safe_filename(value):
    value = re.sub(r'[<>:"/\\|?*]', "", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value[:160] or "ikea-bookcase"


def decode_page(text):
    return html.unescape(unquote(text))


def fetch(url, timeout=30):
    response = requests.get(url, headers=HEADERS, timeout=timeout)
    response.raise_for_status()
    return response.text


def collect_product_links():
    links = []
    seen = set()

    for category_url in BOOKCASE_CATEGORY_URLS:
        print(f"Opening bookcase category: {category_url}", flush=True)
        text = decode_page(fetch(category_url))
        for match in re.findall(r"https://www\.ikea\.com/fi/en/p/[^\"'<>\\\s]+", text):
            clean_url = match.split("?")[0]
            if clean_url not in seen:
                seen.add(clean_url)
                links.append(clean_url)

        print(f"Collected {len(links)} product links so far.", flush=True)

    return links


def find_glb_urls(text):
    decoded = decode_page(text)
    patterns = [
        r"https?://[^\"'<>\\\s]+?\.glb(?:\?[^\"'<>\\\s]*)?",
        r'"url"\s*:\s*"(https?:\\/\\/[^"]+?\.glb(?:\?[^"]*)?)"',
    ]
    hits = []
    for pattern in patterns:
        for hit in re.findall(pattern, decoded):
            hits.append(hit.replace("\\/", "/"))
    return sorted(set(hits))


def page_title(text):
    match = re.search(r"<title>(.*?)</title>", text, flags=re.I | re.S)
    if not match:
        return "IKEA bookcase"
    title = html.unescape(re.sub(r"\s+", " ", match.group(1))).strip()
    return title.replace(" - IKEA", "")


def parse_json_ld(text):
    products = []
    for raw in re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        text,
        flags=re.DOTALL | re.IGNORECASE,
    ):
        try:
            data = json.loads(raw.strip())
        except json.JSONDecodeError:
            continue
        candidates = data if isinstance(data, list) else [data]
        for candidate in candidates:
            if isinstance(candidate, dict) and candidate.get("@type") == "Product":
                products.append(candidate)
    return products


def extract_dimensions_from_text(text):
    decoded = html.unescape(re.sub(r"<[^>]+>", " ", text))
    decoded = re.sub(r"\s+", " ", decoded)
    dimensions = {}
    for label in ("Width", "Depth", "Height", "Max. load/shelf"):
        match = re.search(
            rf"{re.escape(label)}\s*[: ]\s*([0-9.,]+\s*(?:cm|mm|m|kg|lb|in|\"))",
            decoded,
            flags=re.I,
        )
        if match:
            dimensions[label.lower().replace(". ", "_").replace(" ", "_")] = match.group(1)

    product_size_match = re.search(
        r"Product size\s+(.*?)(?:Reviews|Material|Designer|Packaging|Measurements)",
        decoded,
        flags=re.I,
    )
    if product_size_match and not dimensions:
        dimensions["product_size_text"] = product_size_match.group(1).strip()[:500]

    return dimensions


def extract_product_details(product_url):
    text = fetch(product_url)
    title = page_title(text)
    product_name = title
    color = ""
    dimensions = extract_dimensions_from_text(text)

    for product in parse_json_ld(text):
        product_name = product.get("name") or product_name
        color = product.get("color") or color
        dimensions.update(extract_dimensions_from_text(json.dumps(product, ensure_ascii=False)))

    glb_urls = find_glb_urls(text)
    return {
        "name": product_name,
        "color": color,
        "dimensions": dimensions,
        "product_url": product_url,
        "glb_url": glb_urls[0] if glb_urls else None,
    }


def download_file(url, destination):
    response = requests.get(url, headers=HEADERS, stream=True, timeout=60)
    response.raise_for_status()
    total_size = int(response.headers.get("content-length", 0))

    with destination.open("wb") as file, tqdm(
        desc=destination.name,
        total=total_size,
        unit="iB",
        unit_scale=True,
        unit_divisor=1024,
    ) as progress:
        for chunk in response.iter_content(chunk_size=1024 * 256):
            if chunk:
                file.write(chunk)
                progress.update(len(chunk))


def write_metadata(rows):
    fieldnames = [
        "index",
        "name",
        "color",
        "dimensions",
        "filename",
        "product_url",
        "glb_url",
    ]
    with METADATA_CSV.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({**row, "dimensions": json.dumps(row["dimensions"], ensure_ascii=False)})

    with METADATA_JSON.open("w", encoding="utf-8") as file:
        json.dump(rows, file, ensure_ascii=False, indent=2)


def load_existing_metadata():
    if not METADATA_JSON.exists():
        return []
    with METADATA_JSON.open("r", encoding="utf-8") as file:
        rows = json.load(file)
    return rows if isinstance(rows, list) else []


def main():
    start_time = time.monotonic()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    downloaded = load_existing_metadata()
    seen_products = {row.get("product_url") for row in downloaded}
    seen_glbs = {row.get("glb_url") for row in downloaded}

    product_links = collect_product_links()
    print(f"Found {len(product_links)} candidate bookcase product links.", flush=True)

    for product_url in product_links:
        if len(downloaded) >= TARGET_COUNT:
            break
        if time.monotonic() - start_time >= TIME_LIMIT_SECONDS:
            print("Reached the 10 minute time limit; pausing with current results.", flush=True)
            break
        if product_url in seen_products:
            continue

        try:
            details = extract_product_details(product_url)
        except Exception as exc:
            print(f"Failed to inspect {product_url}: {exc}", flush=True)
            continue

        if not details["glb_url"]:
            print(f"No GLB model: {details['name']} ({product_url})", flush=True)
            continue
        if details["glb_url"] in seen_glbs:
            print(f"Duplicate GLB skipped: {details['name']} ({product_url})", flush=True)
            seen_products.add(product_url)
            continue

        index = len(downloaded) + 1
        filename = f"{index:02d} - {safe_filename(details['name'])}.glb"
        destination = OUTPUT_DIR / filename

        print(f"Downloading {index}/{TARGET_COUNT}: {details['name']}", flush=True)
        download_file(details["glb_url"], destination)

        row = {
            "index": index,
            "name": details["name"],
            "color": details["color"],
            "dimensions": details["dimensions"],
            "filename": str(destination),
            "product_url": details["product_url"],
            "glb_url": details["glb_url"],
        }
        downloaded.append(row)
        seen_products.add(details["product_url"])
        seen_glbs.add(details["glb_url"])
        write_metadata(downloaded)
        print(f"Saved metadata after {len(downloaded)} GLB file(s).", flush=True)

    print(f"Downloaded {len(downloaded)} bookcase GLB files.", flush=True)
    print(f"Metadata CSV: {METADATA_CSV}", flush=True)
    print(f"Metadata JSON: {METADATA_JSON}", flush=True)


if __name__ == "__main__":
    main()

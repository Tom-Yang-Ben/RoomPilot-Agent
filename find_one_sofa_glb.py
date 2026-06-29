import csv
import html
import json
import re
from pathlib import Path
from urllib.parse import unquote

import requests
from tqdm import tqdm


PRODUCT_URLS = [
    "https://www.ikea.com/fi/en/p/kivik-3-seat-sofa-tresund-anthracite-s09482829/",
    "https://www.ikea.com/fi/en/p/kivik-3-seat-sofa-tallmyra-white-black-s09484772/",
    "https://www.ikea.com/fi/en/p/kivik-3-seat-sofa-gunnared-light-brown-pink-s29484766/",
]
OUTPUT_DIR = Path("downloaded-files") / "sofas"


def safe_filename(value):
    value = re.sub(r'[<>:"/\\|?*]', "", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value[:140] or "ikea-sofa"


def find_glb_urls(text):
    decoded = html.unescape(unquote(text))
    hits = re.findall(r"https?://[^\"'<>\\\s]+?\.glb(?:\?[^\"'<>\\\s]*)?", decoded)
    return sorted(set(hits))


def page_title(text):
    match = re.search(r"<title>(.*?)</title>", text, flags=re.I | re.S)
    if not match:
        return "IKEA sofa"
    title = html.unescape(re.sub(r"\s+", " ", match.group(1))).strip()
    return title.replace(" - IKEA", "")


def find_dimensions(text):
    decoded = html.unescape(re.sub(r"<[^>]+>", " ", text))
    decoded = re.sub(r"\s+", " ", decoded)
    dimensions = {}
    for label in ["Width", "Depth", "Height", "Seat width", "Seat depth", "Seat height"]:
        match = re.search(rf"{label}\s*[: ]\s*([0-9.,]+\s*(?:cm|mm|m|in|\"))", decoded, flags=re.I)
        if match:
            dimensions[label.lower().replace(" ", "_")] = match.group(1)

    product_size_match = re.search(r"Product size\s+(.*?)(?:Reviews|Material|Designer|Packaging)", decoded, flags=re.I)
    if product_size_match and not dimensions:
        snippet = product_size_match.group(1).strip()
        dimensions["product_size_text"] = snippet[:500]
    return dimensions


def download(url, destination):
    response = requests.get(url, stream=True, timeout=60)
    response.raise_for_status()
    total = int(response.headers.get("content-length", 0))
    with destination.open("wb") as file, tqdm(
        desc=destination.name,
        total=total,
        unit="iB",
        unit_scale=True,
        unit_divisor=1024,
    ) as progress:
        for chunk in response.iter_content(chunk_size=1024 * 256):
            if chunk:
                file.write(chunk)
                progress.update(len(chunk))


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for product_url in PRODUCT_URLS:
        print(f"Checking {product_url}", flush=True)
        response = requests.get(product_url, timeout=30)
        response.raise_for_status()
        text = response.text
        glb_urls = find_glb_urls(text)
        if not glb_urls:
            print("No GLB URL found.", flush=True)
            continue

        title = page_title(text)
        dimensions = find_dimensions(text)
        glb_url = glb_urls[0]
        filename = f"01 - {safe_filename(title)}.glb"
        destination = OUTPUT_DIR / filename
        download(glb_url, destination)

        metadata = {
            "name": title,
            "dimensions": dimensions,
            "filename": str(destination),
            "product_url": product_url,
            "ikea_site": "IKEA Finland English site (ikea.com/fi/en)",
            "glb_url": glb_url,
        }

        with (OUTPUT_DIR / "one_sofa_metadata.json").open("w", encoding="utf-8") as file:
            json.dump(metadata, file, ensure_ascii=False, indent=2)

        with (OUTPUT_DIR / "one_sofa_metadata.csv").open("w", newline="", encoding="utf-8-sig") as file:
            writer = csv.DictWriter(file, fieldnames=metadata.keys())
            writer.writeheader()
            writer.writerow({**metadata, "dimensions": json.dumps(dimensions, ensure_ascii=False)})

        print(json.dumps(metadata, ensure_ascii=False, indent=2), flush=True)
        return

    raise RuntimeError("No sofa GLB URL was found in the candidate IKEA product pages.")


if __name__ == "__main__":
    main()

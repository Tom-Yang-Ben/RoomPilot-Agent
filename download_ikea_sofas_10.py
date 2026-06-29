import csv
import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import urljoin

import requests
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from tqdm import tqdm
from webdriver_manager.chrome import ChromeDriverManager


SOFA_CATEGORY_URL = "https://www.ikea.com/fi/en/cat/sofas-fu003/"
TARGET_COUNT = 10
OUTPUT_DIR = Path("downloaded-files") / "sofas"
METADATA_CSV = OUTPUT_DIR / "sofa_glb_metadata.csv"
METADATA_JSON = OUTPUT_DIR / "sofa_glb_metadata.json"


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def safe_filename(value):
    value = re.sub(r'[<>:"/\\|?*]', "", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value[:160] or "ikea-sofa"


def get_chrome_driver():
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--log-level=3")
    options.add_argument("--window-size=1440,1800")
    options.add_experimental_option("excludeSwitches", ["enable-logging"])
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.set_page_load_timeout(35)
    return driver


def collect_product_links(driver, category_url, minimum_count=40):
    print(f"Opening sofa category: {category_url}", flush=True)
    try:
        driver.get(category_url)
    except TimeoutException:
        print("Category page load timed out; continuing with the loaded DOM.", flush=True)
    WebDriverWait(driver, 30).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, ".plp-fragment-wrapper"))
    )

    links = []
    seen = set()
    last_height = 0

    for _ in range(18):
        anchors = driver.find_elements(
            By.CSS_SELECTOR,
            ".plp-fragment-wrapper a.plp-product__image-link, a[href*='/p/']",
        )
        for anchor in anchors:
            href = anchor.get_attribute("href")
            if href and "/p/" in href:
                clean_url = href.split("?")[0]
                if clean_url not in seen:
                    seen.add(clean_url)
                    links.append(clean_url)

        print(f"Collected {len(links)} product links...", flush=True)
        if len(links) >= minimum_count:
            break

        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height

    return links


def parse_json_ld(page_source):
    products = []
    for raw in re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        page_source,
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
    dimensions = {}
    compact = re.sub(r"\s+", " ", text)
    for label in ("Width", "Depth", "Height", "Seat width", "Seat depth", "Seat height"):
        match = re.search(rf"{re.escape(label)}\s*[:\s]\s*([0-9.,]+\s*(?:cm|mm|m|\"|in))", compact, re.I)
        if match:
            dimensions[label.lower().replace(" ", "_")] = match.group(1)
    return dimensions


def extract_product_details(driver, product_url):
    try:
        driver.get(product_url)
    except TimeoutException:
        print(f"Product page load timed out; continuing with the loaded DOM: {product_url}", flush=True)
    WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.TAG_NAME, "title")))

    title = driver.title.replace(" - IKEA", "").strip()
    page_source = driver.page_source
    glb_url = None

    try:
        script = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.ID, "pip-xr-viewer-model"))
        )
        model_data = json.loads(script.get_attribute("innerHTML"))
        glb_url = model_data.get("url")
    except Exception:
        glb_url = None

    product_name = title
    color = ""
    dimensions = {}

    for product in parse_json_ld(page_source):
        product_name = product.get("name") or product_name
        color = product.get("color") or color
        dimensions.update(extract_dimensions_from_text(json.dumps(product, ensure_ascii=False)))

    try:
        dimension_text = driver.find_element(By.CSS_SELECTOR, ".pip-product-dimensions").text
        dimensions.update(extract_dimensions_from_text(dimension_text))
    except Exception:
        pass

    return {
        "name": product_name,
        "color": color,
        "dimensions": dimensions,
        "product_url": product_url,
        "glb_url": glb_url,
    }


def download_file(url, destination):
    response = requests.get(url, stream=True, timeout=60)
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


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    driver = get_chrome_driver()
    downloaded = []

    try:
        product_links = collect_product_links(driver, SOFA_CATEGORY_URL)
        print(f"Found {len(product_links)} candidate sofa product links.", flush=True)

        for product_url in product_links:
            if len(downloaded) >= TARGET_COUNT:
                break

            try:
                details = extract_product_details(driver, product_url)
            except TimeoutException:
                print(f"Timed out: {product_url}", flush=True)
                continue
            except Exception as exc:
                print(f"Failed to inspect {product_url}: {exc}", flush=True)
                continue

            if not details["glb_url"]:
                print(f"No GLB model: {details['name']} ({product_url})", flush=True)
                continue

            index = len(downloaded) + 1
            filename = f"{index:02d} - {safe_filename(details['name'])}.glb"
            destination = OUTPUT_DIR / filename

            if not destination.exists():
                print(f"Downloading {index}/{TARGET_COUNT}: {details['name']}", flush=True)
                download_file(details["glb_url"], destination)
            else:
                print(f"Already exists: {destination}", flush=True)

            downloaded.append(
                {
                    "index": index,
                    "name": details["name"],
                    "color": details["color"],
                    "dimensions": details["dimensions"],
                    "filename": str(destination),
                    "product_url": details["product_url"],
                    "glb_url": details["glb_url"],
                }
            )
            write_metadata(downloaded)

        print(f"Downloaded {len(downloaded)} sofa GLB files.", flush=True)
        print(f"Metadata CSV: {METADATA_CSV}", flush=True)
        print(f"Metadata JSON: {METADATA_JSON}", flush=True)
    finally:
        driver.quit()


if __name__ == "__main__":
    main()

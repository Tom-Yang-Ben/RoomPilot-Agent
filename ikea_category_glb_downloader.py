import csv
import html
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import unquote, urljoin

import requests
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from tqdm import tqdm
from webdriver_manager.chrome import ChromeDriverManager


IKEA_SITES = {
    "fi": {
        "label": "芬蘭",
        "base_url": "https://www.ikea.com/fi/en",
    },
    "jp": {
        "label": "日本",
        "base_url": "https://www.ikea.com/jp/en",
    },
}
DEFAULT_IKEA_SITE = "fi"
IKEA_SITE_BASE = IKEA_SITES[DEFAULT_IKEA_SITE]["base_url"]
OUTPUT_ROOT = Path("downloaded-files")
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

CATEGORY_GROUPS = {
    "bookcases": {
        "label": "書櫃 / 層架",
        "items": {
            "bookcases": ("書櫃", "bookcases-10382"),
            "shelving-units": ("層架 / 置物架", "shelving-units-10397"),
            "wall-shelves": ("壁架", "wall-shelves-10398"),
        },
    },
    "sofas": {
        "label": "沙發",
        "items": {
            "sofas": ("全部沙發", "sofas-fu003"),
            "fabric-sofas": ("布沙發", "fabric-sofas-10661"),
            "leather-sofas": ("皮沙發 / 仿皮沙發", "leather-coated-fabric-sofas-10662"),
            "sofa-beds": ("沙發床", "sofa-beds-10663"),
            "modular-sofas": ("模組沙發", "modular-sofas-31786"),
            "armchairs": ("扶手椅", "armchairs-16239"),
        },
    },
    "chairs": {
        "label": "椅子 / 扶手椅 / 凳子",
        "items": {
            "chairs": ("全部椅子", "tables-chairs-fu002"),
            "dining-chairs": ("餐椅", "dining-chairs-25219"),
            "office-chairs": ("辦公椅", "office-chairs-20652"),
            "armchairs": ("扶手椅", "armchairs-16239"),
            "stools-benches": ("凳子 / 長凳", "stools-benches-16244"),
            "gaming-chairs": ("電競椅", "gaming-chairs-47067"),
        },
    },
    "tables": {
        "label": "桌子 / 書桌",
        "items": {
            "tables": ("全部桌子", "tables-desks-fu004"),
            "dining-tables": ("餐桌", "dining-tables-21825"),
            "desks": ("書桌 / 電腦桌", "desks-20649"),
            "coffee-tables": ("茶几", "coffee-tables-10705"),
            "bedside-tables": ("床邊桌", "bedside-tables-20656"),
            "bar-tables": ("吧台桌", "bar-tables-20862"),
        },
    },
    "beds": {
        "label": "床 / 床架",
        "items": {
            "beds": ("全部床具", "beds-bm003"),
            "bed-frames": ("床架", "beds-16284"),
            "sofa-beds": ("沙發床", "sofa-beds-10663"),
            "mattresses": ("床墊", "mattresses-bm002"),
            "bedside-tables": ("床邊桌", "bedside-tables-20656"),
        },
    },
    "wardrobes": {
        "label": "衣櫃",
        "items": {
            "wardrobes": ("全部衣櫃", "wardrobes-19053"),
            "pax-wardrobes": ("PAX 衣櫃系統", "pax-wardrobes-19086"),
            "open-wardrobes": ("開放式衣櫃", "open-wardrobes-11480"),
            "clothes-racks": ("衣架 / 掛衣架", "clothes-stands-shoe-racks-10456"),
        },
    },
    "rugs": {
        "label": "地毯",
        "items": {
            "rugs": ("全部地毯", "rugs-10653"),
            "large-medium-rugs": ("大型 / 中型地毯", "large-medium-rugs-10654"),
            "small-rugs": ("小地毯", "small-rugs-10659"),
            "door-mats": ("門墊", "door-mats-10656"),
        },
    },
    "table-lamps": {
        "label": "桌燈 / 燈具",
        "items": {
            "table-lamps": ("桌燈", "table-lamps-10732"),
            "floor-lamps": ("立燈", "floor-lamps-10731"),
            "work-lamps": ("工作燈", "work-lamps-20502"),
            "lamp-shades-bases": ("燈罩 / 燈座", "lamp-shades-bases-cords-10728"),
        },
    },
    "cabinets": {
        "label": "櫃子 / 收納系統",
        "items": {
            "cabinets": ("全部收納系統", "storage-solution-systems-46052"),
            "cabinets-cupboards": ("櫃子 / 碗櫃", "cabinets-cupboards-10409"),
            "tv-benches": ("電視櫃", "tv-benches-10810"),
            "chests-of-drawers": ("抽屜櫃", "chests-of-drawers-10451"),
            "sideboards": ("餐邊櫃 / 玄關桌", "sideboards-buffets-console-tables-30454"),
        },
    },
}

CATEGORY_PRESETS = {
    category_key: category_path
    for group in CATEGORY_GROUPS.values()
    for category_key, (_, category_path) in group["items"].items()
}

FURNITURE_INPUT_EXAMPLES = [
    (group_key, group_data["label"])
    for group_key, group_data in CATEGORY_GROUPS.items()
]

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def safe_filename(value, fallback="ikea-model"):
    """把商品名稱轉成安全的檔名，避免 Windows 不允許的特殊字元。"""
    value = re.sub(r'[<>:"/\\|?*]', "", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value[:160] or fallback


def slugify(value):
    """把使用者輸入的家具類別轉成可用於網址與資料夾名稱的格式。"""
    value = value.lower().strip()
    value = re.sub(r"https?://", "", value)
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")[:80] or "ikea-category"


def decode_page(text):
    """解碼網頁內容，讓被跳脫或 URL 編碼的文字可以被搜尋。"""
    return html.unescape(unquote(text))


def get_chrome_driver():
    """建立無頭 Chrome 瀏覽器，用來讀取 IKEA 動態載入的分類頁與商品頁。"""
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
    driver.set_page_load_timeout(40)
    return driver


def category_name_from_url(url):
    """從 IKEA 分類頁網址中取出類別名稱，作為輸出資料夾名稱。"""
    match = re.search(r"/cat/([^/?#]+)/?", url)
    if match:
        return slugify(match.group(1))
    return slugify(url)


def choose_site():
    """詢問要搜尋哪個 IKEA 國家站。"""
    print("請選擇 IKEA 網站：")
    for key, site in IKEA_SITES.items():
        default_note = "（預設）" if key == DEFAULT_IKEA_SITE else ""
        print(f"  {key:<3} = {site['label']} - {site['base_url']}{default_note}")

    raw_site = input("\n請輸入網站代碼，或貼上 IKEA 網址：").strip()
    if not raw_site:
        raw_site = DEFAULT_IKEA_SITE

    site_key = slugify(raw_site)
    if raw_site.startswith("http://") or raw_site.startswith("https://"):
        return slugify(raw_site), raw_site.rstrip("/")
    if site_key not in IKEA_SITES:
        valid_sites = ", ".join(IKEA_SITES)
        raise ValueError(f"找不到這個 IKEA 網站：{raw_site}。請輸入其中一個：{valid_sites}")
    return site_key, IKEA_SITES[site_key]["base_url"]


def category_url_from_key(site_base, category_key):
    category_path = CATEGORY_PRESETS.get(category_key, category_key)
    return f"{site_base}/cat/{category_path}/"


def print_category_menu():
    """列出家具大分類與細分類，方便使用者選擇更精準的搜尋範圍。"""
    print("\n可輸入的家具分類與細分類（英文代碼 = 中文家具名稱）：")
    for group_key, group_data in CATEGORY_GROUPS.items():
        print(f"\n  {group_key:<16} = {group_data['label']}")
        for item_key, (item_label, _) in group_data["items"].items():
            prefix = "*" if item_key == group_key else "-"
            print(f"    {prefix} {item_key:<18} = {item_label}")


def choose_category(site_key, site_base):
    """詢問要搜尋哪個家具分類。"""
    print(f"\n目前搜尋的 IKEA 網站：{site_key} ({site_base})")
    print_category_menu()
    print("\n提示：左邊英文代碼是你要輸入的內容，右邊中文是家具種類說明。")
    print("輸入大分類會搜尋整個大分類；輸入細分類會更精準。")
    print("你也可以直接貼上完整的 IKEA 分類網址。")

    raw_category = input("\n請輸入家具分類或細分類英文代碼：").strip()
    if not raw_category:
        raise ValueError("家具分類不能空白。")

    if raw_category.startswith("http://") or raw_category.startswith("https://"):
        category_url = raw_category
        category_name = f"{site_key}-{category_name_from_url(raw_category)}"
    else:
        category_key = slugify(raw_category)
        category_url = category_url_from_key(site_base, category_key)
        if category_key not in CATEGORY_PRESETS:
            print(f"找不到預設分類，改試這個分類網址：{category_url}")
        category_name = f"{site_key}-{category_key}"

    return category_name, category_url


def ask_target_count():
    """詢問使用者想下載幾個 GLB 模型，並檢查輸入是否為正整數。"""
    raw_count = input("請輸入要下載幾個 GLB 模型：").strip()
    try:
        count = int(raw_count)
    except ValueError as exc:
        raise ValueError("下載數量必須是整數。") from exc
    if count <= 0:
        raise ValueError("下載數量必須大於 0。")
    return count


def collect_product_links(driver, category_url, target_count, site_base):
    """開啟分類頁並捲動頁面，收集商品頁連結。"""
    print(f"\n正在開啟分類頁：{category_url}", flush=True)
    try:
        driver.get(category_url)
    except TimeoutException:
        print("分類頁載入逾時，會繼續使用目前已載入的內容。", flush=True)

    WebDriverWait(driver, 30).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "body"))
    )

    links = []
    seen = set()
    last_height = 0
    stable_scrolls = 0
    desired_candidates = max(target_count * 25, target_count + 80)

    while len(links) < desired_candidates:
        anchors = driver.find_elements(
            By.CSS_SELECTOR,
            ".plp-fragment-wrapper a.plp-product__image-link, a[href*='/p/']",
        )
        for anchor in anchors:
            href = anchor.get_attribute("href")
            if not href or "/p/" not in href:
                continue
            clean_url = urljoin(site_base, href).split("?")[0]
            if clean_url not in seen:
                seen.add(clean_url)
                links.append(clean_url)

        print(f"已收集 {len(links)} 個商品連結...", flush=True)

        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            stable_scrolls += 1
        else:
            stable_scrolls = 0
        if stable_scrolls >= 5:
            break
        last_height = new_height

    return links


def fetch_product_page_with_requests(product_url):
    """用 requests 直接下載商品頁 HTML，速度比開瀏覽器快。"""
    response = requests.get(product_url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    return response.text


def find_glb_urls(text):
    """從 HTML 或 JSON 字串中找出 IKEA 3D 模型的 GLB 下載網址。"""
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
    """從商品頁的 title 標籤取得商品名稱。"""
    match = re.search(r"<title>(.*?)</title>", text, flags=re.I | re.S)
    if not match:
        return "IKEA product"
    title = html.unescape(re.sub(r"\s+", " ", match.group(1))).strip()
    return title.replace(" - IKEA", "")


def parse_json_ld(text):
    """解析商品頁中的 JSON-LD 結構化資料，取得商品資訊。"""
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
    """從商品文字中擷取寬、深、高、座位尺寸或承重等尺寸資訊。"""
    decoded = html.unescape(re.sub(r"<[^>]+>", " ", text))
    decoded = re.sub(r"\s+", " ", decoded)
    dimensions = {}
    labels = (
        "Width",
        "Depth",
        "Height",
        "Seat width",
        "Seat depth",
        "Seat height",
        "Max. load/shelf",
    )
    for label in labels:
        match = re.search(
            rf"{re.escape(label)}\s*[: ]\s*([0-9.,]+\s*(?:cm|mm|m|kg|lb|in|\"))",
            decoded,
            flags=re.I,
        )
        if match:
            key = label.lower().replace(". ", "_").replace(" ", "_")
            dimensions[key] = match.group(1)
    return dimensions


def details_from_page_text(text, product_url, glb_url):
    """把商品頁內容整理成統一格式，包含名稱、顏色、尺寸、商品網址與 GLB 網址。"""
    product_name = page_title(text)
    color = ""
    dimensions = extract_dimensions_from_text(text)

    for product in parse_json_ld(text):
        product_name = product.get("name") or product_name
        color = product.get("color") or color
        dimensions.update(extract_dimensions_from_text(json.dumps(product, ensure_ascii=False)))

    return {
        "name": product_name,
        "color": color,
        "dimensions": dimensions,
        "product_url": product_url,
        "glb_url": glb_url,
    }


def extract_product_details(driver, product_url):
    """取得單一商品的完整資訊；先用 requests，找不到 GLB 時再改用瀏覽器。"""
    try:
        text = fetch_product_page_with_requests(product_url)
        glb_urls = find_glb_urls(text)
        if glb_urls:
            return details_from_page_text(text, product_url, glb_urls[0])
    except Exception as exc:
        print(f"用 requests 檢查失敗，改用瀏覽器檢查：{exc}", flush=True)

    try:
        driver.get(product_url)
    except TimeoutException:
        print(f"商品頁載入逾時，會繼續使用目前已載入的內容：{product_url}", flush=True)

    WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.TAG_NAME, "title")))
    text = driver.page_source
    glb_url = None

    try:
        script = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.ID, "pip-xr-viewer-model"))
        )
        model_data = json.loads(script.get_attribute("innerHTML"))
        glb_url = model_data.get("url")
    except Exception:
        glb_urls = find_glb_urls(text)
        glb_url = glb_urls[0] if glb_urls else None

    return details_from_page_text(text, product_url, glb_url)


def download_file(url, destination):
    """串流下載 GLB 檔案，並顯示下載進度。"""
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


def metadata_paths(output_dir, category_name):
    """依照輸出資料夾與家具類別，產生 CSV 與 JSON metadata 檔案路徑。"""
    base_name = safe_filename(category_name, "ikea-category")
    return (
        output_dir / f"{base_name}_glb_metadata.csv",
        output_dir / f"{base_name}_glb_metadata.json",
    )


def load_existing_metadata(metadata_json):
    """讀取已存在的 metadata，讓程式可以接續下載並避免重複。"""
    if not metadata_json.exists():
        return []
    with metadata_json.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return metadata_rows_from_project(data)
    return []


def metadata_rows_from_project(data):
    """從新版專案 JSON 取回家具列資料，讓程式可以接續下載。"""
    rows = []
    for item in data.get("scene", {}).get("objects", []):
        source = item.get("source", {})
        rows.append(
            {
                "index": source.get("index") or parse_object_index(item.get("id")),
                "name": item.get("name", ""),
                "color": item.get("color", ""),
                "dimensions": source.get("dimensions") or item.get("size_cm", {}),
                "filename": item.get("glb_path", ""),
                "product_url": source.get("product_url", ""),
                "glb_url": source.get("glb_url", ""),
            }
        )
    return rows


def parse_object_index(object_id):
    match = re.search(r"(\d+)$", object_id or "")
    return int(match.group(1)) if match else 0


def dimension_to_cm(value):
    if isinstance(value, (int, float)):
        return round(float(value), 2)
    match = re.search(r"([0-9]+(?:[.,][0-9]+)?)\s*(cm|mm|m|in|\"|kg|lb)?", str(value), flags=re.I)
    if not match:
        return None
    number = float(match.group(1).replace(",", "."))
    unit = (match.group(2) or "cm").lower()
    if unit == "mm":
        return round(number / 10, 2)
    if unit == "m":
        return round(number * 100, 2)
    if unit in {"in", '"'}:
        return round(number * 2.54, 2)
    if unit in {"kg", "lb"}:
        return None
    return round(number, 2)


def size_cm_from_dimensions(dimensions):
    return {
        "width": dimension_to_cm(dimensions.get("width", "")),
        "depth": dimension_to_cm(dimensions.get("depth", "")),
        "height": dimension_to_cm(dimensions.get("height", "")),
    }


def furniture_type_from_category(category_name):
    category = category_name.split("-", 1)[-1]
    return category.rstrip("s") or "furniture"


def build_scene_object(row, category_name):
    index = row.get("index") or 0
    dimensions = row.get("dimensions") or {}
    size_cm = size_cm_from_dimensions(dimensions)
    return {
        "id": f"furn_{int(index):03d}" if index else "furn_000",
        "sku": f"IKEA_{int(index):03d}" if index else "IKEA_000",
        "name": row.get("name", ""),
        "type": furniture_type_from_category(category_name),
        "position": [0, 0],
        "rotation": 0,
        "size_cm": size_cm,
        "collision_box_cm": size_cm,
        "glb_path": row.get("filename", ""),
        "material": "",
        "color": row.get("color", ""),
        "can_rotate": True,
        "must_against_wall": False,
        "source": {
            "index": index,
            "dimensions": dimensions,
            "product_url": row.get("product_url", ""),
            "glb_url": row.get("glb_url", ""),
        },
    }


def build_project_metadata(rows, category_name, category_url, site_base, output_dir, metadata_csv, metadata_json):
    """輸出成接近 RoomPilot 專案資料的 JSON 結構。"""
    return {
        "project_id": slugify(category_name),
        "title": f"IKEA {category_name} GLB Dataset",
        "input_type": "ikea_category",
        "status": "draft",
        "user_input": {
            "style": "",
            "requirements": [
                "download_ikea_glb_models",
                "collect_product_metadata",
            ],
            "budget": None,
            "preferred_colors": [],
            "preferred_furniture": [category_name],
        },
        "floorplan": {
            "image_path": "",
            "width_cm": None,
            "depth_cm": None,
            "scale_ratio": "",
            "grid_size_cm": None,
            "walls": [],
            "doors": [],
            "windows": [],
        },
        "scene": {
            "mode": "ikea_glb_dataset",
            "objects": [build_scene_object(row, category_name) for row in rows],
        },
        "ai_plan": {
            "understanding": [],
            "recommendations": [],
        },
        "validation": {
            "passed": True,
            "issues": [],
        },
        "manual_adjustment": {
            "enabled": True,
            "actions": [
                "drag",
                "rotate",
                "resize_small_range",
                "text_tune",
            ],
        },
        "output": {
            "category_url": category_url,
            "site_base": site_base,
            "asset_dir": str(output_dir),
            "metadata_csv": str(metadata_csv),
            "metadata_json": str(metadata_json),
            "final_status": "draft",
        },
        "version": 1,
    }


def write_metadata(rows, metadata_csv, metadata_json, category_name, category_url, site_base, output_dir):
    """把已下載商品資料同時寫成 CSV 和 JSON。"""
    fieldnames = [
        "index",
        "name",
        "color",
        "dimensions",
        "filename",
        "product_url",
        "glb_url",
    ]
    with metadata_csv.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({**row, "dimensions": json.dumps(row["dimensions"], ensure_ascii=False)})

    with metadata_json.open("w", encoding="utf-8") as file:
        json.dump(
            build_project_metadata(rows, category_name, category_url, site_base, output_dir, metadata_csv, metadata_json),
            file,
            ensure_ascii=False,
            indent=2,
        )


def main():
    """主流程：詢問使用者輸入、收集商品、下載 GLB，最後輸出 metadata。"""
    site_key, site_base = choose_site()
    category_name, category_url = choose_category(site_key, site_base)
    target_count = ask_target_count()
    output_dir = OUTPUT_ROOT / slugify(category_name)
    metadata_csv, metadata_json = metadata_paths(output_dir, category_name)
    output_dir.mkdir(parents=True, exist_ok=True)

    downloaded = load_existing_metadata(metadata_json)
    seen_products = {row.get("product_url") for row in downloaded}
    seen_glbs = {row.get("glb_url") for row in downloaded}

    driver = get_chrome_driver()
    try:
        product_links = collect_product_links(driver, category_url, target_count, site_base)
        print(f"找到 {len(product_links)} 個候選商品連結。", flush=True)

        for product_url in product_links:
            if len(downloaded) >= target_count:
                break
            if product_url in seen_products:
                continue

            try:
                details = extract_product_details(driver, product_url)
            except Exception as exc:
                print(f"檢查商品失敗：{product_url}，原因：{exc}", flush=True)
                continue

            if not details["glb_url"]:
                print(f"沒有 GLB 模型：{details['name']} ({product_url})", flush=True)
                seen_products.add(product_url)
                continue
            if details["glb_url"] in seen_glbs:
                print(f"重複的 GLB，已略過：{details['name']} ({product_url})", flush=True)
                seen_products.add(product_url)
                continue

            index = len(downloaded) + 1
            filename = f"{index:02d} - {safe_filename(details['name'])}.glb"
            destination = output_dir / filename

            if not destination.exists():
                print(f"正在下載 {index}/{target_count}：{details['name']}", flush=True)
                download_file(details["glb_url"], destination)
            else:
                print(f"檔案已存在：{destination}", flush=True)

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
            write_metadata(downloaded, metadata_csv, metadata_json, category_name, category_url, site_base, output_dir)
            print(f"已儲存 metadata，目前共有 {len(downloaded)} 個 GLB 檔。", flush=True)

        write_metadata(downloaded, metadata_csv, metadata_json, category_name, category_url, site_base, output_dir)
        print(f"\n下載完成，目前共有 {len(downloaded)} 個 GLB 檔。", flush=True)
        print(f"輸出資料夾：{output_dir}", flush=True)
        print(f"Metadata CSV：{metadata_csv}", flush=True)
        print(f"Metadata JSON：{metadata_json}", flush=True)
    finally:
        driver.quit()


if __name__ == "__main__":
    main()

import argparse
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
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException
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
        "label": "Bookcases and shelving / 書櫃與層架",
        "items": {
            "bookcases": ("Bookcases / 書櫃", "bookcases-10382"),
            "shelving-units": ("Shelving units / 層架組", "shelving-units-10397"),
            "wall-shelves": ("Wall shelves / 壁架", "wall-shelves-10398"),
        },
    },
    "sofas": {
        "label": "Sofas and armchairs / 沙發與扶手椅",
        "items": {
            "sofas": ("All sofas / 所有沙發", "sofas-fu003"),
            "fabric-sofas": ("Fabric sofas / 布沙發", "fabric-sofas-10661"),
            "leather-sofas": (
                "Leather and coated fabric sofas / 皮革與塗層布沙發",
                "leather-coated-fabric-sofas-10662",
            ),
            "sofa-beds": ("Sofa beds / 沙發床", "sofa-beds-10663"),
            "modular-sofas": ("Modular sofas / 模組沙發", "modular-sofas-31786"),
            "armchairs": ("Armchairs / 扶手椅", "armchairs-16239"),
        },
    },
    "chairs": {
        "label": "Chairs, stools and benches / 椅子、凳子與長凳",
        "items": {
            "chairs": ("All chairs / 所有椅子", "tables-chairs-fu002"),
            "dining-chairs": ("Dining chairs / 餐椅", "dining-chairs-25219"),
            "office-chairs": ("Office and desk chairs / 辦公椅與書桌椅", "desk-chairs-20652"),
            "armchairs": ("Armchairs / 扶手椅", "armchairs-16239"),
            "stools-benches": ("Stools and benches / 凳子與長凳", "stools-benches-16244"),
            "gaming-chairs": ("Gaming chairs / 電競椅", "gaming-chairs-47067"),
        },
    },
    "tables": {
        "label": "Tables and desks / 桌子與書桌",
        "items": {
            "tables": ("All tables and desks / 所有桌子與書桌", "tables-desks-fu004"),
            "dining-tables": ("Dining tables / 餐桌", "dining-tables-21825"),
            "desks": ("Desks and computer desks / 書桌與電腦桌", "desks-computer-desks-20649"),
            "coffee-tables": ("Coffee tables / 咖啡桌、茶几", "coffee-tables-10705"),
            "bedside-tables": ("Bedside tables / 床邊桌", "bedside-tables-20656"),
            "bar-tables": ("Bar tables / 吧台桌", "bar-tables-20862"),
        },
    },
    "beds": {
        "label": "Beds and mattresses / 床與床墊",
        "items": {
            "beds": ("All beds / 所有床", "beds-bm003"),
            "bed-frames": ("Bed frames / 床架", "beds-16284"),
            "sofa-beds": ("Sofa beds / 沙發床", "sofa-beds-10663"),
            "mattresses": ("Mattresses / 床墊", "mattresses-bm002"),
            "bedside-tables": ("Bedside tables / 床邊桌", "bedside-tables-20656"),
        },
    },
    "wardrobes": {
        "label": "Wardrobes and clothes storage / 衣櫃與衣物收納",
        "items": {
            "wardrobes": ("All wardrobes / 所有衣櫃", "wardrobes-19053"),
            "pax-wardrobes": ("PAX wardrobes / PAX 衣櫃", "pax-wardrobes-19086"),
            "open-wardrobes": ("Open wardrobes / 開放式衣櫃", "open-wardrobes-11480"),
            "clothes-racks": ("Clothes racks and shoe racks / 衣架與鞋架", "clothes-stands-shoe-racks-10456"),
            "shoe-cabinets": ("Shoe cabinets / 鞋櫃", "shoe-cabinets-10456"),
        },
    },
    "storage-furniture": {
        "label": "Storage furniture / 收納家具",
        "items": {
            "storage-furniture": ("All storage furniture / 所有收納家具", "storage-furniture-st001"),
            "storage-solution-systems": ("Storage solution systems / 收納系統", "storage-solution-systems-46052"),
            "cabinets-cupboards": ("Cabinets and cupboards / 櫃子與櫥櫃", "cabinets-cupboards-st003"),
            "display-cabinets": ("Display cabinets / 展示櫃", "display-cabinets-10410"),
            "chests-of-drawers": (
                "Chests of drawers and drawer units / 抽屜櫃與抽屜組",
                "chest-of-drawers-drawer-units-st004",
            ),
            "sideboards": (
                "Sideboards, buffets and console tables / 邊櫃、餐邊櫃與玄關桌",
                "sideboards-buffets-console-tables-30454",
            ),
            "trolleys": ("Trolleys / 推車", "trolleys-fu005"),
            "room-dividers": ("Room dividers / 屏風、空間隔間", "room-dividers-46080"),
        },
    },
    "tv-media-furniture": {
        "label": "TV and media furniture / 電視與影音家具",
        "items": {
            "tv-media-furniture": ("All TV and media furniture / 所有電視與影音家具", "tv-media-furniture-10475"),
            "tv-benches": ("TV benches / 電視櫃", "tv-benches-10810"),
        },
    },
    "outdoor-furniture": {
        "label": "Outdoor furniture / 戶外家具",
        "items": {
            "outdoor-furniture": ("All outdoor furniture / 所有戶外家具", "garden-furniture-od003"),
            "outdoor-seating": ("Outdoor seating / 戶外座椅", "outdoor-seating-700350"),
            "outdoor-dining": ("Outdoor dining / 戶外餐桌椅", "outdoor-dining-700351"),
            "sun-loungers-hammocks": ("Sun loungers and hammocks / 躺椅與吊床", "sun-loungers-hammocks-21963"),
            "outdoor-coffee-side-tables": (
                "Outdoor coffee and side tables / 戶外咖啡桌與邊桌",
                "garden-coffee-side-tables-700192",
            ),
        },
    },
    "childrens-furniture": {
        "label": "Children's furniture / 兒童家具",
        "items": {
            "childrens-furniture": (
                "Children's small furniture / 兒童小型家具",
                "childrens-small-furniture-18767",
            ),
            "kids-chairs-stools": ("Kids chairs and stools / 兒童椅與凳子", "kids-chairs-stools-18769"),
            "childrens-tables": ("Children's tables / 兒童桌", "childrens-tables-18768"),
            "childrens-stools-benches": (
                "Children's stools and benches / 兒童凳與長凳",
                "childrens-stools-benches-45816",
            ),
            "kids-armchairs": ("Kids armchairs / 兒童扶手椅", "kids-armchairs-20483"),
        },
    },
    "mirrors": {
        "label": "Mirrors / 鏡子",
        "items": {
            "mirrors": ("All mirrors / 所有鏡子", "mirrors-20489"),
            "wall-mirrors": ("Wall mirrors / 壁鏡", "wall-mirrors-20490"),
            "large-mirrors": ("Large mirrors / 大型鏡子", "large-mirrors-24858"),
            "standing-mirrors": ("Standing mirrors / 立鏡", "standing-mirrors-20491"),
            "mirror-cabinets": ("Mirror cabinets / 鏡櫃", "mirror-cabinets-20820"),
        },
    },
    "rugs": {
        "label": "Rugs and mats / 地毯與踏墊",
        "items": {
            "rugs": ("All rugs / 所有地毯", "rugs-10653"),
            "large-medium-rugs": ("Large and medium rugs / 大型與中型地毯", "large-medium-rugs-10692"),
            "runner-small-rugs": ("Runners and small rugs / 走道毯與小地毯", "runner-small-rugs-10689"),
            "round-rugs": ("Round rugs / 圓形地毯", "round-rugs-20543"),
            "outdoor-rugs": ("Outdoor rugs / 戶外地毯", "outdoor-rugs-34204"),
            "door-mats": ("Door mats / 門墊", "door-mats-10698"),
            "handmade-rugs": ("Handmade rugs / 手工地毯", "handmade-rugs-39267"),
            "anti-slip-rug-underlays": (
                "Anti-slip and rug underlays / 止滑墊與地毯底墊",
                "anti-slip-rug-underlays-10699",
            ),
            "sheepskins-cowhides": (
                "Cowhides, sheepskins and faux fur rugs / 牛皮、羊皮與仿毛地毯",
                "sheepskins-cowhides-20544",
            ),
            "childrens-rugs-curtains": (
                "Children's rugs and curtains / 兒童地毯與窗簾",
                "childrens-rugs-curtains-18774",
            ),
            "nursery-rugs-and-curtains": (
                "Nursery rugs and curtains / 嬰幼兒房地毯與窗簾",
                "nursery-rugs-and-curtains-18699",
            ),
        },
    },
    "lamps": {
        "label": "Lighting / 燈具",
        "items": {
            "lamps": ("All lamps / 所有燈具", "lamps-li002"),
            "table-lamps": ("Table lamps / 桌燈", "table-lamps-10732"),
            "floor-lamps": ("Floor lamps / 立燈", "floor-lamps-10731"),
            "work-lamps": ("Work lamps / 工作燈", "work-lamps-20502"),
            "lamp-shades-bases": (
                "Lamp shades, bases and cords / 燈罩、燈座與電線",
                "lamp-shades-bases-cords-10728",
            ),
        },
    },
    "decor-small-storage": {
        "label": "Decor and small storage / 裝飾與小型收納",
        "items": {
            "decoration": ("All decor and small storage / 所有裝飾與小型收納", "decoration-de001"),
            "storage-boxes-baskets": (
                "Storage boxes and baskets / 收納盒與籃子",
                "storage-boxes-baskets-10550",
            ),
            "flower-pots-planters": (
                "Flower pots and planters / 花盆與植栽盆",
                "flower-pots-planters-pp004",
            ),
        },
    },
}

CATEGORY_PRESETS = {
    category_key: category_path
    for group in CATEGORY_GROUPS.values()
    for category_key, (_, category_path) in group["items"].items()
}

PROJECT_JSON_KEYS = [
    "project_id",
    "title",
    "input_type",
    "status",
    "user_input",
    "floorplan",
    "scene",
    "ai_plan",
    "validation",
    "manual_adjustment",
    "output",
    "version",
]
SCENE_OBJECT_KEYS = [
    "id",
    "sku",
    "name",
    "type",
    "position",
    "rotation",
    "size_cm",
    "collision_box_cm",
    "glb_path",
    "material",
    "color",
    "can_rotate",
    "must_against_wall",
]
USER_INPUT_KEYS = ["style", "requirements", "budget", "preferred_colors", "preferred_furniture"]
FLOORPLAN_KEYS = [
    "image_path",
    "width_cm",
    "depth_cm",
    "scale_ratio",
    "grid_size_cm",
    "walls",
    "doors",
    "windows",
]
SCENE_KEYS = ["mode", "objects"]
AI_PLAN_KEYS = ["understanding", "recommendations"]
VALIDATION_KEYS = ["passed", "issues"]
MANUAL_ADJUSTMENT_KEYS = ["enabled", "actions"]
OUTPUT_KEYS = ["preview_2d", "preview_3d", "report", "final_status"]

STORAGE_FURNITURE_CATEGORIES = [
    ("storage-solution-systems", "Storage solution systems", "storage-solution-systems-46052"),
    ("cabinets-cupboards", "Cabinets and cupboards", "cabinets-cupboards-st003"),
    ("display-cabinets", "Display cabinets", "display-cabinets-10410"),
    ("chests-of-drawers", "Chests of drawers and drawer units", "chest-of-drawers-drawer-units-st004"),
    ("sideboards", "Sideboards, buffets and console tables", "sideboards-buffets-console-tables-30454"),
    ("trolleys", "Trolleys", "trolleys-fu005"),
    ("room-dividers", "Room dividers", "room-dividers-46080"),
    ("storage-furniture", "All storage furniture", "storage-furniture-st001"),
]

for storage_key, _, storage_path in STORAGE_FURNITURE_CATEGORIES:
    CATEGORY_PRESETS[storage_key] = storage_path

FURNITURE_GROUP_NAMES = {
    "bookcases": "Bookcases and shelving",
    "sofas": "Sofas and armchairs",
    "chairs": "Chairs stools and benches",
    "tables": "Tables and desks",
    "beds": "Beds and mattresses",
    "wardrobes": "Wardrobes and clothes storage",
    "storage-furniture": "Storage furniture",
    "rugs": "Rugs and mats",
    "lamps": "Lighting",
    "tv-media-furniture": "TV and media furniture",
    "outdoor-furniture": "Outdoor furniture",
    "childrens-furniture": "Children's furniture",
    "decor-small-storage": "Decor and small storage",
    "mirrors": "Mirrors",
}

GROUP_TOTAL_CATEGORY_KEYS = {
    "bookcases": "bookcases",
    "decor-small-storage": "decoration",
}

GROUP_SKIP_CATEGORY_KEYS = {
    "chairs": {"armchairs"},
    "beds": {"sofa-beds", "bedside-tables"},
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


def collect_product_links(driver, category_url, target_count, site_base, deadline=None):
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
    desired_candidates = None if target_count is None else max(target_count * 25, target_count + 80)

    while desired_candidates is None or len(links) < desired_candidates:
        if deadline is not None and time.monotonic() >= deadline:
            print("Category search timeout reached while collecting product links.", flush=True)
            break
        anchors = driver.find_elements(
            By.CSS_SELECTOR,
            ".plp-fragment-wrapper a.plp-product__image-link, a[href*='/p/']",
        )
        for anchor in anchors:
            try:
                href = anchor.get_attribute("href")
            except StaleElementReferenceException:
                continue
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


def download_file(url, destination, attempts=3):
    """串流下載 GLB 檔案，並顯示下載進度。"""
    destination.parent.mkdir(parents=True, exist_ok=True)
    response = None
    for attempt in range(1, attempts + 1):
        try:
            response = requests.get(url, headers=HEADERS, stream=True, timeout=60)
            response.raise_for_status()
            break
        except requests.RequestException:
            if response is not None:
                response.close()
            if attempt >= attempts:
                raise
            time.sleep(attempt * 2)
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


def load_existing_metadata(metadata_json, metadata_csv=None):
    """讀取已存在的 metadata，讓程式可以接續下載並避免重複。"""
    if metadata_csv is not None and metadata_csv.exists():
        rows = []
        with metadata_csv.open("r", encoding="utf-8-sig", newline="") as file:
            for row in csv.DictReader(file):
                try:
                    dimensions = json.loads(row.get("dimensions") or "{}")
                except json.JSONDecodeError:
                    dimensions = {}
                rows.append(
                    {
                        "index": int(row.get("index") or len(rows) + 1),
                        "name": row.get("name", ""),
                        "color": row.get("color", ""),
                        "dimensions": dimensions,
                        "filename": row.get("filename", ""),
                        "product_url": row.get("product_url", ""),
                        "glb_url": row.get("glb_url", ""),
                    }
                )
        if rows:
            return rows
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
        rows.append(
            {
                "index": parse_object_index(item.get("id")),
                "name": item.get("name", ""),
                "color": item.get("color", ""),
                "dimensions": item.get("size_cm", {}),
                "filename": item.get("glb_path", ""),
                "product_url": "",
                "glb_url": "",
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


def category_key_from_category_name(category_name):
    parts = category_name.split("-", 1)
    if len(parts) == 2 and parts[0] in IKEA_SITES:
        return parts[1]
    return category_name


def furniture_group_from_category_key(category_key):
    storage_keys = {item_key for item_key, _, _ in STORAGE_FURNITURE_CATEGORIES}
    if category_key in storage_keys:
        return "Storage furniture"
    for group_key, group_data in CATEGORY_GROUPS.items():
        if category_key in group_data.get("items", {}):
            return FURNITURE_GROUP_NAMES.get(group_key, group_key.replace("-", " ").title())
    return category_key.replace("-", " ").title()


def build_scene_object(row, category_name):
    index = row.get("index") or 0
    category_key = category_key_from_category_name(category_name)
    furniture_group = furniture_group_from_category_key(category_key)
    dimensions = row.get("dimensions") or {}
    size_cm = size_cm_from_dimensions(dimensions)
    return {
        "id": f"{furniture_group}_{int(index):03d}" if index else f"{furniture_group}_000",
        "sku": f"{category_key}_{int(index)}" if index else f"{category_key}_0",
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
    }


def build_project_metadata(rows, category_name, category_url, site_base, output_dir, metadata_csv, metadata_json):
    """輸出成接近 RoomPilot 專案資料的 JSON 結構。"""
    return {
        "project_id": slugify(category_name),
        "title": f"IKEA {category_name} GLB Dataset",
        "input_type": "floorplan",
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
            "mode": "2d_to_3d",
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
            "preview_2d": "",
            "preview_3d": "",
            "report": "",
            "final_status": "draft",
        },
        "version": 1,
    }


def validate_project_metadata_schema(data):
    if list(data.keys()) != PROJECT_JSON_KEYS:
        raise ValueError(f"Project JSON keys changed: {list(data.keys())}")
    if list(data.get("user_input", {}).keys()) != USER_INPUT_KEYS:
        raise ValueError(f"User input JSON keys changed: {list(data.get('user_input', {}).keys())}")
    if list(data.get("floorplan", {}).keys()) != FLOORPLAN_KEYS:
        raise ValueError(f"Floorplan JSON keys changed: {list(data.get('floorplan', {}).keys())}")
    if list(data.get("scene", {}).keys()) != SCENE_KEYS:
        raise ValueError(f"Scene JSON keys changed: {list(data.get('scene', {}).keys())}")
    if list(data.get("ai_plan", {}).keys()) != AI_PLAN_KEYS:
        raise ValueError(f"AI plan JSON keys changed: {list(data.get('ai_plan', {}).keys())}")
    if list(data.get("validation", {}).keys()) != VALIDATION_KEYS:
        raise ValueError(f"Validation JSON keys changed: {list(data.get('validation', {}).keys())}")
    if list(data.get("manual_adjustment", {}).keys()) != MANUAL_ADJUSTMENT_KEYS:
        raise ValueError(
            f"Manual adjustment JSON keys changed: {list(data.get('manual_adjustment', {}).keys())}"
        )
    if list(data.get("output", {}).keys()) != OUTPUT_KEYS:
        raise ValueError(f"Output JSON keys changed: {list(data.get('output', {}).keys())}")
    for item in data.get("scene", {}).get("objects", []):
        if list(item.keys()) != SCENE_OBJECT_KEYS:
            raise ValueError(f"Scene object JSON keys changed: {list(item.keys())}")
    return data


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

    project_metadata = validate_project_metadata_schema(
        build_project_metadata(rows, category_name, category_url, site_base, output_dir, metadata_csv, metadata_json)
    )
    with metadata_json.open("w", encoding="utf-8") as file:
        json.dump(project_metadata, file, ensure_ascii=False, indent=2)


def load_registry(registry_path):
    if not registry_path.exists():
        return {"version": 1, "items": []}
    with registry_path.open("r", encoding="utf-8-sig") as file:
        data = json.load(file)
    if isinstance(data, dict) and isinstance(data.get("items"), list):
        return data
    return {"version": 1, "items": []}


def save_registry(registry, registry_path):
    registry["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    with registry_path.open("w", encoding="utf-8") as file:
        json.dump(registry, file, ensure_ascii=False, indent=2)


def registry_sets(registry):
    product_urls = set()
    glb_urls = set()
    for item in registry.get("items", []):
        if item.get("product_url"):
            product_urls.add(item["product_url"])
        if item.get("glb_url"):
            glb_urls.add(item["glb_url"])
    return product_urls, glb_urls


def add_registry_item(registry, row, category_name):
    _, glb_urls = registry_sets(registry)
    if row.get("glb_url") in glb_urls:
        return
    registry.setdefault("items", []).append(
        {
            "category": category_name,
            "name": row.get("name", ""),
            "filename": row.get("filename", ""),
            "product_url": row.get("product_url", ""),
            "glb_url": row.get("glb_url", ""),
        }
    )


def category_info(site_key, site_base, category_key):
    if category_key.startswith("http://") or category_key.startswith("https://"):
        category_url = category_key
        category_name = f"{site_key}-{category_name_from_url(category_key)}"
        return category_name, category_url
    clean_key = slugify(category_key)
    category_url = category_url_from_key(site_base, clean_key)
    category_name = f"{site_key}-{clean_key}"
    return category_name, category_url


def download_category(
    driver,
    site_key,
    site_base,
    category_key,
    target_count,
    output_root,
    registry=None,
    registry_path=None,
    category_timeout_seconds=600,
):
    category_name, category_url = category_info(site_key, site_base, category_key)
    output_dir = output_root / slugify(category_name)
    metadata_csv, metadata_json = metadata_paths(output_dir, category_name)
    output_dir.mkdir(parents=True, exist_ok=True)

    downloaded = load_existing_metadata(metadata_json, metadata_csv)
    seen_products = {row.get("product_url") for row in downloaded}
    seen_glbs = {row.get("glb_url") for row in downloaded}
    if registry is not None:
        registry_products, registry_glbs = registry_sets(registry)
        seen_products.update(registry_products)
        seen_glbs.update(registry_glbs)

    starting_count = len(downloaded)
    first_find_deadline = time.monotonic() + category_timeout_seconds
    product_links = collect_product_links(
        driver,
        category_url,
        target_count,
        site_base,
        deadline=first_find_deadline,
    )
    print(f"Found {len(product_links)} candidate product links for {category_name}.", flush=True)

    for product_url in product_links:
        if target_count is not None and len(downloaded) - starting_count >= target_count:
            break
        if len(downloaded) == starting_count and time.monotonic() >= first_find_deadline:
            print(f"No GLB found within {category_timeout_seconds} seconds for {category_name}; skipping.", flush=True)
            break
        if product_url in seen_products:
            continue

        try:
            details = extract_product_details(driver, product_url)
        except Exception as exc:
            print(f"Failed to inspect product {product_url}: {exc}", flush=True)
            continue

        if not details["glb_url"]:
            print(f"No GLB: {details['name']} ({product_url})", flush=True)
            seen_products.add(product_url)
            continue
        if details["glb_url"] in seen_glbs:
            print(f"Duplicate GLB skipped: {details['name']} ({product_url})", flush=True)
            seen_products.add(product_url)
            continue

        index = len(downloaded) + 1
        filename = f"{index:02d} - {safe_filename(details['name'])}.glb"
        destination = output_dir / filename

        if not destination.exists():
            print(f"Downloading {index}: {details['name']}", flush=True)
            try:
                download_file(details["glb_url"], destination)
            except requests.RequestException as exc:
                print(f"Failed to download GLB for {details['name']}: {exc}", flush=True)
                if destination.exists() and destination.stat().st_size == 0:
                    destination.unlink()
                continue
        else:
            print(f"File already exists: {destination}", flush=True)

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
        if registry is not None:
            add_registry_item(registry, row, category_name)
            if registry_path is not None:
                save_registry(registry, registry_path)
        write_metadata(downloaded, metadata_csv, metadata_json, category_name, category_url, site_base, output_dir)
        print(f"Saved metadata; category total is now {len(downloaded)} GLB files.", flush=True)

    write_metadata(downloaded, metadata_csv, metadata_json, category_name, category_url, site_base, output_dir)
    return {
        "category_name": category_name,
        "category_url": category_url,
        "output_dir": str(output_dir),
        "metadata_csv": str(metadata_csv),
        "metadata_json": str(metadata_json),
        "new_downloads": len(downloaded) - starting_count,
        "total_downloads": len(downloaded),
    }


def run_storage_batch(args):
    site = IKEA_SITES[args.site]
    output_root = Path(args.output_root)
    registry_path = output_root / f"{args.site}-storage-furniture-registry.json"
    registry = load_registry(registry_path)
    target_count = 1 if args.storage_sample else None

    driver = get_chrome_driver()
    results = []
    try:
        for category_key, category_label, _ in STORAGE_FURNITURE_CATEGORIES:
            print(f"\n=== {category_key}: {category_label} ===", flush=True)
            result = download_category(
                driver=driver,
                site_key=args.site,
                site_base=site["base_url"],
                category_key=category_key,
                target_count=target_count,
                output_root=output_root,
                registry=registry,
                registry_path=registry_path,
                category_timeout_seconds=args.category_timeout_seconds,
            )
            results.append(result)
            if args.storage_sample and result["new_downloads"] > 0:
                break
    finally:
        driver.quit()

    save_registry(registry, registry_path)
    return results


def group_batch_categories(group_key):
    if group_key not in CATEGORY_GROUPS:
        valid_groups = ", ".join(sorted(CATEGORY_GROUPS))
        raise ValueError(f"Unknown group '{group_key}'. Valid groups: {valid_groups}")

    group_data = CATEGORY_GROUPS[group_key]
    total_key = GROUP_TOTAL_CATEGORY_KEYS.get(group_key, group_key)
    child_items = []
    total_item = None
    skip_keys = GROUP_SKIP_CATEGORY_KEYS.get(group_key, set())
    for category_key, (category_label, category_path) in group_data["items"].items():
        if category_key in skip_keys:
            continue
        item = (category_key, category_label, category_path)
        if category_key == total_key:
            total_item = item
        else:
            child_items.append(item)

    if total_item is not None:
        child_items.append(total_item)
    return child_items


def run_group_batch(args, group_key):
    site = IKEA_SITES[args.site]
    output_root = Path(args.output_root)
    registry_path = output_root / f"{args.site}-{group_key}-registry.json"
    registry = load_registry(registry_path)

    driver = get_chrome_driver()
    results = []
    try:
        for category_key, category_label, _ in group_batch_categories(group_key):
            print(f"\n=== {category_key}: {category_label} ===", flush=True)
            result = download_category(
                driver=driver,
                site_key=args.site,
                site_base=site["base_url"],
                category_key=category_key,
                target_count=None,
                output_root=output_root,
                registry=registry,
                registry_path=registry_path,
                category_timeout_seconds=args.category_timeout_seconds,
            )
            results.append(result)
    finally:
        driver.quit()

    save_registry(registry, registry_path)
    return results


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Download IKEA category GLB files and metadata.")
    parser.add_argument("--site", default=DEFAULT_IKEA_SITE, choices=sorted(IKEA_SITES))
    parser.add_argument("--category", help="IKEA category key or full category URL.")
    parser.add_argument("--target-count", type=int, help="Maximum new GLB files to download.")
    parser.add_argument("--all", action="store_true", help="Download every GLB found in the category.")
    parser.add_argument("--group-batch", choices=sorted(CATEGORY_GROUPS), help="Download a category group, with the group total category last.")
    parser.add_argument("--storage-batch", action="store_true", help="Download storage furniture subcategories, then the all-storage category last.")
    parser.add_argument("--storage-sample", action="store_true", help="Download one storage furniture GLB and JSON sample.")
    parser.add_argument("--category-timeout-seconds", type=int, default=600)
    parser.add_argument("--output-root", default=str(OUTPUT_ROOT))
    return parser.parse_args(argv)


def interactive_main():
    """主流程：詢問使用者輸入、收集商品、下載 GLB，最後輸出 metadata。"""
    site_key, site_base = choose_site()
    category_name, category_url = choose_category(site_key, site_base)
    target_count = ask_target_count()
    output_dir = OUTPUT_ROOT / slugify(category_name)
    metadata_csv, metadata_json = metadata_paths(output_dir, category_name)
    output_dir.mkdir(parents=True, exist_ok=True)

    downloaded = load_existing_metadata(metadata_json, metadata_csv)
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


def main(argv=None):
    args = parse_args(argv)
    if len(sys.argv) == 1:
        interactive_main()
        return

    if args.storage_batch or args.storage_sample:
        results = run_storage_batch(args)
        print("\nBatch results:")
        for result in results:
            print(
                f"- {result['category_name']}: "
                f"{result['new_downloads']} new, {result['total_downloads']} total; "
                f"json={result['metadata_json']}"
            )
        return

    if args.group_batch:
        results = run_group_batch(args, args.group_batch)
        print("\nBatch results:")
        for result in results:
            print(
                f"- {result['category_name']}: "
                f"{result['new_downloads']} new, {result['total_downloads']} total; "
                f"json={result['metadata_json']}"
            )
        return

    if args.category:
        site = IKEA_SITES[args.site]
        if args.all:
            target_count = None
        elif args.target_count is not None:
            target_count = args.target_count
        else:
            raise ValueError("Use --target-count N or --all with --category.")

        driver = get_chrome_driver()
        try:
            result = download_category(
                driver=driver,
                site_key=args.site,
                site_base=site["base_url"],
                category_key=args.category,
                target_count=target_count,
                output_root=Path(args.output_root),
                category_timeout_seconds=args.category_timeout_seconds,
            )
        finally:
            driver.quit()
        print("\nDone:")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    raise ValueError("No action selected. Use --storage-sample, --storage-batch, or --category.")


if __name__ == "__main__":
    main()

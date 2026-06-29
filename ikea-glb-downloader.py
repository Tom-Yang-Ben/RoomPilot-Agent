import os
import sys
import requests
from bs4 import BeautifulSoup
import json
import sqlite3
import re
from tqdm import tqdm
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import logging

# 降低 webdriver-manager 的輸出量，避免執行時被驅動程式下載訊息洗版。
logging.getLogger('WDM').setLevel(logging.NOTSET)
os.environ['WDM_LOG_LEVEL'] = '0'

# 下載到的 GLB 模型會集中放在這個資料夾。
download_dir = 'downloaded-files'
os.makedirs(download_dir, exist_ok=True)

# 用 SQLite 記錄已處理的商品，避免重複下載相同商品或相同顏色變體。
conn = sqlite3.connect('ikea_products.db')
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS products
             (url TEXT PRIMARY KEY, name TEXT, color TEXT, glb_url TEXT, downloaded INTEGER)''')

def get_chrome_driver():
    """建立無頭 Chrome 瀏覽器，供 Selenium 抓取 IKEA 動態載入的頁面內容。"""
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--log-level=3')  # 只顯示嚴重錯誤。
    options.add_experimental_option('excludeSwitches', ['enable-logging'])
    
    try:
        # 新版 webdriver-manager 支援 log_level，舊版不一定支援，所以用 try/except 相容。
        service = Service(ChromeDriverManager(log_level=0).install())
    except TypeError:
        service = Service(ChromeDriverManager().install())
    
    # 暫時隱藏 ChromeDriver 的 stderr 訊息，建立完成後再還原。
    original_stderr = sys.stderr
    sys.stderr = open(os.devnull, 'w')
    
    driver = webdriver.Chrome(service=service, options=options)
    
    # Restore stderr
    sys.stderr = original_stderr
    
    return driver

def get_product_links(url):
    """從 IKEA 分類頁擷取商品頁連結，會自動捲動頁面載入更多商品。"""
    driver = get_chrome_driver()
    try:
        driver.get(url)
        
        # 等待商品列表容器出現，代表分類頁主要內容已載入。
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, '.plp-fragment-wrapper'))
        )
        
        # IKEA 分類頁採用動態載入；持續捲到底直到頁面高度不再增加。
        last_height = driver.execute_script("return document.body.scrollHeight")
        while True:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)  # 等待新商品卡片載入。
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height
        
        # 取得所有商品圖片連結，這些連結會導向個別商品頁。
        WebDriverWait(driver, 30).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, '.plp-fragment-wrapper a.plp-product__image-link'))
        )
        
        links = [link.get_attribute('href') for link in driver.find_elements(By.CSS_SELECTOR, '.plp-fragment-wrapper a.plp-product__image-link')]
        
        print(f"Found {len(links)} products on this page")
        return list(set(links))  # 去除重複商品連結。
    except TimeoutException:
        print(f"Timeout while loading products on page: {url}")
        return []
    except Exception as e:
        print(f"Error while getting product links from {url}: {str(e)}")
        return []
    finally:
        driver.quit()

def get_color_variant_links(url, download_all_colors):
    """依使用者選項取得商品的所有顏色變體 URL，或只回傳原始商品 URL。"""
    if not download_all_colors:
        return [url]
    
    driver = get_chrome_driver()
    try:
        driver.get(url)
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, '.js-product-style-picker'))
        )
        
        variants = [url]  # 保留原始商品 URL，再追加其他顏色變體。
        style_picker = driver.find_element(By.CSS_SELECTOR, '.js-product-style-picker')
        if style_picker:
            variant_links = style_picker.find_elements(By.CSS_SELECTOR, '.pip-product-styles__link')
            for link in variant_links:
                variants.append(link.get_attribute('href'))
        
        return variants
    finally:
        driver.quit()

def get_product_details(url):
    """進入商品頁，解析商品名稱、顏色與 IKEA XR viewer 中的 GLB 模型 URL。"""
    driver = get_chrome_driver()
    try:
        driver.get(url)
        
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, 'title'))
        )
        
        title = driver.title
        if title:
            full_title = title.strip()
            name_color = full_title.split(' - IKEA')[0]
            # IKEA title 常見格式是「商品名, 顏色 - IKEA」，用逗號切出名稱和顏色。
            match = re.match(r'(.*?),\s*(.*)', name_color)
            if match:
                name, color = match.groups()
            else:
                name = name_color
                color = "Default"
        else:
            name = "Unknown"
            color = "Unknown"
        
        try:
            # 有 3D 模型的商品頁會包含 pip-xr-viewer-model script，內容通常是 JSON。
            script = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.ID, 'pip-xr-viewer-model'))
            )
            if script:
                try:
                    data = json.loads(script.get_attribute('innerHTML'))
                    glb_url = data.get('url')
                    return name, color, glb_url
                except json.JSONDecodeError:
                    print(f"Error decoding JSON for {url}")
        except TimeoutException:
            print(f"GLB model script not found for {url}")
        
    except TimeoutException:
        print(f"Timeout while loading page: {url}")
    except Exception as e:
        print(f"Error processing {url}: {str(e)}")
    finally:
        driver.quit()
    
    return name, color, None

def download_glb(url, filename):
    """串流下載 GLB 檔案，並用 tqdm 顯示下載進度。"""
    response = requests.get(url, stream=True)
    total_size = int(response.headers.get('content-length', 0))
    
    with open(filename, 'wb') as f, tqdm(
        desc=filename,
        total=total_size,
        unit='iB',
        unit_scale=True,
        unit_divisor=1024,
    ) as progress_bar:
        for data in response.iter_content(chunk_size=1024):
            size = f.write(data)
            progress_bar.update(size)

def process_product(url, download_all_colors):
    """處理單一商品：找顏色變體、解析模型 URL、下載檔案並寫入 SQLite。"""
    print(f"\nProcessing product: {url}")
    
    # 主商品 URL 已處理過就跳過，避免重複開瀏覽器與下載。
    c.execute("SELECT * FROM products WHERE url=?", (url,))
    if c.fetchone():
        print(f"Skipping already processed product: {url}")
        return

    try:
        variant_urls = get_color_variant_links(url, download_all_colors)
        print(f"Found {len(variant_urls)} color variants")
        
        for variant_url in variant_urls:
            c.execute("SELECT * FROM products WHERE url=?", (variant_url,))
            if c.fetchone():
                print(f"Skipping already processed variant: {variant_url}")
                continue

            name, color, glb_url = get_product_details(variant_url)
            print(f"Processing variant: {name} - {color}")
            
            if glb_url:
                filename = f"{name} - {color}.glb"
                filename = re.sub(r'[<>:"/\\|?*]', '', filename)  # 移除 Windows 檔名不允許的字元。
                full_path = os.path.join(download_dir, filename)
                download_glb(glb_url, full_path)
                downloaded = 1
            else:
                downloaded = 0
                print(f"No GLB file found for {name} - {color}")

            c.execute("INSERT INTO products VALUES (?, ?, ?, ?, ?)",
                      (variant_url, name, color, glb_url, downloaded))
            conn.commit()
    except Exception as e:
        print(f"Error processing product {url}: {str(e)}")

def main():
    """互動式入口：輸入 IKEA 分類頁 URL 後，逐頁處理分類中的商品。"""
    start_url = input("Enter the IKEA category URL to download products from: ")
    download_all_colors = input("Do you want to download all color variants? (y/n): ").lower() == 'y'
    
    page = 1
    total_processed = 0
    
    while True:
        print(f"\nFetching product links from page {page}")
        # IKEA 分類頁使用 page 查詢參數分頁；若原 URL 已有查詢參數，就用 & 追加。
        current_url = f"{start_url}{'&' if '?' in start_url else '?'}page={page}"
        product_links = get_product_links(current_url)
        
        if not product_links:
            print(f"No products found on page {page}. Finishing process.")
            break

        for i, link in enumerate(product_links, 1):
            print(f"\nProcessing item {i} of {len(product_links)} on page {page}")
            process_product(link, download_all_colors)
            total_processed += 1

        print(f"Completed page {page}. Total products processed so far: {total_processed}")
        page += 1

    conn.close()
    print(f"Finished processing all pages. Total products processed: {total_processed}")

if __name__ == "__main__":
    main()

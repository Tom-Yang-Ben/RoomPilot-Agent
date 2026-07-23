"""backend.server 共用路徑與常數(原 main.py 頂部設定區)。

GLB zip 搜尋設定(_EXTERNAL_GLB_ZIP_*、_DATASET_GLB_ROOTS)屬 GLB 資產解析
的私有細節,放在 services/glb_assets.py。
"""
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent.parent
STATIC_DIR = BASE_DIR / "static"
MOODBOARD_DIR = STATIC_DIR / "moodboard_assets"
STYLE_DB_PATH = BASE_DIR.parent / "catalog" / "data" / "furniture_catalog_6styles_zh.json"
SURFACE_DB_PATH = BASE_DIR.parent / "catalog" / "data" / "surface_catalog.json"
EXTERNAL_IMPORT_PATH = BASE_DIR.parent / "catalog" / "data" / "舊友：12種風格與JSON" / "external_furniture_import_index.json"
DATASET_DIR = PROJECT_DIR / "data" / "dataset"
PLAN_DIR = PROJECT_DIR / "data" / "testdata" / "pic" / "temp"
SAMPLE_GLB_DIR = PROJECT_DIR / "data" / "testdata" / "sample_glb"
FLOORPLAN_EXTENSIONS = (".dxf", ".png", ".jpg", ".jpeg")
MAX_FLOORPLAN_BYTES = 20 * 1024 * 1024

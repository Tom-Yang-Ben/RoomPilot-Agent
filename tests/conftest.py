"""pytest 共用路徑設定：入口 floorplan2room.py 在專案根目錄，
其餘管線模組統一放 scripts/，兩處都加進 sys.path 讓測試直接 import。"""
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "scripts"))
sys.path.insert(0, _ROOT)

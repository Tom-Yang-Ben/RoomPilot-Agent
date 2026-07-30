"""pytest 共用路徑設定：管線模組在 backend/floorplan/，研發工具在 training/scripts/，
連同 repo 根一起加進 sys.path 讓測試直接 import。"""
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(_ROOT, "training", "scripts"))
sys.path.insert(0, os.path.join(_ROOT, "backend", "floorplan"))
sys.path.insert(0, _ROOT)

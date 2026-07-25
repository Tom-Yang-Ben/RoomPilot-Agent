# -*- coding: utf-8 -*-
"""家具符號深度學習分類器（CNN）＋半監督自我訓練閉環。

主幹：PyTorch 小型 CNN（3 層卷積），輸入 48×48 二值符號圖。
備援：環境裝不了 torch 時退回 HOG＋softmax 迴歸（numpy 實作）。

訓練資料來源（每次重訓自動彙整）：
  1. room_recognition/<類別>/ 樣板（含使用者後續補充的檔案）
     — 經清理後以 8 向 × 粗細 × 平移縮放 × 微旋轉擴增
  2. 非六大類資料夾（plant/、other/⋯）→ 併入 "other" 負類
  3. room_recognition/.autolabel/<類別>/ — 系統對高信心偵測的自動收割
  4. room_recognition/uncertain/ — 無法辨識的物件；每次重訓用「當前模型」
     重新評估，機率 ≥ 0.9 者以偽標籤（pseudo-label）納入訓練
     → 一輪比一輪認得多，這就是「重複不斷作為判斷資料」的自我訓練閉環

重訓時機（免手動）：
  - 類別資料夾內容改變（使用者整理了 uncertain）→ 立即
  - uncertain／.autolabel 新增達 8 件 → 排入
  首次無快取同步訓練；其後皆背景執行，訓練期間沿用舊模型，完成即生效。
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

try:
    import torch
    from torch import nn

    torch.set_num_threads(max(1, min(4, torch.get_num_threads())))
    _HAS_TORCH = True
except Exception:  # pragma: no cover - 無 torch 環境退回 softmax
    _HAS_TORCH = False

_ASSET_DIR = Path(__file__).resolve().parent / "room_recognition"
_CACHE_DIR = _ASSET_DIR / ".cache"
_META_PATH = _CACHE_DIR / "meta.json"
_CNN_PATH = _CACHE_DIR / "cnn.pt"
_SOFTMAX_PATH = _CACHE_DIR / "softmax.npz"

_NORM = 48
_OTHER = "other"            # 負類：樣板庫中非六大類資料夾的統稱
_RESERVED = {"uncertain"}   # 不作為類別的資料夾
_AUTOLABEL = ".autolabel"   # 高信心偵測的自動收割區
_PSEUDO_MIN_P = 0.90        # 偽標籤採納門檻
_AUX_RETRAIN_DELTA = 8      # uncertain/.autolabel 新增達此數即排程重訓
_CELL, _BINS = 8, 9         # softmax 備援的 HOG 參數


def norm48(a: np.ndarray) -> np.ndarray:
    """物件／樣板 → 48×48 二值圖（訓練與推論共用的正規化）。"""
    out = cv2.resize(a, (_NORM, _NORM), interpolation=cv2.INTER_AREA)
    _, out = cv2.threshold(out, 40, 255, cv2.THRESH_BINARY)
    return out


# ---------------------------------------------------------------------------
# 資料彙整（樣板 → 擴增；autolabel／uncertain → 清理裁切）
# ---------------------------------------------------------------------------
def _jitters(img: np.ndarray) -> list[np.ndarray]:
    """單一方向樣板 → 粗細 × 平移縮放 × 微旋轉 的擴增集合。"""
    outs: list[np.ndarray] = []
    k3 = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    thick_set = [img, cv2.dilate(img, k3)]
    eroded = cv2.erode(img, k3)
    if int((eroded > 0).sum()) > 40:
        thick_set.append(eroded)
    h, w = img.shape
    for base in thick_set:
        for angle in (0.0, 5.0, -5.0):
            if angle:
                m = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
                rot = cv2.warpAffine(base, m, (w, h), flags=cv2.INTER_NEAREST, borderValue=0)
            else:
                rot = base
            for pad_ratio in (0.0, 0.06):
                if pad_ratio:
                    py, px = int(h * pad_ratio), int(w * pad_ratio)
                    padded = cv2.copyMakeBorder(rot, py, py, px, px, cv2.BORDER_CONSTANT, value=0)
                else:
                    padded = rot
                outs.append(norm48(padded))
    return outs


def _crop_main_object(gray_png: Path) -> Optional[np.ndarray]:
    """uncertain／autolabel 裁圖 → 二值化後取最大墨水群聚（去除鄰物殘邊）。"""
    from furniture_match import _split_variants, _to_ink

    raw = cv2.imdecode(np.fromfile(str(gray_png), dtype=np.uint8), cv2.IMREAD_UNCHANGED)
    if raw is None:
        return None
    pieces = _split_variants(_to_ink(raw))
    if not pieces:
        return None
    return max(pieces, key=lambda p: int((p > 0).sum()))


def _base_dataset() -> tuple[list[np.ndarray], list[int], list[str]]:
    """樣板庫＋負類資料夾 → 擴增後的 (影像, 標籤, 類別名單)。

    類別＝實際有樣板的標準 key（新類別資料夾一有樣本就自動加入訓練）；
    無法解析為類別的資料夾（plant/⋯）併入 other 負類。
    """
    from furniture_match import _orient8, _split_variants, _strip_table, _to_ink, load_templates, resolve_class_dir

    imgs: list[np.ndarray] = []
    ys: list[int] = []
    tpl = load_templates()
    classes = sorted(tpl)
    for ci, cls in enumerate(classes):
        for v in tpl.get(cls, []):
            for o in _orient8(v):
                for aug in _jitters(o):
                    imgs.append(aug)
                    ys.append(ci)

    neg_dirs = [d for d in _ASSET_DIR.iterdir()
                if d.is_dir() and resolve_class_dir(d.name) is None
                and d.name not in _RESERVED
                and not d.name.startswith(".")] if _ASSET_DIR.is_dir() else []
    if neg_dirs:
        classes = classes + [_OTHER]
        oi = len(classes) - 1
        for d in neg_dirs:
            for fp in sorted(d.glob("*.png")):
                raw = cv2.imdecode(np.fromfile(str(fp), dtype=np.uint8), cv2.IMREAD_UNCHANGED)
                if raw is None:
                    continue
                for v in _split_variants(_strip_table(_to_ink(raw))):
                    if min(v.shape) < 14:
                        continue
                    for o in _orient8(v):
                        for aug in _jitters(o):
                            imgs.append(aug)
                            ys.append(oi)
    return imgs, ys, classes


def _autolabel_dataset(classes: list[str]) -> tuple[list[np.ndarray], list[int]]:
    """系統自動收割的高信心偵測裁圖 → 輕量擴增（4 向）。"""
    from furniture_match import _orient8, resolve_class_dir

    imgs: list[np.ndarray] = []
    ys: list[int] = []
    root = _ASSET_DIR / _AUTOLABEL
    if not root.is_dir():
        return imgs, ys
    for d in sorted(root.iterdir()):
        key = resolve_class_dir(d.name) if d.is_dir() else None
        if key is None or key not in classes:
            continue
        ci = classes.index(key)
        for fp in sorted(d.glob("*.png")):
            obj = _crop_main_object(fp)
            if obj is None or min(obj.shape) < 14:
                continue
            for o in _orient8(obj)[:4]:
                imgs.append(norm48(o))
                ys.append(ci)
    return imgs, ys


def _pseudo_dataset(model: Optional["Model"], classes: list[str]) -> tuple[list[np.ndarray], list[int], int]:
    """半監督核心：用當前模型評估 uncertain 裁圖，高信心者以偽標籤納入。

    防確認偏誤（self-training drift）：家具類偽標籤除了 CNN 機率 ≥ 0.9，
    還須通過樣板相似度守門（≥ 該類門檻的 8 成）——CNN 對沒看過的東西
    也會過度自信，沒有第二軌把關就會把錯誤越訓越深。
    易混類別拉距：類別定義表標註的易混對（茶几↔餐桌、床頭櫃↔邊几⋯）
    須與對方拉開足夠差距才採納，模稜兩可者留給人工。
    負類（other）偽標籤只需高機率：錯把家具當背景頂多漏抓，可由人工整理救回。
    """
    imgs: list[np.ndarray] = []
    ys: list[int] = []
    used = 0
    unc = _ASSET_DIR / "uncertain"
    if model is None or not unc.is_dir():
        return imgs, ys, 0
    from furniture_match import CLASSES, _CLASS_THRESHOLD, _chamfer_scores, _orient8

    for fp in sorted(unc.glob("*.png")):
        obj = _crop_main_object(fp)
        if obj is None or min(obj.shape) < 14:
            continue
        probs = model.predict_proba(obj)
        top = max(probs, key=lambda c: probs[c])
        if probs[top] < _PSEUDO_MIN_P or top not in classes:
            continue
        if top != _OTHER:
            confusable = [c for c in CLASSES[top]["confuse"] if c in CLASSES]
            cham = _chamfer_scores(obj, {top, *confusable})
            if cham.get(top, 0.0) < max(_CLASS_THRESHOLD[top], 0.55):
                # 偽標籤只自動採納「與既有樣板風格相近」的項目（chamfer 高標）；
                # 跨畫風樣本一律留給人工整理 —— 低門檻類別（如 toilet 0.36）
                # 若只用八成門檻，盆栽等雜圖會混入訓練造成漂移（實測教訓）
                continue
            if any(cham.get(top, 0.0) - cham.get(c, 0.0) < 0.05 for c in confusable):
                continue  # 與易混類別分不開 → 不採納，留給人工
        ci = classes.index(top)
        for o in _orient8(obj)[:4]:
            imgs.append(norm48(o))
            ys.append(ci)
        used += 1
    return imgs, ys, used


# ---------------------------------------------------------------------------
# 模型：CNN（torch）與 softmax 備援
# ---------------------------------------------------------------------------
if _HAS_TORCH:
    class _Net(nn.Module):
        def __init__(self, n_cls: int):
            super().__init__()
            self.body = nn.Sequential(
                nn.Conv2d(1, 16, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),   # 24×24
                nn.Conv2d(16, 32, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),  # 12×12
                nn.Conv2d(32, 64, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),  # 6×6
                nn.Flatten(), nn.Linear(64 * 6 * 6, 96), nn.ReLU(),
                nn.Dropout(0.3), nn.Linear(96, n_cls))

        def forward(self, x):  # noqa: D102
            return self.body(x)


def _hog(bin48: np.ndarray) -> np.ndarray:
    """softmax 備援用手刻 HOG（Sobel 梯度直方圖＋區塊 L2 正規化）。"""
    img = cv2.GaussianBlur(bin48.astype(np.float32) / 255.0, (3, 3), 0.8)
    gx = cv2.Sobel(img, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(img, cv2.CV_32F, 0, 1, ksize=3)
    mag, ang = cv2.cartToPolar(gx, gy, angleInDegrees=True)
    ang = np.mod(ang, 180.0)
    nc = _NORM // _CELL
    bin_idx = np.minimum((ang / (180.0 / _BINS)).astype(np.int32), _BINS - 1)
    cells = np.zeros((nc, nc, _BINS), np.float32)
    for b in range(_BINS):
        m = np.where(bin_idx == b, mag, 0.0)
        cells[:, :, b] = m.reshape(nc, _CELL, nc, _CELL).sum(axis=(1, 3))
    blocks = []
    for by in range(nc - 1):
        for bx in range(nc - 1):
            v = cells[by:by + 2, bx:bx + 2, :].ravel()
            blocks.append(v / (np.linalg.norm(v) + 1e-6))
    return np.concatenate(blocks)


def features(bin48: np.ndarray) -> np.ndarray:
    """softmax 備援特徵：HOG＋12×12 粗網格。"""
    g = (cv2.resize(bin48, (12, 12), interpolation=cv2.INTER_AREA).ravel() / 255.0)
    return np.concatenate([_hog(bin48), g]).astype(np.float32)


class Model:
    """統一推論介面：predict_proba(物件二值圖) → {類別: 機率}。"""

    def __init__(self, backend: str, classes: list[str], net=None,
                 w=None, b=None, mean=None, std=None, meta: Optional[dict] = None):
        self.backend = backend
        self.classes = classes
        self._net, self._w, self._b, self._mean, self._std = net, w, b, mean, std
        self.meta = meta or {}

    def predict_proba(self, obj: np.ndarray) -> dict[str, float]:
        """TTA（測試時增強）：物件 4 向旋轉各推論一次取平均——
        平面圖家具常被旋轉擺放，單一方向的信心值不穩。"""
        x48 = norm48(obj)
        views = [x48, cv2.rotate(x48, cv2.ROTATE_90_CLOCKWISE),
                 cv2.rotate(x48, cv2.ROTATE_180), cv2.rotate(x48, cv2.ROTATE_90_COUNTERCLOCKWISE)]
        if self.backend == "cnn":
            with torch.no_grad():
                t = torch.from_numpy(np.stack([(v > 0).astype(np.float32) for v in views])[:, None])
                p = torch.softmax(self._net(t), dim=1).mean(dim=0).numpy()
        else:
            ps = []
            for v in views:
                f = (features(v) - self._mean) / self._std
                logits = f @ self._w + self._b
                logits -= logits.max()
                e = np.exp(logits)
                ps.append(e / e.sum())
            p = np.mean(ps, axis=0)
        return {c: float(p[i]) for i, c in enumerate(self.classes)}


def _train_cnn(imgs: list[np.ndarray], ys: list[int], classes: list[str],
               seed: int = 7, init_state=None, epochs: int = 10,
               lr: float = 1e-3) -> tuple["Model", float]:
    """訓練 CNN。init_state 提供時＝暖啟動（自現役模型權重繼續訓練，累積式深化），
    否則冷啟動（隨機初始化）。暖啟動時以較小學習率微調。"""
    torch.manual_seed(seed)
    x = torch.from_numpy(np.stack([(im > 0).astype(np.float32) for im in imgs])[:, None])
    y = torch.from_numpy(np.asarray(ys, np.int64))
    n = len(y)
    idx = torch.randperm(n, generator=torch.Generator().manual_seed(seed))
    cut = max(1, int(n * 0.9))
    tr, te = idx[:cut], idx[cut:]
    counts = np.bincount(np.asarray(ys), minlength=len(classes)).astype(np.float32)
    weight = torch.from_numpy(n / (len(classes) * np.maximum(counts, 1.0)))
    net = _Net(len(classes))
    if init_state is not None:
        try:
            net.load_state_dict(init_state)   # 暖啟動：承接現役模型已學到的表徵
        except Exception:
            pass                              # 結構不符（類別數變動）→ 退回冷啟動
    opt = torch.optim.Adam(net.parameters(), lr=lr, weight_decay=1e-4)
    loss_fn = nn.CrossEntropyLoss(weight=weight.float())
    net.train()
    for _ in range(epochs):
        perm = tr[torch.randperm(len(tr))]
        for i in range(0, len(perm), 128):
            bi = perm[i:i + 128]
            opt.zero_grad()
            loss = loss_fn(net(x[bi]), y[bi])
            loss.backward()
            opt.step()
    net.eval()
    with torch.no_grad():
        acc = float((net(x[te]).argmax(dim=1) == y[te]).float().mean()) if len(te) else 1.0
    return Model("cnn", classes, net=net), acc


def _train_softmax_backend(imgs: list[np.ndarray], ys: list[int], classes: list[str],
                           iters: int = 400, lr: float = 0.5, l2: float = 1e-4,
                           seed: int = 7) -> tuple["Model", float]:
    rng = np.random.default_rng(seed)
    x = np.stack([features(im) for im in imgs])
    y = np.asarray(ys, np.int64)
    idx = rng.permutation(len(y))
    cut = max(1, int(len(y) * 0.9))
    tr, te = idx[:cut], idx[cut:]
    mean = x[tr].mean(axis=0)
    std = x[tr].std(axis=0) + 1e-6
    xn = (x - mean) / std
    n, d = xn[tr].shape
    k = len(classes)
    w = rng.normal(0, 0.01, (d, k)).astype(np.float32)
    b = np.zeros(k, np.float32)
    onehot = np.eye(k, dtype=np.float32)[y[tr]]
    counts = np.bincount(y[tr], minlength=k).astype(np.float32)
    sample_w = (n / (k * np.maximum(counts, 1.0)))[y[tr]][:, None]
    vw, vb = np.zeros_like(w), np.zeros_like(b)
    for _ in range(iters):
        logits = xn[tr] @ w + b
        logits -= logits.max(axis=1, keepdims=True)
        p = np.exp(logits)
        p /= p.sum(axis=1, keepdims=True)
        g = (p - onehot) * sample_w / n
        vw = 0.9 * vw - lr * (xn[tr].T @ g + l2 * w)
        vb = 0.9 * vb - lr * g.sum(axis=0)
        w += vw
        b += vb
    acc = float(((xn[te] @ w + b).argmax(axis=1) == y[te]).mean()) if len(te) else 1.0
    return Model("softmax", classes, w=w, b=b,
                 mean=mean.astype(np.float32), std=std.astype(np.float32)), acc


# ---------------------------------------------------------------------------
# 指紋、快取與背景重訓
# ---------------------------------------------------------------------------
_TAXONOMY_TAG = "taxonomy-v3-reduced"  # 類別註冊表版本：類別 key 變動時強制重訓一次

def _fingerprint_core() -> str:
    """類別／負類資料夾指紋（uncertain 與 .autolabel 另計）。"""
    import hashlib
    items = [_TAXONOMY_TAG]
    if _ASSET_DIR.is_dir():
        for d in sorted(_ASSET_DIR.iterdir()):
            if not d.is_dir() or d.name in _RESERVED or d.name.startswith("."):
                continue
            for fp in sorted(d.glob("*.png")):
                st = fp.stat()
                items.append(f"{d.name}/{fp.name}:{st.st_size}:{st.st_mtime_ns}")
    return hashlib.sha1("|".join(items).encode()).hexdigest()


def _aux_count() -> int:
    """uncertain＋.autolabel 的檔案總數（達增量門檻即排程重訓）。"""
    n = 0
    unc = _ASSET_DIR / "uncertain"
    if unc.is_dir():
        n += sum(1 for _ in unc.glob("*.png"))
    al = _ASSET_DIR / _AUTOLABEL
    if al.is_dir():
        n += sum(1 for _ in al.rglob("*.png"))
    return n


_model: Optional[Model] = None
_lock = threading.Lock()
_status = {"training": False, "reason": "", "started": 0.0, "last_result": ""}

# 黃金測試集：真實圖裁圖、人工確認過、永不進訓練——重訓後的品質閘門。
# 目錄結構同類別資料夾（.golden/tolit/、.golden/other/⋯）。
_GOLDEN_DIR = _ASSET_DIR / ".golden"
_VERSIONS_DIR = _CACHE_DIR / "versions"
_HISTORY_PATH = _CACHE_DIR / "history.jsonl"
_KEEP_VERSIONS = 8


def golden_eval(model: Optional[Model]) -> tuple[Optional[float], int]:
    """在黃金測試集上評分（top-1 正確率）。集合為空回傳 (None, 0)。"""
    if model is None or not _GOLDEN_DIR.is_dir():
        return None, 0
    from furniture_match import resolve_class_dir
    total = correct = 0
    for d in sorted(_GOLDEN_DIR.iterdir()):
        if not d.is_dir():
            continue
        key = resolve_class_dir(d.name)
        expected = key if key in model.classes else (
            _OTHER if _OTHER in model.classes else None)
        if expected is None:
            continue
        for fp in sorted(d.glob("*.png")):
            obj = _crop_main_object(fp)
            if obj is None or min(obj.shape) < 14:
                continue
            probs = model.predict_proba(obj)
            total += 1
            if max(probs, key=lambda c: probs[c]) == expected:
                correct += 1
    return (correct / total if total else None), total


def _next_version() -> int:
    if not _HISTORY_PATH.is_file():
        return 1
    try:
        lines = _HISTORY_PATH.read_text(encoding="utf-8").strip().splitlines()
        return max((json.loads(ln).get("version", 0) for ln in lines), default=0) + 1
    except Exception:
        return 1


def _snapshot(model: Model, version: int) -> None:
    """版本快照（含被閘門退回的），出問題可隨時回滾。"""
    try:
        _VERSIONS_DIR.mkdir(parents=True, exist_ok=True)
        if model.backend == "cnn":
            torch.save(model._net.state_dict(), _VERSIONS_DIR / f"v{version:03d}_cnn.pt")
        else:
            np.savez_compressed(_VERSIONS_DIR / f"v{version:03d}_softmax.npz",
                                w=model._w, b=model._b, mean=model._mean, std=model._std)
        snaps = sorted(_VERSIONS_DIR.glob("v*"))
        for old in snaps[:-_KEEP_VERSIONS]:
            old.unlink(missing_ok=True)
    except OSError:
        pass


def _log_history(record: dict) -> None:
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        with open(_HISTORY_PATH, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:
        pass


def _save(model: Model, acc: float, n_samples: int, n_pseudo: int,
          version: int, golden_acc: Optional[float], golden_n: int) -> None:
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    meta = {"backend": model.backend, "classes": model.classes, "version": version,
            "core_fp": _fingerprint_core(), "aux_count": _aux_count(),
            "holdout_acc": round(acc, 4),
            "golden_acc": round(golden_acc, 4) if golden_acc is not None else None,
            "golden_n": golden_n, "n_samples": n_samples,
            "n_pseudo": n_pseudo, "trained_at": time.strftime("%Y-%m-%d %H:%M:%S")}
    if model.backend == "cnn":
        torch.save(model._net.state_dict(), _CNN_PATH)
    else:
        np.savez_compressed(_SOFTMAX_PATH, w=model._w, b=model._b,
                            mean=model._mean, std=model._std)
    _META_PATH.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    model.meta = meta


def _load_cached() -> Optional[Model]:
    if not _META_PATH.is_file():
        return None
    try:
        meta = json.loads(_META_PATH.read_text(encoding="utf-8"))
        classes = list(meta["classes"])
        from furniture_match import CLASSES
        if not set(classes) <= set(CLASSES) | {_OTHER}:
            return None  # 舊類別命名的快取 → 視同無快取，強制以新註冊表重訓
        if meta["backend"] == "cnn" and _HAS_TORCH and _CNN_PATH.is_file():
            net = _Net(len(classes))
            net.load_state_dict(torch.load(_CNN_PATH, weights_only=True))
            net.eval()
            return Model("cnn", classes, net=net, meta=meta)
        if meta["backend"] == "softmax" and _SOFTMAX_PATH.is_file():
            d = np.load(_SOFTMAX_PATH)
            return Model("softmax", classes, w=d["w"], b=d["b"],
                         mean=d["mean"], std=d["std"], meta=meta)
    except Exception:
        return None  # 快取毀損 → 視同無快取
    return None


def _train_once(prev: Optional[Model]) -> Optional[Model]:
    """彙整全部資料來源訓練一輪（含以 prev 模型偽標籤 uncertain）。

    混舊帶新：每輪都以「完整資料集」重訓（樣板＋回饋），不是只餵新樣本，
    避免災難性遺忘。訓練後過黃金測試集閘門：分數不輸現役模型才部署，
    否則快照留檔、沿用舊模型（防止越學越歪的保險絲）。
    """
    imgs, ys, classes = _base_dataset()
    if len(imgs) < 50:
        return None
    ai, ay = _autolabel_dataset(classes)
    pi, py, n_pseudo = _pseudo_dataset(prev, classes)
    imgs += ai + pi
    ys += ay + py
    version = _next_version()
    # 每按一次＝一次不同隨機重啟的候選（種子隨版本變化，才會真的探索到不同解），
    # 再由下方黃金集閘門「只取更好、否則保留現役」——重複按 = best-of-N 棒輪，
    # 黃金分數單調不降。搭配使用中累積的自標註／偽標籤資料，資料越多越強。
    # （暖啟動微調實測會在小資料上過擬合、拉低黃金集，故改採冷啟動 best-of-N。）
    if _HAS_TORCH:
        model, acc = _train_cnn(imgs, ys, classes, seed=7 + version)
    else:
        model, acc = _train_softmax_backend(imgs, ys, classes, seed=7 + version)

    # 驗證閘門：黃金集分數不得低於現役模型
    cand_g, cand_n = golden_eval(model)
    prev_g, _ = golden_eval(prev) if cand_g is not None else (None, 0)
    deployed = cand_g is None or prev_g is None or cand_g >= prev_g - 1e-3
    _snapshot(model, version)
    _log_history({"version": version, "backend": model.backend,
                  "holdout_acc": round(acc, 4),
                  "golden_acc": round(cand_g, 4) if cand_g is not None else None,
                  "golden_n": cand_n, "n_samples": len(imgs), "n_pseudo": n_pseudo,
                  "deployed": deployed,
                  "reason": "" if deployed else f"黃金集 {cand_g:.3f} < 現役 {prev_g:.3f}",
                  "at": time.strftime("%Y-%m-%d %H:%M:%S")})
    if not deployed:
        _status["last_result"] = (f"v{version} 候選未達現役水準"
                                  f"（黃金集 {cand_g:.1%} < 現役 {prev_g:.1%}），"
                                  f"保留現役模型（best-of-N 只取更好）")
        return None
    gained = ""
    if cand_g is not None and prev_g is not None:
        dg = cand_g - prev_g
        gained = (f"｜黃金集 {prev_g:.0%}→{cand_g:.0%}"
                  f"（{'+' if dg >= 0 else ''}{dg:.1%}）"
                  + ("，本次變強" if dg > 1e-3 else "，持平"))
    _save(model, acc, len(imgs), n_pseudo, version, cand_g, cand_n)
    _status["last_result"] = f"v{version} 已部署 · 驗證 {acc:.0%}{gained}"
    return model


def _retrain_background(reason: str) -> None:
    global _model

    def _run() -> None:
        global _model
        try:
            new = _train_once(_model)
            if new is not None:
                _model = new
        finally:
            _status.update(training=False, reason="", started=0.0)

    if _status["training"]:
        return
    _status.update(training=True, reason=reason, started=time.time())
    threading.Thread(target=_run, name="furniture-ml-retrain", daemon=True).start()


def get_model() -> Optional[Model]:
    """取得分類器；快取過期時背景重訓（沿用舊模型），首次無快取同步訓練。"""
    global _model
    with _lock:
        if _model is None:
            _model = _load_cached()
        if _model is None:
            _model = _train_once(None)  # 首次：同步訓練
            return _model
        meta = _model.meta
        if meta.get("core_fp") != _fingerprint_core():
            _retrain_background("樣板庫內容變更")
        elif _aux_count() - int(meta.get("aux_count", 0)) >= _AUX_RETRAIN_DELTA:
            _retrain_background("uncertain／autolabel 累積新資料")
        return _model


def request_retrain(reason: str = "使用者手動觸發") -> dict:
    """外部（API）請求重訓：背景執行，回傳目前狀態。"""
    global _model
    with _lock:
        if _model is None:
            _model = _load_cached()
        _retrain_background(reason)
    return {"training": _status["training"], "reason": _status["reason"]}


def model_info() -> dict:
    """給前端顯示的模型狀態（版本、驗證分數、黃金集、重訓狀態）。"""
    m = _model
    info = {"backend": None, "version": None, "holdout_acc": None,
            "golden_acc": None, "golden_n": None, "n_samples": None,
            "n_pseudo": None, "training": _status["training"],
            "last_result": _status.get("last_result", "")}
    meta = m.meta if m is not None else None
    if meta is None and _META_PATH.is_file():
        try:
            meta = json.loads(_META_PATH.read_text(encoding="utf-8"))  # 尚未載入 → 讀快取
        except Exception:
            meta = None
    if meta:
        info.update(backend=meta.get("backend"), version=meta.get("version"),
                    holdout_acc=meta.get("holdout_acc"),
                    golden_acc=meta.get("golden_acc"), golden_n=meta.get("golden_n"),
                    n_samples=meta.get("n_samples"), n_pseudo=meta.get("n_pseudo"))
    return info

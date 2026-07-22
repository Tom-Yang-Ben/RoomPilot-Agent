"""門窗開口深度學習分類器。

以 room_recognition/door、room_recognition/windows 的圖檔為訓練樣本，
大量資料增強（旋轉、縮放、平移、線寬變化、雜訊、四向翻轉）後訓練小型 CNN，
三分類：door／window／opening（負類＝純開口，合成空白帶與牆端殘線）。

- 資料夾指紋為快取鍵：新增／替換門窗圖檔 → 下次推論自動重新訓練
- 「重新訓練模型」每按一次：以新種子再訓練一個候選，固定驗證集比較，
  只有不輸現役者才部署（棘輪：探索取最好、永不退步）
- 環境無 torch 時本模組回報不可用，呼叫端退回 chamfer 樣板比對
"""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

try:
    import torch
    from torch import nn
    torch.set_num_threads(max(1, min(4, torch.get_num_threads())))
    _HAS_TORCH = True
except Exception:  # pragma: no cover - 無 torch 環境
    _HAS_TORCH = False

_ASSET_DIR = Path(__file__).resolve().parent / "room_recognition"
_CACHE_DIR = _ASSET_DIR / ".cache"
_MODEL_PATH = _CACHE_DIR / "opening_cnn.pt"
_META_PATH = _CACHE_DIR / "opening_meta.json"

_CLASSES = ["door", "window", "opening"]   # opening＝負類（非門非窗的純開口）
_H, _W = 40, 100                           # 與 furniture_match._open_norm 同尺寸
_AUG_PER_IMG = 90                          # 每張樣本圖的增強數（×4 翻轉）
_N_NEG = 480                               # 合成負類數量
_VAL_SEED = 20260722                       # 固定驗證集種子：跨版本可比較

_lock = threading.Lock()
_runtime: dict = {"fp": None, "net": None, "meta": None}


# ---------------------------------------------------------------------------
# 資料集：讀樣本圖 → 增強 → 正規化 40×100
# ---------------------------------------------------------------------------
def _main_symbol(ink: np.ndarray) -> np.ndarray:
    """去除圖例文字，只留符號本體。

    樣本圖多為圖例截圖：符號＋名稱文字（Sliding Door、Window…）。
    推論裁圖沒有文字，訓練必須把文字剔掉。做法：以最大連通元件為核，
    反覆併入外框相近的元件（同符號的其他筆劃）；距離超過門檻的
    （一顆顆的字母）不併，最後裁到符號範圍。
    """
    n, _lab, stats, _ = cv2.connectedComponentsWithStats((ink > 0).astype(np.uint8), 8)
    if n <= 2:
        return ink
    big = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    bx, by, bx2, by2 = (stats[big, cv2.CC_STAT_LEFT], stats[big, cv2.CC_STAT_TOP],
                        stats[big, cv2.CC_STAT_LEFT] + stats[big, cv2.CC_STAT_WIDTH],
                        stats[big, cv2.CC_STAT_TOP] + stats[big, cv2.CC_STAT_HEIGHT])
    margin = max(8, int(0.6 * (by2 - by)))
    used = {big}
    changed = True
    while changed:
        changed = False
        for i in range(1, n):
            if i in used:
                continue
            x, y, w, h = stats[i, cv2.CC_STAT_LEFT], stats[i, cv2.CC_STAT_TOP], \
                stats[i, cv2.CC_STAT_WIDTH], stats[i, cv2.CC_STAT_HEIGHT]
            if (x <= bx2 + margin and x + w >= bx - margin and
                    y <= by2 + margin and y + h >= by - margin):
                bx, by = min(bx, x), min(by, y)
                bx2, by2 = max(bx2, x + w), max(by2, y + h)
                used.add(i)
                changed = True
    return ink[by:by2, bx:bx2]


def _load_sources() -> dict[str, list[np.ndarray]]:
    """door/windows 資料夾原始墨水裁圖（去圖例文字、未正規化，供增強用）。"""
    from furniture_match import _OPEN_DIRS, _to_ink
    out: dict[str, list[np.ndarray]] = {"door": [], "window": []}
    if not _ASSET_DIR.is_dir():
        return out
    for name, key in _OPEN_DIRS.items():
        d = _ASSET_DIR / name
        if not d.is_dir():
            continue
        for f in sorted(d.glob("*.png")):
            raw = cv2.imdecode(np.fromfile(str(f), dtype=np.uint8), cv2.IMREAD_UNCHANGED)
            if raw is None:
                continue
            ink = _to_ink(raw)
            ys, xs = np.nonzero(ink)
            if xs.size < 20:
                continue
            ink = _main_symbol(ink[ys.min():ys.max() + 1, xs.min():xs.max() + 1])
            if ink.shape[0] > ink.shape[1]:            # 一律水平長條
                ink = cv2.rotate(ink, cv2.ROTATE_90_CLOCKWISE)
            out[key].append(ink)
    return out


def _norm(a: np.ndarray) -> np.ndarray:
    """拉伸到 40×100：保留內部圖樣（窗＝平行線群、門＝門扇＋弧）。

    長寬比資訊由增強階段的異向縮放涵蓋——推論時的裁圖比例
    （窄開口的細長條）在訓練時就見過。
    """
    out = cv2.resize(a, (_W, _H), interpolation=cv2.INTER_AREA)
    _, out = cv2.threshold(out, 40, 255, cv2.THRESH_BINARY)
    return out


def _augment(ink: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """單次隨機增強：旋轉 ±6°、縮放 0.85–1.2、平移 ±4%、線寬 ±1、雜訊。"""
    if rng.random() < 0.85:
        # 異向縮放：推論裁圖的長寬比隨開口寬窄與線距而異（窄開口的窗
        # 只有幾像素高），訓練先把樣本壓扁／拉寬到各種比例再正規化，
        # 讓拉伸後的線寬變化在訓練分佈之內
        fx = float(rng.uniform(0.5, 1.5))
        fy = float(rng.uniform(0.3, 1.8))
        ink = cv2.resize(ink, (max(12, int(ink.shape[1] * fx)),
                               max(6, int(ink.shape[0] * fy))),
                         interpolation=cv2.INTER_AREA)
        _, ink = cv2.threshold(ink, 40, 255, cv2.THRESH_BINARY)
    h, w = ink.shape
    ang = float(rng.uniform(-6, 6))
    sc = float(rng.uniform(0.85, 1.2))
    m = cv2.getRotationMatrix2D((w / 2, h / 2), ang, sc)
    m[0, 2] += float(rng.uniform(-0.04, 0.04)) * w
    m[1, 2] += float(rng.uniform(-0.04, 0.04)) * h
    out = cv2.warpAffine(ink, m, (w, h), flags=cv2.INTER_NEAREST, borderValue=0)
    r = rng.random()
    if r < 0.30:
        out = cv2.dilate(out, np.ones((2, 2), np.uint8))
    elif r < 0.55:
        out = cv2.erode(out, np.ones((2, 2), np.uint8))
    if rng.random() < 0.5:                             # 胡椒雜訊（掃描髒點）
        n = int(rng.integers(1, 6))
        for _ in range(n):
            cx, cy = int(rng.integers(0, w)), int(rng.integers(0, h))
            cv2.circle(out, (cx, cy), int(rng.integers(1, 3)), 255, -1)
    return out


def _synth_negative(rng: np.random.Generator) -> np.ndarray:
    """合成負類：純開口＝幾乎空白，可能殘留牆端短線／樓板線／髒點。"""
    out = np.zeros((_H, _W), np.uint8)
    if rng.random() < 0.7:                             # 兩端牆端殘線（垂直短線）
        for x in (int(rng.integers(0, 6)), int(rng.integers(_W - 6, _W))):
            y0 = int(rng.integers(0, _H // 2))
            cv2.line(out, (x, y0), (x, y0 + int(rng.integers(4, _H - y0))), 255,
                     int(rng.integers(1, 3)))
    if rng.random() < 0.35:                            # 偶有一條貫穿的樓板細線
        y = int(rng.integers(0, _H))
        cv2.line(out, (0, y), (_W - 1, y), 255, 1)
    if rng.random() < 0.6:
        for _ in range(int(rng.integers(1, 5))):
            cv2.circle(out, (int(rng.integers(0, _W)), int(rng.integers(0, _H))),
                       int(rng.integers(1, 3)), 255, -1)
    return out


def _build_dataset(seed: int) -> tuple[np.ndarray, np.ndarray]:
    """增強後資料集 → (x[N,40,100] float32 0/1, y[N] int64)。"""
    rng = np.random.default_rng(seed)
    imgs: list[np.ndarray] = []
    ys: list[int] = []
    src = _load_sources()
    for key in ("door", "window"):
        cls = _CLASSES.index(key)
        if not src[key]:
            continue
        # 類別平衡：每類目標樣本數一致，樣本圖少的類別增強次數多
        per = max(_AUG_PER_IMG, int(round(_AUG_PER_IMG * 6 / len(src[key]))))
        for ink in src[key]:
            for _ in range(per):
                a = ink
                # 窗符號沿長度週期性（平行線一路延伸）：取隨機橫向切片，
                # 模擬各種開口寬度的窗——樣本圖常橫跨整面牆，推論裁圖
                # 只有單一開口寬，不切片會差出一個數量級的壓縮比。
                # 門符號（門扇／錯開門板）不可切片，切了就不成門。
                if key == "window" and a.shape[1] > 80 and rng.random() < 0.7:
                    w_all = a.shape[1]
                    sw = int(w_all * float(rng.uniform(0.15, 0.6)))
                    sw = max(30, sw)
                    x0 = int(rng.integers(0, max(1, w_all - sw)))
                    a = a[:, x0:x0 + sw]
                a = _augment(a, rng)
                for flip in (None, 0, 1, -1):          # 四向翻轉：門弧任一朝向
                    v = a if flip is None else cv2.flip(a, flip)
                    imgs.append(_norm(v))
                    ys.append(cls)
    neg = _CLASSES.index("opening")
    for _ in range(_N_NEG):
        imgs.append(_synth_negative(rng))
        ys.append(neg)
    x = np.stack([(im > 0).astype(np.float32) for im in imgs])
    return x, np.asarray(ys, np.int64)


# ---------------------------------------------------------------------------
# 模型
# ---------------------------------------------------------------------------
if _HAS_TORCH:
    class _Net(nn.Module):
        def __init__(self, n_cls: int):
            super().__init__()
            self.body = nn.Sequential(
                nn.Conv2d(1, 8, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),   # 20×50
                nn.Conv2d(8, 16, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),  # 10×25
                nn.Conv2d(16, 32, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2), # 5×12
            )
            self.head = nn.Sequential(nn.Flatten(), nn.Linear(32 * 5 * 12, 64),
                                      nn.ReLU(), nn.Linear(64, n_cls))

        def forward(self, x):  # noqa: D102
            return self.head(self.body(x))


def _val_set() -> tuple["torch.Tensor", "torch.Tensor"]:
    """固定驗證集（固定種子增強）：跨版本比較的量尺，不參與訓練。"""
    x, y = _build_dataset(_VAL_SEED)
    return torch.from_numpy(x[:, None]), torch.from_numpy(y)


def _train_once(seed: int) -> tuple[dict, float]:
    """訓練一個候選 → (state_dict, 固定驗證集正確率)。"""
    x_np, y_np = _build_dataset(seed)
    torch.manual_seed(seed)
    x = torch.from_numpy(x_np[:, None])
    y = torch.from_numpy(y_np)
    counts = np.bincount(y_np, minlength=len(_CLASSES)).astype(np.float64)
    weight = torch.from_numpy(len(y_np) / (len(_CLASSES) * np.maximum(counts, 1.0))).float()
    net = _Net(len(_CLASSES))
    opt = torch.optim.Adam(net.parameters(), lr=1e-3, weight_decay=1e-4)
    loss_fn = nn.CrossEntropyLoss(weight=weight)
    n = len(y)
    for _ in range(8):
        perm = torch.randperm(n, generator=torch.Generator().manual_seed(seed))
        for i in range(0, n, 64):
            b = perm[i:i + 64]
            opt.zero_grad()
            loss = loss_fn(net(x[b]), y[b])
            loss.backward()
            opt.step()
    net.eval()
    vx, vy = _val_set()
    with torch.no_grad():
        acc = float((net(vx).argmax(1) == vy).float().mean())
    return net.state_dict(), acc


def _fingerprint() -> str:
    from furniture_match import _opening_fingerprint
    return json.dumps(_opening_fingerprint())


def _load_meta() -> Optional[dict]:
    try:
        return json.loads(_META_PATH.read_text("utf-8"))
    except Exception:
        return None


def _deploy(state: dict, meta: dict) -> None:
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    torch.save(state, _MODEL_PATH)
    _META_PATH.write_text(json.dumps(meta, ensure_ascii=False), "utf-8")
    net = _Net(len(_CLASSES))
    net.load_state_dict(state)
    net.eval()
    _runtime.update({"fp": meta["fp"], "net": net, "meta": meta})


def ensure_model():
    """取得現役模型（懶載入；樣本資料夾變動或無快取 → 自動訓練）。"""
    if not _HAS_TORCH:
        return None
    fp = _fingerprint()
    with _lock:
        if _runtime["net"] is not None and _runtime["fp"] == fp:
            return _runtime["net"]
        meta = _load_meta()
        if meta and meta.get("fp") == fp and _MODEL_PATH.exists():
            net = _Net(len(_CLASSES))
            net.load_state_dict(torch.load(_MODEL_PATH, map_location="cpu"))
            net.eval()
            _runtime.update({"fp": fp, "net": net, "meta": meta})
            return net
        # 首次或樣本更新：best-of-2 起步
        src = _load_sources()
        if not src["door"] and not src["window"]:
            return None
        best = max((_train_once(s) for s in (7, 8)), key=lambda t: t[1])
        _deploy(best[0], {"fp": fp, "version": 1, "val_acc": best[1]})
        return _runtime["net"]


def retrain() -> dict:
    """「重新訓練模型」掛鉤：新種子訓練候選，固定驗證集棘輪比較。"""
    if not _HAS_TORCH:
        return {"ok": False, "message": "門窗模型：環境無 torch，維持樣板比對"}
    net = ensure_model()
    if net is None:
        return {"ok": False, "message": "門窗模型：無樣本圖可訓練"}
    with _lock:
        meta = _runtime["meta"] or {"fp": _fingerprint(), "version": 1, "val_acc": 0.0}
        version = int(meta.get("version", 1)) + 1
        state, acc = _train_once(seed=7 + version)
        cur = float(meta.get("val_acc", 0.0))
        if acc >= cur - 1e-3:
            _deploy(state, {"fp": meta["fp"], "version": version, "val_acc": max(acc, cur)})
            return {"ok": True, "message": f"門窗模型 v{version} 已部署 · 驗證 {acc:.1%}（現役 {cur:.1%}）"}
        meta["version"] = version   # 版本號前進（下次換新種子），模型不退步
        _META_PATH.write_text(json.dumps(meta, ensure_ascii=False), "utf-8")
        _runtime["meta"] = meta
        return {"ok": True, "message": f"門窗模型候選 {acc:.1%} 未達現役 {cur:.1%}，保留現役（只取更好）"}


def model_info() -> dict:
    meta = _runtime.get("meta") or _load_meta() or {}
    return {"available": _HAS_TORCH and bool(meta),
            "version": meta.get("version"), "val_acc": meta.get("val_acc")}


def predict(region_ink: np.ndarray) -> Optional[tuple[Optional[str], float]]:
    """開口周邊墨水圖 → (kind, 機率)；kind=None 表示「純開口」。

    不可用（無 torch／無樣本）→ 回傳 None，呼叫端退回 chamfer 樣板比對。
    四向翻轉平均：容忍門弧任一朝向、窗線上下顛倒。
    """
    net = ensure_model()
    if net is None:
        return None
    ys, xs = np.nonzero(region_ink)
    if xs.size < 20:
        return None
    crop = region_ink[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    if crop.shape[0] > crop.shape[1]:
        crop = cv2.rotate(crop, cv2.ROTATE_90_CLOCKWISE)
    views = [_norm(crop), _norm(cv2.flip(crop, 0)),
             _norm(cv2.flip(crop, 1)), _norm(cv2.flip(crop, -1))]
    with torch.no_grad():
        t = torch.from_numpy(np.stack([(v > 0).astype(np.float32) for v in views])[:, None])
        p = torch.softmax(net(t), dim=1).mean(dim=0).numpy()
    i = int(p.argmax())
    kind = _CLASSES[i]
    return (None if kind == "opening" else kind), float(p[i])

"""room_classifier.py — DINOv2 房間裁切分類（去 CubiCasa 路線的房型命名層）。

凍結 DINOv2 ViT-S/14 取 CLS 特徵 ＋ 線性頭。訓練在
`training/scripts/probe_room_classifier.py`（own_dataset 157 房，8 向擴增），
本檔只做推論。

**為什麼取代 CubiCasa 語意投票**：
- 準確度：own_eval 72 房保留集 **90.3% vs 管線 79.2%**（同一批 GT，皆未用於訓練）
- 授權：DINOv2 程式碼與權重皆 **Apache 2.0**（上游 README 明載），
  可商用；CubiCasa5k 權重是 CC BY-NC 禁商用，v5 微調為其衍生物一併受限

缺件即停用（同 symbol_match 契約）：torch/DINOv2/線性頭任一缺失 → `classify()`
回 None，呼叫端退回既有路徑。**但會出聲**，不靜默降級。

骨幹權重 84MB 由 torch.hub 下載並快取在 `~/.cache/torch/hub/`；
離線部署請預先放好該快取，或設 `TORCH_HOME`。
"""
import os

import cv2
import numpy as np

_PKG_DIR = os.path.dirname(os.path.abspath(__file__))
# 雙頭（2026-08-02）：灰階/彩圖畫風各自成頭。混訓實測傷灰階基準
# （own_eval 72 房 90.3%→80.6%），分域訓練兩者都保住；缺 color 頭時
# 彩圖退回灰階頭（行為同雙頭之前）
HEAD_PATHS = {
    "gray": os.environ.get("ROOM_HEAD",
                           os.path.join(_PKG_DIR, "room_head.npz")),
    "color": os.environ.get("ROOM_HEAD_COLOR",
                            os.path.join(_PKG_DIR, "room_head_color.npz")),
}
SIZE = 224
MEAN = np.array([0.485, 0.456, 0.406], np.float32)
STD = np.array([0.229, 0.224, 0.225], np.float32)
CROP_MARGIN = 0.15          # 與 extract_room_crops.py 的預設一致（含鄰接牆上下文）

_states = {}                # variant → None(停用) | dict；骨幹跨頭共用


def letterbox(img):
    """等比縮放＋白底填滿（平面圖底色白）到 SIZE×SIZE。同訓練側 letterbox。"""
    h, w = img.shape[:2]
    s = SIZE / max(h, w)
    nh, nw = max(1, round(h * s)), max(1, round(w * s))
    r = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_AREA)
    out = np.full((SIZE, SIZE, 3), 255, np.uint8)
    t, l = (SIZE - nh) // 2, (SIZE - nw) // 2
    out[t:t + nh, l:l + nw] = r
    return out


def variants(img):
    """8 個剛體變換視角（4 旋轉 × 有無鏡射）——房間圖塊無自然方向。"""
    out = []
    for k in range(4):
        r = np.rot90(img, k)
        out += [r, r[:, ::-1]]
    return out


def _load(variant="gray"):
    """(backbone, head_w, head_b, classes) 或 None。逐 variant 快取，
    骨幹跨頭共用。color 頭缺檔時退回灰階頭（出聲，不靜默）。"""
    if variant in _states:
        return _states[variant]
    path = HEAD_PATHS.get(variant, HEAD_PATHS["gray"])
    if variant != "gray" and not os.path.isfile(path):
        print(f"⚠ 找不到 {variant} 線性頭 {path} → 退回灰階頭")
        _states[variant] = _load("gray")
        return _states[variant]
    _states[variant] = None
    if not os.path.isfile(path):
        print(f"⚠ 找不到房型線性頭 {path} → DINOv2 房型分類停用")
        return _states[variant]
    try:
        import torch
    except ImportError:
        print("⚠ torch 未安裝 → DINOv2 房型分類停用")
        return _states[variant]
    z = np.load(path, allow_pickle=False)
    if bool(z["use_ink"]) or bool(z["use_area"]):
        print("⚠ 線性頭帶額外特徵（ink/area），本推論路徑未實作 → 停用")
        return _states[variant]
    model = None
    for st in _states.values():                  # 骨幹共用（84MB 只載一次）
        if st and str(z["backbone"]) == st.get("backbone"):
            model = st["model"]
            torch = st["torch"]
            break
    if model is None:
        try:
            model = torch.hub.load("facebookresearch/dinov2",
                                   str(z["backbone"]),
                                   trust_repo=True, verbose=False)
        except Exception as e:                   # 離線、hub 快取缺失等
            print(f"⚠ DINOv2 骨幹載入失敗（{type(e).__name__}）→ 房型分類停用")
            return _states[variant]
        model.eval()
        torch.set_num_threads(os.cpu_count() or 4)
    _states[variant] = {"torch": torch, "model": model,
                        "backbone": str(z["backbone"]),
                        "w": z["weight"], "b": z["bias"],
                        "classes": [str(x) for x in z["classes"]]}
    return _states[variant]


def crop_room(bgr, mask, margin=CROP_MARGIN):
    """房間遮罩 → bbox＋比例邊距裁切（同 extract_room_crops.crop_bbox）。"""
    ys, xs = np.nonzero(mask)
    if ys.size == 0:
        return None
    h, w = bgr.shape[:2]
    r0, r1, c0, c1 = ys.min(), ys.max(), xs.min(), xs.max()
    mr, mc = int((r1 - r0) * margin), int((c1 - c0) * margin)
    crop = bgr[max(0, r0 - mr):min(h, r1 + mr),
               max(0, c0 - mc):min(w, c1 + mc)]
    return crop if crop.size else None


def classify(bgr, labels, rooms, variant="gray"):
    """[room] → [{label: 機率}]（順序同 rooms）；停用時回 None。

    每間房以 bbox＋邊距裁切、8 視角 TTA 平均特徵後過線性頭 softmax。
    裁不出圖的房間給空 dict（呼叫端當作無證據）。
    variant："gray"（預設）或 "color"——彩圖畫風用專屬頭。"""
    st = _load(variant)
    if st is None or bgr is None or labels is None or not rooms:
        return None
    torch, model = st["torch"], st["model"]
    crops, idx = [], []
    for i, r in enumerate(rooms):
        c = crop_room(bgr, labels == r["id"])
        if c is not None:
            crops.append(c)
            idx.append(i)
    out = [{} for _ in rooms]
    if not crops:
        return out
    with torch.no_grad():
        for j, c in zip(idx, crops):
            vs = variants(letterbox(c))
            x = np.stack([(cv2.cvtColor(v, cv2.COLOR_BGR2RGB).astype(np.float32)
                           / 255.0 - MEAN) / STD for v in vs])
            f = model(torch.from_numpy(x.transpose(0, 3, 1, 2))).cpu().numpy()
            f = f.mean(0)                              # 8 視角 TTA 平均
            logit = st["w"] @ f + st["b"]
            e = np.exp(logit - logit.max())
            p = e / e.sum()
            out[j] = {c_: float(v) for c_, v in zip(st["classes"], p)}
    return out

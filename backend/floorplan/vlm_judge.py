#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""vlm_judge.py — 平面圖開口的 VLM 仲裁(窗/門/其他)。

傳統 CV 規則的天花板案例(窗簾弧與門弧幾何同構、空心牆與窗同構、窗符號被
吸進牆塊)靠幾何規則已證明會互相打架(見 README 2026-07-12 的回滾記錄)。
這層改用視覺語言模型對「不確定候選」做局部裁圖判讀:

- 裁圖含 2.5 倍脈絡邊距 + 紅框標出待判開口 → 比全圖 bbox 判讀精準得多
- 多個候選拼成編號蒙太奇,一張圖一次判完(免費模型延遲高,呼叫數要省)
- 判讀結果以裁圖內容雜湊快取(FP2DXF_VLM_CACHE,預設專案 .vlm_cache.json)
  → 重跑評測免重打、結果可重現
- 模型失敗(無金鑰/限流/壞回應)回 {} → 呼叫端沿用 CV 原判,不會比基準差

用 OpenRouter 免費視覺模型(池會輪替,OPENROUTER_VISION_MODELS 可覆寫)。
獨立於 server 層(floorplan 管線不依賴 backend.server)。
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import ssl
import urllib.request

import cv2
import numpy as np

try:
    import certifi

    _SSL_CTX = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    _SSL_CTX = ssl.create_default_context()

DEFAULT_VISION_MODELS = [
    "google/gemma-4-26b-a4b-it:free",
    "google/gemma-4-31b-it:free",
    "nvidia/nemotron-nano-12b-v2-vl:free",
]

_PROMPT = """這張圖是「建築平面圖」的數個局部裁圖,由左到右、由上到下編號 1、2、3…(每格左上角有藍底白字編號)。每格中央的紅色框標出一段牆上的開口/符號,請判斷紅框內的東西是什麼:

- window(窗):牆帶上有 2~4 條平行的細直線貫穿開口(玻璃線),兩端有牆墩。
- door(門):開口處有四分之一圓弧(門的開闔軌跡)或斜放的門扇線;弧的一端連在開口端點(鉸鏈)。窗簾符號的波浪弧「不算」門弧。
- other(其他):既不是窗也不是門——例如空心牆(整條牆只有上下兩條輪廓線、中間全空)、流理檯面/家具的邊線、門檻線、樓梯,或只是牆的一部分。

判斷重點:
- 紅框內若「只有」兩條沿牆的輪廓線且左右延伸出框(=空心牆的一段),是 other。
- 紅框緊鄰處有明顯門弧掃過 → 是 door;但如果弧是窗簾/裝飾的波浪線,而紅框內有平行玻璃線 → 仍是 window。
- 有 2 條以上明確平行線段「侷限在紅框範圍內」(不無限延伸)且兩端有實心牆 → window。

只輸出 JSON,格式:{"1": "window", "2": "door", "3": "other", ...},數量必須與編號格數一致。"""


def get_vision_models() -> list[str]:
    raw = os.getenv("OPENROUTER_VISION_MODELS", "").strip()
    if raw:
        models = [m.strip() for m in raw.split(",") if m.strip()]
        if models:
            return models
    return DEFAULT_VISION_MODELS.copy()


def vlm_enabled() -> bool:
    flag = os.getenv("FP2DXF_VLM", "auto")
    if flag == "0":
        return False
    return bool(os.getenv("OPENROUTER_API_KEY", "").strip())


def _cache_path() -> str:
    return os.getenv(
        "FP2DXF_VLM_CACHE",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), ".vlm_cache.json"),
    )


def _load_cache() -> dict:
    try:
        with open(_cache_path(), encoding="utf-8") as fp:
            return json.load(fp)
    except Exception:
        return {}


def _save_cache(cache: dict) -> None:
    try:
        with open(_cache_path(), "w", encoding="utf-8") as fp:
            json.dump(cache, fp, ensure_ascii=False)
    except Exception:
        pass


def _crop_with_context(bgr, box, margin_ratio=1.25, min_margin=40):
    """裁出開口 + 脈絡邊距,紅框標出開口本體。回傳 (crop, sha1)。"""
    H, W = bgr.shape[:2]
    x0, y0, x1, y1 = (int(v) for v in box)
    mw = max(min_margin, int((x1 - x0) * margin_ratio))
    mh = max(min_margin, int((y1 - y0) * margin_ratio))
    cx0, cy0 = max(0, x0 - mw), max(0, y0 - mh)
    cx1, cy1 = min(W, x1 + mw), min(H, y1 + mh)
    crop = bgr[cy0:cy1, cx0:cx1].copy()
    cv2.rectangle(crop, (x0 - cx0, y0 - cy0), (x1 - cx0, y1 - cy0), (0, 0, 255), 2)
    # 統一放大到高 ~300px,細線才看得清
    h, w = crop.shape[:2]
    scale = max(1.0, 300.0 / max(1, h))
    if scale > 1.0:
        crop = cv2.resize(crop, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_CUBIC)
    sha = hashlib.sha1(cv2.imencode(".png", crop)[1].tobytes()).hexdigest()
    return crop, sha


def _montage(crops: list[np.ndarray], cols: int = 3) -> np.ndarray:
    """裁圖拼成編號網格(藍底白字編號在每格左上)。"""
    cell_h = max(c.shape[0] for c in crops) + 8
    cell_w = max(c.shape[1] for c in crops) + 8
    rows = (len(crops) + cols - 1) // cols
    canvas = np.full((rows * cell_h, cols * cell_w, 3), 255, np.uint8)
    for i, c in enumerate(crops):
        r, k = divmod(i, cols)
        y, x = r * cell_h + 4, k * cell_w + 4
        canvas[y:y + c.shape[0], x:x + c.shape[1]] = c
        cv2.rectangle(canvas, (x, y), (x + 62, y + 34), (180, 80, 0), -1)
        cv2.putText(canvas, str(i + 1), (x + 12, y + 27), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
        cv2.rectangle(canvas, (x - 2, y - 2), (x + cell_w - 6, y + cell_h - 6), (120, 120, 120), 1)
    return canvas


def _ask(model: str, png_bytes: bytes, n: int, timeout: float) -> dict[int, str] | None:
    payload = {
        "model": model,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": _PROMPT + f"\n\n本圖共有 {n} 格。"},
                {"type": "image_url", "image_url": {
                    "url": "data:image/png;base64," + base64.b64encode(png_bytes).decode()}},
            ],
        }],
        "temperature": 0.0,
    }
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY', '')}",
            "Content-Type": "application/json",
            "HTTP-Referer": os.getenv("OPENROUTER_SITE_URL", "http://127.0.0.1:8002"),
            "X-Title": "roompilot floorplan opening judge",
        },
        method="POST",
    )
    try:
        body = json.load(urllib.request.urlopen(req, timeout=timeout, context=_SSL_CTX))
        text = body["choices"][0]["message"]["content"].strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        parsed = json.loads(text)
        out = {}
        for k, v in parsed.items():
            idx = int(k)
            label = str(v).strip().lower()
            if label in ("window", "door", "other") and 1 <= idx <= n:
                out[idx] = label
        return out if len(out) == n else None
    except Exception:
        return None


def judge_openings(bgr, boxes: list[tuple[float, float, float, float]],
                   timeout_per_model: float = 90.0) -> dict[int, str]:
    """boxes(影像 px bbox)→ {原始索引: "window"|"door"|"other"}。

    有快取的直接用;其餘拼蒙太奇問模型(一批最多 6 格)。任何一批失敗
    就略過該批(呼叫端沿用 CV 原判)。
    """
    if not boxes or not vlm_enabled():
        return {}
    cache = _load_cache()
    results: dict[int, str] = {}
    pending: list[tuple[int, np.ndarray, str]] = []
    for i, box in enumerate(boxes):
        crop, sha = _crop_with_context(bgr, box)
        hit = cache.get(sha)
        if hit in ("window", "door", "other"):
            results[i] = hit
        else:
            pending.append((i, crop, sha))

    BATCH = 6
    dirty = False
    for start in range(0, len(pending), BATCH):
        batch = pending[start:start + BATCH]
        canvas = _montage([c for _, c, _ in batch])
        png = cv2.imencode(".png", canvas)[1].tobytes()
        answers = None
        for model in get_vision_models():
            answers = _ask(model, png, len(batch), timeout_per_model)
            if answers:
                break
        if not answers:
            continue
        for cell, (idx, _, sha) in enumerate(batch, start=1):
            label = answers.get(cell)
            if label:
                results[idx] = label
                cache[sha] = label
                dirty = True
    if dirty:
        _save_cache(cache)
    return results

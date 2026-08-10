#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""probe_dino_backbone.py — DINOv2 vs DINOv3 骨幹「特徵可分性」離線探針。

用途（主管 DINOv3 提案的**驗證前哨**，2026-08-10）：在投入換機重訓算力之前，
先量「換骨幹後，房型類別在特徵空間裡是否更好分」——不重訓任何線性頭，直接對
既有裁切抽 CLS 特徵，用留一法（LOO）最近質心／kNN 量可分性。DINOv2→DINOv3
若真有增益，這裡會先看到；若持平/倒退，就不必浪費 GPU 重訓一輪才發現。

**不動產品路徑**：本檔只在 training/ 底下，讀取 room_classifier 的前處理常數
（letterbox/SIZE/MEAN/STD）以保證「同前處理、只換骨幹」的公平對比，不修改
backend/floorplan 任何檔案。seg_head 的 patch16 適配以本檔內的 patch 參數化
版驗證接線（見 --seg-check），產品端 seg_head.py 的實際改動留待授權關卡通過、
真正重訓時再動（改法見 seg_check() 內註記）。

骨幹切換走環境變數（同 SYMBOL_KINDS 慣例，跑兩次比數字）：
    DINO_BACKBONE   骨幹 hub 名（預設 dinov2_vits14）。含 'dinov3'→v3/patch16，
                    含 'dinov2'→v2/patch14；repo 由版本推定。
    DINO_WEIGHTS    DINOv3 權重檔路徑（gated，須先於 HF 接受授權後下載）。v2 免。
    DINO_CROPS      裁切目錄（預設 training/room_crops，extract_room_crops.py 產）
    DINO_SPLIT      train | test（預設 train，小樣本先看 dev 面）
    DINO_MAX_PER_CLASS  每類抽樣上限（CPU 提速，預設 40；0=不設限）
    DINO_TTA        1=8 視角 TTA 平均（同產品推論），0=單視角（預設 0，提速）

用法：
    # 先重生裁切（收尾已清空 room_crops，鐵律：不得沿用舊裁切）
    python training/scripts/extract_room_crops.py

    # 量 DINOv2 基準
    DINO_BACKBONE=dinov2_vits14 python training/scripts/probe_dino_backbone.py

    # 量 DINOv3（換機、取得 gated 權重後）
    DINO_BACKBONE=dinov3_vits16 DINO_WEIGHTS=~/dinov3_vits16.pth \
        python training/scripts/probe_dino_backbone.py

    # 只驗 seg_head patch16 接線（不需裁切，只需骨幹能載入）
    python training/scripts/probe_dino_backbone.py --seg-check

    # 度量自測（不需骨幹/裁切，驗 LOO 數學）
    python training/scripts/probe_dino_backbone.py --selftest

報表落 temp/json/dino_probe_<backbone>.json，供 DINOv2/v3 兩次結果並排比較。
"""
import argparse
import json
import os
import sys

import cv2
import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
sys.path.insert(0, os.path.join(_ROOT, "backend", "floorplan"))

import room_classifier as rc     # 只借前處理常數/函式（唯讀），保證與產品同前處理


# ─────────────────────────── 骨幹（v2/v3 統一介面）───────────────────────────
def backbone_spec(name):
    """骨幹名 → (repo, patch, kind)。三種切法：
      含 '/'（HF 庫 id）→ transformers 讀 safetensors（門禁權重的官方格式），kind=v3hf
      dinov2_* → torch.hub facebookresearch/dinov2 patch14，kind=v2
      dinov3_* → torch.hub facebookresearch/dinov3 patch16（需原始 .pth），kind=v3"""
    lo = name.lower()
    if "/" in name:                              # HF 庫 id（facebook/dinov3-vits16-...）
        patch = 14 if "dinov2" in lo else 16
        return name, patch, "v3hf"
    if "dinov3" in lo:
        return "facebookresearch/dinov3", 16, "v3"
    if "dinov2" in lo:
        return "facebookresearch/dinov2", 14, "v2"
    raise SystemExit(f"無法從骨幹名判定版本：{name}（需含 dinov2/dinov3 或為 HF 庫 id）")


def load_backbone(name, weights=None):
    """載入凍結骨幹，回 (model, torch, patch, kind)；失敗回 (None, torch, patch, kind)。

    v3hf：由 transformers 從 HF 門禁庫讀 safetensors（需 hf auth login 且該庫已
    核准，核准後 from_pretrained 自動下載並快取）。
    v3（torch.hub）：需原始 .pth（Meta 表單／設 DINO_WEIGHTS）。"""
    repo, patch, ver = backbone_spec(name)
    try:
        import torch
    except ImportError:
        print("⚠ torch 未安裝 → 骨幹不可用")
        return None, None, patch, ver

    if ver == "v3hf":                            # HF/transformers 路（safetensors）
        try:
            from transformers import AutoModel
            model = AutoModel.from_pretrained(name)
        except Exception as e:
            print(f"⚠ {name} 由 transformers 載入失敗（{type(e).__name__}: {e}）"
                  "（HF 門禁：需 `hf auth login` 且該庫已核准；核准後自動下載 safetensors）")
            return None, torch, patch, ver
        model.eval()
        torch.set_num_threads(os.cpu_count() or 4)
        print(f"骨幹   : {name}  (transformers/HF, patch={patch})")
        return model, torch, patch, ver

    kw = dict(trust_repo=True, verbose=False)    # torch.hub 路（v2 / v3 原始 .pth）
    if ver == "v3" and weights:
        kw["weights"] = weights
    try:
        model = torch.hub.load(repo, name, **kw)
    except TypeError:
        kw.pop("weights", None)
        try:
            model = torch.hub.load(repo, name, **kw)
        except Exception as e:
            print(f"⚠ {name} 載入失敗（{type(e).__name__}: {e}）")
            return None, torch, patch, ver
    except Exception as e:
        hint = ("（DINOv3 原始權重 gated：改用 HF 庫 id 走 transformers，"
                "或設 DINO_WEIGHTS 指向 .pth）" if ver == "v3" else "")
        print(f"⚠ {name} 載入失敗（{type(e).__name__}: {e}）{hint}")
        return None, torch, patch, ver
    model.eval()
    torch.set_num_threads(os.cpu_count() or 4)
    print(f"骨幹   : {name}  repo={repo}  patch={patch}  ({ver})")
    return model, torch, patch, ver


def cls_features(model, torch, crops, kind="v2", tta=False):
    """裁切清單 → L2 正規化 CLS 特徵矩陣 (N, D)。前處理與產品 room_classifier
    完全一致（letterbox 224、8 視角可選、同 MEAN/STD），只有骨幹不同——
    保證「同前處理、只換骨幹」的公平對比。v3hf 走 transformers，CLS 取
    last_hidden_state[:,0]（DINOv3 序列＝CLS＋4 register＋patches，CLS 在 0）。"""
    feats = []
    with torch.no_grad():
        for c in crops:
            views = rc.variants(rc.letterbox(c)) if tta else [rc.letterbox(c)]
            x = np.stack([(cv2.cvtColor(v, cv2.COLOR_BGR2RGB).astype(np.float32)
                           / 255.0 - rc.MEAN) / rc.STD for v in views])
            t = torch.from_numpy(x.transpose(0, 3, 1, 2))
            if kind == "v3hf":
                out = model(pixel_values=t).last_hidden_state[:, 0]   # CLS token
            else:
                out = _pooled(model(t))                 # torch.hub v2/v3 取 CLS/pooled
            f = out.cpu().numpy().mean(0)               # TTA 平均（或單視角）
            feats.append(f)
    F = np.asarray(feats, np.float32)
    n = np.linalg.norm(F, axis=1, keepdims=True)
    return F / np.maximum(n, 1e-8)


def _pooled(out):
    """統一取 CLS/pooled 向量：dinov2/dinov3 hub 的 forward 多半直接回 (N,D)；
    少數回 dict/tuple 時取 CLS token。"""
    if isinstance(out, dict):
        for k in ("x_norm_clstoken", "cls_token", "x_pooled", "pooled"):
            if k in out:
                return out[k]
        return next(iter(out.values()))
    if isinstance(out, (list, tuple)):
        return out[0]
    return out


# ─────────────────────────── 裁切載入 ───────────────────────────
def load_crops(crops_dir, split, max_per_class):
    """extract_room_crops.py 的輸出 <dir>/<split>/<sid>_<idx>_<label>.png →
    (crops[], labels[])。標籤自檔名末段解析（與產出格式對齊）。"""
    d = os.path.join(crops_dir, split)
    if not os.path.isdir(d):
        raise SystemExit(
            f"找不到裁切目錄 {d}\n"
            f"  請先重生裁切（收尾已清空 room_crops，鐵律不得沿用舊裁切）：\n"
            f"    python training/scripts/extract_room_crops.py")
    files = sorted(f for f in os.listdir(d) if f.endswith(".png"))
    by_lab = {}
    for f in files:
        stem = os.path.splitext(f)[0]
        label = stem.rsplit("_", 1)[-1]            # <sid>_<idx>_<label>
        by_lab.setdefault(label, []).append(os.path.join(d, f))
    crops, labels = [], []
    for lab, paths in sorted(by_lab.items()):
        if max_per_class:
            paths = paths[:max_per_class]           # 穩定抽樣（檔名已排序）
        for p in paths:
            img = cv2.imread(p)
            if img is not None and img.size:
                crops.append(img)
                labels.append(lab)
    if not crops:
        raise SystemExit(f"{d} 內無可用裁切")
    return crops, np.array(labels)


# ─────────────────────────── 可分性度量（純 numpy，無 sklearn）───────────────
def loo_nearest_centroid(F, y):
    """留一法最近質心正確率：對每筆，用「排除自己」的各類質心預測最近類。
    純線性可分性訊號，與產品的線性頭同精神但零訓練。"""
    labs = np.unique(y)
    idx = {l: np.where(y == l)[0] for l in labs}
    sums = {l: F[idx[l]].sum(0) for l in labs}
    ok = 0
    for i in range(len(F)):
        yi = y[i]
        best_l, best_d = None, 1e18
        for l in labs:
            cnt = len(idx[l]) - (1 if l == yi else 0)
            if cnt <= 0:
                continue                            # 該類只有這一筆，排除後無質心
            cen = (sums[l] - (F[i] if l == yi else 0)) / cnt
            d = float(np.sum((F[i] - cen) ** 2))
            if d < best_d:
                best_l, best_d = l, d
        ok += int(best_l == yi)
    return ok / len(F)


def loo_knn(F, y, k=5):
    """留一法 kNN（cosine，F 已 L2 正規化 → 內積即相似度）正確率。"""
    S = F @ F.T
    np.fill_diagonal(S, -1.0)                        # 排除自己
    ok = 0
    for i in range(len(F)):
        nn = np.argsort(-S[i])[:k]
        vals, cnts = np.unique(y[nn], return_counts=True)
        ok += int(vals[np.argmax(cnts)] == y[i])
    return ok / len(F)


def per_class_recall(F, y):
    """逐類 LOO 最近質心 recall（看哪些類受益/受害，非只看總分）。"""
    labs = np.unique(y)
    idx = {l: np.where(y == l)[0] for l in labs}
    sums = {l: F[idx[l]].sum(0) for l in labs}
    hit = {l: 0 for l in labs}
    for i in range(len(F)):
        yi = y[i]
        best_l, best_d = None, 1e18
        for l in labs:
            cnt = len(idx[l]) - (1 if l == yi else 0)
            if cnt <= 0:
                continue
            cen = (sums[l] - (F[i] if l == yi else 0)) / cnt
            d = float(np.sum((F[i] - cen) ** 2))
            if d < best_d:
                best_l, best_d = l, d
        hit[yi] += int(best_l == yi)
    return {l: (hit[l] / len(idx[l]), len(idx[l])) for l in labs}


# ─────────────────────────── seg_head patch16 接線驗證 ───────────────────────
def seg_check(name, weights):
    """驗證 seg_head 的 patch 參數化在 v2/v3 都取得正確的 patch 特徵格。

    產品 seg_head.py 目前 PATCH=14 為硬編碼；換 DINOv3（patch16）時，該常數
    必須改為「依載入骨幹推定」。本函式以參數化版重現 seg_head.prob_map 的取特徵
    段，印出特徵格尺寸應 = 影像邊 / patch，證明 get_intermediate_layers(reshape)
    在 v3（含 register tokens）仍回正確空間格。

    ── 產品端待改（授權過關、真正重訓時）──
      backend/floorplan/seg_head.py：
        1) PATCH = 14  →  由 rc._load(...) 的骨幹名推定（14/16）
        2) prob_map() 的 nh/nw 對齊改用推定後的 PATCH
        3) get_intermediate_layers(reshape=True) 於 v3 需確認排除 4 register
           tokens（reshape=True 應已處理，本檢查即驗此點）
    """
    model, torch, patch, kind = load_backbone(name, weights)
    if model is None:
        print("→ seg-check 中止：骨幹未載入")
        return
    if kind == "v3hf":
        print("→ seg-check：transformers/HF 骨幹無 get_intermediate_layers；"
              "seg_head 適配改走 output_hidden_states+reshape，留待真正重訓時實作")
        return
    max_side = 768
    dummy = (np.random.default_rng(0).integers(0, 255, (512, 640, 3))
             ).astype(np.uint8)
    h, w = dummy.shape[:2]
    s = min(1.0, max_side / max(h, w))
    nh = max(patch, int(round(h * s / patch)) * patch)
    nw = max(patch, int(round(w * s / patch)) * patch)
    img = cv2.resize(dummy, (nw, nh), interpolation=cv2.INTER_AREA)
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    x = (rgb - rc.MEAN) / rc.STD                  # 前處理常數同 room_classifier
    with torch.no_grad():
        t = torch.from_numpy(x.transpose(2, 0, 1)[None])
        f = model.get_intermediate_layers(t, 1, reshape=True)[0]
    fh, fw = f.shape[-2], f.shape[-1]
    exp_h, exp_w = nh // patch, nw // patch
    ok = (fh, fw) == (exp_h, exp_w)
    print(f"seg-check: 影像 {nh}x{nw}  patch {patch}  → 特徵格 {fh}x{fw}"
          f"  期望 {exp_h}x{exp_w}  {'✅ 相符' if ok else '❌ 不符（需調 reshape/register 處理）'}")
    print(f"           特徵維度 D={f.shape[1]}（v2/v3 ViT-S 皆 384）")


# ─────────────────────────── 度量自測 ───────────────────────────
def selftest():
    """不需骨幹/裁切：以合成的可分/不可分特徵驗 LOO 數學方向正確。"""
    rng = np.random.default_rng(0)
    y = np.array(["A"] * 30 + ["B"] * 30 + ["C"] * 30)
    # 可分：三類各自繞不同中心
    cen = {"A": [3, 0], "B": [0, 3], "C": [-3, -3]}
    Fs = np.array([cen[l] for l in y], np.float32) + rng.normal(0, 0.4, (90, 2))
    Fs /= np.linalg.norm(Fs, axis=1, keepdims=True)
    # 不可分：全繞同一中心
    Fn = rng.normal(0, 1, (90, 2)).astype(np.float32)
    Fn /= np.linalg.norm(Fn, axis=1, keepdims=True)
    sep_nc, sep_knn = loo_nearest_centroid(Fs, y), loo_knn(Fs, y)
    noi_nc, noi_knn = loo_nearest_centroid(Fn, y), loo_knn(Fn, y)
    print(f"自測 可分特徵  NC={sep_nc:.3f}  kNN={sep_knn:.3f}  (應接近 1.0)")
    print(f"自測 隨機特徵  NC={noi_nc:.3f}  kNN={noi_knn:.3f}  (應接近 0.33)")
    assert sep_nc > 0.9 and noi_nc < 0.6, "度量方向異常"
    print("✅ 度量自測通過")


# ─────────────────────────── 主流程 ───────────────────────────
def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seg-check", action="store_true",
                    help="只驗 seg_head patch16 接線（不需裁切）")
    ap.add_argument("--selftest", action="store_true",
                    help="度量數學自測（不需骨幹/裁切）")
    a = ap.parse_args()

    if a.selftest:
        selftest()
        return

    name = os.environ.get("DINO_BACKBONE", "dinov2_vits14")
    weights = os.path.expanduser(os.environ.get("DINO_WEIGHTS", "") or "") or None

    if a.seg_check:
        seg_check(name, weights)
        return

    crops_dir = os.environ.get("DINO_CROPS",
                               os.path.join(_ROOT, "training", "room_crops"))
    split = os.environ.get("DINO_SPLIT", "train")
    max_pc = int(os.environ.get("DINO_MAX_PER_CLASS", "40"))
    tta = os.environ.get("DINO_TTA", "0") == "1"

    crops, y = load_crops(crops_dir, split, max_pc)
    print(f"裁切   : {len(crops)} 張（{split}，每類上限 {max_pc or '∞'}，"
          f"{len(np.unique(y))} 類）  TTA={'on' if tta else 'off'}")

    model, torch, _patch, kind = load_backbone(name, weights)
    if model is None:
        raise SystemExit("骨幹不可用——無法抽特徵")

    F = cls_features(model, torch, crops, kind=kind, tta=tta)
    nc = loo_nearest_centroid(F, y)
    knn = loo_knn(F, y)
    pcr = per_class_recall(F, y)

    print(f"\n── 特徵可分性（LOO，零重訓）· {name} ──")
    print(f"  最近質心 : {nc:.3f}")
    print(f"  kNN(k=5) : {knn:.3f}")
    print("  逐類 recall（樣本數）：")
    for lab, (r, n) in sorted(pcr.items(), key=lambda kv: -kv[1][0]):
        print(f"    {lab:<12} {r:.3f}  (n={n})")

    os.makedirs(os.path.join(_ROOT, "temp", "json"), exist_ok=True)
    out = os.path.join(_ROOT, "temp", "json", f"dino_probe_{name}.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"backbone": name, "split": split, "n": len(crops),
                   "tta": tta, "max_per_class": max_pc,
                   "loo_nearest_centroid": round(nc, 4),
                   "loo_knn5": round(knn, 4),
                   "per_class_recall": {k: [round(v[0], 4), v[1]]
                                        for k, v in pcr.items()}},
                  f, ensure_ascii=False, indent=2)
    print(f"\n報表   : {out}")
    print("  比較法：對 dinov2_vits14 與 dinov3_vits16 各跑一次，並排看 NC/kNN"
          "\n  ⚠ 這只量『特徵可分性上限』，非端到端辨識率——真正增益仍須重訓後跑四量尺")


if __name__ == "__main__":
    for _s in (sys.stdout, sys.stderr):
        if hasattr(_s, "reconfigure"):
            _s.reconfigure(encoding="utf-8")
    main()

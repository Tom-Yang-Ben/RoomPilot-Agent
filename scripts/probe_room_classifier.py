"""probe_room_classifier.py — 去 CubiCasa 路線 A 原型：DINOv2 房間裁切分類。

凍結 DINOv2 ViT-S/14（通用視覺預訓練，無 CubiCasa 血統）取 CLS 特徵，
只訓線性分類頭。訓練＝own_dataset 131 房裁切（8 向旋轉/鏡射擴增），
測試＝own_eval 73 房（永不進訓練；8 向 TTA 平均）。與 eval_rooms_cc
--own-eval --gt-seg 同一批 GT 房間，分數可直接對比。

用法：python scripts/probe_room_classifier.py [--crops training/room_crops]
輸出：json/eval_rooms/report_own_crops_dinov2.json
"""
import argparse
import json
import os

import cv2
import numpy as np
import torch

CLASSES = ["kitchen", "living", "bed", "bath", "entry",
           "storage", "garage", "outdoor", "space"]
MEAN = np.array([0.485, 0.456, 0.406], np.float32)
STD = np.array([0.229, 0.224, 0.225], np.float32)
SIZE = 224
SEED = 42


def letterbox(img):
    """等比縮放＋白底填滿（平面圖底色白）到 SIZE×SIZE。"""
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


def to_tensor(imgs):
    x = np.stack([(cv2.cvtColor(i, cv2.COLOR_BGR2RGB).astype(np.float32)
                   / 255.0 - MEAN) / STD for i in imgs])
    return torch.from_numpy(x.transpose(0, 3, 1, 2))


@torch.no_grad()
def extract(model, dev, rows, augment):
    """逐裁切取特徵；augment=True 回傳 8 視角展開，False 回傳 8 視角平均。"""
    feats, labels = [], []
    for m in rows:
        img = letterbox(cv2.imread(m["path"]))
        vs = variants(img)
        f = model(to_tensor(vs).to(dev)).cpu().numpy()
        if augment:
            feats.append(f)
            labels += [m["label"]] * len(vs)
        else:
            feats.append(f.mean(0, keepdims=True))
            labels.append(m["label"])
    return np.concatenate(feats), labels


def train_head(X, y, n_cls, dev, epochs=500, lr=1e-3, wd=1e-4):
    torch.manual_seed(SEED)
    Xt = torch.from_numpy(X).float().to(dev)
    yt = torch.tensor(y).to(dev)
    cnt = torch.bincount(yt, minlength=n_cls).float()
    wgt = torch.where(cnt > 0, cnt.sum() / (cnt * (cnt > 0).sum()),
                      torch.zeros_like(cnt))
    head = torch.nn.Linear(X.shape[1], n_cls).to(dev)
    opt = torch.optim.AdamW(head.parameters(), lr=lr, weight_decay=wd)
    for _ in range(epochs):
        opt.zero_grad()
        loss = torch.nn.functional.cross_entropy(head(Xt), yt, weight=wgt)
        loss.backward()
        opt.step()
    return head, float(loss)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--crops", default="training/room_crops")
    ap.add_argument("--backbone", default="dinov2_vits14",
                    help="dinov2_vits14 / dinov2_vitb14 / dinov2_vitl14")
    ap.add_argument("--report",
                    default="json/eval_rooms/report_own_crops_dinov2.json")
    a = ap.parse_args()

    manifest = json.load(open(os.path.join(a.crops, "manifest.json")))
    train = [m for m in manifest if m["split"] == "train"]
    test = [m for m in manifest if m["split"] == "test"]
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    model = torch.hub.load("facebookresearch/dinov2", a.backbone)
    model.eval().to(dev)

    print(f"特徵萃取：train {len(train)}×8 視角、test {len(test)}（TTA 平均）")
    Xtr, ytr = extract(model, dev, train, augment=True)
    Xte, yte = extract(model, dev, test, augment=False)
    ytr_i = [CLASSES.index(c) for c in ytr]

    head, loss = train_head(Xtr, ytr_i, len(CLASSES), dev)
    print(f"線性頭訓練完成 loss={loss:.4f}")

    with torch.no_grad():
        pred_i = head(torch.from_numpy(Xte).float().to(dev)).argmax(1).cpu()
    preds = [CLASSES[i] for i in pred_i]

    cm = {c: {c2: 0 for c2 in CLASSES} for c in CLASSES}
    for g, p in zip(yte, preds):
        cm[g][p] += 1
    per_cls = {}
    for c in CLASSES:
        tp = cm[c][c]
        gt_c = sum(cm[c].values())
        pd_c = sum(cm[g][c] for g in CLASSES)
        per_cls[c] = {"gt": gt_c,
                      "precision": round(tp / pd_c, 3) if pd_c else None,
                      "recall": round(tp / gt_c, 3) if gt_c else None}
    out = {"summary": {"backbone": a.backbone + "(frozen)+linear",
                       "n_train_rooms": len(train), "n_test_rooms": len(test),
                       "confusion": cm, "per_class": per_cls},
           "predictions": [{"floor": m["floor"], "idx": m["idx"],
                            "gt": g, "pred": p}
                           for m, g, p in zip(test, yte, preds)]}
    os.makedirs(os.path.dirname(a.report), exist_ok=True)
    json.dump(out, open(a.report, "w"), ensure_ascii=False, indent=1)

    print("\nGT\\預測".ljust(8)
          + "".join(c[:6].rjust(8) for c in CLASSES))
    for g in CLASSES:
        if sum(cm[g].values()):
            print(g.ljust(8) + "".join(str(cm[g][p]).rjust(8)
                                       for p in CLASSES))
    print("\n逐類  P / R:")
    for c in CLASSES:
        s = per_cls[c]
        if s["gt"] or s["precision"] is not None:
            print(f"  {c:8s} P={s['precision']}  R={s['recall']}"
                  f"  (GT {s['gt']})")
    print(f"\n報表 → {a.report}")


if __name__ == "__main__":
    main()

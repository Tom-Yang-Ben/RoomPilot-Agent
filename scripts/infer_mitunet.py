#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MitUNet 推論：png 平面圖 → 牆 mask(原圖尺寸) + 疊圖。
輸出格式與 infer_cubicasa.py 一致(<out>/<名>_mask.npz 的 wall 欄位)，
可直接餵 eval_cc_masks.py 評分、或設 config_color.ini 的 cc_mask_dir 做融合。
模型：smp.Unet(mit_b4 編碼器, scSE) + Segformer 編碼器移植，照官方 README。
權重 CC-BY-NC 4.0(禁商用)——僅供評估比較，正式部署須另行授權或自行重訓。
用法: python3 infer_mitunet.py <weights.pth> <out_dir> <img1> [img2 ...] [--size 512]
"""
import argparse
import os

import cv2
import numpy as np
import torch
import segmentation_models_pytorch as smp

MEAN = np.array([0.485, 0.456, 0.406], np.float32)
STD = np.array([0.229, 0.224, 0.225], np.float32)


def build_model(weights):
    aux = smp.Segformer(encoder_name="mit_b4", encoder_weights=None)
    model = smp.Unet(encoder_name="mit_b4", encoder_weights=None,
                     in_channels=3, classes=1, decoder_attention_type="scse")
    model.encoder = aux.encoder                  # 官方作法：移植 Segformer 編碼器
    sd = torch.load(weights, map_location="cpu", weights_only=True)  # 安全載入:只收張量
    model.load_state_dict(sd)
    model.eval()
    return model


def main():
    p = argparse.ArgumentParser(description="MitUNet 牆體分割推論")
    p.add_argument("weights")
    p.add_argument("out")
    p.add_argument("imgs", nargs="+")
    p.add_argument("--size", type=int, default=512, help="推論解析度(官方訓練=512)")
    a = p.parse_args()

    os.makedirs(a.out, exist_ok=True)
    torch.set_num_threads(os.cpu_count() or 4)
    model = build_model(a.weights)

    for path in a.imgs:
        base = os.path.splitext(os.path.basename(path))[0]
        bgr = cv2.imread(path, cv2.IMREAD_COLOR)
        if bgr is None:
            print(f"{base}: 讀不到", flush=True)
            continue
        H0, W0 = bgr.shape[:2]
        rgb = cv2.cvtColor(cv2.resize(bgr, (a.size, a.size)), cv2.COLOR_BGR2RGB)
        ten = ((rgb.astype(np.float32) / 255.0 - MEAN) / STD).transpose(2, 0, 1)
        with torch.no_grad():
            prob = torch.sigmoid(model(torch.from_numpy(ten)[None]))[0, 0].numpy()
        wall = cv2.resize((prob > 0.5).astype(np.uint8), (W0, H0),
                          interpolation=cv2.INTER_NEAREST)
        np.savez_compressed(os.path.join(a.out, base + "_mask.npz"),
                            wall=wall.astype(bool))
        vis = bgr.copy()
        vis[wall > 0] = (0, 0, 255)
        cv2.imwrite(os.path.join(a.out, base + "_cc.png"), vis)
        print(f"{base}: 牆 {int(wall.sum())}px", flush=True)


if __name__ == "__main__":
    main()

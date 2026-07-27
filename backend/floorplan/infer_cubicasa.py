#!/usr/bin/env python3
"""CubiCasa5k 推論：png 平面圖 → 牆/窗/門 mask + 房間語意/圖示類別圖(原圖尺寸) + 疊圖。
只用 floortrans 的模型定義，不碰它的 loader(lmdb/svg 相依太舊)。
輸出: <out>/<名>_mask.npz 與 <名>_cc.png 疊圖。npz 欄位：
  wall/window/door  bool mask（既有欄位，讀取端向下相容）
  room  uint8 房間語意 argmax：0背景 1戶外 2牆 3廚房 4客廳 5臥室 6浴室
                              7玄關 8欄杆 9儲藏 10車庫 11未定義
  icon  uint8 圖示 argmax：0無 1窗 2門 3衣櫃 4電器 5馬桶 6水槽
                          7桑拿椅 8壁爐 9浴缸 10煙囪
用法: python infer_cubicasa.py <weights.pkl> <out_dir> <img1> [img2 ...]
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "training/CubiCasa5k"))
import cv2
import numpy as np
import torch
import torch.nn.functional as F
from floortrans.models import get_model

WEIGHTS, OUT = sys.argv[1], sys.argv[2]
IMGS = sys.argv[3:]
MAX_SIDE = 1100          # CPU 推論限制邊長，mask 再放回原尺寸
N_CLASSES = 44           # 21 junction + 12 room + 11 icon
ROOM0 = 21
WALL_CH = ROOM0 + 2      # room class 2 = Wall
ICON0 = 33
# icon class 1 = Window, 2 = Door

os.makedirs(OUT, exist_ok=True)
_cwd = os.getcwd()                # floortrans 以相對路徑載入 floortrans/models/model_1427.pth
os.chdir(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "training/CubiCasa5k"))
model = get_model('hg_furukawa_original', 51)
os.chdir(_cwd)
model.conv4_ = torch.nn.Conv2d(256, N_CLASSES, bias=True, kernel_size=1)
model.upsample = torch.nn.ConvTranspose2d(N_CLASSES, N_CLASSES, kernel_size=4, stride=4)
# 安全載入:只收張量與 numpy 標量(微調 checkpoint 的 best_loss 統計)，杜絕 pickle 任意程式碼
torch.serialization.add_safe_globals(
    [np._core.multiarray.scalar, np.dtype]
    + [getattr(np.dtypes, n) for n in dir(np.dtypes) if n.endswith('DType')])
ckpt = torch.load(WEIGHTS, map_location='cpu', weights_only=True)
model.load_state_dict(ckpt['model_state'])
model.eval()
torch.set_num_threads(os.cpu_count() or 4)
DEV = 'cuda' if torch.cuda.is_available() else 'cpu'
model.to(DEV)


def _predict(ten, dev):
    """4 方向旋轉平均(照官方 eval)；回傳 CPU 張量。"""
    with torch.no_grad():
        acc = torch.zeros(1, N_CLASSES, *ten.shape[2:], device=dev)
        for k in range(4):
            t = torch.rot90(ten.to(dev), k, dims=(2, 3))
            p = model(t)
            p = F.interpolate(p, size=t.shape[2:], mode='bilinear', align_corners=True)
            acc += torch.rot90(p, -k, dims=(2, 3))
        return (acc / 4).cpu()

for path in IMGS:
    base = os.path.splitext(os.path.basename(path))[0]
    bgr = cv2.imread(path, cv2.IMREAD_COLOR)
    if bgr is None:
        print(f"{base}: 讀不到", flush=True); continue
    H0, W0 = bgr.shape[:2]
    sc = min(1.0, MAX_SIDE / max(H0, W0))
    img = cv2.resize(bgr, (int(W0 * sc), int(H0 * sc))) if sc < 1.0 else bgr
    h, w = img.shape[:2]
    h4, w4 = (h + 3) // 4 * 4, (w + 3) // 4 * 4      # 補到 4 的倍數
    pad = cv2.copyMakeBorder(img, 0, h4 - h, 0, w4 - w,
                             cv2.BORDER_CONSTANT, value=(255, 255, 255))
    rgb = cv2.cvtColor(pad, cv2.COLOR_BGR2RGB).astype(np.float32)
    ten = torch.from_numpy(2.0 * (rgb / 255.0) - 1.0).permute(2, 0, 1)[None]
    try:
        pred = _predict(ten, DEV)
    except torch.cuda.OutOfMemoryError:              # 大圖爆 VRAM → 單張退回 CPU
        torch.cuda.empty_cache()
        model.to('cpu')
        pred = _predict(ten, 'cpu')
        model.to(DEV)
    rooms = F.softmax(pred[0, ROOM0:ROOM0 + 12], 0).argmax(0).numpy()[:h, :w]
    icons = F.softmax(pred[0, ICON0:ICON0 + 11], 0).argmax(0).numpy()[:h, :w]
    wall = (rooms == 2).astype(np.uint8)
    win = (icons == 1).astype(np.uint8)
    door = (icons == 2).astype(np.uint8)
    rooms = rooms.astype(np.uint8)
    icons = icons.astype(np.uint8)
    if sc < 1.0:                                     # 放回原尺寸
        wall = cv2.resize(wall, (W0, H0), interpolation=cv2.INTER_NEAREST)
        win = cv2.resize(win, (W0, H0), interpolation=cv2.INTER_NEAREST)
        door = cv2.resize(door, (W0, H0), interpolation=cv2.INTER_NEAREST)
        rooms = cv2.resize(rooms, (W0, H0), interpolation=cv2.INTER_NEAREST)
        icons = cv2.resize(icons, (W0, H0), interpolation=cv2.INTER_NEAREST)
    np.savez_compressed(os.path.join(OUT, base + "_mask.npz"),
                        wall=wall.astype(bool), window=win.astype(bool),
                        door=door.astype(bool), room=rooms, icon=icons)
    vis = bgr.copy()
    vis[wall > 0] = (0, 0, 255)                      # 紅=牆
    vis[win > 0] = (0, 200, 0)                       # 綠=窗
    vis[door > 0] = (0, 165, 255)                    # 橘=門
    cv2.imwrite(os.path.join(OUT, base + "_cc.png"), vis)
    print(f"{base}: 牆 {int(wall.sum())}px 窗 {int(win.sum())}px 門 {int(door.sum())}px",
          flush=True)

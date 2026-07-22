"""apply_cubicasa_patches.py — CubiCasa5k 程式庫的本地相容補丁（可重複執行）。

CubiCasa5k/ 不進版控（.gitignore 註記 re-clone 重建），上游最後更新於
2019，新環境需要多處補丁。全部做成冪等腳本：clone 後跑一次即可，
已補丁的檔案自動跳過。

補丁清單：
1. svg_utils np.matrix → np.array：numpy 2.x 拆行指派 ValueError，任何
   含 FixedFurniture 圖示的樣本都無法被 House 解析（round-trip/訓練中招）
2. train.py 資料格式 lmdb → txt：微調直接現場解析 SVG，不建 lmdb
3. train.py DataFrame.append → pd.concat：pandas 2.x 移除 append
4. uncertainty_loss 統計轉 float：0 維 tensor 進 DataFrame 後 mean() 會
   TypeError，epoch 結尾才爆
5. train.py 驗證期單張 OOM 跳過：驗證做整圖推論，大圖（如 own_val 的
   floor01 1908×2732）在 4GB 卡 OOM；跳過該張仍有其餘 val 樣本監控

用法：python scripts/apply_cubicasa_patches.py [--dir CubiCasa5k]
"""
import argparse
import os

# (檔案相對路徑, 說明, OLD, NEW)
PATCHES = [
    ("floortrans/loaders/svg_utils.py", "np.matrix → np.array（numpy 2.x）",
     """            v = np.matrix([[X[i]], [Y[i]], [1]])
            vv = np.matmul(M, v)
            new_x, new_y, _ = np.round(np.matmul(M_p, vv))
            X[i] = new_x
            Y[i] = new_y
    else:
        for i in range(len(X)):
            v = np.matrix([[X[i]], [Y[i]], [1]])
            vv = np.matmul(M, v)
            new_x, new_y, _ = np.round(vv)
            X[i] = new_x
            Y[i] = new_y""",
     """            v = np.array([[X[i]], [Y[i]], [1.0]])
            vv = np.round(np.matmul(M_p, np.matmul(M, v)))
            X[i] = float(vv[0, 0])
            Y[i] = float(vv[1, 0])
    else:
        for i in range(len(X)):
            v = np.array([[X[i]], [Y[i]], [1.0]])
            vv = np.round(np.matmul(M, v))
            X[i] = float(vv[0, 0])
            Y[i] = float(vv[1, 0])"""),

    ("train.py", "資料格式 lmdb → txt（現場解析 SVG）",
     """    train_set = FloorplanSVG(args.data_path, 'train.txt', format='lmdb',
                             augmentations=aug)
    val_set = FloorplanSVG(args.data_path, 'val.txt', format='lmdb',
                           augmentations=DictToTensor())""",
     """    train_set = FloorplanSVG(args.data_path, 'train.txt', format='txt',
                             augmentations=aug)
    val_set = FloorplanSVG(args.data_path, 'val.txt', format='txt',
                           augmentations=DictToTensor())"""),

    ("train.py", "訓練迴圈 DataFrame.append → pd.concat（pandas 2.x）",
     """            losses = losses.append(criterion.get_loss(), ignore_index=True)
            variances = variances.append(criterion.get_var(), ignore_index=True)
            ss = ss.append(criterion.get_s(), ignore_index=True)""",
     """            losses = pd.concat([losses, criterion.get_loss()], ignore_index=True)
            variances = pd.concat([variances, criterion.get_var()], ignore_index=True)
            ss = pd.concat([ss, criterion.get_s()], ignore_index=True)"""),

    ("train.py", "驗證迴圈 DataFrame.append → pd.concat（pandas 2.x）",
     """                val_losses = val_losses.append(criterion.get_loss(), ignore_index=True)
                val_variances = val_variances.append(criterion.get_var(), ignore_index=True)
                val_ss = val_ss.append(criterion.get_s(), ignore_index=True)""",
     """                val_losses = pd.concat([val_losses, criterion.get_loss()], ignore_index=True)
                val_variances = pd.concat([val_variances, criterion.get_var()], ignore_index=True)
                val_ss = pd.concat([val_ss, criterion.get_s()], ignore_index=True)"""),

    ("train.py", "驗證期單張 CUDA OOM 跳過（4GB 卡整圖推論退路）",
     """                outputs = model(images_val)
                labels_val = F.interpolate(labels_val, size=outputs.shape[2:], mode='bilinear', align_corners=False)""",
     """                try:
                    outputs = model(images_val)
                except torch.cuda.OutOfMemoryError:
                    del images_val, labels_val
                    torch.cuda.empty_cache()
                    logger.info("val sample %d OOM, skipped", i_val)
                    continue
                labels_val = F.interpolate(labels_val, size=outputs.shape[2:], mode='bilinear', align_corners=False)"""),

    ("train.py", "兩個 loader 關 pin_memory（WSL 鎖頁記憶體與 GPU 位址空間共用，4GB 卡 VRAM 吃滿後 pin 執行緒 CUDA OOM）",
     """    trainloader = data.DataLoader(train_set, batch_size=args.batch_size,
                                  num_workers=num_workers, shuffle=True, pin_memory=True)
    valloader = data.DataLoader(val_set, batch_size=1,
                                num_workers=num_workers, pin_memory=True)""",
     """    trainloader = data.DataLoader(train_set, batch_size=args.batch_size,
                                  num_workers=num_workers, shuffle=True, pin_memory=False)
    valloader = data.DataLoader(val_set, batch_size=1,
                                num_workers=num_workers, pin_memory=False)"""),

    ("floortrans/losses/uncertainty_loss.py", "get_loss 統計轉 float（pandas 2.x）",
     """        d = {'total loss': [self.loss.data],
             'room loss': [self.loss_rooms.data],
             'icon loss': [self.loss_icons.data],
             'heatmap loss': [self.loss_heatmap.data],
             'total loss with variance': [self.loss_var.data],
             'room loss with variance': [self.loss_rooms_var.data],
             'icon loss with variance': [self.loss_icons_var.data],
             'heatmap loss with variance': [self.loss_heatmap_var.data]}""",
     """        d = {'total loss': [float(self.loss.data)],
             'room loss': [float(self.loss_rooms.data)],
             'icon loss': [float(self.loss_icons.data)],
             'heatmap loss': [float(self.loss_heatmap.data)],
             'total loss with variance': [float(self.loss_var.data)],
             'room loss with variance': [float(self.loss_rooms_var.data)],
             'icon loss with variance': [float(self.loss_icons_var.data)],
             'heatmap loss with variance': [float(self.loss_heatmap_var.data)]}"""),

    ("floortrans/losses/uncertainty_loss.py", "get_var 統計轉 float（pandas 2.x）",
     """        d = {'room variance': [variance[0]],
             'icon variance': [variance[1]]}
        for i, m in enumerate(mse_variance):
            key = 'heatmap ' + str(i)
            d[key] = [m]""",
     """        d = {'room variance': [float(variance[0])],
             'icon variance': [float(variance[1])]}
        for i, m in enumerate(mse_variance):
            key = 'heatmap ' + str(i)
            d[key] = [float(m)]"""),

    ("floortrans/losses/uncertainty_loss.py", "get_s 統計轉 float（pandas 2.x）",
     """        d = {'room s': [s[0]],
             'icon s': [s[1]]}
        for i, m in enumerate(mse_s):
            key = 'heatmap s' + str(i)
            d[key] = [m]""",
     """        d = {'room s': [float(s[0])],
             'icon s': [float(s[1])]}
        for i, m in enumerate(mse_s):
            key = 'heatmap s' + str(i)
            d[key] = [float(m)]"""),
]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dir", default="training/CubiCasa5k")
    a = ap.parse_args()

    for rel, desc, old, new in PATCHES:
        path = os.path.join(a.dir, rel)
        with open(path) as f:
            src = f.read()
        if new in src:
            print(f"已補丁，跳過：{rel}（{desc}）")
            continue
        if old not in src:
            raise SystemExit(f"補丁目標碼不符（上游改版？）：{rel}（{desc}）")
        with open(path, "w") as f:
            f.write(src.replace(old, new))
        print(f"補丁完成：{rel}（{desc}）")


if __name__ == "__main__":
    main()

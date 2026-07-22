"""pack_finetune_data.py — 路線圖 C：打包微調資料 zip。

內容：Identify_ans/own_dataset 43 張（管線草稿→人工修正後）＋ hq_arch train 前 300
樣本（防災難性遺忘）＋混合清單（own 行 ×3 過採樣，直混會被 300 張淹沒）。
own_val.txt 僅作訓練監控；正式驗收永遠走路線 A 的 val/test 評分集。

用法：python pack_finetune_data.py [--n-hq 300] [--oversample 3]
產出：training/finetune_data.zip（本機訓練解壓用；亦可上傳雲端環境）
"""
import argparse
import os
import shutil
import zipfile

DATA = "training/CubiCasa5k/data/cubicasa5k"
SUBSET = "high_quality_architectural"
OWN = "Identify_ans/own_dataset"
STAGE = "training/finetune_data"


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--n-hq", type=int, default=300)
    ap.add_argument("--oversample", type=int, default=3)
    a = ap.parse_args()

    with open(os.path.join(DATA, "train.txt")) as f:
        hq = sorted((ln.strip().strip("/").split("/")[1] for ln in f
                     if ln.strip().startswith("/" + SUBSET + "/")), key=int)
    hq = [i for i in hq
          if os.path.isfile(os.path.join(DATA, SUBSET, i, "F1_scaled.png"))
          and os.path.isfile(os.path.join(DATA, SUBSET, i, "model.svg"))
          ][:a.n_hq]
    with open(os.path.join(OWN, "own_train.txt")) as f:
        own = [ln.strip().strip("/") for ln in f if ln.strip()]
    with open(os.path.join(OWN, "own_val.txt")) as f:
        own_val = [ln.strip().strip("/") for ln in f if ln.strip()]

    if os.path.isdir(STAGE):
        shutil.rmtree(STAGE)
    for i in hq:
        shutil.copytree(os.path.join(DATA, SUBSET, i),
                        os.path.join(STAGE, SUBSET, i))
    for n in own:
        d = os.path.join(STAGE, "own", n)
        os.makedirs(d)
        for fn in ("F1_scaled.png", "F1_original.png", "model.svg"):
            shutil.copy(os.path.join(OWN, n, fn), os.path.join(d, fn))

    train_lines = [f"/own/{n}/\n" for n in own] * a.oversample \
                + [f"/{SUBSET}/{i}/\n" for i in hq]
    with open(os.path.join(STAGE, "train.txt"), "w") as f:
        f.writelines(train_lines)
    with open(os.path.join(STAGE, "val.txt"), "w") as f:
        f.writelines(f"/own/{n}/\n" for n in own_val)

    zip_path = "training/finetune_data.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for root, _dirs, files in os.walk(STAGE):
            for fn in files:
                p = os.path.join(root, fn)
                z.write(p, os.path.relpath(p, "."))
    mb = os.path.getsize(zip_path) / 1e6
    print(f"train.txt {len(train_lines)} 行（own {len(own)}×{a.oversample}"
          f" + hq_arch {len(hq)}）  val.txt {len(own_val)} 行")
    print(f"→ {zip_path}（{mb:.0f} MB，上傳 Google Drive 根目錄）")


if __name__ == "__main__":
    main()

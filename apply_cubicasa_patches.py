"""apply_cubicasa_patches.py — CubiCasa5k 程式庫的 numpy 2.x 相容補丁。

上游 svg_utils.get_icon 用 np.matrix 拆行指派（X[i] = 1x1 matrix），
numpy 2.x 直接 ValueError——任何含 FixedFurniture 圖示的樣本都無法
被 House 解析（本機 round-trip 與 Colab 訓練都會中招）。

CubiCasa5k/ 不進版控（.gitignore 註記 re-clone 重建），故補丁做成
可重複執行腳本：clone 後跑一次即可，已補丁則跳過。Colab notebook
的環境 cell 同樣呼叫本腳本。

用法：python apply_cubicasa_patches.py [--dir CubiCasa5k]
"""
import argparse
import os

OLD = """            v = np.matrix([[X[i]], [Y[i]], [1]])
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
            Y[i] = new_y"""

NEW = """            v = np.array([[X[i]], [Y[i]], [1.0]])
            vv = np.round(np.matmul(M_p, np.matmul(M, v)))
            X[i] = float(vv[0, 0])
            Y[i] = float(vv[1, 0])
    else:
        for i in range(len(X)):
            v = np.array([[X[i]], [Y[i]], [1.0]])
            vv = np.round(np.matmul(M, v))
            X[i] = float(vv[0, 0])
            Y[i] = float(vv[1, 0])"""


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dir", default="CubiCasa5k")
    a = ap.parse_args()
    path = os.path.join(a.dir, "floortrans", "loaders", "svg_utils.py")
    with open(path) as f:
        src = f.read()
    if NEW in src:
        print(f"已補丁，跳過：{path}")
        return
    if OLD not in src:
        raise SystemExit(f"補丁目標碼不符（上游改版？）：{path}")
    with open(path, "w") as f:
        f.write(src.replace(OLD, NEW))
    print(f"補丁完成：{path}（np.matrix → np.array，numpy 2.x 相容）")


if __name__ == "__main__":
    main()

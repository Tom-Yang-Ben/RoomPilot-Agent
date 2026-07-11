# IKEA-Dataset 下載與整理步驟

最後更新：2026-06-28

這份文件是給第一批實作用的，目標很單純：

1. 先把 IKEA-Dataset 的客廳資料拿進來
2. 先挑出 10 種客廳家具的第一批樣本
3. 把樣本整理成後續 3D 生成可以直接用的格式

官方 repo 根目錄有：

- `Living Room 1.zip`
- `Living Room2.zip`

而 README 也說明這個資料集有 12,600+ 張圖片，並且多數物件有尺寸描述，所以很適合拿來做真實尺寸家具主線。

## 1. 下載來源

優先只下載這兩個客廳包：

1. `Living Room 1.zip`
2. `Living Room2.zip`

不要一開始就抓其他房間包，因為我們現在的主線是客廳家具。

## 2. 放進哪裡

下載完後，放到這兩個資料夾：

```text
dataset/ikea/raw/living_room_1/
dataset/ikea/raw/living_room_2/
```

如果你是直接把 zip 留著也可以，但建議解壓後仍保留原始 zip，方便之後重跑。

## 3. 建議整理順序

先從下面這 10 種家具開始：

1. 沙發
2. 扶手椅
3. 單人椅
4. 茶几
5. 邊几
6. 電視櫃
7. 書櫃
8. 收納櫃
9. 腳凳
10. 層架 / 展示櫃

## 4. 每類先抓幾張

每一類先抓：

- 1 張主樣本
- 1 到 2 張備樣本

不要一開始就抓太多，先把第一輪流程跑通。

## 5. 下載後怎麼分

把每一類選好的圖片放到：

```text
dataset/ikea/selected/sofa/
dataset/ikea/selected/armchair/
dataset/ikea/selected/chair/
dataset/ikea/selected/coffee_table/
dataset/ikea/selected/side_table/
dataset/ikea/selected/tv_stand/
dataset/ikea/selected/bookshelf/
dataset/ikea/selected/storage_cabinet/
dataset/ikea/selected/ottoman/
dataset/ikea/selected/shelf_display/
```

## 6. 檔名怎麼取

建議格式：

```text
{category}_ikea_{item_id}_source.jpg
{category}_ikea_{item_id}_raw.glb
{category}_ikea_{item_id}_normalized.glb
{category}_ikea_{item_id}.json
```

範例：

```text
sofa_ikea_0001_source.jpg
sofa_ikea_0001_raw.glb
sofa_ikea_0001_normalized.glb
sofa_ikea_0001.json
```

## 7. JSON 要放什麼

每個樣本至少記這些欄位：

- `category`
- `source_file`
- `width_cm`
- `depth_cm`
- `height_cm`
- `notes`
- `selected_view`

## 8. 篩選原則

共同原則：

- 家具主體清楚
- 輪廓完整
- 遮擋少
- 有尺寸描述
- 適合做 3D

不合格就先不要：

- 遮擋太多
- 反光太重
- 背景太亂
- 底部看不懂
- 家具不是這一類的代表款

## 9. 後續接 3D

選好的圖片之後，下一步就會進：

1. raw GLB 生成
2. normalize
3. bottom-center pivot
4. Y = 0 貼地
5. 真實尺寸縮放
6. 輸出到 `web_fastapi/static/models/`

## 10. 這份文件的用途

這份文件只負責「下載與整理」。  
如果你要看完整主線、決策、後續風格，還是回去看：

- `PROJECT_CONTEXT.md`
- `docs/ikea_dataset_plan.md`
- `docs/ikea_dataset_checklist.md`

## 11. WSL 下載指令

如果你現在在 WSL，而且專案根目錄是 `~/projects/test_furniture`，可以直接這樣做：

```bash
cd ~/projects/test_furniture
mkdir -p dataset/ikea/raw/living_room_1
mkdir -p dataset/ikea/raw/living_room_2
git clone https://github.com/valexande/IKEA-Dataset.git dataset/ikea/source_repo
cp "dataset/ikea/source_repo/Living Room 1.zip" "dataset/ikea/raw/living_room_1/"
cp "dataset/ikea/source_repo/Living Room2.zip" "dataset/ikea/raw/living_room_2/"
```

如果你要確認有沒有放對，再跑：

```bash
ls -lh dataset/ikea/raw/living_room_1
ls -lh dataset/ikea/raw/living_room_2
```

## 12. Windows 手動下載方式

如果你比較想用瀏覽器：

1. 打開 [IKEA-Dataset](https://github.com/valexande/IKEA-Dataset)
2. 點 `Living Room 1.zip`
3. 點 `Living Room2.zip`
4. 下載後放進：
   - `dataset/ikea/raw/living_room_1/`
   - `dataset/ikea/raw/living_room_2/`

這種方式適合你想手動確認檔案時使用。

## 13. 解壓縮步驟

下載完如果是 zip，先解壓縮成資料夾內容，但 zip 本身建議保留。

### WSL

如果你在 WSL，且 zip 已經放到專案內，可以用：

```bash
cd ~/projects/test_furniture
unzip -o "dataset/ikea/raw/living_room_1/Living Room 1.zip" -d "dataset/ikea/raw/living_room_1/"
unzip -o "dataset/ikea/raw/living_room_2/Living Room2.zip" -d "dataset/ikea/raw/living_room_2/"
```

`-o` 的意思是如果同名檔案已經存在，就直接覆蓋。這樣你之後重跑不會卡住。

### Windows PowerShell

如果你在 Windows PowerShell，可以用：

```powershell
Expand-Archive -LiteralPath "D:\產業新兵計畫\期末專題\test_furniture\dataset\ikea\raw\living_room_1\Living Room 1.zip" -DestinationPath "D:\產業新兵計畫\期末專題\test_furniture\dataset\ikea\raw\living_room_1" -Force
Expand-Archive -LiteralPath "D:\產業新兵計畫\期末專題\test_furniture\dataset\ikea\raw\living_room_2\Living Room2.zip" -DestinationPath "D:\產業新兵計畫\期末專題\test_furniture\dataset\ikea\raw\living_room_2" -Force
```

`-Force` 是為了讓重跑時可以直接覆蓋。

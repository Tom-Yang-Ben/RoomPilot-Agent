# IKEA GLB 下載工具簡易說明書

這個工具可以從 IKEA 商品頁尋找可下載的 3D 模型檔案，也就是 `.glb` 檔，並把下載結果整理成 metadata。

目前程式支援的 IKEA 網站：

| 代碼 | 國家 | 網址 |
| --- | --- | --- |
| `fi` | 芬蘭 | https://www.ikea.com/fi/en |
| `jp` | 日本 | https://www.ikea.com/jp/en |

## 1. 安裝套件

第一次使用前，請在專案資料夾執行：

```bash
pip install -r requirements.txt
```

## 2. 執行程式

在專案資料夾執行：

```bash
python ikea_category_glb_downloader.py
```

## 3. 使用流程

程式會依序問你三件事。

### 第一步：選 IKEA 網站

畫面會顯示：

```text
請選擇 IKEA 網站：
  fi  = 芬蘭 - https://www.ikea.com/fi/en（預設）
  jp  = 日本 - https://www.ikea.com/jp/en
```

想抓芬蘭就輸入：

```text
fi
```

想抓日本就輸入：

```text
jp
```

直接按 Enter 會使用預設的芬蘭 `fi`。

### 第二步：選家具分類或細分類

程式會顯示家具分類清單，格式是：

```text
英文代碼 = 中文家具名稱
```

左邊英文代碼是你要輸入的內容，右邊中文是說明。

例如椅子分類會像這樣：

```text
chairs = 椅子 / 扶手椅 / 凳子
  * chairs             = 全部椅子
  - dining-chairs      = 餐椅
  - office-chairs      = 辦公椅
  - armchairs          = 扶手椅
  - stools-benches     = 凳子 / 長凳
  - gaming-chairs      = 電競椅
```

如果你想找辦公椅，就輸入：

```text
office-chairs
```

也可以直接輸入大分類，例如：

```text
chairs
```

但大分類裡面很多商品可能沒有 GLB，所以通常建議先用細分類，會比較容易找到。

## 4. 家具分類表

輸入時請使用「輸入代碼」欄位。中文名稱只是幫你辨認家具種類。

| 大分類 | 輸入代碼 | 中文名稱 |
| --- | --- | --- |
| 書櫃 / 層架 | `bookcases` | 書櫃 |
| 書櫃 / 層架 | `shelving-units` | 層架 / 置物架 |
| 書櫃 / 層架 | `wall-shelves` | 壁架 |
| 沙發 | `sofas` | 全部沙發 |
| 沙發 | `fabric-sofas` | 布沙發 |
| 沙發 | `leather-sofas` | 皮沙發 / 仿皮沙發 |
| 沙發 | `sofa-beds` | 沙發床 |
| 沙發 | `modular-sofas` | 模組沙發 |
| 沙發 | `armchairs` | 扶手椅 |
| 椅子 / 扶手椅 / 凳子 | `chairs` | 全部椅子 |
| 椅子 / 扶手椅 / 凳子 | `dining-chairs` | 餐椅 |
| 椅子 / 扶手椅 / 凳子 | `office-chairs` | 辦公椅 |
| 椅子 / 扶手椅 / 凳子 | `armchairs` | 扶手椅 |
| 椅子 / 扶手椅 / 凳子 | `stools-benches` | 凳子 / 長凳 |
| 椅子 / 扶手椅 / 凳子 | `gaming-chairs` | 電競椅 |
| 桌子 / 書桌 | `tables` | 全部桌子 |
| 桌子 / 書桌 | `dining-tables` | 餐桌 |
| 桌子 / 書桌 | `desks` | 書桌 / 電腦桌 |
| 桌子 / 書桌 | `coffee-tables` | 茶几 |
| 桌子 / 書桌 | `bedside-tables` | 床邊桌 |
| 桌子 / 書桌 | `bar-tables` | 吧台桌 |
| 床 / 床架 | `beds` | 全部床具 |
| 床 / 床架 | `bed-frames` | 床架 |
| 床 / 床架 | `sofa-beds` | 沙發床 |
| 床 / 床架 | `mattresses` | 床墊 |
| 床 / 床架 | `bedside-tables` | 床邊桌 |
| 衣櫃 | `wardrobes` | 全部衣櫃 |
| 衣櫃 | `pax-wardrobes` | PAX 衣櫃系統 |
| 衣櫃 | `open-wardrobes` | 開放式衣櫃 |
| 衣櫃 | `clothes-racks` | 衣架 / 掛衣架 |
| 地毯 | `rugs` | 全部地毯 |
| 地毯 | `large-medium-rugs` | 大型 / 中型地毯 |
| 地毯 | `small-rugs` | 小地毯 |
| 地毯 | `door-mats` | 門墊 |
| 桌燈 / 燈具 | `table-lamps` | 桌燈 |
| 桌燈 / 燈具 | `floor-lamps` | 立燈 |
| 桌燈 / 燈具 | `work-lamps` | 工作燈 |
| 桌燈 / 燈具 | `lamp-shades-bases` | 燈罩 / 燈座 |
| 櫃子 / 收納系統 | `cabinets` | 全部收納系統 |
| 櫃子 / 收納系統 | `cabinets-cupboards` | 櫃子 / 碗櫃 |
| 櫃子 / 收納系統 | `tv-benches` | 電視櫃 |
| 櫃子 / 收納系統 | `chests-of-drawers` | 抽屜櫃 |
| 櫃子 / 收納系統 | `sideboards` | 餐邊櫃 / 玄關桌 |

## 5. 輸入下載數量

程式會問：

```text
請輸入要下載幾個 GLB 模型：
```

建議第一次測試先輸入：

```text
1
```

確認可以成功下載後，再增加數量。

## 6. 下載結果在哪裡

下載完成後，檔案會放在：

```text
downloaded-files/<網站代碼>-<分類代碼>/
```

例如：

```text
downloaded-files/fi-office-chairs/
downloaded-files/jp-bookcases/
```

資料夾裡會有：

| 檔案 | 說明 |
| --- | --- |
| `.glb` | 下載到的 3D 模型 |
| `*_glb_metadata.csv` | 商品資料 CSV |
| `*_glb_metadata.json` | 商品資料 JSON |

## 7. 注意事項

不是每一個 IKEA 商品都有 GLB。程式會逐一檢查商品，如果沒有 GLB，就會跳過。

大分類通常商品很多，但沒有 GLB 的商品也很多。想更快找到模型，建議優先輸入細分類，例如：

```text
office-chairs
desks
bookcases
sofa-beds
```

如果 PowerShell 顯示中文亂碼，通常是終端機編碼問題，不一定是檔案壞掉。

## 授權與來源

本專案基於 apinanaivot/IKEA-3d-model-batch-downloader 修改：

https://github.com/apinanaivot/IKEA-3d-model-batch-downloader

原專案使用 GPL-3.0 授權，因此本專案也保留 GPL-3.0 授權。詳細授權內容請查看 `LICENSE` 檔案。

如果你要把這個專案上傳到自己的 GitHub，請保留 `LICENSE` 檔案，並保留本段來源說明。

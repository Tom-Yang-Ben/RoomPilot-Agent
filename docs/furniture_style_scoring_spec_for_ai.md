# 家具風格前處理打分規格（供另一個 AI 重建分類器）

更新日期：2026-07-08

## 1. 這份文件要解決什麼

這份文件的目的，是讓另一個 AI 或另一支程式能夠盡量模仿 RoomPilot 目前的「家具風格前處理」邏輯，為每件家具產生：

- `style_candidates`
- `primary_style`
- `style_confidence`
- `style_rule_flags`
- `style_assignment_source`
- `manual_style_note_zh`（若有人工覆核）

重點要先說清楚：

- 目前這個 repo **沒有**保存真正產生 `ikea_furniture_style_database.json` 的原始打分腳本。
- repo 內可以直接驗證的是：
  - 風格規格資料 `roompilot/catalog/data/style_moodboard.json`
  - 已完成標註的成品 `roompilot/catalog/data/ikea_furniture_style_database.json`
  - 文件說明 `docs/STYLE_DATA_STATUS.md`
- 因此本文件分成兩種資訊：
  - `已驗證`：可直接從 repo 內容確認
  - `高可信推論`：從資料產物的欄位與 `reasons` 反推

如果你的目標是「做出與現在資料分布接近的分類器」，這份文件足夠作為重建規格。

## 2. 整體流程

目前的做法不是「看整個房間決定家具風格」，也不是「直接看 GLB 幾何做視覺分類」。

而是：

1. 先定義每種風格的規格
2. 對每件家具抽取文字與結構特徵
3. 對每個風格各自累積分數
4. 產生 `style_candidates`
5. 取最高分作為 `primary_style`
6. 少數案例再做人為覆核

## 3. 輸入資料

### 3.1 家具資料

另一個 AI 至少需要下列欄位：

- `name_en`
- `name_zh_raw`
- `normalized_type`
- `color`
- `material`
- `category_label`
- `subcategory_slug`

實務上，很多命中規則都來自英文名稱中的 token。

### 3.2 風格規格資料

來源：`roompilot/catalog/data/style_moodboard.json`

每個 style 至少包含：

- `style_id`
- `keywords_zh`
- `main_colors_zh`
- `materials_zh`
- `shape_features_zh`
- `avoid_elements_zh`
- `furniture_mapping_zh`

可參考：

- [style_moodboard.json](/D:/產業新兵計畫/期末專題/7-7%20網頁版/RoomPilot-Agent/roompilot/catalog/data/style_moodboard.json:1)
- [style_progress_handoff_2026-07-03.md](/D:/產業新兵計畫/期末專題/7-7%20網頁版/RoomPilot-Agent/docs/style_progress_handoff_2026-07-03.md:37)

## 4. 輸出資料格式

每件家具最終應產出：

```json
{
  "style_candidates": [
    {
      "style_id": "modern",
      "score": 0.52,
      "reasons": ["match:white", "match:tv", "type:tv-bench"]
    }
  ],
  "primary_style": "modern",
  "style_confidence": 0.52,
  "style_assignment_source": "scored",
  "style_rule_flags": []
}
```

欄位含義：

- `style_candidates`
  - 所有候選風格與各自分數
- `primary_style`
  - 分數最高的風格
- `style_confidence`
  - 通常等於最高分風格的分數
- `style_assignment_source`
  - `scored` / `manual_review` / `fallback`
- `style_rule_flags`
  - 額外語意旗標，例如高彩度、兒童系列
- `manual_style_note_zh`
  - 只有人工覆核時才需要

可參考：

- [STYLE_DATA_STATUS.md](/D:/產業新兵計畫/期末專題/7-7%20網頁版/RoomPilot-Agent/docs/STYLE_DATA_STATUS.md:30)

## 5. 已驗證的打分證據

### 5.1 風格分數真的存在於資料內

以下是成品資料中的實例：

- [ikea_furniture_style_database.json](/D:/產業新兵計畫/期末專題/7-7%20網頁版/RoomPilot-Agent/roompilot/catalog/data/ikea_furniture_style_database.json:4421)
- [ikea_furniture_style_database.json](/D:/產業新兵計畫/期末專題/7-7%20網頁版/RoomPilot-Agent/roompilot/catalog/data/ikea_furniture_style_database.json:100721)

可看到：

- `style_candidates[].score`
- `primary_style`
- `style_confidence`
- `reasons`

### 5.2 `reasons` 暗示了前處理規則

已驗證到的原因 token 包含：

- `match:white`
- `match:black`
- `match:beige`
- `match:yellow`
- `match:oak`
- `match:rattan`
- `match:tv`
- `match:storage`
- `match:glass`
- `type:tv-bench`
- `context:high_chroma_fits_eclectic`
- `context:high_chroma_blocks_minimal`
- `context:novelty_motif_fits_eclectic`
- `context:novelty_motif_blocks_minimal`
- `context:kids_accessory_not_primary_fit`
- `manual_review`

這代表分類依據主要來自：

- 顏色
- 材質
- 家具類型
- 名稱關鍵字
- 情境修正規則

## 6. 風格旗標規則

### 6.1 已驗證存在的旗標

根據文件與成品資料，已確認旗標有：

- `novelty_motif`
- `high_chroma`
- `children_series`
- `soft_kids_accessory`

可參考：

- [STYLE_DATA_STATUS.md](/D:/產業新兵計畫/期末專題/7-7%20網頁版/RoomPilot-Agent/docs/STYLE_DATA_STATUS.md:55)

### 6.2 這些旗標的作用

`高可信推論`

這些旗標不是獨立風格，而是對原始風格分數做修正。

大致邏輯如下：

- `high_chroma`
  - 明亮高彩度色，如 yellow / orange / turquoise / hot pink / primary red
  - 會壓低 `scandinavian`、`minimalist_muji`、`nordic_modern`、`wabi_sabi`
  - 可能提高 `eclectic`
- `novelty_motif`
  - 特殊造型、圖案、童趣 motif，如 mushroom / animal / pattern
  - 會壓低簡約安靜風格
  - 可能提高 `eclectic`
- `children_series`
  - 標記該家具屬於兒童系列
  - 本身不必然決定風格，但常搭配其他旗標影響判斷
- `soft_kids_accessory`
  - 軟性兒童配件，不應輕易成為主風格代表家具

## 7. 高可信重建規則

以下規則是從 `style_candidates[].reasons` 與人工覆核案例反推，建議你交給另一個 AI 直接照做。

### 7.1 基本分數概念

每個風格從 `0.0` 開始。

當命中某種特徵時，就為該風格加分或扣分。

最後：

1. 把所有分數 `<= 0` 的候選保留為 `0` 或直接略過
2. 將大於 `0` 的風格按分數排序
3. 第一名設為 `primary_style`
4. 第一名分數設為 `style_confidence`

### 7.2 建議使用的特徵來源

對每件家具建立可比對 token：

- 英文名稱 token：從 `name_en` 切字
- 中文名稱 token：從 `name_zh_raw` 擷取顏色或材質詞
- `normalized_type`
- `color`
- `material`
- `category_label`

建議全部轉成小寫、去符號、拆成 token。

### 7.3 顏色與材質加分

`高可信推論`

依據目前資料，以下映射最值得優先重建：

- 白、淺灰、米色、淺木、oak、pine、birch
  - `scandinavian += 0.15`
  - `minimalist_muji += 0.15`
  - `nordic_modern += 0.15`
- 黑、深灰、玻璃、金屬、chrome
  - `modern += 0.15`
  - `industrial += 0.15`
- rattan、藤編、自然纖維、beige、tan
  - `melad += 0.15`
  - `nordic_modern += 0.15`
- brass、gold、glass
  - `light_luxury += 0.15`
- brown、wood、country 取向木色
  - `american_country += 0.15`
  - `american += 0.15`

分值 `0.15` 是因為成品資料裡大量出現單一命中後得到 `0.15` 的 pattern。

### 7.4 類型加分

`已驗證 + 高可信推論`

某些類型會帶有預設風格傾向。

已驗證例子：

- `type:tv-bench`

例如：

- `modern = 0.52`
- `scandinavian = 0.37`
- `nordic_modern = 0.37`
- `american = 0.22`

見：

- [ikea_furniture_style_database.json](/D:/產業新兵計畫/期末專題/7-7%20網頁版/RoomPilot-Agent/roompilot/catalog/data/ikea_furniture_style_database.json:100721)

建議重建為：

- 若 `normalized_type == "tv-bench"`：
  - `modern += 0.22`
  - `scandinavian += 0.22`
  - `nordic_modern += 0.22`
  - `american += 0.22`

再依顏色或材質追加額外分數。

### 7.5 名稱功能詞加分

`高可信推論`

從資料可見這類 `match`：

- `match:tv`
- `match:storage`
- `match:glass`

建議規則：

- 若名稱含 `tv`
  - `modern += 0.15`
- 若名稱含 `storage`
  - `modern += 0.15`
  - `nordic_modern += 0.08`
- 若名稱含 `glass`
  - `light_luxury += 0.15`
  - `modern += 0.08`
  - `nordic_modern += 0.08`

### 7.6 高彩度懲罰與混搭加分

`已驗證 + 高可信推論`

當命中以下 token，可設 `high_chroma`：

- yellow
- orange
- turquoise
- hot pink
- primary red
- multicolour

若 `high_chroma = true`：

- `eclectic += 0.15`
- `scandinavian -= 0.03`
- `minimalist_muji -= 0.03`
- `nordic_modern -= 0.03`
- `wabi_sabi -= 0.03`

如果要更貼近現有資料，可以在 `reasons` 中附加：

- `context:high_chroma_fits_eclectic`
- `context:high_chroma_blocks_minimal`

說明文件也明講北歐風要排除跳色、兒童高對比圖樣：

- [STYLE_DATA_STATUS.md](/D:/產業新兵計畫/期末專題/7-7%20網頁版/RoomPilot-Agent/docs/STYLE_DATA_STATUS.md:73)

### 7.7 童趣 motif 修正

`已驗證 + 高可信推論`

若名稱中出現：

- mushroom
- toadstool
- animal
- pattern
- dot pattern

可設：

- `novelty_motif = true`

建議修正：

- `eclectic += 0.15`
- `minimalist_muji -= 0.15`
- `scandinavian -= 0.08`
- `wabi_sabi -= 0.08`

若同時屬於兒童配件：

- `soft_kids_accessory = true`
- 避免它成為 `scandinavian` / `minimalist_muji` 的 `primary_style`

### 7.8 兒童系列但配色乾淨

`高可信推論`

如果是 `children_series`，但顏色是：

- white
- beige
- wood
- pine

則不一定要排除北歐或 MUJI。

例如兒童白色椅、白木兒童桌，仍可被判成 `scandinavian`。

### 7.9 人工覆核規則

當以下情況出現，建議另一個 AI 輸出 `manual_review`：

- 多個風格同分且缺乏更多結構資訊
- 顏色衝突明顯，但原始材質又很符合安靜風格
- 兒童家具同時具備乾淨木色與高彩度跳色
- 你希望與現有資料集保留相同人工例外

人工覆核案例：

- `GREJSIMOJS Children's table - wood/orange 84x42 cm`
  - 原本有 `scandinavian += 0.15`
  - 但最後改成 `eclectic`
  - `style_assignment_source = manual_review`
  - `manual_style_note_zh = 北歐風排除明顯跳色，木/橘色兒童桌改為混搭風`

可參考：

- [ikea_furniture_style_database.json](/D:/產業新兵計畫/期末專題/7-7%20網頁版/RoomPilot-Agent/roompilot/catalog/data/ikea_furniture_style_database.json:4893)

## 8. 建議的實作偽程式碼

```python
STYLE_IDS = [
    "scandinavian",
    "modern",
    "minimalist_muji",
    "industrial",
    "wabi_sabi",
    "japanese",
    "american",
    "light_luxury",
    "nordic_modern",
    "eclectic",
    "american_country",
    "melad",
]

def classify_furniture(item):
    scores = {style_id: 0.0 for style_id in STYLE_IDS}
    reasons = {style_id: [] for style_id in STYLE_IDS}
    flags = set()

    tokens = extract_tokens(item)
    item_type = item.get("normalized_type", "")

    # 1. 類型預設
    if item_type == "tv-bench":
        add(scores, reasons, "modern", 0.22, "type:tv-bench")
        add(scores, reasons, "scandinavian", 0.22, "type:tv-bench")
        add(scores, reasons, "nordic_modern", 0.22, "type:tv-bench")
        add(scores, reasons, "american", 0.22, "type:tv-bench")

    # 2. 顏色 / 材質 / 名稱 token
    for token in tokens:
        if token in {"white", "light", "beige", "oak", "pine", "birch", "wood"}:
            add(scores, reasons, "scandinavian", 0.15, f"match:{token}")
            add(scores, reasons, "minimalist_muji", 0.15, f"match:{token}")
            add(scores, reasons, "nordic_modern", 0.15, f"match:{token}")

        if token in {"black", "dark-grey", "metal", "chrome"}:
            add(scores, reasons, "modern", 0.15, f"match:{token}")
            add(scores, reasons, "industrial", 0.15, f"match:{token}")

        if token in {"rattan", "tan"}:
            add(scores, reasons, "melad", 0.15, f"match:{token}")
            add(scores, reasons, "nordic_modern", 0.15, f"match:{token}")

        if token in {"glass", "brass", "gold"}:
            add(scores, reasons, "light_luxury", 0.15, f"match:{token}")
            add(scores, reasons, "modern", 0.08, f"match:{token}")

        if token == "tv":
            add(scores, reasons, "modern", 0.15, "match:tv")

        if token == "storage":
            add(scores, reasons, "modern", 0.15, "match:storage")

    # 3. 旗標
    if any(token in tokens for token in {"yellow", "orange", "turquoise", "hot pink", "red", "multicolour"}):
        flags.add("high_chroma")
        add(scores, reasons, "eclectic", 0.15, "context:high_chroma_fits_eclectic")
        penalize(scores, reasons, "scandinavian", 0.03, "context:high_chroma_blocks_minimal")
        penalize(scores, reasons, "minimalist_muji", 0.03, "context:high_chroma_blocks_minimal")
        penalize(scores, reasons, "nordic_modern", 0.03, "context:high_chroma_blocks_minimal")
        penalize(scores, reasons, "wabi_sabi", 0.03, "context:high_chroma_blocks_minimal")

    if any(token in tokens for token in {"mushroom", "toadstool", "animal", "pattern", "dot"}):
        flags.add("novelty_motif")
        add(scores, reasons, "eclectic", 0.15, "context:novelty_motif_fits_eclectic")
        penalize(scores, reasons, "minimalist_muji", 0.15, "context:novelty_motif_blocks_minimal")

    if is_children_series(item):
        flags.add("children_series")

    if is_soft_kids_accessory(item):
        flags.add("soft_kids_accessory")

    # 4. 清理分數
    candidates = []
    for style_id, score in scores.items():
        score = max(0.0, round(score, 2))
        if score > 0:
            candidates.append({
                "style_id": style_id,
                "score": score,
                "reasons": reasons[style_id],
            })

    # 5. 排序
    candidates.sort(key=lambda x: x["score"], reverse=True)

    # 6. fallback
    if not candidates:
        return {
            "style_candidates": [],
            "primary_style": fallback_style(item),
            "style_confidence": 0.0,
            "style_assignment_source": "fallback",
            "style_rule_flags": sorted(flags),
        }

    top = candidates[0]
    return {
        "style_candidates": candidates,
        "primary_style": top["style_id"],
        "style_confidence": top["score"],
        "style_assignment_source": "scored",
        "style_rule_flags": sorted(flags),
    }
```

## 9. 三個對照案例

### 9.1 高彩度兒童家具 -> 混搭風

例子：

- [ikea_furniture_style_database.json](/D:/產業新兵計畫/期末專題/7-7%20網頁版/RoomPilot-Agent/roompilot/catalog/data/ikea_furniture_style_database.json:4421)

特徵：

- `match:yellow`
- `context:high_chroma_fits_eclectic`
- `context:high_chroma_blocks_minimal`

結果：

- `eclectic = 0.3`
- `scandinavian = 0.12`
- `primary_style = eclectic`

### 9.2 木色兒童桌，但人工改判

例子：

- [ikea_furniture_style_database.json](/D:/產業新兵計畫/期末專題/7-7%20網頁版/RoomPilot-Agent/roompilot/catalog/data/ikea_furniture_style_database.json:4893)

特徵：

- 原始 `match:wood`
- 多個風格同分 `0.15`
- 最後 `manual_review`

結果：

- `primary_style = eclectic`
- `style_assignment_source = manual_review`

### 9.3 白色 TV bench -> modern 優先

例子：

- [ikea_furniture_style_database.json](/D:/產業新兵計畫/期末專題/7-7%20網頁版/RoomPilot-Agent/roompilot/catalog/data/ikea_furniture_style_database.json:100721)

特徵：

- `match:white`
- `match:tv`
- `type:tv-bench`

結果：

- `modern = 0.52`
- `scandinavian = 0.37`
- `nordic_modern = 0.37`
- `american = 0.22`
- `primary_style = modern`

## 10. 與執行期挑家具的關係

這份文件描述的是「前處理」。

前處理完成後，server 端挑家具時才會讀：

- `primary_style`
- `style_candidates[].score`
- `style_confidence`

再把它轉成場景配置用的選件分數。

可參考：

- [scene_service.py](/D:/產業新兵計畫/期末專題/7-7%20網頁版/RoomPilot-Agent/roompilot/server/scene_service.py:412)

換句話說：

- 這份文件是「家具本身怎麼先被貼風格」
- `scene_service.py` 是「房間要某個風格時，怎麼用這些標籤去選家具」

## 11. 建議給另一個 AI 的最短任務描述

如果你要把這份邏輯交給另一個 AI，可以直接給它這段：

```text
請依據家具的 name_en、name_zh_raw、normalized_type、color、material 等欄位，
模仿 RoomPilot 現有的規則式風格前處理，為每件家具產生：
style_candidates、primary_style、style_confidence、style_rule_flags、style_assignment_source。

請優先使用以下規則：
1. 顏色、材質、名稱 token 命中風格特徵時加分。
2. 類型（例如 tv-bench）可提供預設風格基礎分。
3. 高彩度與童趣 motif 會提高 eclectic，並壓低 scandinavian / minimalist_muji / nordic_modern / wabi_sabi。
4. 兒童系列可保留 children_series flag，但不要因此自動排除北歐；只有在高彩度或童趣造型時才顯著轉向 eclectic。
5. 若多個風格同分但存在語意衝突，請輸出 manual_review。
6. 產生 style_candidates 時，請保留 reasons，格式如 match:white、type:tv-bench、context:high_chroma_blocks_minimal。
```

## 12. 已知限制

- 目前 repo 缺少原始打分腳本，無法 100% 還原權重來源。
- 本文件的權重設計以「模仿現有資料分布」為目標，不保證與歷史產生器逐點完全一致。
- 若你要更高一致性，建議後續額外做：
  - 全量掃描 `style_candidates[].reasons`
  - 統計每個 `reason` 對應的常見分值
  - 反推出更精細的權重表


# 從 RoomPilot 資料到交付文件的對應

## 成果包長什麼樣

第 8 步完成後的標準結構（見專案 `docs/ROOMPILOT_6_8_AGENT_RENDER_IMPLEMENTATION_SPEC.md`）：

```
RoomPilot_成果包_<project>_<version>.zip
├─ README.md
├─ manifest.json
├─ render_brief.json
├─ configuration_snapshot.json
├─ rooms/<房名>/最終渲染.png
├─ rooms/<房名>/鎖定視角.png
└─ adjustments/最後一次LLM調整紀錄.json
```

實務上不一定這麼齊。`collect_context.py` 會用模糊比對去找，找不到的列在 `gaps`。

## 各檔案負責什麼

`configuration_snapshot.json` 是第 6 步確認後的唯一最終配置，也是**尺寸與家具的唯一可信來源**。裡面有結構（牆門窗樑柱）、所有鎖定家具的位置尺寸與 GLB 參考、牆地天花材質、燈具。文案裡任何家具名稱與尺寸都應該對得回這裡。

`render_brief.json` 是送去生圖的封包：選定的色卡、每房鎖定視角與相機參數、確認過的生圖摘要、風險標記。色卡與視角的描述從這裡拿。

`manifest.json` 有版本與任務對應（`room_id` + `scene_version` + `render_brief_version`）與各房任務狀態。**哪些房間生圖失敗要看這裡**，失敗的要寫進 `appendix.limits`。

`scene_json`（若存在）是提案本體，內容與 `configuration_snapshot` 高度重疊；兩者都在時以 `configuration_snapshot` 為準，因為那是使用者按過「確認最終配置」的版本。

`layout_json` 只描述空間本身（牆、門窗、房間輪廓、坪數、比例尺），不含任何設計決定。坪數與格局從這裡拿。

`adjustments/*.json` 是第 8 步唯一一次 LLM 調整的原文與結構化理解。如果屋主當時提過什麼要求，這裡看得到——是 `rationale` 的好素材（「你後來提到想加一張邊桌，我們放在……」）。

## 對應到 content.json

| content.json 欄位 | 來源 |
|---|---|
| `meta.project_name` | `manifest.json` 的專案名稱，或使用者告知 |
| `meta.subtitle` 坪數格局 | `layout_json` 房間數與面積 |
| `meta.subtitle` 風格名 | `configuration_snapshot` / 第 5 步問卷的全屋風格 |
| `meta.version` / `appendix.version_line` | `manifest.json` 的 `scene_version`、`render_brief_version` |
| `overview.facts` | `layout_json` 面積與房間數、`render_brief` 選定色卡 |
| `overview.plan_image` | 白模或 2D 平面參考圖 |
| `rooms[].name` | `rooms/` 底下的資料夾名，或 `manifest` 的 `room_id` 對應名稱 |
| `rooms[].hero_image` | `rooms/<房名>/最終渲染.png` |
| `rooms[].extra_images` | `鎖定視角.png`、白模圖 |
| `rooms[].specs` | `configuration_snapshot` 該房的家具清單、尺寸、材質 |
| `rooms[].rationale` 的依據 | 第 5 步問卷逐房需求、使用者補充文字、`adjustments` |
| `palette.swatches` | `render_brief` 選定的那一張色卡 |
| `materials` | `configuration_snapshot` 的牆地天花材質決定 |
| `lighting.items` | `configuration_snapshot` 的燈具與天花形式 |
| `appendix.limits` | `manifest` 中 `status = failed` 的房間、`render_brief` 的風險標記 |

## 兩條不能破的規則

**沒有來源的規格不要寫。** 不只是尺寸——**色溫（3000K）、照度（lux）、演色性（Ra）、比例（八成、90%）、材質性能（可拆洗、防滑、耐磨等級）都算規格**。這些是最容易不小心寫出來的，因為它們聽起來像常識；但屋主可能拿著這份文件去跟工班對話，寫錯一個他對整份文件的信任就沒了。

`preflight_check.py` 的數字溯源會抓帶單位的數字，但抓不到「沙發套可拆洗」這種文字型的規格宣稱——那要靠自己：每寫一句關於材質或性能的斷言，先回頭確認 `configuration_snapshot` 裡真的有這個欄位。沒有就寫「待選樣確認」。

**不要改設計決定。** 這份文件是在解釋既有的方案，不是在提新方案。`configuration_snapshot` 寫沙發在南牆，文案就不能說「建議改放東牆」。有意見寫進 `next_steps.notes` 當作討論事項。

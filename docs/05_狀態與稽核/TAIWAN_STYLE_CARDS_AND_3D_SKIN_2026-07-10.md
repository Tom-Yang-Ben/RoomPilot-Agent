# 台灣住宅風格色卡與 3D 材質展示

## 目前契約

- `/styles` 由 `/api/site-data.taiwan_style_cards` 提供 6 種風格、每種 3 張色卡，共 18 張。
- 色卡圖片由 `roompilot/server/static/style_cards/` 提供；來源為台灣住宅版色卡資料夾。
- 從風格頁進入場景時使用 `style` 與 `style_card` query parameters。
- 場景生成 payload 會保留 `style_card` 與 `design_choices.style_card_id`，讓前端 viewer 可依選定色卡套用材質色調。

## 3D 展示行為

- GLB 載入後會保留原始貼圖，並依色卡 palette 對材質顏色、粗糙度做非破壞式 tint，作為快速「貼皮」預覽。
- OrbitControls 在室內 preset 仍開啟旋轉；室內模式限制平移與縮放，避免拖曳時離開房間。
- 天花板群組預設隱藏，可由現有天花板切換控制顯示。
- 房間建立時會產生 2～3 盞暖色吊燈，包含吊線、燈罩、燈泡與 PointLight。

## 後續可擴充

- 將目前 palette tint 升級為材質類型對應的 PBR 貼圖（木皮、石材、布料、金屬）。
- 若 GLB 內有明確材質命名，可增加材質角色 mapping，避免依名稱關鍵字推斷。

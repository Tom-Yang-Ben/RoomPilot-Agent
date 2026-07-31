# 價格與工率資料政策

## 價格優先順序

```text
同地區有效廠商書面報價
> 同地區已完成歷史案件
> 品牌／供應商可追溯價格
> 公共工程或公開資料參考
> pending_quote
```

`DEMO_ONLY` 只在 `ROOMPILOT_DEMO_MODE=true` 使用，不屬於上述正式優先順序。

## PriceRecord 最少欄位

```json
{
  "price_record_id": "...",
  "work_item_code": "...",
  "region": "新北市",
  "effective_date": "2026-07-29",
  "material_unit_price": null,
  "labor_unit_price": null,
  "other_unit_price": null,
  "tax_included": null,
  "source": "待廠商書面報價",
  "source_type": "contractor_quote_pending",
  "status": "pending_quote",
  "confidence": "low"
}
```

## 不可混用

```text
材料零售價 ≠ 包工包料價
工人基本薪資 ≠ 對客戶人工單價
公共工程參考價 ≠ 私人住宅成交價
網路文章價格 ≠ 廠商正式報價
```

## 工率資料

工率必須記錄：

- work_item_code
- daily_productivity
- crew_count
- preparation_days
- waiting_days
- 適用條件
- 日期與來源
- confidence

正式工期前要再考量：

- 材料交期。
- 社區施工時段。
- 樓層與搬運。
- 現場基底狀況。
- 工班實際人力。
- 可否平行施工。

## 前端顯示

| 狀態 | 顯示文字 |
|---|---|
| demo_reference | Demo 示範價格 |
| pending_quote | 待廠商詢價 |
| historical_reference | 歷史案件參考 |
| contractor_confirmed | 廠商已確認 |
| productivity_data_missing | 工率資料不足 |


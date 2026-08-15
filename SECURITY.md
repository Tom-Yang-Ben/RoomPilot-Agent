# Security policy

## Supported scope

目前僅支援 loopback 綁定的 local-development preview。公開網際網路、多租戶與不受信任使用者環境不在支援範圍。

## Reporting

請不要在公開 issue 張貼憑證、個資、可利用 payload 或尚未修補的完整攻擊步驟。請透過 repository 所屬組織提供的私人安全通報管道聯絡維護者；若尚未設定私人通報，請只建立不含敏感細節的 issue，要求維護者提供安全聯絡方式。

## Secret handling

- 金鑰只放在未追蹤的 `.env` 或作業系統 secret store。
- 測試與範例只能使用明顯無效的 placeholder。
- 發現已提交 secret 時，先撤銷／輪替，再清理公開歷史；只刪目前檔案不足以解除風險。

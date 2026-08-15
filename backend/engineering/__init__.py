"""設計師確認後的工程估算與文件生成 MVP。

流程：ProjectSnapshot(鎖定) → Quantity → Advanced RAG → Rule → Cost
→ Schedule → Narrative → ReportPayload → HTML / XLSX / JSON。

本套件只透過 Adapter 使用既有模組（backend.engine、ProjectStore workflow、
render 紀錄），不重寫 2D / 3D / 生圖 / 家具功能。
"""

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RoomPilot 部署拓撲圖 — 宣告式 spec
==================================
對應規格：./deployment_topology.md §2（生成 prompt）；引擎：
../../../VibeCoding_Workflow_Templates/03_architecture/diagrams/_tools/drawio_kit.py

佐證基準：分支 yen、HEAD 8f378b24、2026-08-12 工作樹。節點標籤內的 file:line
皆為本次實讀，未實讀者不寫。

版面心法（讓 analyze_layout score=0）：
  1. 長線走專用通道：外部出向走頁頂 y=112/126 與右緣 x=1670/1690 兩條垂直通道。
  2. 主機內的橫向長線走「元件列之間的空隙」（y=165 / y=340 / y=485 / y=660），
     四條走廊互不同高，且都避開葉節點的收縮框。
  3. 同源的線（WEB→CF、WEB→unpkg）共端點，交叉不計，可並行走頂部通道。

執行：  .venv/Scripts/python.exe RoomPilot_Docs/03_architecture/diagrams/deployment_topology.py
驗收：  .venv/Scripts/python.exe VibeCoding_Workflow_Templates/03_architecture/diagrams/_tools/analyze_layout.py \
            RoomPilot_Docs/03_architecture/diagrams/deployment_topology.drawio -v
鐵律：絕不手改生成出的 .drawio（重生會覆蓋）。
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(
    _HERE, "..", "..", "..",
    "VibeCoding_Workflow_Templates", "03_architecture", "diagrams", "_tools",
))
from drawio_kit import (  # noqa: E402
    E_DASH, E_MAIN, E_SOLID,
    container, cyl, edge, legend, node, note, rect, rrect, subtitle, title,
    write_drawio,
)


def small(style, size=10):
    """同樣的語意色，字級調小塞得下 file:line。"""
    return style + f"fontSize={size};"


def topology():
    c = [
        title("t", "RoomPilot 部署拓撲（AS-IS · Pilot 單機 loopback）", w=900),
        subtitle("st", "八步工作流的邏輯容器跑在哪台機器／哪個行程／哪個埠；"
                       "執行資料落在哪個檔案或資料庫；跨邊界連線的協定與失敗語意。"
                       "全圖無 🔜 節點——未落地的元件不畫，見 md §4。", w=1300),
    ]

    # ── 實體邊界 ────────────────────────────────────────────────────────────
    c.append(node("host", "開發者工作站（單機；app 未容器化、無反向代理、無 TLS）",
                  40, 140, 1000, 580, container("gray")))
    c.append(node("proc", "uvicorn 單一 Python 行程 · 127.0.0.1:8002 --reload"
                          "（README.md:49；install.ps1:79；install.sh:65）",
                  250, 40, 420, 500, container("red"), parent="host"))
    c.append(node("db", "Docker 容器（本機或遠端主機，由 DB_HOST 決定）",
                  1090, 140, 560, 150, container("teal")))
    c.append(node("ext", "外部 HTTPS 出向（本機行程或瀏覽器發起）",
                  1090, 330, 560, 390, container("gray")))

    # ── 工作站內元件 ────────────────────────────────────────────────────────
    c.append(node("web", "瀏覽器：靜態單頁前端（MOD-WEB）\n"
                         "scene.html + scene_v2.js，由同一行程 /static 供檔\n"
                         "無獨立 web server｜main.py:216-217,1664-1669",
                  24, 210, 210, 110, small(rrect("blue"), 9), parent="host"))
    c.append(node("api", "FastAPI app：REST 路由 ＋ 靜態檔掛載（MOD-SRV-API）\n"
                         "中介層只有 GZipMiddleware：無 CORS／認證／授權／限流\n"
                         "main.py:195-197",
                  30, 50, 360, 80, small(rrect("red")), parent="proc"))
    c.append(node("eng", "幾何引擎 backend/engine/（MOD-ENG）\n"
                         "同行程函式呼叫；家具合法性唯一裁決者",
                  20, 190, 175, 90, small(rrect("green"), 9), parent="proc"))
    c.append(node("conc", "行程內併發（MOD-SRV-RENDER／MOD-RAG）\n"
                          "生圖 ThreadPoolExecutor(max=房數)\n"
                          "ai_render_service.py:425\n"
                          "檢索單一 daemon worker，佇列上限 24、\n"
                          "狀態存記憶體，重啟即失\n"
                          "rag_api.py:28-34,121-137",
                  225, 190, 175, 110, small(rrect("orange"), 8), parent="proc"))
    c.append(node("rt", ".runtime/（ROOMPILOT_RUNTIME_DIR 可覆寫）MOD-SRV-STORE\n"
                        "projects.sqlite3（WAL、foreign_keys=ON）｜uploads｜renders\n"
                        "manuals｜indexes｜agent_pipeline／<project_id>.json\n"
                        "runtime_paths.py:20-25；project_store.py:80-93；\n"
                        "agent_pipeline_service.py:54-60",
                  700, 60, 290, 120, small(cyl("purple"), 8), parent="host"))
    c.append(node("pdf", "Chromium 子行程：交付提案 PDF 排版\n"
                         "sys.executable 起 build_pdf.py，逾時 180 秒\n"
                         "delivery/__init__.py:40-57,273-290",
                  700, 230, 290, 90, small(rrect("blue"), 9), parent="host"))
    c.append(node("cache", "檢索模型權重快取（offline-only）MOD-RAG\n"
                           "ROOMPILOT_RAG_MODEL_CACHE→HF_HOME→~/.cache/huggingface\n"
                           "local_files_only=True，未快取直接 503\n"
                           "rag/settings.py:59-60,96；model_runtime.py:103-105,120,127",
                  700, 370, 290, 110, small(cyl("purple"), 8), parent="host"))

    # ── 容器外資料庫與外部服務 ──────────────────────────────────────────────
    c.append(node("pg", "PostgreSQL 17 + pgvector（MOD-SQL／MOD-CAT）\n"
                        "唯讀 view roompilot.furniture_catalog_current；pg_isready healthcheck\n"
                        "postgres_repository.py:20；docker_postgresql/docker-compose.yml:5-27",
                  24, 45, 500, 90, small(cyl("purple"), 9), parent="db"))
    c.append(node("or", "OpenRouter：LLM 與生圖唯一閘道（MOD-AGT／MOD-SRV-RENDER）\n"
                        "文字 /api/v1/chat/completions、生圖 /api/v1/images；"
                        "agent/llm.py:32,37；ai_render_service.py:67-74",
                  24, 40, 500, 70, small(rect("gray"), 9), parent="ext"))
    c.append(node("cf", "CloudFront：GLB 與型錄圖片（MOD-CAT）\n"
                        "交付模式預設 cloudfront；services/cloud_models.py:32,45-52；"
                        "main.py:4012-4018",
                  24, 135, 500, 70, small(rect("gray"), 9), parent="ext"))
    c.append(node("unpkg", "unpkg CDN：three@0.165.0 importmap（瀏覽器直載）\n"
                           "scene.html:1212-1213；sad.md §9 登記為待確認（與「本機可跑」衝突）",
                  24, 230, 500, 70, small(rect("gray"), 9), parent="ext"))
    c.append(node("rp", "遠端算圖 provider（現況未設 URL 即停用）\n"
                        "render_service.py:33-49",
                  24, 320, 500, 55, small(rect("gray"), 9), parent="ext"))

    # ── 跨邊界連線（協定＋失敗語意）────────────────────────────────────────
    c.append(edge("e1", "web", "api", "HTTP 127.0.0.1:8002（明文，無 TLS／無認證）", E_MAIN))
    c.append(edge("e2", "api", "eng", "同行程函式呼叫", E_SOLID))
    c.append(edge("e3", "api", "conc", "同行程執行緒", E_SOLID))
    c.append(edge("e4", "api", "rt", "本機檔案 I/O（無配額、無輪替）", E_MAIN))
    c.append(edge("e5", "api", "pdf",
                  "子行程；缺 playwright→503、逾時 180 秒／排版失敗→502", E_SOLID))
    c.append(edge("e6", "api", "pg",
                  "TCP 5432｜sslmode 預設 disable｜池 1–8｜connect_timeout 3s；"
                  "不可用→/api/catalog/status available=false（RB-001）",
                  E_MAIN, pts=[(500, 165), (1364, 165)]))
    c.append(edge("e7", "conc", "or",
                  "HTTPS｜逾時 120 秒；未設 OPENROUTER_API_KEY→configured:false／503（RB-002）",
                  E_SOLID, pts=[(700, 485), (1060, 485), (1060, 405)]))
    c.append(edge("e8", "conc", "cache", "本機檔案；不在請求路徑下載（RB-004）", E_SOLID))
    c.append(edge("e9", "api", "rp",
                  "HTTPS（可選，現況未啟用）；逾時夾限 5–180 秒",
                  E_DASH, pts=[(500, 660), (1060, 660)]))
    c.append(edge("e10", "web", "cf",
                  "HTTPS 直載（/model 回 307）；本機拆解端點回 410（RB-008）",
                  E_DASH, pts=[(169, 112), (1670, 112), (1670, 500)]))
    c.append(edge("e11", "web", "unpkg", "HTTPS；離線或 CDN 故障即 3D 不可用",
                  E_DASH, pts=[(169, 126), (1690, 126), (1690, 595)]))

    # ── metadata banner、圖例、缺席清單 ────────────────────────────────────
    c.append(node("meta",
                  "部署拓撲｜受眾：團隊成員（自行架環境）／示範窗口／稽核\n"
                  "回答的問題：什麼跑在同一台機器、同一個行程裡？資料落在哪？哪些連線出得了本機？\n"
                  "正典來源：sad.md §7 部署視圖、srs.md FR-065–067／NFR-019–023、ADR-012｜最後校驗：2026-08-12",
                  420, 760, 620, 92, note("yellow")))
    c.append(node("absent",
                  "本機不存在（md §4，故不畫節點）：反向代理／TLS 終結、認證／授權／CORS／限流、"
                  "app 容器化與服務化（無 Dockerfile、啟動帶 --reload）、CI／CD（無 .github/）、"
                  "訊息佇列／分散式快取／多實例／可觀測性、備份與保留刪除機制。",
                  1080, 760, 570, 92, note("gray")))
    c += legend("lg", 40, 760, [
        ("edge", E_MAIN, "粗實線＝現況必經主鏈"),
        ("edge", E_SOLID, "細實線＝同行程或同機呼叫"),
        ("edge", E_DASH, "虛線＝瀏覽器直連或可選（未啟用）"),
        ("fill", "red", "紅＝關鍵熱路徑（行程／API）"),
        ("fill", "blue", "藍＝前端與後台面"),
        ("fill", "green", "綠＝幾何引擎（共用裁決）"),
        ("fill", "orange", "橘＝AI 能力（生圖／檢索）"),
        ("fill", "purple", "紫＝資料存放（圓柱）"),
        ("fill", "teal", "青＝Docker 容器邊界"),
        ("fill", "gray", "灰＝外部實體／工作站邊界"),
    ], w=350)
    return ("roompilot_deploy", "RoomPilot 部署拓撲 AS-IS", c)


if __name__ == "__main__":
    write_drawio([topology()],
                 os.path.join(_HERE, "deployment_topology.drawio"),
                 page_w=1700, page_h=1000)

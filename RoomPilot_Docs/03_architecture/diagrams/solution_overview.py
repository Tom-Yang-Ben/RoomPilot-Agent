#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RoomPilot — 解決方案總覽（Solution Overview）宣告式 spec
=======================================================
資料來源：solution_overview.md §2（端到端資料流）與 §4（逐步產物與守門條件）；
模組代號與程式碼佐證：../sad.md §1.3、§5。引擎：VibeCoding_Workflow_Templates/03_architecture/diagrams/_tools/drawio_kit.py。

佐證基準：分支 yen、HEAD 8f378b24、2026-08-12 工作樹。

版面心法（讓 analyze_layout score=0）：
  1. 八步在 Z2 排成單一縱列，Gn 放行條件是相鄰短垂直線。
  2. 前端→快照的四條寫入走左側 x=318/326/334/342 巢狀通道（同 target 不計交叉），
     上傳走最外側 x=306；辨識端的快照寫入走最外框 x=1665（唯一必須跨越 S7/S8 長橫線的線）。
  3. Z3/Z4 各卡列刻意讓出 y=482/486 與 y≥560 兩條水平走廊給 S6→型錄、S7/S8→生圖。
執行：python solution_overview.py
驗收：python ../../../VibeCoding_Workflow_Templates/03_architecture/diagrams/_tools/analyze_layout.py solution_overview.drawio -v
"""
import os
import sys

_KIT = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "..", "..",
    "VibeCoding_Workflow_Templates", "03_architecture", "diagrams", "_tools",
)
sys.path.insert(0, _KIT)
from drawio_kit import (  # noqa: E402
    E_REF_EVENT, E_REF_INTERACTION, E_REF_STORAGE,
    actor, container, edge, legend, node, note, rect, ref_component,
    ref_store, ref_zone, title, write_drawio,
)

ZY, ZH, ZW = 80, 620, 254
ZX = [40, 310, 580, 850, 1120, 1390]

BLUE, AI, SVC, ENGC = "#2563EB", "#D79B00", "#64748B", "#B85450"


def overview():
    c = [title("t", "RoomPilot — 一張既有平面圖走完八步的端到端資料流（AS-IS）", w=1000)]

    for zid, name, x in [
        ("z1", "Z1 操作者與輸入訊號", ZX[0]),
        ("z2", "Z2 MOD-WEB 八步單頁前端（static/scene_v2.js）", ZX[1]),
        ("z3", "Z3 辨識・檢索・選件", ZX[2]),
        ("z4", "Z4 方案組裝・幾何裁決・型錄", ZX[3]),
        ("z5", "Z5 生圖與交付", ZX[4]),
        ("z6", "Z6 外部相依（不受本系統控制）", ZX[5]),
    ]:
        c.append(node(zid, name, x, ZY, ZW, ZH, ref_zone()))

    # ── Z1 ──────────────────────────────────────────────────────────────────
    c.append(node("a_user", "操作者\n屋主或設計顧問", 97, 60, 60, 90, actor(), parent="z1"))
    c.append(node("in_file", "既有平面圖檔\nPNG／JPG／PDF／DXF", 20, 280, 214, 56,
                  rect("gray"), parent="z1"))

    # ── Z2 八步（對外 8 顆＝內部 11 個 step key 折疊，ADR-010）──────────────
    steps = [
        ("s1", "S1 建立專案\nproject_id＋revision"),
        ("s2", "S2 上傳平面圖\nfloorplan_confirmation"),
        ("s3", "S3 確定尺寸\n辨識＋比例標定"),
        ("s4", "S4 空間與結構\nfloorplan_editor"),
        ("s5", "S5 需求問卷\nroom_requirements"),
        ("s6", "S6 配置與預覽\n2D＋白模 3D"),
        ("s7", "S7 鎖定方案與視角\nmaster_view＋色卡"),
        ("s8", "S8 生圖與成果包\n逐房影像＋交付提案"),
    ]
    for i, (sid, label) in enumerate(steps):
        # 卡片右移到 rel x=40：讓出 x≤348 的左側巢狀通道給「寫入快照」四條線
        c.append(node(sid, label, 40, 56 + i * 68, 194, 52,
                      ref_component(BLUE), parent="z2"))

    # ── Z3 ──────────────────────────────────────────────────────────────────
    c.append(node("m_fp", "MOD-FP 辨識管線\nbackend/floorplan/\n輸出止於 layout_json",
                  20, 176, 214, 64, ref_component(AI), parent="z3"))
    c.append(node("st_model", "本機模型權重快取（offline-only）\nmodel_runtime.py:104-127",
                  20, 268, 214, 44, ref_store(), parent="z3"))
    c.append(node("m_rag", "MOD-RAG 檢索排序\nspatial_data/rag/＋rag_api.py\n只重排候選，失敗降級不阻塞",
                  20, 336, 214, 60, ref_component(AI), parent="z3"))
    c.append(node("m_agt", "MOD-AGT 選件閘門\nbackend/agent/（main.py:3440）",
                  20, 412, 214, 60, ref_component(AI), parent="z3"))

    # ── Z4 ──────────────────────────────────────────────────────────────────
    c.append(node("m_cat", "MOD-CAT 型錄唯讀\npostgres_repository.py:199-204（view 優先，JSON 僅降級）",
                  16, 336, 222, 60, ref_component(SVC), parent="z4"))
    c.append(node("m_scn", "MOD-SRV-SCENE\nscene_service.py:2888\n組裝 scene_json",
                  16, 412, 100, 60, ref_component(SVC), parent="z4"))
    c.append(node("m_eng", "MOD-ENG 幾何\n唯一裁決者\nbackend/engine/",
                  138, 412, 100, 60, ref_component(ENGC), parent="z4"))

    # ── Z5 ──────────────────────────────────────────────────────────────────
    c.append(node("m_rnd", "MOD-SRV-RENDER\n色卡 main.py:2135｜逐房生圖 :2070\n提案 PDF :2384｜成果包 :2920-2943",
                  20, 480, 214, 80, ref_component(AI), parent="z5"))

    # ── Z6 外部相依 ─────────────────────────────────────────────────────────
    c.append(node("x_pg", "PostgreSQL roompilot\nview＋pgvector", 20, 240, 214, 52,
                  rect("gray"), parent="z6"))
    c.append(node("x_cf", "CloudFront\nGLB／三視角圖", 20, 336, 214, 60,
                  rect("gray"), parent="z6"))
    c.append(node("x_or", "OpenRouter\n色卡／生圖／文案 LLM", 20, 500, 214, 52,
                  rect("gray"), parent="z6"))
    c.append(node("x_pdf", "Chromium PDF 子行程", 20, 568, 214, 44,
                  rect("gray"), parent="z6"))

    # ── 底部：MOD-SRV-STORE 落地面 ──────────────────────────────────────────
    c.append(node("zs", "MOD-SRV-STORE ── .runtime/ 單一快照與檔案落地"
                        "（project_store.py:80-84,100-113；無版本歷史表、無事件流，ADR-004）",
                  40, 740, 1604, 140, container("white")))
    c.append(node("st_up", "uploads/\n原始平面圖檔", 30, 50, 240, 60, ref_store(), parent="zs"))
    c.append(node("st_snap", "projects.sqlite3 · workflow_json 單一快照\n"
                             "深合併寫入、序列化上限 2 MB、revision 樂觀鎖",
                  660, 50, 360, 60, ref_store(), parent="zs"))
    c.append(node("st_man", "manuals/\n交付提案 PDF", 1060, 50, 240, 60, ref_store(), parent="zs"))
    c.append(node("out_pkg", "成果包 JSON ＋ 交付提案 PDF\n（下載給操作者）", 1340, 50, 240, 60,
                  rect("gray"), parent="zs"))

    # ── 藍實線：同步呼叫與步驟放行 ──────────────────────────────────────────
    c.append(edge("e_user", "a_user", "s1", "開啟 /scene 單頁", E_REF_INTERACTION))
    c.append(edge("e_file", "in_file", "s2", "上傳檔案", E_REF_INTERACTION,
                  pts=[(300, 388), (300, 232)]))
    gates = [
        ("s1", "s2", "G1 name 去空白後非空"),
        ("s2", "s3", "G2 已勾「圖檔內容正確」"),
        ("s3", "s4", "G3 engine∈{cody,dxf}＋distanceCm>0"),
        ("s4", "s5", "G4 三旗標＋review_items 全清"),
        ("s5", "s6", "G5 basicConfirmed＆roomsResolved"),
        ("s6", "s7", "G6 layout_2d.confirmed＋可見家具>0"),
        ("s7", "s8", "G7 相機三元組＋fov_deg>0"),
    ]
    for i, (a, b, lab) in enumerate(gates, start=1):
        c.append(edge(f"g{i}", a, b, lab, E_REF_INTERACTION))

    c.append(edge("e_fp", "s3", "m_fp", "POST …/floorplan/analyze（main.py:2981）",
                  E_REF_INTERACTION))
    c.append(edge("e_rag", "s5", "m_rag", "POST /api/rag/search/jobs（fast:true）",
                  E_REF_INTERACTION))
    c.append(edge("e_agt", "s6", "m_agt", "選件閘門 /api/agent/*", E_REF_INTERACTION))
    c.append(edge("e_scn", "m_agt", "m_scn", "候選清單", E_REF_INTERACTION))
    c.append(edge("e_eng", "m_scn", "m_eng", "落點送審（公分制）", E_REF_INTERACTION))
    c.append(edge("e_cat", "s6", "m_cat", "型錄分頁＋GLB 交付", E_REF_INTERACTION,
                  pts=[(560, 482), (880, 482)]))
    c.append(edge("e_pg_cat", "m_cat", "x_pg", "furniture_catalog_current view", E_REF_INTERACTION))
    c.append(edge("e_cf", "m_cat", "x_cf", "GLB 307 導向", E_REF_INTERACTION))
    c.append(edge("e_pg_rag", "m_rag", "x_pg", "SQL＋pgvector（共用 MOD-CAT 連線池）",
                  E_REF_INTERACTION, pts=[(838, 446), (838, 404), (1380, 404)]))
    c.append(edge("e_r7", "s7", "m_rnd", "色卡生成（每案一次）", E_REF_INTERACTION))
    c.append(edge("e_r8", "s8", "m_rnd", "逐房生圖／改圖／成果包", E_REF_INTERACTION))
    c.append(edge("e_or", "m_rnd", "x_or", "LLM 呼叫（金鑰只在伺服器，ADR-009）", E_REF_INTERACTION))
    c.append(edge("e_pdf", "m_rnd", "x_pdf", "PDF 排版子行程", E_REF_INTERACTION))

    # ── 綠虛線：回傳產物（邊界鐵律所在）────────────────────────────────────
    c.append(edge("r_fp", "m_fp", "s3", "layout_json＋spatial_report（辨識止於此，ADR-001）",
                  E_REF_EVENT))
    c.append(edge("r_eng", "m_eng", "m_scn", "合法座標／失敗理由", E_REF_EVENT))
    c.append(edge("r_mdl", "st_model", "m_rag", "權重未快取即 503", E_REF_EVENT))

    # ── 橘虛線：寫入快照與檔案落地 ──────────────────────────────────────────
    c.append(edge("o_up", "s2", "st_up", "原始圖檔落地", E_REF_STORAGE,
                  pts=[(306, 230), (306, 812)]))
    c.append(edge("o_fp", "m_fp", "st_snap",
                  "recognition 寫入＋七個下游節點寫 null（main.py:3036-3060）", E_REF_STORAGE,
                  pts=[(707, 250), (1665, 250), (1665, 870), (880, 870)]))
    c.append(edge("o_s4", "s4", "st_snap", "floorplan_editor＋space_confirmation", E_REF_STORAGE,
                  pts=[(318, 366), (318, 790)]))
    c.append(edge("o_s5", "s5", "st_snap", "room_requirements（家電只進 render_context，ADR-006）",
                  E_REF_STORAGE, pts=[(326, 434), (326, 784)]))
    c.append(edge("o_s6", "s6", "st_snap", "scene_json → layout_2d＋white_model_3d", E_REF_STORAGE,
                  pts=[(334, 502), (334, 778)]))
    c.append(edge("o_s7", "s7", "st_snap", "proposal_review.masterView＋palette_render",
                  E_REF_STORAGE, pts=[(342, 570), (342, 772)]))
    c.append(edge("o_man", "m_rnd", "st_man", "PDF 落地", E_REF_STORAGE))
    c.append(edge("o_out", "m_rnd", "out_pkg", "六章成果包 JSON", E_REF_STORAGE))

    # ── metadata banner 與圖例 ──────────────────────────────────────────────
    c.append(node("meta",
                  "RoomPilot 解決方案總覽｜受眾：新人 onboarding、跨 owner 對接\n"
                  "回答的問題：八步端到端流動哪些資料、每步產物存到哪、靠什麼條件放行\n"
                  "正典來源：solution_overview.md §2／§4、sad.md §1.3／§5｜最後校驗：2026-08-12\n"
                  "佐證基準：分支 yen、HEAD 8f378b24；本圖只畫已落地路徑，無 🔜 節點",
                  700, 940, 620, 92, note("yellow")))
    c += legend("ov", 40, 940, [
        ("edge", E_REF_INTERACTION, "藍實線＝同步呼叫／步驟放行 Gn"),
        ("edge", E_REF_EVENT, "綠虛線＝回傳產物（layout_json／合法座標）"),
        ("edge", E_REF_STORAGE, "橘虛線＝寫入單一快照或檔案落地"),
        ("fill", "orange", "橘卡＝持久化（.runtime/ 之下）"),
        ("fill", "gray", "灰直角＝外部相依／輸入輸出"),
        ("fill", "red", "紅框＝MOD-ENG 幾何唯一裁決者（ADR-002）"),
    ], w=380)
    return ("rp_ov", "RoomPilot Solution Overview", c)


if __name__ == "__main__":
    base = os.path.dirname(os.path.abspath(__file__))
    write_drawio([overview()], os.path.join(base, "solution_overview.drawio"),
                 page_w=1740, page_h=1180)

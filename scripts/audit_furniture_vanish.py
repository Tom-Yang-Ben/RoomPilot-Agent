#!/usr/bin/env python
"""家具「無聲消失」風險稽核——把 2026-08-01/02 床消失案的每一道關卡變成全量掃描。

那晚的教訓：家具可以在五種不同的關卡被**靜默丟棄**（不報錯、不留痕），
症狀一律是「畫面上就是沒有它」。本工具靜態掃出每一關現在還會殺誰。

    .venv/bin/python scripts/audit_furniture_vanish.py

live 專案的個案驗屍（2D→3D 差集）見 skill：furniture-vanish-audit。
"""
from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.agent.knowledge import ROOM_MINIMUM_FAMILIES, family_of  # noqa: E402
from backend.server.main import _furniture_payload_cache  # noqa: E402
from backend.server.scene_service import (  # noqa: E402
    catalog_item_matches_type_semantics,
)


def section(title: str) -> None:
    print(f"\n{'═' * 8} {title} {'═' * 8}")


def main() -> int:
    cache = list(_furniture_payload_cache())
    by_type: dict[str, list[dict]] = {}
    for item in cache:
        by_type.setdefault(str(item.get("normalized_type") or ""), []).append(item)

    # ── 關卡 1：床語意關（唯一有語意審查的類型） ────────────────────────
    section("關卡 1｜床語意關 catalog_item_matches_type_semantics")
    fails: list[tuple[str, str, str]] = []
    total_beds = 0
    for bed_type in ("bed", "bed-frame"):
        for item in by_type.get(bed_type, []):
            total_beds += 1
            if catalog_item_matches_type_semantics(item, bed_type):
                continue
            size = item.get("size_cm") or {}
            height = size.get("height") or 0
            why = "高度>150（非 loft）" if float(height or 0) > 150 else "無床身分證據"
            fails.append((str(item.get("furniture_id")), str(item.get("name_en") or "")[:40], why))
    print(f"床類共 {total_beds} 件，仍會被語意關擋下：{len(fails)} 件")
    for fid, name, why in fails[:15]:
        print(f"  ✗ {fid[:46]:46} {name:40} {why}")
    if len(fails) > 15:
        print(f"  … 另 {len(fails) - 15} 件")

    # ── 關卡 2：前端 2D 圖示庫缺口（unknown_furniture_type 即死） ───────
    section("關卡 2｜前端 2D 圖示庫缺口（createFurniture2DItem 會 throw）")
    layout2d = (REPO_ROOT / "backend/server/static/scene_layout2d.js").read_text(encoding="utf-8")
    library_types = set(re.findall(r'^\s{4}type:\s*"([a-z0-9-]+)"', layout2d, re.M))
    print(f"前端圖示庫登記 {len(library_types)} 型：{sorted(library_types)}")
    catalog_types = {t for t in by_type if t}
    # RAG 快取涵蓋全部型錄族系、補件涵蓋必備族系——這些型別都可能被送進前端
    reachable = {t for t in catalog_types}
    missing = sorted(t for t in reachable if t not in library_types)
    exposure = {t: len(by_type.get(t, [])) for t in missing}
    print(f"型錄有、圖示庫沒有（一旦被選中就 unknown_furniture_type 消失）：{len(missing)} 型")
    for t in sorted(missing, key=lambda x: -exposure[x])[:20]:
        required = "⚠️ 必備族系" if any(
            family_of(t) in fams for fams in ROOM_MINIMUM_FAMILIES.values()
        ) else ""
        print(f"  ✗ {t:26} 型錄 {exposure[t]:4d} 件 {required}")
    if len(missing) > 20:
        print(f"  … 另 {len(missing) - 20} 型")

    # ── 關卡 3：前端種子表死鍵（型錄 0 件 → 永遠灰盒或空白） ────────────
    section("關卡 3｜前端種子表死鍵（recommended/questionnaire 表列、型錄 0 件）")
    seed_types = set(re.findall(r'\[\["?([a-z0-9-]+)"?,', layout2d))
    seed_types |= set(re.findall(r'defaults:\s*\[([^\]]*)\]', (REPO_ROOT / "backend/server/static/scene_v2.js").read_text(encoding="utf-8")) and [])
    dead = sorted(t for t in seed_types if t and len(by_type.get(t, [])) == 0)
    for t in dead:
        print(f"  ✗ {t:26} 型錄 0 件（會生出無 GLB 假件→灰盒）")
    if not dead:
        print("  （無）")

    # ── 關卡 4：引擎淨空死鍵 ─────────────────────────────────────────
    section("關卡 4｜引擎淨空死鍵（規則永遠不會命中）")
    from backend.engine.clearance_defaults import (  # noqa: PLC0415
        DEFAULT_CLEARANCE_BY_TYPE,
        DEFAULT_CLEARANCE_SPEC_BY_TYPE,
    )
    engine_keys = set(DEFAULT_CLEARANCE_BY_TYPE) | set(DEFAULT_CLEARANCE_SPEC_BY_TYPE)
    for key in sorted(engine_keys - catalog_types):
        print(f"  ✗ {key:26} 型錄查無此分類")

    # ── 關卡 5：設計上刻意的丟棄（列出以免誤判成 bug） ─────────────────
    section("關卡 5｜刻意丟棄（不是 bug，遇到時別追）")
    print("  家電（refrigerator/washer/…）：G5，永不進 2D/3D")
    print("  無 model_url 且非使用者確認：generate 合併時剔除（待處理清單）")
    print("  地毯/壁架：overlay/ignore 特殊路徑（scene_service _OVERLAY/_IGNORE）")

    # ── 總結 ────────────────────────────────────────────────────────
    section("總結")
    print(f"床語意關殘餘風險：{len(fails)} 件")
    print(f"2D 圖示庫缺口：{len(missing)} 型（實測已殺過 shelving-unit）")
    print(f"種子死鍵：{len(dead)} 型；引擎死鍵：{len(engine_keys - catalog_types)} 個")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

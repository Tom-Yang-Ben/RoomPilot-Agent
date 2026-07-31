"""three.js 本地 vendor 契約（2026-07 盤點第 8 項／風險清單第 1 條修復）。

盤點結論：three.js 只從 unpkg CDN 載入、倉庫無本地副本——會場網路擋掉
unpkg，scene.html 與 library.html 的模組 JS 整包不執行，演示第一步就中斷。

本檔鎖住三件事：importmap 指向本地 vendor、頁面不再引用任何 CDN、
vendor 樹裡「每一個被 import 的 addons 模組」都真的存在（含遞移相依，
漏一檔就是執行期 404，效果等同 CDN 斷線）。
"""
from __future__ import annotations

import re
from pathlib import Path

STATIC = Path(__file__).resolve().parents[1] / "backend" / "server" / "static"
VENDOR = STATIC / "vendor" / "three"


def test_importmaps_point_to_local_vendor_not_cdn() -> None:
    for name in ("scene.html", "library.html"):
        html = (STATIC / name).read_text(encoding="utf-8")
        assert "unpkg.com" not in html, f"{name} 仍依賴 unpkg CDN"
        assert '"three": "/static/vendor/three/build/three.module.js"' in html
        assert '"three/addons/": "/static/vendor/three/examples/jsm/"' in html


def test_vendored_three_core_exists_and_is_the_module_build() -> None:
    core = VENDOR / "build" / "three.module.js"
    assert core.is_file(), "缺 three.module.js 本體"
    assert core.stat().st_size > 500_000, "three.module.js 大小異常，可能是損壞或占位檔"


def test_every_imported_addon_and_its_dependencies_are_vendored() -> None:
    imported: set[str] = set()
    for js in STATIC.glob("*.js"):
        imported.update(
            re.findall(r"three/addons/([A-Za-z0-9_/.-]+\.js)", js.read_text(encoding="utf-8"))
        )
    assert imported, "掃不到任何 three/addons import，測試前提失效"

    jsm = VENDOR / "examples" / "jsm"
    queue = sorted(imported)
    seen: set[str] = set()
    while queue:
        rel = queue.pop()
        if rel in seen:
            continue
        seen.add(rel)
        module = jsm / rel
        assert module.is_file(), f"vendor 缺模組：{rel}（執行期會 404，等同 CDN 斷線）"
        for target in re.findall(r'from\s+[\'"](\.[^\'"]+)[\'"]', module.read_text(encoding="utf-8")):
            parts: list[str] = []
            for part in (str(Path(rel).parent / target)).split("/"):
                if part == "..":
                    parts.pop()
                elif part != ".":
                    parts.append(part)
            queue.append("/".join(parts))

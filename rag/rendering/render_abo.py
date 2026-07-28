# -*- coding: utf-8 -*-
"""批次渲染 ABO/ 資料夾內所有 .glb（front + iso 兩視角），不依賴 items JSON。
用法: python render_abo.py [--limit N]
輸出: renders/ABO/<相對路徑>_{front,iso}.png、renders/ABO/render_meta.jsonl（可續跑）
"""
import argparse, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent          # rendering/
PROJ = ROOT.parent                              # 專案根 RAG/
sys.path.insert(0, str(PROJ / "vlm_annotation"))  # 讓 import 找到 pipeline
import glb_annotation_pipeline as p

ABO_DIR = PROJ / "models"
OUT_DIR = ROOT / "output"
META = OUT_DIR / "render_meta.jsonl"


def main(limit=None):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    done = set()
    if META.exists():
        done = {json.loads(l)["id"] for l in open(META, encoding="utf-8") if l.strip()}
    glbs = sorted(ABO_DIR.rglob("*.glb"))
    todo = [g for g in glbs if g.stem not in done]
    if limit:
        todo = todo[:limit]
    print(f"待渲染 {len(todo)} 筆（共 {len(glbs)}、已完成 {len(done)}）")
    ok = fail = 0
    with open(META, "a", encoding="utf-8") as mf:
        for i, g in enumerate(todo, 1):
            out_sub = OUT_DIR / g.parent.relative_to(ABO_DIR)
            out_sub.mkdir(parents=True, exist_ok=True)
            try:
                paths, gray = p.render_views(g, str(out_sub / g.stem))
                mf.write(json.dumps({"id": g.stem, "category": g.parent.name,
                                     "images": paths, "is_gray": gray},
                                    ensure_ascii=False) + "\n"); mf.flush()
                ok += 1
                print(f"  [{i}/{len(todo)}] OK {'(灰模)' if gray else ''} {g.name}")
            except Exception as e:
                mf.write(json.dumps({"id": g.stem, "category": g.parent.name,
                                     "error": str(e)[:200]}, ensure_ascii=False) + "\n"); mf.flush()
                fail += 1
                print(f"  [{i}/{len(todo)}] FAIL {g.name}: {e}")
    print(f"渲染完成 ok={ok} fail={fail} → {OUT_DIR}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int)
    main(ap.parse_args().limit)

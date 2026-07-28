# -*- coding: utf-8 -*-
"""全量家具 VLM 標註（IKEA + ABO 預渲染 PNG），套用現行 VLM 格式並合併進主資料集。
輸入: rag_dataset/furniture_enriched_v1.json（items 提示欄位）
      vlm_annotation/render_meta_full.jsonl（id → 正面/45度 圖 + 灰模）
輸出: vlm_annotation/annotations_full.jsonl（進度檔，可續跑）
      merge → rag_dataset/furniture_enriched_v2.json（就地更新，先備份）
用法:
  export ANTHROPIC_API_KEY="$(tr -d '\n' < .anthropic_key)"
  python vlm_annotation/annotate_full.py annotate --sample 20   # 跨品牌抽樣試跑
  python vlm_annotation/annotate_full.py annotate               # 全量（可續跑）
  python vlm_annotation/annotate_full.py merge
"""
import argparse, json, shutil
from pathlib import Path
import glb_annotation_pipeline as p   # 同資料夾，重用 build_prompt / call_vlm

ROOT = Path(__file__).resolve().parent          # vlm_annotation/
PROJ = ROOT.parent
ITEMS_PATH = PROJ / "rag_dataset" / "furniture_enriched_v1.json"
META_PATH = ROOT / "render_meta_full.jsonl"
ANN_PATH = ROOT / "annotations_full.jsonl"
TAX_PATH = ROOT / "taxonomy_v2.json"   # 六風格色卡版
V2_PATH = PROJ / "rag_dataset" / "furniture_enriched_v2.json"
BAK_PATH = PROJ / "rag_dataset" / "furniture_enriched_v2.bak_before_full.json"
PLACEHOLDER_MAT = {"GLB材質(未標示)", "GLB材質（未標示）"}


def load_meta():
    meta = {}
    for l in open(META_PATH, encoding="utf-8"):
        if l.strip():
            r = json.loads(l); meta[r["id"]] = r
    return meta


def load_done():
    """只把『成功』的列視為完成；錯誤列（暫時性 429 等）留待重跑時自動重試。"""
    if not ANN_PATH.exists():
        return set()
    done = set()
    for l in open(ANN_PATH, encoding="utf-8"):
        if l.strip():
            r = json.loads(l)
            if "error" not in r:
                done.add(r["id"])
    return done


def pick_todo(items, meta, done, limit, sample):
    todo = [it for it in items if it["id"] in meta and it["id"] not in done]
    if sample:                              # 跨品牌均衡抽樣
        per = {}
        out = []
        for it in todo:
            b = meta[it["id"]]["brand"]
            if per.get(b, 0) < sample // 2 or (b not in per and len(out) < sample):
                per[b] = per.get(b, 0) + 1; out.append(it)
            if len(out) >= sample:
                break
        return out
    return todo[:limit] if limit else todo


def annotate(limit=None, sample=None):
    import anthropic
    client = anthropic.Anthropic()
    d = json.load(open(ITEMS_PATH, encoding="utf-8"))
    items = d["items"]
    tax = json.load(open(TAX_PATH, encoding="utf-8"))
    meta, done = load_meta(), load_done()
    todo = pick_todo(items, meta, done, limit, sample)
    print(f"待標註 {len(todo)} 件（meta {len(meta)}、已完成 {len(done)}）")
    valid = set(tax["styles"])
    ok = fail = 0
    with open(ANN_PATH, "a", encoding="utf-8") as f:
        for i, it in enumerate(todo, 1):
            m = meta[it["id"]]; gray = m.get("is_gray", False)
            try:
                prompt = p.build_prompt(it, tax, gray)
                ann = p.call_vlm(client, prompt, [] if gray else m["images"])
                # VLM 有時把 enum 附中文註（如 "minimalist(極簡風)"），比對前先正規化
                def norm(s):
                    return (s or "").split("(")[0].split("（")[0].strip()
                sp, ss = norm(ann.get("style_primary")), norm(ann.get("style_secondary"))
                if sp in valid:
                    ann["style_primary"] = sp
                else:
                    ann["style_primary"] = "modern_minimal"
                    ann["confidence"] = min(ann.get("confidence", 0.3), 0.3)
                ann["style_secondary"] = ss if ss in valid else ann["style_primary"]
                ann["mood_tags"] = [t for t in ann.get("mood_tags", []) if t in tax["mood_vocab"]][:3]
                ann.update({"id": it["id"], "brand": m.get("brand"),
                            "desc_source": "text_inference" if gray else "glb_render"})
                f.write(json.dumps(ann, ensure_ascii=False) + "\n"); f.flush(); ok += 1
                if i % 25 == 0 or sample:
                    print(f"  [{i}/{len(todo)}] {m.get('brand')} {it['name_zh']} → "
                          f"{ann.get('style_primary')} conf={ann.get('confidence')}")
            except Exception as e:
                f.write(json.dumps({"id": it["id"], "error": str(e)[:200]}, ensure_ascii=False) + "\n")
                f.flush(); fail += 1
                print(f"  [{i}/{len(todo)}] FAIL {it['id']}: {e}")
    print(f"標註完成 ok={ok} fail={fail}")


def merge():
    anns = {}
    for l in open(ANN_PATH, encoding="utf-8"):
        if l.strip():
            r = json.loads(l)
            if "error" not in r:
                anns[r["id"]] = r
    d = json.load(open(V2_PATH, encoding="utf-8"))
    by_id = {it["id"]: it for it in d["items"]}
    hit = 0
    for aid, a in anns.items():
        it = by_id.get(aid)
        if it is None:
            continue
        for k in ("style_primary", "style_secondary", "pattern", "mood_tags",
                  "description", "confidence", "desc_source"):
            it[k] = a.get(k)
        if a.get("colors_seen") and not it.get("colors"):
            it["colors"] = a["colors_seen"]
        if a.get("materials_seen") and (not it.get("materials")
                                        or set(it.get("materials", [])) & PLACEHOLDER_MAT):
            it["materials"] = a["materials_seen"]
        hit += 1
    if "full_render_vlm" not in str(d.get("schema_version", "")):
        d["schema_version"] = str(d.get("schema_version", "")) + "+full_render_vlm"
    shutil.copy(V2_PATH, BAK_PATH)
    json.dump(d, open(V2_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"合併 {hit} 筆 → {V2_PATH.name}（備份 {BAK_PATH.name}）")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["annotate", "merge"])
    ap.add_argument("--limit", type=int)
    ap.add_argument("--sample", type=int, help="跨品牌均衡抽樣件數（試跑用）")
    a = ap.parse_args()
    annotate(a.limit, a.sample) if a.stage == "annotate" else merge()

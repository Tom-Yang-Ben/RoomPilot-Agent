# -*- coding: utf-8 -*-
"""把既有全量 VLM 匯出 all_furniture_vlm_responses_.json 中、
本專案標註格式所『沒有』的 RAG 欄位，補進主資料集 furniture_enriched_v2.json。

補充欄位（皆為匯出獨有、對 RAG 檢索有價值）:
  object_type_zh / shape_tags / features / search_keywords / rag_text(檢索文本)
不覆寫既有欄位；匯出失敗(failed/blocked)的筆自動略過。就地更新，先備份。
"""
import json, shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent          # vlm_annotation/
PROJ = ROOT.parent
EXPORT = PROJ / "all_furniture_vlm_responses_.json"
V2 = PROJ / "rag_dataset" / "furniture_enriched_v2.json"
BAK = PROJ / "rag_dataset" / "furniture_enriched_v2.bak_before_supplement.json"


def main():
    ex = {it["id"]: it for it in json.load(open(EXPORT, encoding="utf-8"))["items"]}
    d = json.load(open(V2, encoding="utf-8"))
    add = miss = skip = 0
    for it in d["items"]:
        e = ex.get(it["id"])
        if e is None:
            miss += 1
            continue
        if e.get("final_status") != "success":
            skip += 1
            continue
        vr = e.get("visual_result") or {}
        rag = [x for x in (e.get("effective_rag_text_1"), e.get("effective_rag_text_2"),
                           e.get("effective_rag_text_3")) if x]
        for field, val in (("object_type_zh", vr.get("object_type_zh")),
                           ("shape_tags", vr.get("shape_tags")),
                           ("features", vr.get("features")),
                           ("search_keywords", vr.get("search_keywords_zh")),
                           ("rag_text", rag or None)):
            if val and not it.get(field):        # 只補、不覆寫
                it[field] = val
        add += 1
    if "export_supplemented" not in str(d.get("schema_version", "")):
        d["schema_version"] = str(d.get("schema_version", "")) + "+export_supplemented"
    shutil.copy(V2, BAK)
    json.dump(d, open(V2, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"補充 {add} 筆（匯出缺 {miss}、非成功略過 {skip}）→ {V2.name}")
    print(f"備份 → {BAK.name}；schema_version = {d['schema_version']}")


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""
RoomPilot GLB 外觀標註 pipeline(本機執行)
流程:download → render → annotate → merge

用法(在你自己的電腦):
  pip install trimesh pyrender pillow numpy gdown anthropic
  set ANTHROPIC_API_KEY=你的key (Windows;mac/linux 用 export)

  python glb_annotation_pipeline.py download --folder <雲端資料夾URL1> --folder <URL2>
  python glb_annotation_pipeline.py render   --limit 50
  python glb_annotation_pipeline.py annotate --limit 50
  python glb_annotation_pipeline.py merge
  python glb_annotation_pipeline.py report

特性:
- --limit N 試跑 / 不加為全量
- 可續跑:已完成的檔案自動跳過(annotations.jsonl 為進度檔)
- 灰模(無貼圖無色彩)自動改用文字推斷 fallback,標記 desc_source 與低信心
"""
import argparse, base64, io, json, os, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent          # vlm_annotation/
PROJ = ROOT.parent                              # 專案根 RAG/
GLB_DIR = PROJ / "models"
IMG_DIR = PROJ / "rendering" / "output"
ANN_PATH = ROOT / "annotations.jsonl"
DATA_PATH = PROJ / "rag_dataset" / "furniture_enriched_v1.json"
TAX_PATH = ROOT / "taxonomy_v2.json"   # 六風格色卡版（v1 為舊 12 風格，僅保留供回溯）
OUT_PATH = PROJ / "rag_dataset" / "furniture_enriched_v2.json"
VLM_MODEL = "claude-haiku-4-5-20251001"

# ---------------------------------------------------------------- utilities

def load_items():
    d = json.load(open(DATA_PATH, encoding="utf-8"))
    return d, d["items"]

def key_to_filename(object_key: str) -> str:
    return Path(object_key).name  # models/abo/furniture/xxx.glb -> xxx.glb

def load_done_ids():
    if not ANN_PATH.exists():
        return set()
    return {json.loads(l)["id"] for l in open(ANN_PATH, encoding="utf-8") if l.strip()}

# ---------------------------------------------------------------- stage: download

def stage_download(folders):
    GLB_DIR.mkdir(exist_ok=True)
    for url in folders:
        print(f"下載資料夾: {url}")
        subprocess.run([sys.executable, "-m", "gdown", "--folder", url,
                        "-O", str(GLB_DIR), "--remaining-ok"], check=True)
    n = len(list(GLB_DIR.rglob("*.glb")))
    print(f"完成,共 {n} 個 .glb")

# ---------------------------------------------------------------- stage: render

def is_gray_model(scene):
    import numpy as np
    for g in scene.geometry.values():
        v = g.visual
        mat = getattr(v, "material", None)
        if mat is not None:
            if getattr(mat, "baseColorTexture", None) is not None:
                return False
            bcf = getattr(mat, "baseColorFactor", None)
            if bcf is not None:
                rgb = np.array(bcf[:3], dtype=float)
                if rgb.max() > 1.5:
                    rgb = rgb / 255.0
                if np.ptp(rgb) > 0.05 or rgb.mean() < 0.35 or rgb.mean() > 0.92:
                    return False
        if getattr(v, "kind", None) == "vertex":
            return False
    return True

def render_views(glb_path, out_prefix):
    """渲染正面與 45 度斜角兩張圖;回傳 (圖片路徑list, 是否灰模)"""
    import numpy as np, trimesh, pyrender
    from PIL import Image
    tscene = trimesh.load(glb_path, force="scene")
    gray = is_gray_model(tscene)
    scene = pyrender.Scene.from_trimesh_scene(tscene, ambient_light=[0.35] * 3)
    bounds = tscene.bounds
    center = bounds.mean(axis=0)
    size = float(np.linalg.norm(bounds[1] - bounds[0]))
    cam = pyrender.PerspectiveCamera(yfov=np.pi / 4)
    light = pyrender.DirectionalLight(intensity=3.0)
    r = pyrender.OffscreenRenderer(768, 768)
    paths = []
    for name, azim in (("front", 0.0), ("iso", np.pi / 4)):
        dist = size * 1.6
        eye = center + dist * np.array([np.sin(azim), 0.35, np.cos(azim)])
        pose = look_at(eye, center)
        cn = scene.add(cam, pose=pose)
        ln = scene.add(light, pose=pose)
        color, _ = r.render(scene)
        p = f"{out_prefix}_{name}.png"
        Image.fromarray(color).save(p)
        paths.append(p)
        scene.remove_node(cn); scene.remove_node(ln)
    r.delete()
    return paths, gray

def look_at(eye, target):
    import numpy as np
    fwd = np.array(target) - np.array(eye); fwd /= np.linalg.norm(fwd)
    right = np.cross(fwd, [0, 1, 0]); right /= np.linalg.norm(right)
    up = np.cross(right, fwd)
    m = np.eye(4)
    m[:3, 0], m[:3, 1], m[:3, 2], m[:3, 3] = right, up, -fwd, eye
    return m

def stage_render(limit=None):
    IMG_DIR.mkdir(exist_ok=True)
    _, items = load_items()
    fmap = {p.name: p for p in GLB_DIR.rglob("*.glb")}
    meta_path = IMG_DIR / "render_meta.jsonl"
    done = set()
    if meta_path.exists():
        done = {json.loads(l)["id"] for l in open(meta_path, encoding="utf-8")}
    todo = [it for it in items if key_to_filename(it["object_key"]) in fmap
            and it["id"] not in done]
    if limit:
        todo = todo[:limit]
    print(f"待渲染 {len(todo)} 筆(GLB 在手 {len(fmap)}、已完成 {len(done)})")
    ok = fail = 0
    with open(meta_path, "a", encoding="utf-8") as mf:
        for i, it in enumerate(todo, 1):
            try:
                paths, gray = render_views(fmap[key_to_filename(it["object_key"])],
                                           str(IMG_DIR / it["id"]))
                mf.write(json.dumps({"id": it["id"], "images": paths,
                                     "is_gray": gray}, ensure_ascii=False) + "\n")
                ok += 1
            except Exception as e:
                mf.write(json.dumps({"id": it["id"], "error": str(e)[:200]},
                                    ensure_ascii=False) + "\n")
                fail += 1
            if i % 10 == 0:
                print(f"  {i}/{len(todo)}")
    print(f"渲染完成 ok={ok} fail={fail}")

# ---------------------------------------------------------------- stage: annotate

def build_prompt(item, tax, gray):
    styles = ", ".join(f"{k}({v['zh']})" for k, v in tax["styles"].items())
    moods = ", ".join(tax["mood_vocab"])
    base = f"""你是專業室內設計師,為 3D 家具模型做外觀標註。
商品資訊:名稱「{item['name_zh']}」/ 類別「{item['canonical_category_zh']}」/ 已知材質 {item.get('materials') or '未知'} / 已知顏色 {item.get('colors') or '未知'}

請只輸出 JSON(無 markdown 圍欄),格式:
{{"style_primary": "<從此清單擇一: {styles}>",
 "style_secondary": "<次要風格,同清單擇一,可與主風格相同>",
 "pattern": "<擇一: {'/'.join(tax['pattern_enum'])}>",
 "colors_seen": ["<實際看到的顏色,繁中,最多3個>"],
 "materials_seen": ["<看到的材質,繁中,最多3個>"],
 "mood_tags": ["<從此詞彙表選最多3個: {moods}>"],
 "description": "<80-120字繁體中文外觀描述,寫線條、色調、材質、氛圍與適合情境,不要提及圖片或模型>",
 "confidence": <0到1,你對這次標註的把握>}}"""
    if gray:
        base += "\n注意:此模型無材質貼圖(灰模),請主要依商品名稱與已知欄位推斷,confidence 請勿超過 0.5。"
    else:
        base += "\n請以圖片實際外觀為準,與已知欄位衝突時以你看到的為準。"
    return base

def call_vlm(client, prompt, image_paths):
    content = []
    for p in image_paths:
        b64 = base64.standard_b64encode(open(p, "rb").read()).decode()
        content.append({"type": "image",
                        "source": {"type": "base64", "media_type": "image/png", "data": b64}})
    content.append({"type": "text", "text": prompt})
    msg = client.messages.create(model=VLM_MODEL, max_tokens=800,
                                 messages=[{"role": "user", "content": content}])
    text = "".join(b.text for b in msg.content if b.type == "text")
    return json.loads(text.replace("```json", "").replace("```", "").strip())

def stage_annotate(limit=None):
    import anthropic
    client = anthropic.Anthropic()
    d, items = load_items()
    tax = json.load(open(TAX_PATH, encoding="utf-8"))
    meta = {}
    for l in open(IMG_DIR / "render_meta.jsonl", encoding="utf-8"):
        row = json.loads(l)
        meta[row["id"]] = row
    done = load_done_ids()
    todo = [it for it in items if it["id"] in meta and "error" not in meta[it["id"]]
            and it["id"] not in done]
    if limit:
        todo = todo[:limit]
    print(f"待標註 {len(todo)} 筆(已完成 {len(done)})")
    valid_styles = set(tax["styles"])
    with open(ANN_PATH, "a", encoding="utf-8") as f:
        for i, it in enumerate(todo, 1):
            m = meta[it["id"]]
            gray = m.get("is_gray", False)
            try:
                prompt = build_prompt(it, tax, gray)
                ann = call_vlm(client, prompt, [] if gray else m["images"])
                # enum 驗證:VLM 輸出不在清單內就降信心
                if ann.get("style_primary") not in valid_styles:
                    ann["style_primary"] = "modern_minimal"
                    ann["confidence"] = min(ann.get("confidence", 0.3), 0.3)
                ann["mood_tags"] = [t for t in ann.get("mood_tags", [])
                                    if t in tax["mood_vocab"]][:3]
                ann.update({"id": it["id"],
                            "desc_source": "text_inference" if gray else "glb_render"})
                f.write(json.dumps(ann, ensure_ascii=False) + "\n"); f.flush()
            except Exception as e:
                f.write(json.dumps({"id": it["id"], "error": str(e)[:200]},
                                   ensure_ascii=False) + "\n"); f.flush()
            if i % 10 == 0:
                print(f"  {i}/{len(todo)}")
    print("標註完成")

# ---------------------------------------------------------------- stage: merge / report

def stage_merge():
    d, items = load_items()
    anns = {}
    for l in open(ANN_PATH, encoding="utf-8"):
        row = json.loads(l)
        if "error" not in row:
            anns[row["id"]] = row
    hit = 0
    for it in items:
        a = anns.get(it["id"])
        if not a:
            continue
        for k in ("style_primary", "style_secondary", "pattern", "mood_tags",
                  "description", "confidence", "desc_source"):
            it[k] = a.get(k)
        if a.get("colors_seen") and not it.get("colors"):
            it["colors"] = a["colors_seen"]
        if a.get("materials_seen") and (not it.get("materials")
                                        or it["materials"] == ["GLB材質(未標示)"]
                                        or it["materials"] == ["GLB材質（未標示）"]):
            it["materials"] = a["materials_seen"]
        hit += 1
    d["schema_version"] = str(d.get("schema_version", "")) + "+vlm_annotated"
    json.dump(d, open(OUT_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"合併 {hit} 筆標註 → {OUT_PATH.name}")

def stage_report():
    rows = [json.loads(l) for l in open(ANN_PATH, encoding="utf-8")]
    ok = [r for r in rows if "error" not in r]
    err = [r for r in rows if "error" in r]
    gray = [r for r in ok if r.get("desc_source") == "text_inference"]
    from collections import Counter
    print(f"標註 {len(ok)} 成功 / {len(err)} 失敗;灰模 fallback {len(gray)} 筆"
          f"({len(gray)/max(len(ok),1):.0%})")
    print("風格分布:", Counter(r.get("style_primary") for r in ok).most_common())
    confs = [r.get("confidence", 0) for r in ok]
    if confs:
        print(f"平均信心 {sum(confs)/len(confs):.2f};低於0.5的 {sum(c<0.5 for c in confs)} 筆")

# ---------------------------------------------------------------- main

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["download", "render", "annotate", "merge", "report"])
    ap.add_argument("--folder", action="append", default=[])
    ap.add_argument("--limit", type=int)
    a = ap.parse_args()
    if a.stage == "download":
        stage_download(a.folder)
    elif a.stage == "render":
        stage_render(a.limit)
    elif a.stage == "annotate":
        stage_annotate(a.limit)
    elif a.stage == "merge":
        stage_merge()
    else:
        stage_report()

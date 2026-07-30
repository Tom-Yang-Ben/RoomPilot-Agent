"""依 taxonomy_v2（六風格色卡）重新判定 9,350 件家具的風格。

不重看渲染圖：既有的 80–120 字描述本來就是 VLM 看圖寫的，已含顏色、材質、造型線索，
用文字重判比視覺重標快一個量級、便宜一個量級。判定同時回傳最接近的色卡，
之後可用色卡的 palette 做視覺一致性檢查。

**混合方案的批次端**：本檔預設用本機 Ollama（Qwen3），零 API 成本、不會跑到一半
額度用盡；互動的需求解析（query_parser.py）仍走 Haiku，因為那裡延遲才是關鍵。
兩邊共用同一份 prompt 與 JSON schema，只有呼叫層不同。

輸出：vlm_annotation/style_v2_annotations.jsonl（可續跑，每行一件）
      舊的 12 風格值不動，合併進 v3 時才搬到 style_primary_v1。

用法：
    python3 json_adjustment/reclassify_styles.py --limit 30            # 冒煙測試（本機 Qwen3）
    python3 json_adjustment/reclassify_styles.py --provider anthropic  # 改用 Haiku
    python3 json_adjustment/reclassify_styles.py --compare 50          # 與既有判定比對一致率
    python3 json_adjustment/reclassify_styles.py --report              # 只看目前進度與分布
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path

import anthropic

PROJ = Path(__file__).resolve().parent.parent
SRC = PROJ / "rag_dataset" / "furniture_enriched_v3.json"
TAXONOMY = PROJ / "vlm_annotation" / "taxonomy_v2.json"
OUT = PROJ / "vlm_annotation" / "style_v2_annotations.jsonl"
KEY_FILE = PROJ / ".anthropic_key"

MODEL = "claude-haiku-4-5"           # --provider anthropic 時使用
OLLAMA_MODEL = "qwen3:8b"            # --provider ollama 時使用（預設）
OLLAMA_URL = "http://localhost:11434"
TZ8 = timezone(timedelta(hours=8))

_write_lock = threading.Lock()


def get_client() -> anthropic.Anthropic:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key and KEY_FILE.exists():
        key = KEY_FILE.read_text(encoding="utf-8").strip()
    # 併發下偶爾 429，交給 SDK 退避重試
    return anthropic.Anthropic(api_key=key, max_retries=5) if key else anthropic.Anthropic(max_retries=5)


def build_system(tax: dict) -> str:
    blocks = []
    for key, spec in tax["styles"].items():
        cards = "\n".join(
            f"    - {c['name_zh']}（{c['card_id']}）：{ '、'.join(c['palette_hex']) }"
            for c in spec["cards"]
        )
        blocks.append(f"{key}（{spec['zh']}）\n  定義：{spec['definition']}\n  色卡：\n{cards}")
    styles_block = "\n\n".join(blocks)

    return f"""你是室內設計風格判定器。根據家具的既有描述（顏色、材質、造型、氛圍），
判定它最接近下列六種風格中的哪一種，並指出最接近的色卡。

# 六風格與色卡
{styles_block}

# 判定規則
1. style_primary 必須從六個 key 中擇一，不可自創。
2. style_secondary 是次要風格，可與主風格不同；真的只像一種風格時，填與主風格相同。
3. card_id 選最接近的那張色卡——優先看家具的實際顏色是否落在該色卡的色票附近，
   其次看材質與造型是否符合該色卡的名稱意象。
4. 判定依據優先序：**顏色與材質 > 造型線條 > 氛圍詞 > 名稱**。
   名稱常有翻譯雜訊（法文、義大利文殘留），不要被名稱帶偏。
5. 六種風格都不像時，選最接近的一個並把 confidence 壓到 0.5 以下，不要硬掰。
6. reason 用一句話（20 字內）說明關鍵依據，例如「淺木+米白布面，色票接近自然木質」。

# 常見判別要點
- 淺木＋白／米色、線條圓潤 → scandinavian；低彩度米灰＋原木藤編、低矮貼地 → japanese
- 黑白灰、平整無把手、極少裝飾 → modern_minimal；奶油白／奶茶色、圓弧柔霧、絨布 → cream
- 黑鐵、水泥灰、深色皮革、結構外露 → industrial；深胡桃木、線板雕花、格紋皮革 → american
- 中古世紀風格（胡桃木斜腳、復古色）多半歸 american 或 modern_minimal，依色調決定
- 輕奢／大理石＋黃銅多半歸 modern_minimal 或 american，依整體色調決定"""


def build_schema(style_keys: list, card_ids: list) -> dict:
    return {
        "type": "object",
        "properties": {
            "style_primary": {"type": "string", "enum": style_keys},
            "style_secondary": {"type": "string", "enum": style_keys},
            "card_id": {"type": "string", "enum": card_ids},
            "confidence": {"type": "number"},
            "reason": {"type": "string"},
        },
        "required": ["style_primary", "style_secondary", "card_id", "confidence", "reason"],
        "additionalProperties": False,
    }


def item_payload(item: dict) -> str:
    def join(v):
        return "、".join(v) if isinstance(v, list) else (v or "")

    return "\n".join(
        f"{label}：{value}"
        for label, value in [
            ("名稱", item.get("name_zh") or ""),
            ("類別", item.get("category_final") or ""),
            ("物件類型", item.get("object_type_zh") or ""),
            ("顏色", join(item.get("colors"))),
            ("材質", join(item.get("materials"))),
            ("表面圖樣", item.get("pattern") or ""),
            ("造型", join(item.get("shape_tags"))),
            ("氛圍", join(item.get("mood_tags"))),
            ("描述", item.get("description") or ""),
            ("特徵", join(item.get("features"))),
        ]
        if value
    )


def classify_ollama(session, model: str, url: str, system: str, schema: dict, item: dict) -> tuple:
    """本機 Qwen3。format 傳 JSON schema → llama.cpp 語法約束解碼，保證 JSON 合法。

    think=False 是關鍵：Qwen3 預設會先產一大段推理，token 量多 2-3 倍，
    在 M1 上會讓每件從數秒變成數十秒。
    """
    resp = session.post(
        f"{url}/api/chat",
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": item_payload(item)},
            ],
            "format": schema,
            "think": False,
            "stream": False,
            "options": {"temperature": 0, "num_predict": 512},
        },
        timeout=300,
    )
    resp.raise_for_status()
    data = resp.json()
    out = json.loads(data["message"]["content"])
    usage = {
        "in": data.get("prompt_eval_count", 0),
        "out": data.get("eval_count", 0),
        "cache_read": 0,
    }
    return out, usage


def classify_anthropic(client, system: str, schema: dict, item: dict) -> tuple:
    resp = client.messages.create(
        model=MODEL,
        max_tokens=512,
        system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
        output_config={"format": {"type": "json_schema", "schema": schema}},
        messages=[{"role": "user", "content": item_payload(item)}],
    )
    if resp.stop_reason == "refusal":
        raise RuntimeError("refusal")
    out = json.loads(next(b.text for b in resp.content if b.type == "text"))
    usage = {
        "in": resp.usage.input_tokens,
        "out": resp.usage.output_tokens,
        "cache_read": getattr(resp.usage, "cache_read_input_tokens", 0) or 0,
    }
    return out, usage


def classify(runner, system: str, schema: dict, item: dict) -> dict:
    """runner 由 main 依 --provider 綁定，兩條路徑輸出同一種 row。"""
    out, usage = runner(system, schema, item)
    out["id"] = item["id"]
    out["style_primary_v1"] = item.get("style_primary")
    out["annotated_at"] = datetime.now(TZ8).isoformat(timespec="seconds")
    out["_usage"] = usage
    return out


def load_done() -> set:
    if not OUT.exists():
        return set()
    done = set()
    with OUT.open(encoding="utf-8") as fh:
        for line in fh:
            try:
                done.add(json.loads(line)["id"])
            except Exception:
                continue
    return done


def report() -> int:
    if not OUT.exists():
        print("尚未有任何判定結果")
        return 1
    rows = [json.loads(l) for l in OUT.open(encoding="utf-8")]
    print(f"已判定 {len(rows)} 筆")
    print("\n新風格分布：")
    for k, v in Counter(r["style_primary"] for r in rows).most_common():
        print(f"  {k:16s}{v:>6}  ({v/len(rows)*100:.1f}%)")
    print("\n色卡分布 top 10：")
    for k, v in Counter(r["card_id"] for r in rows).most_common(10):
        print(f"  {k:20s}{v:>6}")
    conf = [r["confidence"] for r in rows]
    print(f"\n把握度：中位 {sorted(conf)[len(conf)//2]:.2f}／低於 0.5 者 {sum(1 for c in conf if c < 0.5)} 筆")
    print("\n舊 → 新 遷移（top 12）：")
    for (o, n), v in Counter((r.get("style_primary_v1"), r["style_primary"]) for r in rows).most_common(12):
        print(f"  {str(o):18s} → {n:16s}{v:>6}")
    return 0


def build_runner(args):
    """依 --provider 綁定判定函式，回傳 (runner, 標籤)。"""
    if args.provider == "ollama":
        import requests

        session = requests.Session()
        model = args.model or OLLAMA_MODEL
        try:
            session.get(f"{args.ollama_url}/api/version", timeout=5).raise_for_status()
        except Exception as exc:
            raise SystemExit(f"連不上 Ollama（{args.ollama_url}）：{exc}\n請先執行 `ollama serve`")
        runner = lambda s, sc, it: classify_ollama(session, model, args.ollama_url, s, sc, it)
        return runner, f"ollama/{model}"

    client = get_client()
    model = args.model or MODEL
    runner = lambda s, sc, it: classify_anthropic(client, s, sc, it)
    return runner, f"anthropic/{model}"


def compare(args, system: str, schema: dict, items: list) -> int:
    """拿既有判定當基準，量本機模型的一致率。

    9,350 筆 Haiku 判定就是現成的評測集——換模型前先量，才知道品質掉多少。
    """
    done = load_done()
    if not done:
        print("沒有既有判定可比對")
        return 1
    ref = {}
    with OUT.open(encoding="utf-8") as fh:
        for line in fh:
            row = json.loads(line)
            ref[row["id"]] = row

    sample = [i for i in items if i["id"] in ref][: args.compare]
    runner, label = build_runner(args)
    print(f"比對 {len(sample)} 筆：{label} vs 既有判定", flush=True)

    agree_style = agree_card = 0
    started = time.time()
    mismatches = []
    for n, item in enumerate(sample, start=1):
        try:
            got, _ = runner(system, schema, item)
        except Exception as exc:
            print(f"  ✗ {item['id'][:44]} {type(exc).__name__}: {exc}", flush=True)
            continue
        base = ref[item["id"]]
        if got["style_primary"] == base["style_primary"]:
            agree_style += 1
        else:
            mismatches.append((item.get("name_zh", "")[:24], base["style_primary"], got["style_primary"]))
        if got["card_id"] == base["card_id"]:
            agree_card += 1
        if n % 10 == 0:
            print(f"  {n}/{len(sample)}  {(time.time()-started)/n:.1f} 秒/筆", flush=True)

    elapsed = time.time() - started
    print(f"\n風格一致率 {agree_style}/{len(sample)} = {agree_style/len(sample)*100:.1f}%")
    print(f"色卡一致率 {agree_card}/{len(sample)} = {agree_card/len(sample)*100:.1f}%")
    print(f"平均 {elapsed/len(sample):.1f} 秒/筆　→ 全量 9,350 筆推估 {elapsed/len(sample)*9350/3600:.1f} 小時")
    if mismatches:
        print("\n不一致樣本（既有 → 本機）：")
        for name, a, b in mismatches[:8]:
            print(f"  {name:26s} {a:16s} → {b}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="只處理前 N 筆未完成的")
    ap.add_argument("--workers", type=int, default=0, help="0 = 依 provider 自動（ollama 2／anthropic 12）")
    ap.add_argument("--provider", default="ollama", choices=["ollama", "anthropic"])
    ap.add_argument("--model", default="", help="覆寫模型名稱")
    ap.add_argument("--ollama-url", default=OLLAMA_URL)
    ap.add_argument("--compare", type=int, default=0, help="與既有判定比對 N 筆，不寫檔")
    ap.add_argument("--report", action="store_true", help="只看目前進度與分布")
    args = ap.parse_args()

    if args.report:
        return report()

    tax = json.loads(TAXONOMY.read_text(encoding="utf-8"))
    system = build_system(tax)
    card_ids = [c["card_id"] for s in tax["styles"].values() for c in s["cards"]]
    schema = build_schema(list(tax["styles"]), card_ids)

    items = json.loads(SRC.read_text(encoding="utf-8"))["items"]

    if args.compare:
        return compare(args, system, schema, items)

    # 本機模型受記憶體頻寬限制，併發開太多只會互相拖累
    if not args.workers:
        args.workers = 2 if args.provider == "ollama" else 12

    done = load_done()
    todo = [i for i in items if i["id"] not in done]
    if args.limit:
        todo = todo[: args.limit]

    runner, label = build_runner(args)
    print(f"總數 {len(items)}／已完成 {len(done)}／本次處理 {len(todo)}"
          f"（{label}，併發 {args.workers}）", flush=True)
    if not todo:
        return report()

    started = time.time()
    ok = fail = 0
    tokens = Counter()

    with OUT.open("a", encoding="utf-8") as fh, ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(classify, runner, system, schema, it): it for it in todo}
        for n, fut in enumerate(as_completed(futures), start=1):
            item = futures[fut]
            try:
                row = fut.result()
                row["provider"] = label
                usage = row.pop("_usage")
                tokens.update(usage)
                with _write_lock:
                    fh.write(json.dumps(row, ensure_ascii=False) + "\n")
                    fh.flush()
                ok += 1
            except Exception as exc:
                fail += 1
                print(f"  ✗ {item['id'][:50]} {type(exc).__name__}: {exc}", flush=True)

            if n % 200 == 0 or n == len(todo):
                elapsed = time.time() - started
                rate = n / elapsed
                eta = (len(todo) - n) / rate if rate else 0
                print(f"  {n}/{len(todo)}  {rate:.1f} 筆/秒  已用 {elapsed/60:.1f}m  剩餘 {eta/60:.1f}m"
                      f"  成功 {ok} 失敗 {fail}", flush=True)

    print(f"\n完成：成功 {ok}／失敗 {fail}／耗時 {(time.time()-started)/60:.1f} 分鐘（{label}）")
    if args.provider == "anthropic":
        cost = tokens["in"] / 1e6 * 1.0 + tokens["out"] / 1e6 * 5.0 + tokens["cache_read"] / 1e6 * 0.1
        print(f"token：輸入 {tokens['in']:,}／輸出 {tokens['out']:,}／快取讀取 {tokens['cache_read']:,}"
              f"　估計成本 US${cost:.2f}")
    else:
        print(f"token：輸入 {tokens['in']:,}／輸出 {tokens['out']:,}　本機推論，零 API 成本")
    print()
    return report()


if __name__ == "__main__":
    sys.exit(main())

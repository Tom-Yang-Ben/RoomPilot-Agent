#!/usr/bin/env python3
"""交付前自我檢查。出檔給屋主之前跑這支，比出去之後被抓包便宜太多。

用法：
    python3 preflight_check.py content.json --pdf 交付文件.pdf \
        --data report_data.json --base-dir <成果包資料夾>

--data 是選填；有給的話會做「數字溯源」：把文案裡的尺寸、坪數、數量拿去比對
原始資料，找不到來源的會標成「需人工確認」。這條不是要擋你，是因為在提案裡
講錯一個尺寸，屋主對整份文件的信任就沒了。

離開碼：0 = 全過或只有提醒，1 = 有 FAIL。
"""

import argparse
import json
import re
import sys
from pathlib import Path

# 只抓「忘了寫」的痕跡。「待補」「待現場確認」是合法的誠實標註，不在這裡攔。
PLACEHOLDERS = [
    "TODO", "TBD", "FIXME", "lorem ipsum", "xxx", "XXX",
    "undefined", "[object", "【", "〇〇", "??", "待填", "此處填",
]

results = []


def check(name, ok, detail="", level="FAIL"):
    results.append({"name": name, "ok": bool(ok), "detail": detail, "level": level})


def walk_strings(node, path=""):
    if isinstance(node, str):
        yield path, node
    elif isinstance(node, dict):
        for k, v in node.items():
            yield from walk_strings(v, f"{path}.{k}" if path else k)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from walk_strings(v, f"{path}[{i}]")


def check_meta(content):
    meta = content.get("meta", {})
    for key, label in [("project_name", "案名"), ("subtitle", "格局/坪數/風格副標")]:
        check(f"封面有{label}", bool(meta.get(key)), f"meta.{key} 為空")
    cover_meta = " ".join(
        f"{m.get('label')}{m.get('value')}" for m in meta.get("cover_meta", [])
    )
    check("封面標註日期", bool(re.search(r"\d{4}", cover_meta)),
          "cover_meta 找不到年份，屋主無法判斷這是哪一版")
    check("封面標註版本", bool(re.search(r"v\d|版|version", cover_meta, re.I)),
          "cover_meta 沒有版本資訊", level="WARN")
    check("有封面主視覺", bool(meta.get("cover_image")),
          "沒有 cover_image，封面會是空白色塊", level="WARN")


# 敘述裡不該出現的東西：家具型號／品牌與製程用語。
# 括號裡的中英並陳是刻意的（「橡木海島型 (oak engineered)」方便發包），先剝掉再比對；
# 抓的是連續兩個以上的拉丁詞、全大寫品牌（BESTÅ／HEMNES／POÄNG）與英寸標示。
PARENS = re.compile(r"[（(][^）)]*[）)]")
MODEL_NUMBER = re.compile(
    r"[A-ZÅÄÖÆØ]{4,}"
    r"|[A-Za-zÀ-ÿ]{2,}(?:[\s&\-–]+[A-Za-z0-9À-ÿ][\w.]*)+"
    r"|\d+(?:\.\d+)?\s*[\"”']\s*[WDHwdh]"
)
PROCESS_WORDS = ["幾何引擎", "淨空", "碰撞", "不重疊", "第 5 步", "第 6 步", "第 7 步",
                 "見下方規格表", "圖面與清單一致", "正式家具庫"]
# 這兩種空間不在軟裝提案範圍，不排篇章。比對字根，「主浴」「工作陽台」也算。
OUT_OF_SCOPE_ROOMS = ["浴", "廁", "陽台", "露台"]


def check_rooms(content, base_dir):
    rooms = content.get("rooms", [])
    check("至少有一個空間篇章", len(rooms) > 0, "rooms 是空的")
    limits_text = " ".join(str(x) for x in (content.get("appendix", {}).get("limits") or []))
    for r in rooms:
        n = r.get("name", "(未命名)")
        src = r.get("hero_image")
        if src:
            p = Path(src) if Path(src).is_absolute() else base_dir / src
            check(f"「{n}」主視覺圖檔案存在", p.exists(), f"hero_image = {src!r} 找不到檔案")
        else:
            # 生圖失敗的房間可以沒有圖，但一定要在已知限制裡交代，否則屋主以為你漏做。
            check(f"「{n}」無圖但已在限制中說明", n in limits_text,
                  f"「{n}」沒有 hero_image，appendix.limits 也沒提到，屋主會以為漏了這個空間")
        look = str(r.get("look", "")).strip()
        check(f"「{n}」寫了空間樣貌", len(look) >= 40,
              "look 太短或缺漏，屋主看不出這個空間長什麼樣")
        # 型號倒進敘述裡是這份文件最常見的毛病：屋主讀到第三個破折號就放棄了。
        hit = MODEL_NUMBER.search(PARENS.sub("", look))
        check(f"「{n}」敘述沒有家具型號", not hit,
              f"look 裡出現「{hit.group(0)[:32] if hit else ''}」——型號與品牌留在 specs，"
              "敘述只用通用中文名（床、衣櫃、餐桌）")
        check(f"「{n}」至少有一條設計理由", len(r.get("rationale", [])) >= 1,
              "rationale 是空的，屋主看不出為什麼這樣設計")
        check(f"「{n}」有生活場景句", bool(r.get("scene_line")),
              "缺 scene_line，整段會變成規格說明而不是提案", level="WARN")
        check(f"「{n}」有關鍵配置規格", len(r.get("specs", [])) >= 1,
              "沒有 specs，屋主無從核對家具與尺寸", level="WARN")
        seen, dup = set(), []
        for s in r.get("specs", []):
            key = (str(s.get("label")), str(s.get("value")))
            if key in seen:
                dup.append(str(s.get("label"))[:20])
            seen.add(key)
        check(f"「{n}」規格表沒有重複列", not dup,
              f"同款同尺寸要合併成一列加數量（重複：{'; '.join(dup[:3])}）")

    out = [str(r.get("name", "")) for r in rooms
           if any(w in str(r.get("name", "")) for w in OUT_OF_SCOPE_ROOMS)]
    check("沒有排出範圍外的空間", not out,
          f"「{'」「'.join(out)}」不在軟裝提案範圍，不排篇章；"
          "在 overview.intro 交代不列的原因即可")


def check_process_talk(content):
    """屋主付錢買的是空間，不是製程說明。

    「位置由幾何引擎計算與驗證：不重疊、留走道、不擋門窗」這種句子讀起來像
    系統日誌。家具放得下是我們的義務，不是設計理由。
    """
    hits = []
    for path, text in walk_strings(content):
        if path.startswith("appendix"):  # 已知限制本來就要講清楚缺什麼
            continue
        for w in PROCESS_WORDS:
            if w in text:
                hits.append(f"{path}: 「{w}」")
    check("沒有製程說明混進文案", not hits,
          "把它換成空間本身的事實或屋主的需求：" + "; ".join(hits[:8]))


def check_repetition(content):
    """同一句話在八個空間各寫一次，屋主翻到第三頁就開始跳著看。"""
    sentences = {}
    for room in content.get("rooms", []):
        for field in ("look", "scene_line"):
            for sent in re.split(r"[。！？]", str(room.get(field, ""))):
                sent = sent.strip()
                if len(sent) >= 12:
                    sentences.setdefault(sent, []).append(str(room.get("name", "")))
    dup = {s: names for s, names in sentences.items() if len(names) > 1}
    check("各空間的敘述沒有整句重複", not dup,
          "全案共用的事實在總論與色彩章講一次就好："
          + "; ".join(f"「{s[:20]}…」出現在 {'、'.join(n)}" for s, n in list(dup.items())[:3]))


def check_statement(content):
    """設計總論的 pillars 是後續每一章的摘要，不是三個抽象主張。"""
    st = content.get("statement")
    if not st:
        return
    chapter_names = {"全案速覽", "色彩與材質", "燈光與氛圍", "接下來"} | {
        str(r.get("name", "")) for r in content.get("rooms", [])
    }
    titles = [str(p.get("title", "")) for p in st.get("pillars") or []]
    matched = [t for t in titles if t in chapter_names]
    check("設計總論是後續章節的摘要", titles and len(matched) >= len(titles) - 1,
          f"pillars 的 title 要對上章名（目前 {len(matched)}/{len(titles)} 條對得上）；"
          "抽象主張換哪個案子都成立，屋主看不出這份文件裡有什麼")


# 建案廣告腔與 AI 高頻詞。抓得到的只是冰山一角，還是要自己讀一次。
# 完整清單與改寫示範見 references/writing-rules.md。
AD_WORDS = [
    "奢華", "頂級", "極致", "尊榮", "匠心", "精雕細琢", "絕美", "令人讚嘆",
    "坐落於", "坐落在", "療癒", "氛圍感", "質感生活", "大器", "必訪",
    "精心打造", "用心打造", "獨具", "絕佳",
]
AI_WORDS = [
    "此外", "再者", "值得一提的是", "至關重要", "關鍵性的", "深入探討",
    "進而", "從而", "藉由", "賦予", "型塑", "勾勒", "串聯", "挹注", "饒富",
    "不可磨滅", "雋永", "奠定了", "揭開序幕",
]
# 句尾掛修飾語的假深度：「，營造出…」「，展現了…」
TAIL_PATTERNS = [
    r"[，,]\s*(?:營造|展現|彰顯|體現|象徵|詮釋|增添|型塑|勾勒|賦予)[出了著]?[^。；\n]{0,20}[。；]",
    r"不只是[^。；\n]{0,25}(?:更是|而是)",
    r"不僅[^。；\n]{0,25}(?:更是|而是|也是)",
]


def check_ai_tells(content):
    """抓建案廣告腔與 AI 寫作痕跡。

    室內設計文案是這類語病的重災區，因為訓練資料裡塞滿了建案文宣。
    這些句子不會讓文件出錯，但會讓屋主覺得是機器寫的——而那正是這份文件要避免的。
    """
    ad_hits, ai_hits, tail_hits = [], [], []
    for path, text in walk_strings(content):
        for w in AD_WORDS:
            if w in text:
                ad_hits.append(f"{path}: 「{w}」")
        for w in AI_WORDS:
            if w in text:
                ai_hits.append(f"{path}: 「{w}」")
        for pat in TAIL_PATTERNS:
            for m in re.finditer(pat, text):
                tail_hits.append(f"{path}: 「{m.group(0)[:24]}」")

    check("沒有建案廣告腔", not ad_hits,
          "刪掉或換成具體的材質與尺寸：" + "; ".join(ad_hits[:8]))
    check("沒有 AI 高頻詞", not ai_hits,
          "多半可以直接刪或換成白話：" + "; ".join(ai_hits[:8]), level="WARN")
    check("句尾沒有掛空的修飾語", not tail_hits,
          "把那串刪掉看資訊量有沒有變少，沒有就是贅字：" + "; ".join(tail_hits[:6]))


def check_rhythm(content):
    """檢查空間篇章有沒有淪為同一個模子。"""
    rooms = content.get("rooms", [])
    heads = [str(r.get("look", ""))[:6] for r in rooms if r.get("look")]
    dup = len(heads) - len(set(heads))
    check("空間敘述沒有用同一個句型開頭", dup == 0,
          "有空間的 look 開頭前六字相同，讀者翻到第三個就會開始跳著看", level="WARN")

    for r in rooms:
        look = str(r.get("look", ""))
        if not look:
            continue
        sents = [s for s in re.split(r"[。！？]", look) if s.strip()]
        if len(sents) >= 3:
            lens = [len(s) for s in sents]
            if max(lens) - min(lens) <= 4:
                check(f"「{r.get('name')}」的句子長度有變化", False,
                      "三句以上長度幾乎一樣，讀起來像機器；刻意混一個短句進去",
                      level="WARN")


def check_placeholders(content):
    hits = []
    for path, text in walk_strings(content):
        for ph in PLACEHOLDERS:
            if ph.lower() in text.lower():
                hits.append(f"{path}: …{ph}…")
    check("沒有佔位文字", not hits, "; ".join(hits[:6]))


def check_numbers(content, data_path):
    """文案裡的尺寸與坪數，要能在原始資料裡找得到。"""
    if not data_path:
        check("數字溯源", True, "未提供 --data，略過", level="INFO")
        return
    raw = Path(data_path).read_text(encoding="utf-8")
    raw_nums = set(re.findall(r"\d+(?:\.\d+)?", raw))
    # 尺寸只是規格的一種。色溫、照度、演色性、比例同樣是屋主會拿去對照的數字，
    # 憑印象寫一個 3000K 跟憑印象寫一個尺寸一樣傷信任。
    pattern = re.compile(
        r"(\d+(?:\.\d+)?)\s*(mm|cm|m²|m2|m³|m3|坪|米|公分|公尺|K\b|lux|Lux|Ra|%|成)"
    )
    unsourced = []
    for path, text in walk_strings(content):
        for num, unit in pattern.findall(text):
            variants = {num, num.rstrip("0").rstrip("."), str(int(float(num)))
                        if float(num).is_integer() else num}
            # 公分/公尺互換：1 m 可能在原始資料裡是 100 或 1000
            try:
                f = float(num)
                variants |= {str(int(f * 10)), str(int(f * 100)), str(int(f / 10)), str(int(f / 100))}
            except (ValueError, OverflowError):
                pass
            if not (variants & raw_nums):
                unsourced.append(f"{path}: {num}{unit}")
    check("文案數字可溯源", not unsourced,
          "以下數字在原始資料找不到，出檔前請人工確認：" + "; ".join(unsourced[:8]),
          level="WARN")


def check_pdf(pdf_path, content):
    if not pdf_path:
        check("PDF 產出", True, "未提供 --pdf，略過", level="INFO")
        return
    p = Path(pdf_path)
    check("PDF 檔案存在", p.exists(), str(p))
    if not p.exists():
        return
    lazy = re.search(r"^(output|untitled|document|test|final|未命名)", p.stem, re.I)
    check("PDF 檔名可辨識", not lazy and bool(re.search(r"v\d|版", p.stem)),
          f"建議 <案名>_室內設計提案_<版本>.pdf，屋主的下載資料夾裡要認得出來（現為 {p.name}）",
          level="WARN")
    size_mb = p.stat().st_size / 1_048_576
    check("PDF 大小適合寄送", size_mb <= 20,
          f"{size_mb:.1f} MB，超過 20 MB 常被信箱擋下；把 PNG 轉成品質 85 的 JPG 再重跑",
          level="WARN")
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(p))
        pages = len(reader.pages)
        expected = 3 + len(content.get("rooms", []))
        check("PDF 頁數合理", pages >= expected - 1,
              f"實際 {pages} 頁，預期至少 {expected - 1} 頁（可能有區塊沒被排進去）")
        text = "".join((pg.extract_text() or "") for pg in reader.pages[:6])
        check("中文正常嵌入（無豆腐字）", "□" not in text and "�" not in text,
              "偵測到方框或替代字元，字型可能沒嵌進去")
        check("PDF 內含實際文字", len(text.strip()) > 100,
              "抽不到文字，可能整頁被當成圖片", level="WARN")
    except ImportError:
        check("PDF 內容檢查", True, "pypdf 未安裝，略過內容檢查", level="INFO")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("content")
    ap.add_argument("--pdf")
    ap.add_argument("--data")
    ap.add_argument("--base-dir", default=".")
    args = ap.parse_args()

    content = json.loads(Path(args.content).read_text(encoding="utf-8"))
    base_dir = Path(args.base_dir).resolve()

    check_meta(content)
    check_rooms(content, base_dir)
    check_statement(content)
    check_placeholders(content)
    check_ai_tells(content)
    check_process_talk(content)
    check_repetition(content)
    check_rhythm(content)
    check_numbers(content, args.data)
    check_pdf(args.pdf, content)

    fails = [r for r in results if not r["ok"] and r["level"] == "FAIL"]
    warns = [r for r in results if not r["ok"] and r["level"] == "WARN"]
    passes = [r for r in results if r["ok"]]

    print(f"\n交付前檢查：{len(passes)} 通過 / {len(warns)} 提醒 / {len(fails)} 未過\n")
    for r in results:
        if r["ok"]:
            continue
        mark = "✗" if r["level"] == "FAIL" else "!"
        print(f" {mark} [{r['level']}] {r['name']}")
        if r["detail"]:
            print(f"     {r['detail']}")
    if not fails and not warns:
        print(" ✓ 全部通過，可以交付。")

    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()

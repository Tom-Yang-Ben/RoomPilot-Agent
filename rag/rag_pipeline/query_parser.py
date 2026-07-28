"""自然語言需求 → 受控詞彙的結構化檢索條件（Claude Haiku 4.5 structured outputs）。

設計要點（見 docs/query_parser_spec.md）：
  - 風格/氛圍詞表從 taxonomy_v2.json（六風格色卡）動態注入，改詞表不用改 prompt
  - 類別用 18 個群組（category_groups.json），不讓 LLM 從 64 個細類挑
  - 單物件 = items 長度 1，多物件走同一條程式路徑
  - semantic_query 寫成與 embedded_text 相同句式（HyDE 併進同一次呼叫）

用法：
    .venv-rag/bin/python rag_pipeline/query_parser.py "日式侘寂感、預算兩萬內的客廳沙發"
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import anthropic

PROJ = Path(__file__).resolve().parent.parent
TAXONOMY = PROJ / "vlm_annotation" / "taxonomy_v2.json"
GROUPS = PROJ / "rag_pipeline" / "category_groups.json"
KEY_FILE = PROJ / ".anthropic_key"

MODEL = "claude-haiku-4-5"
MAX_ITEMS = 6

ROOM_TYPES = [
    "living_room", "bedroom", "dining_room", "study",
    "entryway", "kids_room", "outdoor", "bathroom", "kitchen",
]
PATTERNS = ["素色", "木紋", "幾何", "花紋"]
# 24 個氛圍詞，與 taxonomy 標註產出的實際詞表一致
MOODS = [
    "溫馨", "俐落", "沉穩", "寧靜", "自然", "質樸", "優雅", "大器",
    "復古", "懷舊", "放鬆", "明亮", "活潑", "浪漫", "溫潤", "率性",
    "療癒", "粗獷", "精緻", "純粹", "繽紛", "都會", "靜謐", "高級",
]


def load_vocab() -> tuple:
    tax = json.loads(TAXONOMY.read_text(encoding="utf-8"))
    groups = json.loads(GROUPS.read_text(encoding="utf-8"))
    return tax["styles"], groups


def nullable(inner: dict) -> dict:
    """可為 null 的欄位。

    不能寫成 {"type": ["string", "null"], "enum": [...]} —— structured outputs 的
    schema 驗證會判定 enum 值與宣告型別不符（400）。用 anyOf 包一層才過。
    """
    return {"anyOf": [inner, {"type": "null"}]}


def build_schema(style_keys: list, group_keys: list) -> dict:
    """structured outputs 的 JSON schema。

    注意 API 對 schema 的限制：所有 object 必須 additionalProperties=false，
    且不支援 minLength / maxItems 等數量約束 —— 上限改在 prompt 講、程式端再裁切。
    """
    item = {
        "type": "object",
        "properties": {
            "item_id": {"type": "string", "description": "英文 slug，如 main_sofa"},
            "label_zh": {"type": "string", "description": "顯示用中文，如「主沙發」"},
            "category_group": nullable({"type": "string", "enum": group_keys}),
            "quantity": {"type": "integer", "description": "件數，預設 1"},
            "priority": {"type": "string", "enum": ["must_have", "nice_to_have"]},
            "is_inferred": {"type": "boolean", "description": "true = 使用者沒明講，系統推論的品項"},
            "semantic_query": {"type": "string", "description": "此品項專屬的 embedded_text 句式描述"},
            "styles": {"type": "array", "items": {"type": "string", "enum": style_keys}},
            "price_max": nullable({"type": "integer"}),
            "max_width_cm": nullable({"type": "number"}),
            "max_height_cm": nullable({"type": "number"}),
            "role": nullable({"type": "string", "enum": ["anchor", "accent"]}),
            "size_hint": nullable({"type": "string", "enum": ["S", "M", "L"]}),
        },
        "required": [
            "item_id", "label_zh", "category_group", "quantity", "priority",
            "is_inferred", "semantic_query", "styles",
            "price_max", "max_width_cm", "max_height_cm", "role", "size_hint",
        ],
        "additionalProperties": False,
    }

    return {
        "type": "object",
        "properties": {
            "room_type": nullable({"type": "string", "enum": ROOM_TYPES}),
            "styles": {"type": "array", "items": {"type": "string", "enum": style_keys}},
            "moods": {"type": "array", "items": {"type": "string", "enum": MOODS}},
            "pattern": nullable({"type": "string", "enum": PATTERNS}),
            "color_hint": nullable({"type": "string"}),
            "material_hint": nullable({"type": "string"}),
            "price_level": nullable({"type": "string", "enum": ["budget", "mid", "premium"]}),
            "budget_total": nullable({"type": "integer"}),
            "is_set": {"type": "boolean"},
            "items": {"type": "array", "items": item},
            "confidence": {"type": "number"},
            "needs_clarification": {"type": "boolean"},
            "clarify_question": {"type": ["string", "null"]},
            "clarify_options": {"type": "array", "items": {"type": "string"}},
            "reasoning": {"type": "string"},
        },
        "required": [
            "room_type", "styles", "moods", "pattern", "color_hint", "material_hint",
            "price_level", "budget_total", "is_set", "items", "confidence",
            "needs_clarification", "clarify_question", "clarify_options", "reasoning",
        ],
        "additionalProperties": False,
    }


def build_system_prompt(styles: dict, groups: dict) -> str:
    style_lines = "\n".join(f"{k}（{v['zh']}）：{v['definition']}" for k, v in styles.items())
    group_lines = "\n".join(
        f"{k}（{v['label_zh']}）：{'、'.join(v['categories'][:6])}" for k, v in groups["groups"].items()
    )
    room_sets = "\n".join(
        f"  {r}: {' + '.join(g)}" for r, g in groups["room_default_sets"].items()
    )

    return f"""你是室內設計家具檢索系統的需求解析器。把使用者的自然語言需求，轉成結構化檢索條件。

## 風格詞彙（只能從中挑選，最多 2 個）
{style_lines}

## 氛圍詞彙（只能從中挑選，最多 3 個）
{" ".join(MOODS)}

## 房型（room_type）
{" ".join(ROOM_TYPES)}

## 類別群組（category_group）
{group_lines}

## 硬規則
1. 只能使用上列受控詞彙。使用者的口語要對映到最接近的詞：
   侘寂／無印風／禪風／和風→japanese、北歐／斯堪地那維亞→scandinavian、
   性冷淡風／極簡／黑白灰→modern_minimal、loft／水泥／黑鐵→industrial、
   奶油風／奶茶色／法式柔霧／柔霧感→cream、美式／鄉村／中古世紀／輕奢→american。
   每個風格各有 3 張色卡，使用者若提到色卡名稱（例如「自然木質」「侘寂自然」
   「黑白俐落」「奶茶木質」「黑鐵水泥」「鄉村溫馨」）也對映到所屬風格。
2. 使用者沒提到的欄位一律填 null 或空陣列，不要臆造。沒說房間就不要填 room_type。
3. 金額只在使用者給出具體數字時填 price_max / budget_total；
   說「便宜」「平價」「高級一點」時**只**填 price_level（budget / mid / premium）。
   兩者互斥：已經有具體金額就把 price_level 留 null。
4. max_width_cm / max_height_cm 是**空間限制**，只有使用者明講尺寸時才填
   （例如「牆面只有 180 公分」「高度不能超過 200」）。
   ★ 絕對不要用常識推測家具「應該多大」——這是硬過濾條件，猜錯會直接濾掉正確結果。
   使用者沒講尺寸就填 null。size_hint 同理，只在使用者說「大一點」「小巧」時才填。
5. 需求太模糊而無法檢索時，needs_clarification = true，
   在 clarify_question 問一個最關鍵的問題，並在 clarify_options 給 2-4 個快速選項。

## 何時展開成多個品項
使用者說「一整套」「配一組」「整個客廳」「幫我規劃」，或一次列舉多件家具時，
展開成多個品項（最多 {MAX_ITEMS} 件），並設定 is_set = true。
使用者沒明講、但你認為該補上的品項，一律標 is_inferred = true。

各房型的典型組合（供推論參考，非強制）：
{room_sets}

quantity 只在使用者明說數量、或常識上必然成組（餐椅通常 4 張）時才 > 1。
單一物件需求時，items 只放 1 個元素、is_set = false。

★ items 絕對不可以是空陣列，至少要有 1 個元素。
使用者只講了風格或房間、沒指定家具類型時（例如「臥室想弄成工業風」），
放 1 個 category_group = null 的品項，semantic_query 描述整體風格氛圍，
讓系統跨類別回傳最搭的物件；此時仍可設 needs_clarification 追問想先買哪一件。
每個品項的 semantic_query 都要獨立撰寫，不可共用同一段文字。

## semantic_query 的寫法（最重要）
資料庫裡每件家具的檢索文本長這樣：
  「名稱：…。類別：沙發。物件類型：三人座布沙發。顏色：米色、淺灰。材質：亞麻布、木材。
    適用空間：客廳。風格：日式(japanese)。氛圍：寧靜、自然。表面圖樣：素色。
    造型：直線造型。描述：（80-120 字外觀描述）。特徵：…。關鍵字：…」

請把 semantic_query 也寫成**同樣的句式**，並在「描述」段落補寫一段你想像中
理想物件的外觀（30-50 字，精簡但具體），即使使用者沒講到那麼細。
不要只是複述使用者的句子。

## 其他欄位
- styles / moods / pattern 是軟性條件（只影響排序），room_type / category_group /
  price 是硬過濾條件，填錯會直接濾掉正確結果，請保守。
- role：主要大型家具（沙發、床、餐桌、書桌）填 anchor，配件填 accent，不確定填 null。
- confidence：0-1，反映你對這次解析的把握度。
- reasoning：一句話說明你的判斷依據。"""


def get_client() -> anthropic.Anthropic:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key and KEY_FILE.exists():
        key = KEY_FILE.read_text(encoding="utf-8").strip()
    return anthropic.Anthropic(api_key=key) if key else anthropic.Anthropic()


def parse_query(text: str, client: anthropic.Anthropic | None = None) -> dict:
    styles, groups = load_vocab()
    client = client or get_client()

    response = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        system=[
            {
                "type": "text",
                "text": build_system_prompt(styles, groups),
                "cache_control": {"type": "ephemeral"},  # 詞表固定，快取住省成本
            }
        ],
        output_config={"format": {"type": "json_schema", "schema": build_schema(list(styles), list(groups["groups"]))}},
        messages=[{"role": "user", "content": text}],
    )

    if response.stop_reason == "refusal":
        raise RuntimeError(f"模型拒答：{response.stop_details}")

    payload = json.loads(next(b.text for b in response.content if b.type == "text"))

    # schema 不支援 maxItems，上限在此裁切
    payload["styles"] = payload.get("styles", [])[:2]
    payload["moods"] = payload.get("moods", [])[:3]
    payload["items"] = payload.get("items", [])[:MAX_ITEMS]
    payload["clarify_options"] = payload.get("clarify_options", [])[:4]
    for item in payload["items"]:
        item["quantity"] = max(1, int(item.get("quantity") or 1))
        item["styles"] = (item.get("styles") or [])[:2]

    payload["_usage"] = {
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        "cache_read": getattr(response.usage, "cache_read_input_tokens", 0),
    }
    return payload


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    result = parse_query(" ".join(sys.argv[1:]))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

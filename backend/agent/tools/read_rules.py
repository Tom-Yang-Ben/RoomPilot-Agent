"""讀規則/需求 tool：載入規則文件（硬規則說明＋語意軟潛規則）。

規則文件分兩節：

- 硬規則：碰撞、淨空、超界、開門迴轉——只由 ``backend/engine/`` 判定，
  這裡僅保留說明文字，agent 不得重做幾何判斷。
- 軟潛規則：語意類擺放潛規則（沙發面向電視、床不正對門、風格一致…），
  Furniture Agent 挑擺時參考、Validation Agent 事後檢查；違反僅警告不阻擋。
"""
from __future__ import annotations

from ..documents import RulesDoc, SoftRule
from .base import ToolContract

DEFAULT_SOFT_RULES: list[SoftRule] = [
    SoftRule(
        rule_id="sofa_faces_tv",
        description="沙發正面朝向電視櫃或媒體牆，形成客廳視聽焦點。",
        applies_to=["sofa", "media"],
    ),
    SoftRule(
        rule_id="bed_head_against_wall",
        description="床頭靠牆擺放，避免床頭懸空。",
        applies_to=["bed"],
    ),
    SoftRule(
        rule_id="bed_not_facing_door",
        description="床避免正對房門，兼顧隱私與臥室安定感。",
        applies_to=["bed"],
    ),
    SoftRule(
        rule_id="nightstand_beside_bed",
        description="床側保留床頭櫃或邊几位置，方便就寢動線。",
        applies_to=["side_table", "bed"],
    ),
    SoftRule(
        rule_id="rug_anchored",
        description="地毯壓在主家具（沙發或床）下方，不單獨漂浮在空地。",
        applies_to=["rug"],
    ),
    SoftRule(
        rule_id="coffee_table_serves_sofa",
        description="茶几緊鄰沙發正面，距離保持可及性。",
        applies_to=["coffee_table", "sofa"],
    ),
    SoftRule(
        rule_id="desk_near_light",
        description="書桌靠窗或靠近光源，利於工作照明。",
        applies_to=["desk"],
    ),
    SoftRule(
        rule_id="dining_near_kitchen",
        description="餐桌靠近廚房與上菜動線。",
        applies_to=["dining_table"],
    ),
    SoftRule(
        rule_id="style_consistency",
        description="全室家具風格與問卷選定風格一致，不混搭衝突風格。",
        applies_to=["*"],
    ),
    SoftRule(
        rule_id="palette_harmony",
        description="全室主色不超過三種，並與使用者選定色卡協調。",
        applies_to=["*"],
    ),
]


class ReadRulesTool:
    contract = ToolContract(
        name="read_rules",
        description="載入規則文件：硬規則說明（engine 判定）＋語意軟潛規則清單。",
        input_schema={
            "type": "object",
            "properties": {"rules_json": {"type": ["object", "null"]}},
        },
        output_schema={"type": "object", "description": "RulesDoc dict"},
    )

    def run(self, rules_json: dict | None = None) -> RulesDoc:
        if rules_json:
            doc = RulesDoc.from_dict(rules_json)
            if doc.soft_rules:
                return doc
        return RulesDoc(soft_rules=list(DEFAULT_SOFT_RULES))

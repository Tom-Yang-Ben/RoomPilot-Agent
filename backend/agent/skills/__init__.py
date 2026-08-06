"""Agent skills：每個 skill＝一個資料夾＋一份 ``SKILL.md``＋Python 流程。

``SKILL.md``（agent 架構慣例，對齊 repo `.agents/skills/` 模式）是宣告層，
也是提示詞與輸出 schema 的唯一來源：frontmatter（name / description /
agent / tools）＋「## 提示詞：<key>」＋「## 輸出 schema：<key>」＋流程說明。
調整提示詞不需改程式；``base.load_skill_doc()`` 於匯入期解析並驗證。

每個 skill 都支援「LLM 不可用時 deterministic fallback」，流程不因離線而
中斷；LLM 的職權限於語意決策（需求歸納、選件、修復方案、敘事），
幾何一律交給 engine、成圖一律交給生圖模型。

例外：``interior_design_principles/`` 與 ``interior_designer/`` 是知識型
skill（foundry-skills 英文原文），只有 SKILL.md 宣告層、無流程層，
由 ``tools.design_knowledge`` 節錄供選件提示與生圖措辭引用。
"""
from .base import SkillDoc, SkillSpec, ask_llm_json, load_skill_doc
from .editpic import STAGE_EDIT, EditPicSkill
from .furniture import STRATEGIES, FurnitureSkill, Strategy
from .genpic import STAGE_FULL, STAGE_PALETTE, GenPicSkill
from .report import ReportSkill
from .requirements import RequirementSkill
from .validation import ValidationSkill

__all__ = [
    "SkillDoc",
    "SkillSpec",
    "ask_llm_json",
    "load_skill_doc",
    "RequirementSkill",
    "FurnitureSkill",
    "Strategy",
    "STRATEGIES",
    "ValidationSkill",
    "GenPicSkill",
    "EditPicSkill",
    "ReportSkill",
    "STAGE_PALETTE",
    "STAGE_FULL",
    "STAGE_EDIT",
]

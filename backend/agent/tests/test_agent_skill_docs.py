"""SKILL.md 宣告層：每個 skill 資料夾都要有合法的 SKILL.md。"""
from pathlib import Path

import backend.agent.skills as skills_pkg
from backend.agent.skills import load_skill_doc
from backend.agent.skills.editpic import REFINE_SPEC
from backend.agent.skills.furniture import REPAIR_SPEC, SELECT_SPEC
from backend.agent.skills.requirements import SPEC as REQUIREMENT_SPEC

SKILL_DIRS = ["requirements", "furniture", "validation", "genpic", "editpic", "report"]


def test_every_skill_folder_has_valid_skill_md():
    base = Path(skills_pkg.__file__).parent
    for name in SKILL_DIRS:
        doc = load_skill_doc(base / name)
        assert doc.name, f"{name}/SKILL.md 缺 name"
        assert doc.description, f"{name}/SKILL.md 缺 description"
        assert doc.agent, f"{name}/SKILL.md 缺 agent 歸屬"
        # 每個提示詞段落的 schema（若有）都必須是合法 JSON 且成對
        for key in doc.schemas:
            assert key in doc.prompts, f"{name}/SKILL.md 的 schema「{key}」沒有對應提示詞"


def test_specs_are_loaded_from_skill_md():
    # 提示詞與 schema 的唯一來源是 SKILL.md；抽查關鍵欄位確認載入正確。
    assert "三分流" not in REQUIREMENT_SPEC.system_prompt  # 提示詞本文，不是流程說明
    assert "appliances" in REQUIREMENT_SPEC.system_prompt
    assert REQUIREMENT_SPEC.output_schema["required"] == ["hard", "soft", "appliances"]

    assert "白名單" in SELECT_SPEC.system_prompt
    assert "selections" in SELECT_SPEC.output_schema["properties"]
    assert "swap" in REPAIR_SPEC.system_prompt
    assert REPAIR_SPEC.output_schema["required"] == ["actions"]
    assert REFINE_SPEC.output_schema["required"] == ["instruction"]


def test_genpic_skill_md_declares_no_llm_prompts():
    base = Path(skills_pkg.__file__).parent
    doc = load_skill_doc(base / "genpic")
    assert doc.prompts == {}  # 生圖 skill 為 deterministic 組稿，無文字 LLM

"""Skill 基礎：skill＝一個資料夾＋一份 ``SKILL.md``＋Python 流程。

agent 架構慣例（對齊 repo `.agents/skills/` 的模式）：

- ``SKILL.md`` 是宣告層，也是**提示詞與輸出 schema 的唯一來源**：
  frontmatter（name / description / agent）＋若干「## 提示詞：<key>」段落
  ＋對應「## 輸出 schema：<key>」的 ```json 區塊＋流程說明。
  調整提示詞或 schema 只需改 markdown，不動程式。
- ``__init__.py`` 是流程層：用 ``load_skill_doc()`` 載入宣告，呼叫 LLM 做
  語意決策；LLM 不可用（無金鑰、逾時、輸出無法解析）時一律走
  deterministic fallback，流程不中斷——沿用 repo「OpenRouter-first、
  安全回退」慣例。
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from ..llm import LLMError, LLMGateway, parse_json_block


@dataclass(frozen=True)
class SkillSpec:
    name: str
    description: str
    system_prompt: str
    output_schema: dict = field(default_factory=dict)


@dataclass(frozen=True)
class SkillDoc:
    """一份 SKILL.md 解析後的內容。"""

    name: str
    description: str
    agent: str
    prompts: dict[str, str]
    schemas: dict[str, dict]
    path: str

    def spec(self, key: str = "main") -> SkillSpec:
        if key not in self.prompts:
            raise KeyError(f"{self.path} 缺少「## 提示詞：{key}」段落")
        return SkillSpec(
            name=self.name if key == "main" else f"{self.name}:{key}",
            description=self.description,
            system_prompt=self.prompts[key],
            output_schema=self.schemas.get(key, {}),
        )


_SCHEMA_FENCE = re.compile(r"```json\s*(.*?)```", re.S)


def load_skill_doc(skill_dir: str | Path) -> SkillDoc:
    """解析 ``<skill_dir>/SKILL.md``。格式錯誤時直接丟例外（匯入期即發現）。"""
    md_path = Path(skill_dir) / "SKILL.md"
    text = md_path.read_text(encoding="utf-8")

    meta = {"name": "", "description": "", "agent": ""}
    body = text
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            for line in text[3:end].splitlines():
                if ":" in line:
                    key, value = line.split(":", 1)
                    key = key.strip()
                    if key in meta:
                        meta[key] = value.strip()
            body = text[end + 4 :]

    prompts: dict[str, str] = {}
    schemas: dict[str, dict] = {}
    for section in re.split(r"^##\s+", body, flags=re.M)[1:]:
        title, _, content = section.partition("\n")
        title = title.strip()
        if title.startswith("提示詞："):
            prompts[title.removeprefix("提示詞：").strip()] = content.strip()
        elif title.startswith("輸出 schema："):
            key = title.removeprefix("輸出 schema：").strip()
            fence = _SCHEMA_FENCE.search(content)
            if fence:
                schemas[key] = json.loads(fence.group(1))
    if not meta["name"]:
        raise ValueError(f"{md_path} frontmatter 缺少 name")
    return SkillDoc(
        name=meta["name"],
        description=meta["description"],
        agent=meta["agent"],
        prompts=prompts,
        schemas=schemas,
        path=str(md_path),
    )


def ask_llm_json(
    gateway: LLMGateway | None,
    spec: SkillSpec,
    user_prompt: str,
    *,
    required: tuple[str, ...] = (),
    retries: int = 1,
    temperature: float = 0.3,
    model: str | None = None,
    reasoning: dict | None = None,
) -> dict | None:
    """呼叫 LLM 並要求 JSON 輸出；回傳 ``None`` 表示改走 deterministic fallback。

    重試次數由程式固定（預設多一次），不交給 LLM 自律。
    ``model``／``reasoning`` 只在有指定時往下傳，避免打到不接這些參數的假 gateway。
    """
    if gateway is None or not getattr(gateway, "available", True):
        return None
    system = spec.system_prompt
    if spec.output_schema:
        system += "\n\n請只輸出一個符合以下 JSON schema 的 JSON 物件，不要多餘文字：\n"
        system += json.dumps(spec.output_schema, ensure_ascii=False)
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user_prompt},
    ]
    extra: dict = {}
    if model:
        extra["model"] = model
    if reasoning is not None:
        extra["reasoning"] = reasoning
    for _attempt in range(retries + 1):
        try:
            text = gateway.chat(
                messages, force_json=True, temperature=temperature, **extra
            )
            data = parse_json_block(text)
            missing = [key for key in required if key not in data]
            if missing:
                raise LLMError(f"輸出缺少欄位：{missing}")
            return data
        except LLMError as exc:
            messages.append(
                {
                    "role": "user",
                    "content": f"上一次輸出無法使用（{exc.reason}）。請重新只輸出符合 schema 的 JSON。",
                }
            )
    return None

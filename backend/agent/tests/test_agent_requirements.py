"""需求整理 skill：三分流 fallback 與家電契約防線。"""
import json

from backend.agent.documents import LayoutDoc, LayoutRoom
from backend.agent.skills.requirements import RequirementSkill

from .conftest import FakeChatGateway


def _layout() -> LayoutDoc:
    return LayoutDoc(
        rooms=[
            LayoutRoom(room_id="living", name="客廳", width_cm=420, depth_cm=360),
            LayoutRoom(room_id="bedroom", name="主臥", width_cm=360, depth_cm=300),
        ]
    )


def test_fallback_three_way_split(questionnaire):
    doc = RequirementSkill(gateway=None).run(questionnaire, _layout())

    hard_texts = [item.text for item in doc.hard]
    appliance_texts = [item.text for item in doc.appliances]
    assert "三人沙發" in hard_texts and "雙人床" in hard_texts
    # 家電只進 appliances，不進 hard
    assert "壁掛冷氣" in appliance_texts and "除濕機" in appliance_texts
    assert all("冷氣" not in text for text in hard_texts)
    # category 對照
    by_text = {item.text: item for item in doc.hard}
    assert by_text["三人沙發"].category == "sofa"
    assert by_text["雙人床"].category == "bed"
    assert by_text["雙人床"].room_id == "bedroom"
    # 軟偏好含房間備註與風格
    soft_texts = [item.text for item in doc.soft]
    assert any("瑜伽" in text for text in soft_texts)
    assert any("日式無印" in text for text in soft_texts)
    # req_id 分流編號
    assert doc.hard[0].req_id.startswith("H")
    assert doc.appliances[0].req_id.startswith("A")


def test_llm_appliance_misclassification_is_corrected(questionnaire):
    """LLM 把電視、冷氣放進 hard 時，契約防線必須把它們移回 appliances。"""
    llm_json = json.dumps(
        {
            "hard": [
                {"text": "55 吋電視", "room_id": "living", "category": "media"},
                {"text": "壁掛冷氣", "room_id": "living", "category": None},
                {"text": "雙人床", "room_id": "bedroom", "category": "bed"},
                {"text": "掛畫", "room_id": "living", "category": "不存在的類別"},
            ],
            "soft": [{"text": "溫暖色調"}],
            "appliances": [],
            "styles": ["日式無印"],
            "notes": "",
        },
        ensure_ascii=False,
    )
    doc = RequirementSkill(FakeChatGateway([llm_json])).run(questionnaire, _layout())

    hard_texts = [item.text for item in doc.hard]
    appliance_texts = [item.text for item in doc.appliances]
    assert "55 吋電視" in appliance_texts and "壁掛冷氣" in appliance_texts
    assert "55 吋電視" not in hard_texts
    assert "雙人床" in hard_texts
    # 非法 category 會被清掉或改為對照表結果
    guessed = {item.text: item.category for item in doc.hard}
    assert guessed["掛畫"] is None

"""生圖提示詞的家具外觀描述（型錄／RAG 的 VLM description）與尺寸清除。"""
import pytest

from backend.agent.documents import LayoutRoom, RequirementDoc, SceneDoc
from backend.agent.tools.genpic_info import (
    GenPicInfoTool,
    furniture_lines,
    furniture_prompt_lines,
    strip_measurements,
    visual_description,
)

ROOM = LayoutRoom(room_id="living", name="客廳", width_cm=420, depth_cm=360)

SOFA_DESCRIPTION = (
    "此款沙發融合北歐極簡美學，淺灰色柔和布料包覆飽滿的靠背與扶手，線條簡潔俐落。"
    "四根原木色細長腿展現輕盈感，營造溫暖療癒的氛圍。"
    "適合現代居家、工作室或商業空間，散發寧靜優雅的質感。"
)


def _scene(**overrides) -> SceneDoc:
    row = {
        "id": "sofa_1",
        "name": "北歐布沙發",
        "type": "sofa",
        "material": "亞麻布",
        "description": SOFA_DESCRIPTION,
    }
    row.update(overrides)
    return SceneDoc(rooms={"living": {"placed": [row], "failed": []}})


def test_visual_description_drops_usage_sentences():
    text = visual_description(SOFA_DESCRIPTION)
    assert "淺灰色柔和布料" in text
    assert "適合現代居家" not in text
    # 只在句號邊界切，不留半句話
    assert text.endswith("。")


def test_visual_description_stops_at_char_budget():
    long_text = "。".join(f"第{index}句外觀敘述，描述材質與顏色細節" for index in range(10))
    text = visual_description(long_text)
    assert len(text) <= 90 + len("第0句外觀敘述，描述材質與顏色細節") + 1
    assert "第0句" in text and "第9句" not in text


def test_visual_description_empty_when_no_source():
    assert visual_description(None) == ""
    assert visual_description("") == ""
    assert visual_description("適合客廳使用。") == ""


def test_prompt_lines_carry_description_labels_stay_short():
    scene = _scene()
    assert furniture_lines(scene, ROOM) == ["北歐布沙發（sofa，亞麻布）"]
    line = furniture_prompt_lines(scene, ROOM)[0]
    assert line.startswith("北歐布沙發（sofa，亞麻布）：")
    assert "淺灰色柔和布料" in line


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        # 型錄名稱的各種規格寫法（樣本取自 furniture_catalog_current）
        ("HAUGA 電視櫃，白色，206x46x54 公分", "HAUGA 電視櫃，白色"),
        ("Rivet 中世紀落地燈 148公分", "Rivet 中世紀落地燈"),
        ('Stone & Beam Rylee Bookcase 27.6"W x 76.8”H, Mixed Gray',
         "Stone & Beam Rylee Bookcase, Mixed Gray"),
        ("Movian Martin Bookcase - 35cm L x 77cm W x 185cm H",
         "Movian Martin Bookcase"),
        ("鉚釘幾何拼色地毯,5 英尺 x 8 英尺,藍色", "鉚釘幾何拼色地毯,藍色"),
        ("Ravenna 地毯，尺寸6'×9'", "Ravenna 地毯，尺寸"),
        ("BRIMNES TV storage combination - black 200x41x95",
         "BRIMNES TV storage combination - black"),
        ("陶瓷花盆 9.1 英寸（約 22.9 釐米）高", "陶瓷花盆 高"),
        # 型號、件數、座數不是尺寸，一律留著
        ("2L Lifestyle Hyder 木質書架，棕色", "2L Lifestyle Hyder 木質書架，棕色"),
        ("Rivet A8910 Dresser", "Rivet A8910 Dresser"),
        ("ROSSINI LOUNGE 2 SEATER MAXI", "ROSSINI LOUNGE 2 SEATER MAXI"),
        ("邊几，配置X型交叉支撐", "邊几，配置X型交叉支撐"),
    ],
)
def test_strip_measurements_removes_specs_but_keeps_model_codes(raw, expected):
    assert strip_measurements(raw) == expected


def test_prompt_drops_measurements_report_and_lock_keep_them():
    scene = _scene(name="HAUGA 電視櫃，白色，206x46x54 公分", type="tv-bench")
    # 清單與報告要看得到規格
    assert furniture_lines(scene, ROOM) == [
        "HAUGA 電視櫃，白色，206x46x54 公分（tv-bench，亞麻布）"
    ]
    # 提示詞不要數值：比例由 img2img 截圖鎖定，給數字只會讓模型重推比例
    prompt_line = furniture_prompt_lines(scene, ROOM)[0]
    assert prompt_line.startswith("HAUGA 電視櫃，白色（tv-bench，亞麻布）：")
    assert "206" not in prompt_line and "公分" not in prompt_line


def test_description_measurements_are_dropped_too():
    scene = _scene(description="深棕木質椅腿，座高 45 公分，米白色棉麻布料。")
    line = furniture_prompt_lines(scene, ROOM)[0]
    assert "米白色棉麻布料" in line
    assert "45" not in line and "公分" not in line


def test_placeholder_material_never_reaches_prompt():
    scene = _scene(material="GLB材質（未標示）")
    assert furniture_lines(scene, ROOM) == ["北歐布沙發（sofa）"]
    assert "GLB" not in furniture_prompt_lines(scene, ROOM)[0]


def test_genpic_prompt_includes_description_lock_manifest_does_not():
    out = GenPicInfoTool().run(
        RequirementDoc(), _scene(), ROOM, stage="full_render"
    )
    assert "淺灰色柔和布料" in out["prompt"]
    # 改圖鎖定清單維持短標籤，否則編輯指令會被描述灌爆
    assert out["lock_manifest"]["locked_furniture"] == ["北歐布沙發（sofa，亞麻布）"]


def test_missing_description_falls_back_to_label_only():
    scene = _scene(description="")
    assert furniture_prompt_lines(scene, ROOM) == ["北歐布沙發（sofa，亞麻布）"]

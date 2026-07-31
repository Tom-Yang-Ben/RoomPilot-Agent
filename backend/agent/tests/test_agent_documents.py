"""DocStore 與文件契約的基本行為。"""
from backend.agent.documents import (
    DocKey,
    DocStore,
    RequirementDoc,
    RequirementItem,
)


def test_docstore_checkpoint_undo_roundtrip():
    store = DocStore()
    store.set("a", {"value": 1})
    store.checkpoint("第一步")
    store.set("a", {"value": 2})
    store.set("b", {"value": 3})

    label = store.undo()
    assert label == "第一步"
    assert store.get("a") == {"value": 1}
    assert store.get("b") is None
    assert store.undo() is None  # 沒有更早的 checkpoint


def test_docstore_serialization_keeps_checkpoints():
    store = DocStore()
    store.set("a", {"value": 1})
    store.checkpoint("cp")
    store.set("a", {"value": 2})

    restored = DocStore.from_dict(store.to_dict())
    assert restored.get("a") == {"value": 2}
    assert restored.undo() == "cp"
    assert restored.get("a") == {"value": 1}


def test_requirement_doc_roundtrip_and_must_have():
    doc = RequirementDoc(
        hard=[
            RequirementItem(req_id="H1", text="雙人床", room_id="bedroom", category="bed"),
            RequirementItem(req_id="H2", text="預算上限", room_id=None, category=None),
        ],
        styles=["日式無印"],
    )
    restored = RequirementDoc.from_dict(doc.to_dict())
    assert [item.req_id for item in restored.hard] == ["H1", "H2"]
    # must_have 只回傳有 category 的硬需求
    assert [item.req_id for item in restored.must_have()] == ["H1"]
    assert restored.must_have("living") == []


def test_dockey_variant_naming():
    assert DocKey.variant(DocKey.SCENE, "A") == "scene:A"

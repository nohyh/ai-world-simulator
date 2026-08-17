import pytest

# 全部为同步测试


# ---------------- extract_meta ----------------

def test_extract_meta_basic():
    from app.prompts import extract_meta
    text = '他转过身。\n[[META]]\n{"choices": ["追问", "沉默"], "minutes": 10, "place": "大厅", "present": ["老周"]}\n[[END]]'
    meta = extract_meta(text)
    assert meta["choices"] == ["追问", "沉默"]
    assert meta["minutes"] == 10
    assert meta["place"] == "大厅"
    assert meta["present"] == ["老周"]


def test_extract_meta_no_end_tag():
    from app.prompts import extract_meta
    text = '正文。\n[[META]] {"minutes": 5}'
    assert extract_meta(text)["minutes"] == 5


def test_extract_meta_code_fenced():
    from app.prompts import extract_meta
    text = '正文\n[[META]]\n```json\n{"choices": ["a"], "minutes": 3}\n```\n[[END]]'
    assert extract_meta(text)["choices"] == ["a"]


def test_extract_meta_missing_returns_none():
    from app.prompts import extract_meta
    assert extract_meta("没有任何结构化块的正文") is None


def test_extract_meta_prose_with_braces():
    from app.prompts import extract_meta
    text = '他笑了笑（{那笑容里有话}）。\n[[META]]\n{"minutes": 1}\n[[END]]'
    assert extract_meta(text)["minutes"] == 1


# ---------------- normalize_meta ----------------

def test_normalize_meta_defaults():
    from app.prompts import normalize_meta
    m = normalize_meta(None, fallback_place="避难所", fallback_present=["老周"])
    assert len(m["choices"]) == 2
    assert m["minutes"] == 5
    assert m["place"] == "避难所"
    assert m["present"] == ["老周"]


def test_normalize_meta_clamps():
    from app.prompts import normalize_meta
    m = normalize_meta(
        {"choices": ["x" * 60, "好"], "minutes": 999999999, "place": "", "present": []},
        fallback_place="旧地点", fallback_present=["甲"])
    assert len(m["choices"]) == 2
    assert m["choices"][0] == "好"
    assert m["minutes"] == 60 * 24 * 30
    assert m["place"] == "旧地点"
    assert m["present"] == []


def test_normalize_meta_missing_present_inherits_previous_scene():
    from app.prompts import normalize_meta
    m = normalize_meta({"minutes": 5}, fallback_place="旧地点", fallback_present=["甲"])
    assert m["present"] == ["甲"]


# ---------------- 大小写/类型脏数据 ----------------

def test_normalize_meta_dirty_types():
    from app.prompts import normalize_meta
    m = normalize_meta({"minutes": "30", "choices": "不是列表", "present": [1, " 乙 "]},
                       fallback_place="P", fallback_present=[])
    assert m["minutes"] == 30
    assert len(m["choices"]) == 2
    assert m["present"] == ["1", "乙"]


def test_normalize_meta_keeps_two_to_four_choices():
    from app.prompts import normalize_meta

    m = normalize_meta(
        {"choices": ["一", "二", "三", "四", "五"], "minutes": 5},
        fallback_place="P",
        fallback_present=[],
    )
    assert m["choices"] == ["一", "二", "三", "四"]

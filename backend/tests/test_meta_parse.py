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


def test_public_meta_strips_hidden_fields():
    from app.prompts import public_meta
    full = {
        "choices": ["a", "b"], "minutes": 10, "place": "P", "present": ["林雨"],
        "chapter_done": {"done": False, "reason": ""},
        "npc_updates": {"林雨": {"current_thought": "秘密"}},
        "relationship_updates": [{"from": "林雨", "to": "主角", "favor_delta": -6,
                                  "bond": "裂痕"}],
        "player_update": {"status": "已死亡"},
    }
    out = public_meta(full)
    assert set(out) == {"choices", "minutes", "place", "present", "chapter_done"}
    assert "npc_updates" not in out and "relationship_updates" not in out
    assert "player_update" not in out and "quality_updates" not in out
    assert public_meta(None) == {}
    assert public_meta({"minutes": 5}) == {"minutes": 5}


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


# ---------------- Narrator 状态补丁（单作者，阶段 4/5） ----------------

def test_normalize_meta_patch_fields_normalized():
    from app.prompts import normalize_meta
    m = normalize_meta({
        "choices": ["a", "b"], "minutes": 10, "place": "P", "present": ["林雨"],
        "npc_updates": {"林雨": {"status": "受伤", "current_thought": "怀疑主角", "goal": "不该被存"},
                        "陈浩": {"status": "在场"}},
        "quality_updates": {"林雨": {"体质": -3, "可控": 99}},
        "relationship_updates": [
            {"from": "林雨", "to": "主角", "favor_delta": -6, "bond": "裂痕", "reason": "隐瞒"},
            {"from": "", "to": "主角", "favor_delta": -1},       # 无效 from → 丢弃
            {"from": "林雨", "to": "主角", "favor_delta": 999},   # clamp ±20
        ],
        "important_event": {"summary": "主角坦白", "participants": ["林雨"], "importance": "BOGUS"},
        "player_update": {"status": "已死亡"},
        "player_attr_changes": {"体质": -2, "智力": 99},
        "key_item_changes": {"add": ["钥匙"], "remove": []},
        "main_plot_update": "北迁",
        "chapter_done": {"done": True, "reason": "离开学校"},
    }, fallback_place="X", fallback_present=[])
    assert m["npc_updates"]["林雨"]["current_thought"] == "怀疑主角"
    assert "goal" not in m["npc_updates"]["林雨"]          # 非白名单字段被过滤
    assert m["npc_updates"]["陈浩"]["status"] == "在场"
    assert m["quality_updates"]["林雨"]["体质"] == -3
    assert m["quality_updates"]["林雨"]["可控"] == 10      # clamp ±10
    assert len(m["relationship_updates"]) == 2
    assert m["relationship_updates"][1]["favor_delta"] == 20
    assert m["important_event"]["importance"] == "minor"   # 非法值回退
    assert m["player_update"]["status"] == "已死亡"
    assert m["player_attr_changes"] == {"体质": -2, "智力": 3}
    assert m["key_item_changes"]["add"] == ["钥匙"]
    assert m["main_plot_update"] == "北迁"
    assert m["chapter_done"] == {"done": True, "reason": "离开学校"}


def test_normalize_meta_patch_safe_defaults_when_absent():
    from app.prompts import normalize_meta
    m = normalize_meta(None, fallback_place="X", fallback_present=[])
    assert m["npc_updates"] == {}
    assert m["new_npcs"] == []
    assert m["quality_updates"] == {}
    assert m["relationship_updates"] == []
    assert m["important_event"] is None
    assert m["player_update"] == {}
    assert m["player_attr_changes"] == {}
    assert m["key_item_changes"] == {"add": [], "remove": []}
    assert m["main_plot_update"] is None
    assert m["chapter_done"] is None


def test_normalize_meta_patch_tolerates_bad_types():
    from app.prompts import normalize_meta
    m = normalize_meta({
        "npc_updates": "不是对象",
        "new_npcs": {"name": "x"},
        "relationship_updates": {"from": "x"},
        "important_event": "纯文本",
        "player_update": [],
        "key_item_changes": "坏了",
    }, fallback_place="X", fallback_present=[])
    assert m["npc_updates"] == {}
    assert m["new_npcs"] == []
    assert m["relationship_updates"] == []
    assert m["important_event"] is None
    assert m["player_update"] == {}
    assert m["key_item_changes"] == {"add": [], "remove": []}


def test_normalize_meta_new_npc_cards():
    from app.prompts import normalize_meta
    m = normalize_meta({
        "new_npcs": [
            {"name": "苏晴", "identity": "调查员", "desire": "找线索",
             "qualities": {"观察": 80}, "current_thought": "这里不对劲"},
            {"name": "", "identity": "无名字会被丢"},
        ],
    }, fallback_place="X", fallback_present=[])
    assert len(m["new_npcs"]) == 1
    assert m["new_npcs"][0]["name"] == "苏晴"
    assert m["new_npcs"][0]["qualities"]["观察"] == 80

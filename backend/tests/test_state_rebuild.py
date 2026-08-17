from app.world_state import WorldState, parse_start_time

CONFIG = {
    "player": {
        "name": "阿远", "identity": "侦察员", "background": "背景",
        "attrs": {"力量": 50, "智力": 60}, "key_items": [],
    },
    "npc_cards": [
        {"name": "陈医生", "identity": "医疗官", "personality": "冷静",
         "relationship": "信任", "goal": "找医疗队", "secret_plan": "隐瞒感染"},
        {"name": "老周", "identity": "老猎人", "personality": "嘴硬",
         "relationship": "旧识", "goal": "", "secret_plan": ""},
    ],
    "main_plot": "铁鸦集团逼近",
    "start_time": "2041年7月16日 08:00",
}


def test_parse_start_time():
    dt = parse_start_time("2041年7月16日 08:00")
    assert (dt.year, dt.month, dt.day, dt.hour) == (2041, 7, 16, 8)
    assert parse_start_time("垃圾输入") is not None  # 回退当前时间


def test_rebuild_turn_updates_clock_and_place():
    st = WorldState.rebuild([
        ("TURN", {"player_action": "询问地图",
                  "narrative": "陈医生摊开地图。",
                  "meta": {"choices": ["a"], "minutes": 25, "place": "医务室", "present": ["陈医生"]}}),
        ("TURN", {"player_action": "出发",
                  "narrative": "你们上路了。",
                  "meta": {"choices": [], "minutes": 120, "place": "北岭", "present": ["老周"]}}),
    ], CONFIG)
    assert st.time_minutes == 145
    assert st.place == "北岭"
    assert st.present == ["老周"]
    assert st.turn_count == 2
    assert st.display_time() == "2041年7月16日 10:25"


def test_rebuild_side_effect_events():
    st = WorldState.rebuild([
        ("TURN", {"player_action": None, "narrative": "开篇",
                  "meta": {"minutes": 0, "place": "避难所", "present": ["陈医生", "老周"]}}),
        ("NPC_STATE", {"npcs": {"陈医生": {"feeling": "焦虑", "secret_plan": "隐瞒感染加剧"}}}),
        ("ATTR_CHANGE", {"changes": {"力量": -2, "不存在的属性": 5}}),
        ("ITEM_CHANGE", {"add": ["染血的地图"], "remove": []}),
        ("WORLD_TICK", {"developments": ["铁鸦前进了十公里"], "plot_pressure": "逼近中"}),
        ("CRYSTAL", {"layer": "short", "crystal": {"summary": "开篇与地图"}}),
        ("PLOT_PROGRESS", {}),
    ], CONFIG)
    assert st.npcs["陈医生"]["feeling"] == "焦虑"
    assert st.npcs["陈医生"]["secret_plan"] == "隐瞒感染加剧"
    assert st.player["attrs"]["力量"] == 48
    assert "不存在的属性" not in st.player["attrs"]
    assert st.player["key_items"] == ["染血的地图"]
    assert st.world_threads == ["铁鸦前进了十公里"]
    assert st.plot_pressure == "逼近中"
    assert st.turns_since_plot == 0
    # 抽屉只暴露玩家视角：秘密不外泄
    snap = st.drawer_snapshot()
    npc = [n for n in snap["character"]["npcs"] if n["name"] == "陈医生"][0]
    assert "secret_plan" not in npc and "goal" not in npc
    assert snap["world"]["chronicle"] == ["开篇与地图"]


def test_pending_crystal_turns_tracks_cursor():
    events = [("TURN", {"player_action": f"a{i}", "narrative": "n", "meta": {}}) for i in range(5)]
    events.append(("CRYSTAL", {"layer": "short", "crystal": {"summary": "s"}}))
    st = WorldState.rebuild(events, CONFIG)
    assert len(st.pending_crystal_turns) == 1
    assert st.pending_crystal_turns[0]["player_action"] == "a4"

from app.world_state import WorldState, parse_start_time

CONFIG = {
    "player": {
        "name": "阿远", "identity": "侦察员", "background": "背景",
        "attrs": {"力量": 50, "智力": 60}, "key_items": [],
    },
    "npc_cards": [
        {"name": "陈医生", "age": 45, "identity": "医疗官",
         "status": "右臂受伤", "qualities": {"智力": 80, "医疗": 85},
         "personality": "冷静", "desire": "找医疗队",
         "background": "军区医院出身", "current_thought": "医疗队还没回来"},
        {"name": "老周", "age": 60, "identity": "老猎人",
         "status": "清点弹药", "qualities": {"力量": 70, "追踪": 82},
         "personality": "嘴硬", "desire": "护住孩子",
         "background": "山里猎人", "current_thought": "粮快不够了"},
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
    assert st.turns[0]["beats"] == []


def test_rebuild_preserves_narrative_beats_when_present():
    beats = [{"type": "dialogue", "speaker": "陈医生", "text": "不要开灯。"}]
    st = WorldState.rebuild([
        ("TURN", {"narrative": "陈医生：不要开灯。", "beats": beats,
                  "meta": {"minutes": 1, "present": ["陈医生"]}}),
    ], CONFIG)
    assert st.turns[0]["beats"] == beats


def test_rebuild_side_effect_events():
    st = WorldState.rebuild([
        ("TURN", {"player_action": None, "narrative": "开篇",
                  "meta": {"minutes": 0, "place": "避难所", "present": ["陈医生", "老周"]}}),
        ("NPC_STATE", {"npcs": {"陈医生": {"status": "焦急地翻看地图", "current_thought": "必须尽快找到医疗队"}}}),
        ("ATTR_CHANGE", {"changes": {"力量": -2, "不存在的属性": 5}}),
        ("ITEM_CHANGE", {"add": ["染血的地图"], "remove": []}),
        ("WORLD_TICK", {"developments": ["铁鸦前进了十公里"], "plot_pressure": "逼近中"}),
        ("CRYSTAL", {"layer": "short", "crystal": {"summary": "开篇与地图"}}),
        ("PLOT_PROGRESS", {}),
    ], CONFIG)
    assert st.npcs["陈医生"]["status"] == "焦急地翻看地图"
    assert st.npcs["陈医生"]["current_thought"] == "必须尽快找到医疗队"
    assert st.player["attrs"]["力量"] == 48
    assert "不存在的属性" not in st.player["attrs"]
    assert st.player["key_items"] == ["染血的地图"]
    assert st.world_threads == ["铁鸦前进了十公里"]
    assert st.plot_pressure == "逼近中"
    assert st.turns_since_plot == 0
    # 抽屉只暴露玩家视角：内心/品质/关系不外泄
    snap = st.drawer_snapshot()
    npc = [n for n in snap["character"]["npcs"] if n["name"] == "陈医生"][0]
    assert "current_thought" not in npc and "desire" not in npc and "qualities" not in npc
    assert snap["world"] == {}
    assert "main_plot" not in snap["world"]


def test_new_npc_event_persists_and_exposes_seen_character():
    st = WorldState.rebuild([
        ("TURN", {"narrative": "陌生女人走进房间。",
                  "meta": {"minutes": 1, "present": ["苏晴"]}}),
        ("NPC_ADD", {"npcs": {
            "苏晴": {"identity": "调查员", "personality": "谨慎",
                     "desire": "寻找线索", "status": "打量着房间",
                     "current_thought": "这个避难所不对劲"}
        }}),
    ], CONFIG)
    assert st.npcs["苏晴"]["identity"] == "调查员"
    assert {n["name"] for n in st.drawer_snapshot()["character"]["npcs"]} == {"苏晴"}


def test_pending_crystal_turns_tracks_cursor():
    events = [("TURN", {"player_action": f"a{i}", "narrative": "n", "meta": {}}) for i in range(5)]
    events.append(("CRYSTAL", {"layer": "short", "crystal": {"summary": "s"}}))
    st = WorldState.rebuild(events, CONFIG)
    assert len(st.pending_crystal_turns) == 1
    assert st.pending_crystal_turns[0]["player_action"] == "a4"


def test_world_tick_accumulates_and_consumes_narrative_minutes():
    st = WorldState.rebuild([
        ("TURN", {"narrative": "短暂交谈", "meta": {"minutes": 30, "present": []}}),
        ("TURN", {"narrative": "继续赶路", "meta": {"minutes": 35, "present": []}}),
    ], CONFIG)
    assert st.time_minutes == 65
    assert st.world_tick_pending_minutes == 65

    st.apply("WORLD_TICK", {
        "minutes": 65,
        "developments": [],
        "npc_updates": {"陈医生": {"desire": "赶往北岭", "status": "焦急"}},
    })
    assert st.world_tick_pending_minutes == 0
    assert st.npcs["陈医生"]["desire"] == "赶往北岭"
    assert st.npcs["陈医生"]["status"] == "焦急"

    st.apply("WORLD_TICK", {"minutes": 0, "developments": [], "plot_pressure": ""})
    assert st.plot_pressure == ""


def test_world_tick_cursor_survives_memory_crystal():
    st = WorldState.rebuild([
        ("WORLD_TICK", {"minutes": 60, "developments": ["王城沦陷"]}),
    ], CONFIG)
    assert len(st.pending_crystal_world_ticks) == 1
    st.apply("CRYSTAL", {
        "layer": "short", "source_world_tick_count": 1,
        "source_turn_count": 0, "crystal": {"summary": "王城沦陷"},
    })
    assert st.pending_crystal_world_ticks == []


def test_npc_knowledge_window_only_contains_witnessed_turns():
    st = WorldState.rebuild([
        ("TURN", {"narrative": "陈医生说了秘密", "witnessed_by": ["陈医生"],
                   "meta": {"minutes": 5, "present": ["陈医生"]}}),
        ("TURN", {"narrative": "玩家独自发现了线索", "witnessed_by": [],
                   "meta": {"minutes": 5, "present": []}}),
    ], CONFIG)
    knowledge = st.npc_knowledge_window("陈医生")
    assert "陈医生说了秘密" in knowledge
    assert "独自发现了线索" not in knowledge


def test_public_snapshot_hides_director_state():
    st = WorldState.rebuild([
        ("WORLD_TICK", {"developments": ["暗流"], "plot_pressure": "逼近"}),
    ], CONFIG)
    snapshot = st.drawer_snapshot()
    assert "plot_pressure" not in snapshot["status"]
    assert "threads" not in snapshot["world"]


def test_tick_summary_contains_world_context():
    config = {**CONFIG, "world_setting": "1453 年的城邦", "world_rules": "没有无线电"}
    st = WorldState(config)
    summary = st.tick_summary()
    assert "1453 年的城邦" in summary
    assert "没有无线电" in summary
    assert "当前时间：2041年7月16日 08:00" in summary
    assert "当前地点：未知地点" in summary


def test_main_plot_update_is_event_sourced():
    st = WorldState.rebuild([
        ("MAIN_PLOT_UPDATE", {"main_plot": "铁鸦集团已经封锁北岭"}),
    ], CONFIG)
    assert st.main_plot == "铁鸦集团已经封锁北岭"


# ---------------- 有向稀疏关系表 ----------------

def test_relationship_created_on_first_update_with_default_50():
    st = WorldState.rebuild([
        ("REL_UPDATE", {"from": "林雨", "to": "主角", "favor_delta": -6,
                        "bond": "合作仍在继续，但已有裂痕", "reason": "主角隐瞒了感染者"}),
    ], CONFIG)
    rel = st.relationships[("林雨", "主角")]
    assert rel["favor"] == 44   # 默认 50 + (-6)
    assert rel["bond"] == "合作仍在继续，但已有裂痕"


def test_relationship_is_directed_reverse_edge_distinct():
    st = WorldState.rebuild([
        ("REL_UPDATE", {"from": "主角", "to": "林雨", "bond": "觉得她可信"}),
        ("REL_UPDATE", {"from": "林雨", "to": "主角", "favor_delta": 10}),
    ], CONFIG)
    assert st.relationships[("主角", "林雨")]["favor"] == 50
    assert st.relationships[("林雨", "主角")]["favor"] == 60
    assert len(st.relationships) == 2


def test_relationship_favor_clamped_and_bond_overwrites():
    st = WorldState.rebuild([
        ("REL_UPDATE", {"from": "甲", "to": "乙", "favor_delta": 999}),
        ("REL_UPDATE", {"from": "甲", "to": "乙", "favor_delta": -999}),
        ("REL_UPDATE", {"from": "甲", "to": "乙", "bond": "第一句"}),
        ("REL_UPDATE", {"from": "甲", "to": "乙", "bond": "第二句覆盖"}),
    ], CONFIG)
    rel = st.relationships[("甲", "乙")]
    assert rel["favor"] == 0    # +999→100，-999→0
    assert rel["bond"] == "第二句覆盖"


def test_relationship_seeded_from_initial_config():
    cfg = {**CONFIG, "initial_relationships": [
        {"from": "陈医生", "to": "主角", "favor": 70, "bond": "欠你一个人情"},
        {"from": "林雨", "to": "主角", "favor": 120},
    ]}
    st = WorldState(cfg)
    assert st.relationships[("陈医生", "主角")] == {"favor": 70, "bond": "欠你一个人情"}
    assert st.relationships[("林雨", "主角")]["favor"] == 100  # clamp


def test_relationship_context_injects_only_relevant_edges():
    cfg = {**CONFIG, "initial_relationships": [
        {"from": "陈医生", "to": "主角", "favor": 70, "bond": "信任"},
        {"from": "老周", "to": "主角", "favor": 55, "bond": "旧识"},
        {"from": "陈医生", "to": "老周", "favor": 60, "bond": "搭档"},
    ]}
    st = WorldState(cfg)
    ctx = st.relationship_context(["陈医生"])
    assert "陈医生 → 主角" in ctx
    assert "陈医生 → 老周" in ctx
    assert "老周 → 主角" not in ctx
    assert "好感 70" in ctx


def test_relationship_context_respects_budget():
    st = WorldState.rebuild([
        ("REL_UPDATE", {"from": "长名甲乙", "to": "主角", "favor_delta": 0, "bond": "一句话" * 200}),
    ], CONFIG)
    ctx = st.relationship_context(["长名甲乙"], budget=60)
    assert len(ctx) <= 60

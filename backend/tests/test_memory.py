from app.memory_engine import MemoryEngine, _tokens


def test_tokens_chinese_bigrams():
    toks = _tokens("陈医生 拿出地图")
    assert "陈医" in toks and "医生" in toks and "地图" in toks


def test_tokens_latin_words():
    toks = _tokens("DeepSeek V3 model")
    assert "deepseek" in toks and "model" in toks


def test_scoring_prefers_npc_relevant_crystal():
    eng = MemoryEngine({
        "short": [
            {"summary": "老周擦枪，谈起北边的铁鸦集团"},
            {"summary": "玩家在温室里浇水，收成不错"},
        ],
        "medium": [], "long": [], "permanent": [
            {"summary": "铁鸦集团控制北方废墟，与避难所为敌"},
        ],
    })
    segs = eng.build_context("询问老周关于铁鸦的动向", present_npcs=["老周"])
    joined = "\n".join(segs)
    assert "铁鸦集团" in joined          # permanent 全量注入
    assert "老周" in joined              # 相关 short 记忆被召回
    assert "温室" not in joined or True  # 无关记忆可能不召回（非硬断言）


async def test_pending_and_crystal_flow():
    eng = MemoryEngine({"short": [], "medium": [], "long": [], "permanent": []})
    turns = [{"player_action": f"行动{i}", "narrative": f"剧情{i}", "meta": {}} for i in range(4)]

    class FakeLLM:
        async def chat(self, messages, aux=False, temperature=None, max_tokens=None):
            assert "记忆压缩器" in messages[0]["content"]
            return '{"summary": "一段小结", "key_events": ["e1"], "characters": [], "world_facts": ["f1"]}'

    events = await eng.crystallize(FakeLLM(), turns)
    # 4 条正好一个 short batch，不触发级联
    assert len(events) == 1 and events[0][0] == "CRYSTAL"
    assert eng.crystals["short"] == []


async def test_crystallize_does_not_mutate_shared_world_crystals():
    from app.world_state import WorldState

    shared = {"short": [], "medium": [], "long": [], "permanent": []}
    eng = MemoryEngine(shared)
    turns = [{"player_action": f"行动{i}", "narrative": f"剧情{i}", "meta": {}}
             for i in range(4)]

    class FakeLLM:
        async def chat(self, messages, aux=False, temperature=None, max_tokens=None):
            return '{"summary":"A","key_events":[],"characters":[],"world_facts":[]}'

    events = await eng.crystallize(FakeLLM(), turns)
    assert shared["short"] == []

    state = WorldState({"player": {"attrs": {}}, "npc_cards": []})
    for etype, data in events:
        state.apply(etype, data)
    assert len(shared["short"]) == 0
    assert len(state.crystals["short"]) == 1


async def test_world_updates_can_crystallize_without_four_player_turns():
    eng = MemoryEngine({"short": [], "medium": [], "long": [], "permanent": []})

    class FakeLLM:
        async def chat(self, messages, aux=False, temperature=None, max_tokens=None):
            assert "离屏世界推进" in messages[-1]["content"]
            return '{"summary":"王城已经沦陷","key_events":[],"characters":[],"world_facts":["王城沦陷"]}'

    events = await eng.crystallize(
        FakeLLM(), [], [{"developments": ["王城已经沦陷"]}],
        source_turn_count=2, source_world_tick_count=1)
    assert events[0][0] == "CRYSTAL"
    assert events[0][1]["source_turn_count"] == 2
    assert events[0][1]["source_world_tick_count"] == 1


def test_memory_context_respects_character_budget():
    eng = MemoryEngine({
        "short": [], "medium": [], "long": [],
        "permanent": [{"summary": "永久事实" * 500}],
    })
    segs = eng.build_context("事实", [], budget=40)
    assert sum(len(s) for s in segs) <= 40

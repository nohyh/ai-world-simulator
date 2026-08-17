import pytest

from app import npc_mind, world_reactor
from app.game_session import GameSession
from app.world_state import WorldState

pytestmark = pytest.mark.asyncio


async def test_npc_mind_still_updates_player_when_scene_is_empty():
    class FakeLLM:
        async def chat(self, messages, **kwargs):
            assert "当前无 NPC 在场" in messages[-1]["content"]
            return ('{"npcs":{},"main_plot_update":"主线已转向实验室线索",'
                    '"plot_advanced":true,"player_attr_changes":{"体质":-2},'
                    '"key_item_changes":{"add":["实验室钥匙"],"remove":[]}}')

    result = await npc_mind.update_minds(
        FakeLLM(), {}, [], "搜索废墟", "你找到了钥匙。", {"体质": 50}, "旧主线")
    assert result == (
        {}, {}, True, "主线已转向实验室线索", {"体质": -2},
        {"add": ["实验室钥匙"], "remove": []},
    )


async def test_world_tick_failure_is_not_a_consumable_tick():
    class FailingLLM:
        async def chat(self, messages, **kwargs):
            raise TimeoutError("provider timeout")

    result = await world_reactor.world_tick(
        FailingLLM(), 180, "主线", "状态", [], {})
    assert result["ok"] is False


async def test_world_tick_invalid_json_is_not_a_consumable_tick():
    class InvalidLLM:
        async def chat(self, messages, **kwargs):
            return "模型没有按要求返回 JSON"

    result = await world_reactor.world_tick(
        InvalidLLM(), 180, "主线", "状态", [], {})
    assert result["ok"] is False


async def test_world_tick_only_receives_offscreen_npcs():
    class FakeLLM:
        def __init__(self):
            self.user = ""

        async def chat(self, messages, **kwargs):
            self.user = messages[-1]["content"]
            return "{}"

    llm = FakeLLM()
    result = await world_reactor.world_tick(
        llm, 180, "主线", "世界上下文", [], {
            "陈医生": {"identity": "医生"},
            "老周": {"identity": "猎人"},
        }, ["陈医生"])
    assert result["ok"] is True
    assert "陈医生" not in llm.user
    assert "老周" in llm.user


async def test_narrator_without_meta_gets_safe_fallback():
    class ProseOnlyLLM:
        async def stream_chat(self, messages):
            yield "你推开门，房间里空无一人。"

    session = object.__new__(GameSession)
    session.llm = ProseOnlyLLM()
    session.state = WorldState({"start_time": "2041年7月16日 08:00"})
    events = [event async for event in session._run_narrator([])]
    assert session._last_prose.startswith("你推开门")
    assert isinstance(session._last_meta, dict)
    assert events[-1]["type"] == "meta"
    assert events[-1]["meta"]["choices"]

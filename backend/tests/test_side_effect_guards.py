import pytest

from app import npc_mind, world_reactor

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
        {}, True, "主线已转向实验室线索", {"体质": -2},
        {"add": ["实验室钥匙"], "remove": []},
    )


async def test_world_tick_failure_is_not_a_consumable_tick():
    class FailingLLM:
        async def chat(self, messages, **kwargs):
            raise TimeoutError("provider timeout")

    result = await world_reactor.world_tick(
        FailingLLM(), 180, "主线", "状态", [], {})
    assert result["ok"] is False

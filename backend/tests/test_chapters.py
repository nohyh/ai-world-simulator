"""阶段 6/7/8：章节框架 + Chapter Planner + 本章重开（in-memory DB 绕开沙箱 tmp_path）。"""
import pytest

from app.db import Database
from app.game_session import get_session
from app import prompts


CARDS = [
    {"name": "陈医生", "age": 45, "identity": "医疗官", "status": "右臂受伤",
     "qualities": {"智力": 80, "医疗": 85}, "personality": "冷静",
     "desire": "找医疗队", "background": "军区医院出身",
     "current_thought": "医疗队还没回来"},
    {"name": "老周", "age": 60, "identity": "老猎人", "status": "清点弹药",
     "qualities": {"力量": 70, "追踪": 82}, "personality": "嘴硬",
     "desire": "护住孩子", "background": "山里猎人",
     "current_thought": "粮快不够了"},
]

CONFIG = {
    "world_setting": "末日废土",
    "current_situation": "清晨的医务室，陈医生刚把你叫醒。",
    "important_people": "陈医生——医疗官；老周——老猎人",
    "player": {"name": "阿远", "identity": "侦察员", "background": "b",
               "attrs": {}, "key_items": []},
    "start_time": "2041年7月16日 08:00",
    "npc_cards": CARDS,
    "initial_relationships": [{"from": "陈医生", "to": "主角", "favor": 60, "bond": "合作"}],
    "main_plot": "北迁",
    "first_chapter": {"title": "逃离学校", "time_scope": "当天上午",
                      "location_scope": "校园", "theme": "逃出学校",
                      "success_condition": "主角离开校园", "failure_condition": "主角死亡"},
}


def _fresh_session(db):
    db.set_settings({"provider": "mock", "api_key": ""})
    wid = db.create_world(CONFIG, "测试世界")
    return get_session(wid, db.get_world(wid), db)


class ChapterLLM:
    def __init__(self):
        self.aux_flag = None

    async def close(self):
        pass

    async def chat(self, messages, aux=False, temperature=None, max_tokens=None):
        self.aux_flag = aux
        assert "章节规划者" in messages[0]["content"]
        return ('{"chapter_summary": "第一章结束了。",'
                '"next_chapter": {"title": "第二章", "time_scope": "夜间",'
                '"location_scope": "避难所", "theme": "过夜",'
                '"success_condition": "获得落脚点", "failure_condition": "主角死亡"}}')


@pytest.mark.asyncio
async def test_chapter_advance_uses_main_model_and_keeps_character_state():
    db = Database(":memory:")
    s = _fresh_session(db)
    try:
        s._append("CHAPTER", {"index": 1, "frame": CONFIG["first_chapter"]}, stamp_seq=True)
        meta = {"choices": ["a", "b"], "minutes": 10, "place": "校门", "present": ["陈医生"],
                "npc_updates": {"陈医生": {"status": "擦伤了腿"}},
                "relationship_updates": [{"from": "陈医生", "to": "主角", "favor_delta": -2,
                                          "bond": "裂痕初现", "reason": "逃命中的摩擦"}],
                "chapter_done": {"done": True, "reason": "主角已离开校园"}}
        s._commit_turn({"player_action": "翻墙逃出", "narrative": "你翻过了围墙。",
                        "beats": [], "meta": meta})
        assert s.chapter_done_pending == {"done": True, "reason": "主角已离开校园"}

        llm = ChapterLLM()
        s.llm = llm
        result = await s.advance_chapter()
        assert result is not None
        assert result["chapter"] == 2
        assert llm.aux_flag is False            # 主模型调用
        assert s.state.current_chapter == 2
        assert len(s.state.chapters) == 2
        assert s.state.chapter_ends[-1]["index"] == 1
        assert s.state.chapters[-1]["frame"]["title"] == "第二章"
        # 规划器绝不改人物/关系状态
        assert s.state.npcs["陈医生"]["status"] == "擦伤了腿"
        assert s.state.relationships[("陈医生", "主角")]["favor"] == 58
    finally:
        await s.close()


@pytest.mark.asyncio
async def test_first_chapter_created_on_parse_with_mock():
    db = Database(":memory:")
    cfg = dict(CONFIG)
    cfg.pop("npc_cards")        # 触发创建时 LLM 提取（mock 提供 first_chapter）
    cfg.pop("initial_relationships")
    db.set_settings({"provider": "mock", "api_key": ""})
    wid = db.create_world(cfg, "提取世界")
    from app.game_session import GameSession
    s = GameSession(wid, db.get_world(wid), db)
    try:
        await s._parse_npc_cards()
        assert s.state.current_chapter == 1
        assert s.state.chapters[0]["frame"]["title"] == "逃离学校"
        assert s.state.chapters[0]["start_seq"] == 1   # stamp 固化
        assert s.config["first_chapter"]["success_condition"] == "主角真正离开学校"
    finally:
        await s.close()


@pytest.mark.asyncio
async def test_restart_chapter_truncates_to_chapter_start():
    db = Database(":memory:")
    s = _fresh_session(db)
    try:
        s._append("CHAPTER", {"index": 1, "frame": CONFIG["first_chapter"]}, stamp_seq=True)
        s._commit_turn({"player_action": "行动一", "narrative": "n1", "beats": [],
                        "meta": {"choices": ["a", "b"], "minutes": 5, "place": "P",
                                 "present": ["陈医生"]}})
        s._commit_turn({"player_action": "行动二", "narrative": "n2", "beats": [],
                        "meta": {"choices": ["a", "b"], "minutes": 5, "place": "P",
                                 "present": [], "player_update": {"status": "已死亡"}}})
        assert s.state.turn_count == 2
        assert s.state.player["status"] == "已死亡"

        s2 = await s.restart_chapter()
        assert s2.state.turn_count == 0
        assert s2.state.current_chapter == 1
        assert s2.state.player["status"] == ""       # 回滚掉「已死亡」
        assert "陈医生" in s2.state.npcs              # 人物卡来自 config，保留
        assert len(db.get_events(s2.world_id)) == 1   # 只剩 CHAPTER 事件
    finally:
        pass


def test_chapter_and_event_prompt_blocks():
    frame = {"title": "逃离学校", "time_scope": "上午至下午", "location_scope": "校园",
             "theme": "逃", "success_condition": "离开学校", "failure_condition": "死亡"}
    b = prompts.chapter_block(frame)
    assert "当前章节" in b and "离开学校" in b and "chapter_done" in b
    assert prompts.chapter_block({}) == ""
    ev = prompts.events_block([
        {"summary": "主角坦白", "importance": "major"},
        {"summary": "藏身点被烧", "importance": "minor"}])
    assert "★" in ev and "主角坦白" in ev
    assert prompts.events_block([]) == ""

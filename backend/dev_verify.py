"""v2 阶段级冒烟：mock LLM 驱动 创建→开篇→行动→抽屉，验证新 NPC 卡结构。
运行在沙箱内（DB 落在 backend/data，绕开 tmp_path 权限限制）。
用法：python dev_verify.py
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from app import routes
from app.db import Database
from app.game_session import get_session, drop_session, GameSession

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "verify.db")


async def main():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    db = Database(DB_PATH)
    routes.db = db
    db.set_settings({"provider": "mock", "api_key": ""})

    wid = db.create_world({
        "world_setting": "末日废土",
        "current_situation": "清晨的医务室，陈医生刚把你叫醒。",
        "custom_notes": "避免血腥描写",
        "important_people": "陈医生——医疗官；老周——老猎人",
        "player": {"name": "阿远", "identity": "侦察员", "background": "b",
                   "attrs": {"力量": 50}, "key_items": []},
        "start_time": "2041年7月16日 08:00",
    }, "末日世界")

    row = db.get_world(wid)
    s = get_session(wid, row, db)
    try:
        beats, metas, dones = [], [], []
        async for ev in s.ensure_opening():
            if ev["type"] == "beat":
                beats.append(ev["beat"])
            elif ev["type"] == "meta":
                metas.append(ev["meta"])
            elif ev["type"] == "done":
                dones.append(ev)

        assert beats and beats[1]["speaker"] == "陈医生", "beats missing"
        assert len(metas[0]["choices"]) >= 2, "meta choices missing"
        assert dones and len(dones[0]["history"]["turns"]) == 1
        assert "陈医生" in s.state.npcs and "老周" in s.state.npcs

        # 新卡结构
        card = s.state.npcs["陈医生"]
        assert "desire" in card and "current_thought" in card and "status" in card and "qualities" in card
        assert "feeling" not in card and "goal" not in card and "secret_plan" not in card

        # 有向关系表（创建时由提取调用生成；开篇补丁再 +2；别名归一→玩家「阿远」）
        assert ("陈医生", "阿远") in s.state.relationships
        assert s.state.relationships[("陈医生", "阿远")]["favor"] == 72
        ctx = s.state.relationship_context(["陈医生"])
        assert "陈医生 → 阿远" in ctx

        for action in ("询问地图的来源", "提议立即出发"):
            seen = []
            async for ev in s.process_action(action):
                seen.append(ev)
            assert seen[-1]["type"] == "done"
        await s._drain_side_effects(timeout=10)

        st = s.state
        assert st.turn_count == 3, st.turn_count
        # 单作者补丁：Narrator 的 META 补丁同步生效（不再有 npc_mind 二次裁决）
        assert st.npcs["陈医生"]["current_thought"] == "也许该试着信任主角了。"
        assert "队长" in st.npcs                       # new_npcs 建档
        assert st.relationships[("陈医生", "阿远")]["favor"] == 76  # 70 + 2×3 回合
        assert len(st.important_events) >= 3
        snap = st.drawer_snapshot()
        assert snap["character"]["player"]["name"] == "阿远"
        npc = next(n for n in snap["character"]["npcs"] if n["name"] == "陈医生")
        assert set(npc.keys()) == {"name", "identity", "status", "age"}, npc

        # 重建一致
        row2 = db.get_world(wid)
        drop_session(wid)
        s3 = GameSession(wid, row2, db)
        assert s3.state.turn_count == 3
        assert set(s3.state.npcs) == set(st.npcs)
        assert s3.state.npcs["陈医生"]["current_thought"] == st.npcs["陈医生"]["current_thought"]
        assert s3.state.current_chapter == 1              # 第一章框架来自 mock 提取
        assert s3.state.chapters[0]["frame"]["title"] == "逃离学校"
        # 隐藏 META 服务端化：history 的 TURN meta 只含公共字段。
        payload = s3._history_payload()
        for t in payload["turns"]:
            assert "npc_updates" not in t["meta"]
            assert "relationship_updates" not in t["meta"]
            assert "quality_updates" not in t["meta"]
            assert "player_update" not in t["meta"]

        # 章节边界（阶段 6/7/8，走真实 mock）：达成→规划下一章→本章重开
        s3._commit_turn({"player_action": "离开学校", "narrative": "你终于离开了学校。",
                         "beats": [], "meta": {
                             "choices": ["a", "b"], "minutes": 30, "place": "校门外",
                             "present": [], "chapter_done": {"done": True, "reason": "已达成功条件"}}})
        adv = await s3.advance_chapter()
        assert adv is not None and adv["chapter"] == 2
        assert s3.state.current_chapter == 2
        assert s3.state.chapter_ends[-1]["index"] == 1
        s4 = await s3.restart_chapter()
        assert s4.state.current_chapter == 2
        # 「本章重开」= 回滚当前章（第 2 章）起点，第一章历史保留。
        assert s4.state.turn_count == 4   # 第一章 3 回合 + 达成回合

        print("V2-SMOKE-OK turns=%d npcs=%s rels=%d chapter=%d" % (
            s4.state.turn_count if s4 else st.turn_count, list(s4.state.npcs), len(s4.state.relationships), s4.state.current_chapter))
        print("  card_sample:", {k: s4.state.npcs["陈医生"][k] for k in ("status", "desire", "current_thought")})
    finally:
        drop_session(wid)
        try:
            db._conn.close()
        except Exception:
            pass
        if os.path.exists(DB_PATH):
            for _ in range(5):
                try:
                    os.remove(DB_PATH)
                    break
                except PermissionError:
                    import time
                    time.sleep(0.3)


if __name__ == "__main__":
    asyncio.run(main())

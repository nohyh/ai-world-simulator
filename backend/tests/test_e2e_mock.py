"""端到端冒烟：mock LLM 驱动 创建世界 → 生成开篇 → 行动 → 抽屉状态。"""
import pytest

pytestmark = pytest.mark.asyncio


async def test_full_game_flow(tmp_path, monkeypatch):
    from app import routes
    from app.db import Database
    from app.game_session import get_session, drop_session

    db = Database(tmp_path / "test.db")
    monkeypatch.setattr(routes, "db", db)

    # 0) 全局设置：模型配置已从世界剥离
    db.set_settings({"provider": "mock", "api_key": ""})

    # 1) 创建世界（无 LLM）
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
        # 2) 开篇（NPC 解析 + 主叙事，全是 mock）
        beats, metas, dones = [], [], []
        async for ev in s.ensure_opening():
            if ev["type"] == "beat":
                beats.append(ev["beat"])
            elif ev["type"] == "meta":
                metas.append(ev["meta"])
            elif ev["type"] == "done":
                dones.append(ev)
        prose = "\n\n".join(
            f"{b['speaker']}：{b['text']}" if b["speaker"] else b["text"]
            for b in beats
        )
        assert "[[META]]" not in prose and "[[END]]" not in prose
        assert "雨水" in prose
        assert beats and beats[1]["speaker"] == "陈医生"
        assert metas and len(metas[0]["choices"]) >= 2
        assert dones and len(dones[0]["history"]["turns"]) == 1
        # NPC 卡已由 aux 解析并持久化
        assert "陈医生" in s.state.npcs and "老周" in s.state.npcs
        assert s.config["main_plot"]

        # 3) 两轮玩家行动（含后台副作用）
        for action in ("询问地图的来源", "提议立即出发"):
            seen = []
            async for ev in s.process_action(action):
                seen.append(ev)
            assert seen[-1]["type"] == "done"
            assert seen[0]["type"] == "beat"
        await s._drain_side_effects(timeout=10)

        st = s.state
        assert st.turn_count == 3
        assert all("[[META]]" not in t["narrative"] for t in st.turns)
        assert all(t["beats"] for t in st.turns)
        # 事件树数据：每回合带属性/物品变化槽位 + 初始属性快照
        assert all("attr_changes" in t and "item_changes" in t for t in st.turns)
        payload = s._history_payload()
        assert all(t["beats"] for t in payload["turns"])
        assert payload["initial_attrs"] == {"力量": 50}

        # 4) 玩家视角抽屉
        snap = st.drawer_snapshot()
        assert snap["character"]["player"]["name"] == "阿远"
        names = {n["name"] for n in snap["character"]["npcs"]}
        assert {"陈医生", "老周"} <= names
        for n in snap["character"]["npcs"]:
            assert "current_thought" not in n and "desire" not in n and "qualities" not in n
        assert snap["status"]["time"].startswith("2041年7月16日")

        # 5) 事件溯源重建 == 内存态
        row2 = db.get_world(wid)
        s2 = get_session(wid, row2, db)  # 同一实例；强制重建验证
        drop_session(wid)
        from app.game_session import GameSession
        s3 = GameSession(wid, row2, db)
        assert s3.state.turn_count == 3
        assert s3.state.place == st.place
        assert set(s3.state.npcs) == set(st.npcs)

        # 6) 世界列表
        worlds = db.list_worlds()
        assert worlds[0]["has_opening"] is True
    finally:
        drop_session(wid)

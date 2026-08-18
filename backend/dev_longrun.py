"""阶段 12：长剧情机械验证（3 个世界 × 40+ 回合 × 跨 2-3 章）。

注入真实剧情创作质量无法用 mock 判定——本脚本验证系统级稳定性：
连续回合、记忆结晶、世界推进、关系有界增长、章节推进、重启重建完全一致。

用法：python dev_longrun.py
"""
import asyncio
import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))

import re
from app import llm as llm_mod


async def _fast_mock_narrator_stream(messages):
    """长局用：加大 mock 流式块、缩短 sleep，避免 44 回合×3 世界过慢。"""
    text = llm_mod._MOCK_TURN
    user_txt = ""
    for m in reversed(messages):
        if m["role"] == "user":
            user_txt = m["content"][-60:]
            break
    echo = re.sub(r"\s+", "", user_txt)[:12] or "行动"
    text = text.replace("{action_echo}", f"「{echo}」")
    for i in range(0, len(text), 200):
        yield text[i:i + 200]
        await asyncio.sleep(0)


llm_mod._mock_narrator_stream = _fast_mock_narrator_stream

from app.db import Database
from app.game_session import GameSession

WORLDS = [
    {
        "title": "末日校园",
        "world_setting": "灾难爆发的校园，感染正在蔓延，学生必须尽快离开学校。",
        "current_situation": "你在教学楼二层，警报长鸣，浓烟从楼梯间涌上来。",
        "important_people": "林雨——学生会成员；陈浩——班长；苏晴——医务室同学",
        "player": {"name": "林默", "identity": "高三学生", "background": "体能普通，擅长观察",
                   "attrs": {"智力": 55, "体质": 45}, "key_items": []},
    },
    {
        "title": "雾都侦探",
        "world_setting": "常年大雾的港口城市，连续七人失踪，警局束手无策。",
        "current_situation": "你收到一封没有署名的信，上面只有一张旧照片。",
        "important_people": "白薇——女法医；老陆——老警探；陈停——失踪者家属",
        "player": {"name": "程野", "identity": "私家侦探", "background": "退役刑警",
                   "attrs": {"智力": 70, "魅力": 60}, "key_items": []},
    },
    {
        "title": "星海殖民船",
        "world_setting": "驶向新星系的殖民船，蓄水池开始失压，休眠舱区亮起红灯。",
        "current_situation": "你在环形舱段值夜班，广播通知有一节舱段失联。",
        "important_people": "伊芙——总工程师；韩森——医疗官；北——舰桥领航员",
        "player": {"name": "诺亚", "identity": "轮机员", "background": "机械师",
                   "attrs": {"智力": 60, "体质": 55}, "key_items": []},
    },
]

ACTIONS = ["调查附近的线索", "和同伴商量对策", "试着绕开封锁", "翻找有用的物资",
           "蹲下来休息片刻", "询问目击者经过"]


async def run_world(world):
    db = Database(":memory:")
    db.set_settings({"provider": "mock", "api_key": ""})
    wid = db.create_world(dict(world, start_time="2041年7月16日 08:00"), world["title"])
    s = GameSession(wid, db.get_world(wid), db)
    results = {}
    try:
        # 开局（创建时 mock 解析 NPC 卡 / 关系 / 第一章）
        async for _ in s.ensure_opening():
            pass
        await s._drain_side_effects(timeout=30)
        print(f"  [world start] opening done", flush=True)

        for i in range(44):
            t0 = time.monotonic()
            async for _ in s.process_action(ACTIONS[i % len(ACTIONS)]):
                pass
            t1 = time.monotonic()
            await s._drain_side_effects(timeout=30)
            t2 = time.monotonic()
            if t1 - t0 > 0.5 or t2 - t1 > 0.5:
                print(f"  [world] turn {i} action={t1-t0:.2f}s drain={t2-t1:.2f}s "
                      f"tasks={len(s._side_tasks)}", flush=True)
            if (i + 1) % 12 == 0:
                print(f"  [world] turn {i} chapter boundary", flush=True)
                s._commit_turn({
                    "player_action": "完成了本章的目标",
                    "narrative": "这一章落下了帷幕。",
                    "beats": [],
                    "meta": {"choices": ["继续前行", "稍作停留"], "minutes": 30,
                             "place": "当前地标", "present": [],
                             "chapter_done": {"done": True, "reason": "本章目标达成"}}})
                adv = await s.advance_chapter()
                if adv is None:
                    raise AssertionError("章节推进失败")
        await s._drain_side_effects(timeout=30)
        print("  [world] loop done", flush=True)

        st = s.state
        results["turns"] = st.turn_count
        results["chapter"] = st.current_chapter
        results["chapters"] = len(st.chapters)
        results["npcs"] = len(st.npcs)
        results["rels"] = len(st.relationships)
        results["imp_events"] = len(st.important_events)
        results["crystals_short"] = len(st.crystals["short"])
        results["crystals_medium"] = len(st.crystals["medium"])
        results["crystals_long"] = len(st.crystals["long"])

        # 关系有界
        for rel in st.relationships.values():
            assert 0 <= rel["favor"] <= 100, rel
        # 记忆已结晶
        assert results["crystals_short"] > 0, "short 层无结晶"

        # 重启重建完全一致
        s2 = GameSession(wid, db.get_world(wid), db)
        assert s2.state.turn_count == st.turn_count
        assert s2.state.current_chapter == st.current_chapter
        assert set(s2.state.npcs) == set(st.npcs)
        assert s2.state.relationships == st.relationships
        for name in st.npcs:
            a = s2.state.npcs[name].get("current_thought")
            b = st.npcs[name].get("current_thought")
            assert a == b, f"{name} current_thought 重建不一致"
        results["rebuild_ok"] = True
        return s, db, results
    except Exception:
        try:
            await s.close()
        except Exception:
            pass
        raise


async def main():
    print("=== 阶段 12：长剧情机械验证（3 个世界 × 44 回合 × 跨 3 章，mock LLM）===")
    all_ok = True
    for idx, w in enumerate(WORLDS, 1):
        try:
            s, db, r = await run_world(w)
            print(f"[世界{idx}·{w['title']}] turns={r['turns']} chapter={r['chapter']}(共{r['chapters']}章) "
                  f"npcs={r['npcs']} rels={r['rels']} imp={r['imp_events']} "
                  f"crystals={r['crystals_short']}/{r['crystals_medium']}/{r['crystals_long']} "
                  f"rebuild={r['rebuild_ok']}")
            try:
                await s.close()
            except Exception:
                pass
        except AssertionError as e:
            all_ok = False
            print(f"[世界{idx}·{w['title']}] FAIL: {e}")
        except Exception as e:
            all_ok = False
            print(f"[世界{idx}·{w['title']}] ERROR: {type(e).__name__}: {e}")

    if all_ok:
        print("=== 全部通过：多回合/结晶/世界推进/章节推进/重建一致 ===")
        print("（注：剧情创作质量的四项成功标准需要在真实 LLM 下试玩评估）")
    else:
        print("=== 存在失败项 ===")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

"""Game Orchestrator：唯一的回合循环。

玩家行动 → 读世界状态 → 读记忆窗口 → 组装上下文 → 主 LLM（流式正文+结尾结构化块）
→ 更新状态与事件库 → 异步副作用（NPC 心智 / 属性物品 / 世界推进 / 记忆结晶）→ 等待玩家。

同步路径只有 1 次 LLM 调用（决策 #3/#5）；副作用全部走辅助便宜模型。
"""
import asyncio
import logging
from datetime import datetime

from . import config as C
from . import prompts
from .llm import LLMClient, LLMConfig
from .memory_engine import MemoryEngine, _loads
from . import npc_mind, world_reactor
from .world_state import WorldState
from .beat_parser import BeatStreamParser, beats_to_prose

logger = logging.getLogger(__name__)

_sessions: dict = {}

_MODEL_KEYS = ("provider", "base_url", "api_key", "model", "aux_model", "temperature")


def resolve_llm_config(db, world_cfg):
    """全局设置 + 世界级覆盖（新世界不再存模型配置，始终跟随全局设置）。"""
    merged = dict(db.get_settings() or {})
    for k in _MODEL_KEYS:
        if world_cfg.get(k):
            merged[k] = world_cfg[k]
    return merged


def get_session(world_id, world_row, db):
    s = _sessions.get(world_id)
    if s is None:
        s = GameSession(world_id, world_row, db)
        _sessions[world_id] = s
    return s


def drop_session(world_id):
    session = _sessions.pop(world_id, None)
    if session is None:
        return
    session._closed = True
    loop = getattr(session, "_loop", None)
    if not loop or not loop.is_running():
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
    if loop and loop.is_running():
        loop.call_soon_threadsafe(lambda: asyncio.create_task(session.close()))
        return
    try:
        asyncio.run(session.close())
    except RuntimeError:
        logger.warning("Could not synchronously close session %s", world_id, exc_info=True)


async def close_session(world_id):
    """Awaitable cleanup used by destructive API routes before deleting a world."""
    session = _sessions.pop(world_id, None)
    if session is not None:
        await session.close()


def drop_all_sessions():
    for world_id in list(_sessions):
        drop_session(world_id)


class GameSession:
    def __init__(self, world_id, world_row, db):
        self.world_id = world_id
        self.db = db
        self.config = world_row["config"]
        # Migrate older worlds that were created before start_time became a
        # persisted field. Derive it once from creation time, never from each
        # subsequent rebuild.
        if not self.config.get("start_time"):
            created_at = world_row.get("created_at")
            try:
                start_dt = datetime.fromtimestamp(float(created_at)) if created_at else datetime.now()
            except (TypeError, ValueError, OverflowError, OSError):
                start_dt = datetime.now()
            self.config["start_time"] = start_dt.replace(microsecond=0).isoformat(timespec="minutes")
            self.db.save_world_config(self.world_id, self.config)
        self.llm = LLMClient(LLMConfig(resolve_llm_config(db, self.config)))
        self.state = WorldState.rebuild(db.get_events(world_id), self.config)
        self.mem = MemoryEngine(self.state.crystals)
        self._side_tasks: list[asyncio.Task] = []
        self._turn_lock = asyncio.Lock()
        self._loop = None
        self._closed = False

    # ================= 对外：开篇 =================
    async def ensure_opening(self):
        """串行执行一个世界的开篇，避免重复创建 TURN。"""
        async with self._turn_lock:
            async for ev in self._ensure_opening_unlocked():
                yield ev

    async def _ensure_opening_unlocked(self):
        """SSE 生成器：若已有回合则直接结束，否则生成开篇。"""
        if self.state.turns:
            yield {"type": "done", "history": self._history_payload()}
            return
        if not self.config.get("npc_cards"):
            await self._parse_npc_cards()
        await self._drain_side_effects()

        msgs = [
            {"role": "system", "content": self._narrator_system()},
            {"role": "user", "content": prompts.opening_user_message(
                self.config.get("world_setting") or "",
                self.config.get("world_rules") or "",
                self.config.get("tone") or "",
                self.state.player,
                self._npc_cards_desc(),
                self.state.display_time(),
                situation=self.config.get("current_situation") or "",
                notes=self.config.get("custom_notes") or "")},
        ]
        async for ev in self._run_narrator(msgs):
            yield ev
        meta = self._last_meta
        turn = {"player_action": None, "narrative": self._last_prose, "meta": meta}
        self._commit_turn(turn)
        self.config["_has_opening"] = True
        self.db.save_world_config(self.world_id, self.config)
        self._schedule_side_effects(turn)
        yield {"type": "done", "history": self._history_payload()}

    # ================= 对外：玩家行动 =================
    async def process_action(self, action):
        """串行执行一个世界的玩家行动，保证事件序列不会交叉。"""
        async with self._turn_lock:
            async for ev in self._process_action_unlocked(action):
                yield ev

    async def _process_action_unlocked(self, action):
        action = (action or "").strip()
        if not action:
            yield {"type": "error", "message": "行动不能为空"}
            return
        await self._drain_side_effects()
        if not self.state.turns and not self.config.get("_has_opening"):
            yield {"type": "error", "message": "世界尚未开局，请先调用 start"}
            return

        self.state.decay_feelings()
        msgs = [
            {"role": "system", "content": self._narrator_system()},
            {"role": "user", "content": self._narrator_user(action)},
        ]
        async for ev in self._run_narrator(msgs):
            yield ev
        meta = self._last_meta
        turn = {"player_action": action, "narrative": self._last_prose, "meta": meta}
        self._commit_turn(turn)
        self.db.touch_world(self.world_id)
        self._schedule_side_effects(turn)
        yield {"type": "done", "history": self._history_payload()}

    # ================= 叙事主调用 =================
    async def _run_narrator(self, messages):
        """流式产出完整 Beat 与最终 meta；结果同时暂存到 self._last_*。"""
        self._last_prose = ""
        self._last_beats = []
        self._last_meta = None
        buf = ""
        meta_mode = False
        meta_raw = ""
        parser = BeatStreamParser()

        def emit(beats):
            for beat in beats:
                self._last_beats.append(beat)
                yield {"type": "beat", "beat": beat}

        async for delta in self.llm.stream_chat(messages):
            buf += delta
            if meta_mode:
                meta_raw += delta
                continue
            idx = buf.find(C.META_SENTINEL)
            if idx >= 0:
                prose = buf[:idx]
                for event in emit(parser.feed(prose)):
                    yield event
                meta_mode = True
                meta_raw = buf[idx + len(C.META_SENTINEL):]
                buf = ""
            else:
                safe = len(buf) - (len(C.META_SENTINEL) - 1)
                if safe > 0:
                    prose = buf[:safe]
                    for event in emit(parser.feed(prose)):
                        yield event
                    buf = buf[safe:]
        if not meta_mode:
            # 没有哨兵：残余仍交给 parser，格式 miss 时降级为 narration beat。
            for event in emit(parser.feed(buf)):
                yield event
        else:
            meta = prompts.extract_meta(C.META_SENTINEL + meta_raw)
            self._last_meta = prompts.normalize_meta(
                meta, self.state.place, list(self.state.present))
        for event in emit(parser.finish()):
            yield event
        if not self._last_beats:
            fallback = {"type": "narration", "speaker": None,
                        "text": "（世界陷入了奇异的沉默……请重试一次。）"}
            self._last_beats.append(fallback)
            yield {"type": "beat", "beat": fallback}
        self._last_prose = beats_to_prose(self._last_beats)
        if self._last_meta is None:
            self._last_meta = prompts.normalize_meta(None, self.state.place, list(self.state.present))
        yield {"type": "meta", "meta": self._last_meta}

    # ================= 异步副作用 =================
    def _schedule_side_effects(self, turn):
        if self._closed:
            logger.warning("Skipping side effects for closed session %s", self.world_id)
            return
        self._loop = asyncio.get_running_loop()
        self._side_tasks.append(asyncio.create_task(self._side_effects(turn)))

    async def close(self):
        """Stop pending side effects before a session/world is discarded."""
        self._closed = True
        tasks = list(self._side_tasks)
        self._side_tasks = []
        for task in tasks:
            if not task.done():
                task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        await self.llm.close()

    async def _drain_side_effects(self, timeout=90):
        tasks = []
        for task in self._side_tasks:
            if task.done():
                try:
                    task.result()
                except asyncio.CancelledError:
                    logger.warning("Side-effect task was cancelled")
                except Exception:
                    logger.exception("Side-effect task failed")
            else:
                tasks.append(task)
        self._side_tasks = []
        if tasks:
            done, pending = await asyncio.wait(tasks, timeout=timeout)
            for task in done:
                try:
                    task.result()
                except asyncio.CancelledError:
                    logger.warning("Side-effect task was cancelled")
                except Exception:
                    logger.exception("Side-effect task failed")
            if pending:
                # Do not let a slow provider task from turn N write events
                # after turn N+1 has started.  The turn itself is already
                # committed; a timed-out auxiliary effect is best-effort and
                # must be cancelled at the boundary to preserve ordering.
                for task in pending:
                    task.cancel()
                await asyncio.gather(*pending, return_exceptions=True)
                logger.warning("Cancelled %d side-effect task(s) after %ss timeout", len(pending), timeout)

    async def _side_effects(self, turn):
        action = turn["player_action"] or "（冒险开始）"
        narrative = turn["narrative"]
        present = turn["meta"].get("present") or []

        # 1) NPC 心智 + 属性/物品变化。每个副作用独立失败，避免一个辅助
        # 模型超时把世界时钟和记忆结晶一起吞掉。
        try:
            knowledge = {name: self.state.npc_knowledge_window(name)
                         for name in present if name in self.state.npcs}
            unknown_present = [name for name in present if name not in self.state.npcs]
            npc_context = ""
            if unknown_present:
                npc_context = ("\n\n【本回合首次出现、待建立人物卡的名字】\n" +
                               "、".join(unknown_present))
            npc_sections = ("\n\n".join(
                npc_mind.npc_section(
                    name, self.state.npcs[name], knowledge.get(name, ""))
                for name in present if name in self.state.npcs
            ) or "（当前无已知 NPC 在场；只判断玩家属性、物品和主线是否变化）") + npc_context
            updates, new_npcs, plot_advanced, plot_update, attr_changes, item_changes = (
                await npc_mind.update_minds(
                    self.llm, self.state.npcs, present, action, narrative,
                    self.state.player["attrs"], self.state.main_plot, knowledge,
                    npc_sections=npc_sections))
            if new_npcs:
                self._append("NPC_ADD", {"npcs": new_npcs})
            if updates:
                self._append("NPC_STATE", {"npcs": updates})
            if attr_changes:
                self._append("ATTR_CHANGE", {"changes": attr_changes})
            if item_changes.get("add") or item_changes.get("remove"):
                self._append("ITEM_CHANGE", item_changes)
            if plot_update:
                self._append("MAIN_PLOT_UPDATE", {"main_plot": plot_update})
            if plot_advanced:
                self._append("PLOT_PROGRESS", {})
        except Exception:
            logger.exception("NPC side effect failed")

        # 2) 世界推进：使用累计的、尚未被 WORLD_TICK 消费的叙事分钟数。
        try:
            pending_minutes = self.state.world_tick_pending_minutes
            if pending_minutes >= C.WORLD_TICK_MIN_MINUTES:
                offscreen_npcs = {
                    name: npc for name, npc in self.state.npcs.items()
                    if name not in self.state.present
                }
                tick = await world_reactor.world_tick(
                    self.llm, pending_minutes, self.state.main_plot,
                    self.state.tick_summary(), self.state.world_threads,
                    offscreen_npcs, self.state.present)
                if not tick.get("ok", True):
                    logger.warning("World tick did not complete; retaining %s pending minutes",
                                   pending_minutes)
                else:
                    # 即使 LLM 没生成可见变化，也必须记录消费事件，否则同一
                    # 段时间会在下一回合被重复推进。
                    tick["minutes"] = pending_minutes
                    self._append("WORLD_TICK", tick)
        except Exception:
            logger.exception("World tick side effect failed")

        # 3) 记忆结晶
        try:
            pending_turns = self.state.pending_crystal_turns
            pending_ticks = self.state.pending_crystal_world_ticks
            source_turn_count = self.state._turn_crystal_cursor
            # WORLD_TICK can trigger a crystal before four turns are ready.
            # Advance by the number actually included in the batch so those
            # turns are not summarized again on a later crystal.
            source_turn_count += min(len(pending_turns), C.CRYSTAL_INTERVAL)
            events = await self.mem.crystallize(
                self.llm,
                pending_turns,
                pending_ticks,
                source_turn_count=source_turn_count,
                source_world_tick_count=self.state.world_tick_count,
            )
            for etype, data in events:
                self._append(etype, data)
        except Exception:
            logger.exception("Memory side effect failed")

    # ================= 上下文组装 =================
    def _narrator_system(self):
        rules = self.config.get("world_rules") or "（无特殊规则）"
        notes = self.config.get("custom_notes")
        if notes:
            rules += "\n【用户补充设定（与世界规则同等效力）】\n" + notes
        return prompts.NARRATOR_SYSTEM.format(
            world_setting=self.config.get("world_setting") or "（自由世界）",
            world_rules=rules,
            tone=self.config.get("tone") or "（默认：沉浸、克制、有张力）",
        )

    def _narrator_user(self, action):
        st = self.state
        # 记忆检索：查询 = 玩家行动 + 最近两回合的叙事
        query = action + " " + " ".join(
            t["narrative"][:200] for t in st.recent_turns(2))
        pressure = st.plot_pressure
        if st.turns_since_plot >= C.PLOT_PRESSURE_TURNS and st.main_plot:
            pressure = (pressure + " " if pressure else "") + \
                       f"主线已经 {st.turns_since_plot} 回合无实质推进，必须开始主动介入。"

        knowledge = {name: st.npc_knowledge_window(name)
                     for name in st.present if name in st.npcs}
        state_text = prompts.state_block(
            st.player, st.npcs, st.display_time(), st.place, st.present, knowledge)
        thread_text = prompts.thread_block(st.main_plot, pressure, st.world_threads)
        fixed_chars = len(state_text) + len(thread_text) + len(action) + 180
        available = max(0, C.CONTEXT_BUDGET_CHARS - fixed_chars)
        memory_budget = min(C.MEMORY_BUDGET_CHARS, available)
        mem_segments = self.mem.build_context(query, st.present, budget=memory_budget)
        mem_block = prompts.memory_block(mem_segments)
        # Return unused memory capacity to recent history instead of reserving
        # a fixed 40/60 split.
        history_budget = max(0, available - len(mem_block))

        return prompts.narrator_user_message(
            state_text,
            mem_block,
            thread_text,
            prompts.history_block(st.recent_turns(), budget=history_budget),
            action,
        )

    def _npc_cards_desc(self):
        lines = []
        for n, v in self.state.npcs.items():
            lines.append(f"- {n}：{v['identity']}；与玩家关系：{v['relationship']}")
        return "\n".join(lines) or "（无初始人物，请根据世界设定自行安排）"

    # ================= 持久化与杂项 =================
    async def _parse_npc_cards(self):
        try:
            raw = await self.llm.chat(
                [{"role": "system", "content": prompts.NPC_CARDS_SYSTEM},
                 {"role": "user", "content": prompts.npc_cards_user_message(
                     self.config.get("world_setting") or "", self.config.get("important_people") or "")}],
                aux=True, max_tokens=1200)
            obj = _loads(raw) or {}
            cards = obj.get("npcs") or []
            if isinstance(cards, list) and cards:
                self.config["npc_cards"] = [c for c in cards if isinstance(c, dict) and c.get("name")]
            if isinstance(obj.get("main_plot"), str) and obj["main_plot"].strip():
                self.config["main_plot"] = obj["main_plot"].strip()[:200]
            self.db.save_world_config(self.world_id, self.config)
            self.state = WorldState.rebuild(self.db.get_events(self.world_id), self.config)
            self.mem = MemoryEngine(self.state.crystals)
        except Exception:
            logger.exception("NPC card parsing failed")

    def _turn_state_snapshots(self):
        """Rebuild the public state at the end of each explored turn.

        Events after a turn (NPC, inventory, world and memory side effects) are
        included up to the next TURN boundary, so the UI can inspect a node's
        state without exposing private NPC fields.
        """
        events = self.db.get_events(self.world_id)
        state = WorldState(self.config)
        snapshots = []
        open_turn = None
        for etype, data in events:
            # Side effects belong to the preceding turn. Capture that state
            # before applying the next TURN event, so each snapshot is built
            # by one event-stream pass instead of rebuilding an ever-growing
            # prefix for every turn.
            if etype == "TURN" and open_turn is not None:
                snapshots[open_turn] = state.drawer_snapshot()
            state.apply(etype, data)
            if etype == "TURN":
                snapshots.append(None)
                open_turn = len(snapshots) - 1
        if open_turn is not None:
            snapshots[open_turn] = state.drawer_snapshot()
        return snapshots

    def _commit_turn(self, turn):
        meta = turn.get("meta") or {}
        turn["witnessed_by"] = list(meta.get("present") or [])
        self._append("TURN", turn)

    def _append(self, etype, data):
        if self._closed:
            logger.warning("Ignoring %s event for closed world %s", etype, self.world_id)
            return None
        seq = self.db.append_event(self.world_id, etype, data)
        self.state.apply(etype, data)
        return seq

    def _history_payload(self):
        snapshots = self._turn_state_snapshots()
        turns = [{
            "player_action": t["player_action"],
            "narrative": t["narrative"],
            "meta": t["meta"],
            "time_display": t["time_display"],
            "attr_changes": dict(t.get("attr_changes") or {}),
            "item_changes": t.get("item_changes") or {"add": [], "remove": []},
            "state_after": snapshots[i] if i < len(snapshots) else None,
        } for i, t in enumerate(self.state.turns)]
        return {
            "turns": turns,
            "state": self.state.drawer_snapshot(),
            "initial_attrs": dict((self.config.get("player") or {}).get("attrs") or {}),
        }

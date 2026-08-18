"""世界状态：从事件流重建的内存态（借鉴 Project Lunar 的事件溯源模式）。

事件类型见 db.py 文档。重建是唯一的事实来源——内存态只是事件流的投影。
"""
import re
from datetime import datetime, timedelta

from . import config as C


_PATCHABLE_NPC_FIELDS = ("status", "personality", "desire", "current_thought")


def _npc_state(card):
    return {
        "name": str(card.get("name") or "").strip(),
        "age": card.get("age") or "",
        "identity": card.get("identity") or "",
        "status": card.get("status") or "",
        "qualities": dict(card.get("qualities") or {}),
        "personality": card.get("personality") or "",
        "desire": card.get("desire") or "",
        "background": card.get("background") or "",
        "current_thought": card.get("current_thought") or "",
    }


def parse_start_time(text):
    """支持中文日期和 ISO 格式；无效值使用稳定兜底，避免重建时漂移。"""
    if text:
        m = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日(?:\s*(\d{1,2}):(\d{2}))?", str(text))
        if m:
            y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
            hh, mm = int(m.group(4) or 9), int(m.group(5) or 0)
            try:
                return datetime(y, mo, d, hh, mm)
            except ValueError:
                pass
        try:
            return datetime.fromisoformat(str(text))
        except ValueError:
            pass
    # New worlds persist a generated start_time at creation, and old worlds
    # are migrated from created_at by GameSession. This final deterministic
    # fallback prevents a malformed legacy config from changing every time
    # the event stream is rebuilt.
    return datetime(2000, 1, 1, 0, 0)


class WorldState:
    def __init__(self, config):
        self.config = config
        p = config.get("player") or {}
        self.player = {
            "name": p.get("name") or "无名者",
            "identity": p.get("identity") or "旅行者",
            "background": p.get("background") or "",
            "attrs": dict(p.get("attrs") or {}),
            "key_items": list(p.get("key_items") or []),
            "status": str(p.get("status") or "").strip(),
        }
        self.npcs = {}
        for card in config.get("npc_cards") or []:
            name = str(card.get("name") or "").strip()
            if not name:
                continue
            self.npcs[name] = _npc_state(card)
        # 有向稀疏关系表：(from, to) -> {"favor": 0..100, "bond": str}
        self.relationships = {}
        for rel in config.get("initial_relationships") or []:
            frm = str(rel.get("from") or "").strip()
            to = str(rel.get("to") or "").strip()
            if not frm or not to:
                continue
            try:
                favor = max(0, min(100, int(rel.get("favor") or 50)))
            except (TypeError, ValueError):
                favor = 50
            self.relationships[(frm, to)] = {
                "favor": favor,
                "bond": str(rel.get("bond") or "").strip(),
            }
        # Only characters the protagonist has encountered belong in the public
        # character view. `present` is emitted by each narrator turn and is the
        # existing witness signal used by the game state.
        self.seen_npcs = set()
        self.main_plot = config.get("main_plot") or ""
        self.plot_pressure = ""
        self.world_threads = []
        self.world_tick_events = []
        self.world_tick_count = 0
        self._world_tick_crystal_cursor = 0
        self.turns = []           # {player_action, narrative, beats, meta, time_display}
        self.time_minutes = 0
        self.world_tick_pending_minutes = 0
        self.place = config.get("start_place") or "未知地点"
        self.present = []
        self.turn_count = 0
        self.turns_since_plot = 0
        self.crystals = {"short": [], "medium": [], "long": [], "permanent": []}
        self.important_events = []       # {summary, participants, witnessed_by, importance, chapter}
        self.chapters = []               # {index, frame, start_seq}
        self.chapter_ends = []           # {index, summary, ...}
        self.current_chapter = 0
        self._short_crystal_count = 0
        self._turn_crystal_cursor = 0
        self.start_dt = parse_start_time(config.get("start_time"))

    # ---------------- 重建 ----------------
    @classmethod
    def rebuild(cls, events, config):
        st = cls(config)
        for etype, data in events:
            st.apply(etype, data)
        return st

    def apply(self, etype, data):
        if etype == "TURN":
            meta = data.get("meta") or {}
            minutes = int(meta.get("minutes") or 0)
            self.time_minutes += minutes
            self.world_tick_pending_minutes += minutes
            if meta.get("place"):
                self.place = meta["place"]
            self.present = list(meta.get("present") or [])
            self.seen_npcs.update(name for name in self.present if name in self.npcs)
            self.turn_count += 1
            self.turns_since_plot += 1
            witnessed = data.get("witnessed_by")
            if not isinstance(witnessed, list):
                witnessed = meta.get("present") if isinstance(meta.get("present"), list) else []
            self.turns.append({
                "player_action": data.get("player_action"),
                "narrative": data.get("narrative") or "",
                "beats": list(data.get("beats") or []),
                "meta": meta,
                "time_display": self.display_time(),
                "witnessed_by": list(witnessed),
                "chapter": self.current_chapter,
                "attr_changes": {},
                "item_changes": {"add": [], "remove": []},
            })
        elif etype == "NPC_STATE":
            for name, fields in (data.get("npcs") or {}).items():
                npc = self.npcs.get(name)
                if not npc or not isinstance(fields, dict):
                    continue
                for k in _PATCHABLE_NPC_FIELDS:
                    v = fields.get(k)
                    if isinstance(v, str) and v.strip():
                        npc[k] = v.strip()
        elif etype == "NPC_ADD":
            for name, card in (data.get("npcs") or {}).items():
                name = str(name).strip()
                if not name or name in self.npcs or not isinstance(card, dict):
                    continue
                self.npcs[name] = _npc_state(card)
                if name in self.present:
                    self.seen_npcs.add(name)
        elif etype == "REL_UPDATE":
            frm = str(data.get("from") or "").strip()
            to = str(data.get("to") or "").strip()
            if not frm or not to:
                return
            key = (frm, to)
            cur = self.relationships.get(key)
            if cur is None:
                # 首次建立关系：默认 favor=50 再叠加 delta。
                cur = {"favor": 50, "bond": ""}
                self.relationships[key] = cur
            try:
                delta = int(data.get("favor_delta") or 0)
            except (TypeError, ValueError):
                delta = 0
            cur["favor"] = max(0, min(100, cur["favor"] + delta))
            bond = str(data.get("bond") or "").strip()
            if bond:
                cur["bond"] = bond
        elif etype == "QUALITY_UPDATE":
            entity = str(data.get("entity") or "").strip()
            changes = data.get("changes") or {}
            target = self.npcs.get(entity) if entity else None
            if not target or not isinstance(changes, dict):
                return
            quals = target.setdefault("qualities", {})
            for q, d in changes.items():
                if not isinstance(q, str) or not q:
                    continue
                try:
                    delta = int(d)
                except (TypeError, ValueError):
                    continue
                if q in quals:
                    quals[q] = max(0, min(100, int(quals[q]) + delta))
        elif etype == "ATTR_CHANGE":
            for k, d in (data.get("changes") or {}).items():
                if k in self.player["attrs"]:
                    self.player["attrs"][k] = max(0, min(100, self.player["attrs"][k] + int(d)))
                    if self.turns:
                        prev = self.turns[-1]["attr_changes"].get(k, 0)
                        self.turns[-1]["attr_changes"][k] = prev + int(d)
        elif etype == "ITEM_CHANGE":
            for it in data.get("add") or []:
                if it not in self.player["key_items"]:
                    self.player["key_items"].append(it)
                    if self.turns:
                        self.turns[-1]["item_changes"]["add"].append(it)
            for it in data.get("remove") or []:
                if it in self.player["key_items"]:
                    self.player["key_items"].remove(it)
                    if self.turns:
                        self.turns[-1]["item_changes"]["remove"].append(it)
        elif etype == "IMPORTANT_EVENT":
            summary = str(data.get("summary") or "").strip()
            if not summary:
                return
            self.important_events.append({
                "summary": summary[:160],
                "participants": list(data.get("participants") or []),
                "witnessed_by": list(data.get("witnessed_by")
                                    or data.get("participants") or []),
                "importance": data.get("importance") if data.get("importance") in ("major", "minor") else "minor",
                "chapter": self.current_chapter,
            })
            self.important_events = self.important_events[-C.MAX_IMPORTANT_EVENTS:]
        elif etype == "PLAYER_UPDATE":
            status = str(data.get("status") or "").strip()
            if status:
                self.player["status"] = status
        elif etype == "CHAPTER":
            index = int(data.get("index") or (self.current_chapter + 1))
            self.current_chapter = index
            frame = data.get("frame") if isinstance(data.get("frame"), dict) else {}
            self.chapters.append({
                "index": index,
                "frame": frame,
                "start_seq": data.get("seq") or data.get("start_seq"),
            })
        elif etype == "CHAPTER_END":
            self.chapter_ends.append(dict(data))
            self.chapter_ends = self.chapter_ends[-C.MAX_CHAPTER_ENDS:]
        elif etype == "WORLD_TICK":
            consumed = max(0, int(data.get("minutes") or 0))
            self.world_tick_pending_minutes = max(
                0, self.world_tick_pending_minutes - consumed)
            self.world_threads = (self.world_threads + list(data.get("developments") or []))[-5:]
            # Every successful tick is the authoritative pressure snapshot;
            # an empty value is meaningful and clears stale pressure.
            self.plot_pressure = str(data.get("plot_pressure") or "")[:120]
            self.world_tick_count += 1
            self.world_tick_events.append({
                "minutes": consumed,
                "developments": list(data.get("developments") or []),
                "plot_pressure": data.get("plot_pressure") or "",
                "npc_updates": dict(data.get("npc_updates") or {}),
            })
            # Keep off-screen NPC progression in the same event as the tick,
            # so rebuilding after an interrupted side effect cannot lose it.
            for name, fields in (data.get("npc_updates") or {}).items():
                npc = self.npcs.get(name)
                if not npc or not isinstance(fields, dict):
                    continue
                for k in _PATCHABLE_NPC_FIELDS:
                    v = fields.get(k)
                    if isinstance(v, str) and v.strip():
                        npc[k] = v.strip()
        elif etype == "MAIN_PLOT_UPDATE":
            plot = str(data.get("main_plot") or "").strip()
            if plot:
                self.main_plot = plot[:240]
        elif etype == "CRYSTAL":
            layer = data.get("layer")
            if layer == "short":
                self._short_crystal_count += 1
                if "source_turn_count" in data:
                    try:
                        self._turn_crystal_cursor = max(
                            self._turn_crystal_cursor, int(data.get("source_turn_count") or 0))
                    except (TypeError, ValueError):
                        pass
                else:
                    # Compatibility with crystals written before source
                    # cursors were persisted.
                    self._turn_crystal_cursor += C.CRYSTAL_INTERVAL
                try:
                    self._world_tick_crystal_cursor = max(
                        self._world_tick_crystal_cursor,
                        int(data.get("source_world_tick_count") or 0))
                except (TypeError, ValueError):
                    pass
            self.crystals.setdefault(layer, []).append(data.get("crystal") or {})
        elif etype == "CRYSTAL_POP":
            layer = data.get("layer")
            n = int(data.get("count") or 0)
            if layer in self.crystals:
                self.crystals[layer] = self.crystals[layer][:-n] if n else self.crystals[layer]
        elif etype == "PLOT_PROGRESS":
            self.turns_since_plot = 0

    # ---------------- 派生 ----------------
    def display_time(self):
        dt = self.start_dt + timedelta(minutes=self.time_minutes)
        return f"{dt.year}年{dt.month}月{dt.day}日 {dt.hour:02d}:{dt.minute:02d}"

    @property
    def pending_crystal_turns(self):
        return self.turns[self._turn_crystal_cursor:]

    @property
    def pending_crystal_world_ticks(self):
        return self.world_tick_events[self._world_tick_crystal_cursor:]

    def npc_knowledge_window(self, name, budget=C.NPC_KNOWLEDGE_BUDGET_CHARS):
        """Return only the recent turn history this NPC actually witnessed.

        `witnessed_by` is persisted on TURN events, so this projection survives
        a restart and cannot accidentally expose an off-screen scene to an NPC.
        """
        if not name:
            return ""
        lines = []
        used = 0
        for turn in reversed(self.turns):
            witnesses = turn.get("witnessed_by") or turn.get("meta", {}).get("present") or []
            if name not in witnesses:
                continue
            action = turn.get("player_action") or "（开局）"
            line = f"玩家：{action}\n剧情：{turn.get('narrative') or ''}"
            if used + len(line) > budget:
                if not lines and budget > 0:
                    lines.append(line[:budget])
                break
            lines.append(line)
            used += len(line)
        if not lines:
            return "（没有目击到更早的相关事件）"
        return "\n\n".join(reversed(lines))

    def relationship_context(self, names, budget=C.RELATIONSHIP_BUDGET_CHARS):
        """当前剧情相关的有向关系：任一端点在 names（或在场 NPC）或玩家，按预算注入。

        关系数据只供叙事者参考，绝不进玩家抽屉。
        """
        if not self.relationships:
            return ""
        wanted = set(names or [])
        player = self.player.get("name")
        if player:
            wanted.add(player)
        lines = []
        used = 0
        for (frm, to), rel in sorted(self.relationships.items()):
            if frm not in wanted and to not in wanted:
                continue
            line = f"{frm} → {to}：好感 {rel['favor']}"
            if rel.get("bond"):
                line += f"；羁绊：{rel['bond']}"
            if used + len(line) + 1 > budget:
                if not lines:
                    lines.append(line[:budget])
                break
            lines.append(line)
            used += len(line) + 1
        return "\n".join(lines)

    # ---------------- 抽屉（玩家视角） ----------------
    def drawer_snapshot(self):
        return {
            "character": {
                "player": dict(self.player),
                # 玩家视角只暴露最基本信息：身份/年龄/现状。关系、内心、品质全部隐藏。
                "npcs": [{
                    "name": n,
                    "identity": v["identity"],
                    "status": v["status"],
                } for n, v in self.npcs.items() if n in self.seen_npcs],
            },
            "status": {
                "time": self.display_time(),
                "place": self.place,
                "attrs": dict(self.player["attrs"]),
                "key_items": list(self.player["key_items"]),
            },
            # Director state and hidden world memory stay server-side. The
            # public drawer only exposes player-facing character/status data.
            "world": {},
        }

    def tick_summary(self):
        attrs = "，".join(f"{k}{v}" for k, v in self.player["attrs"].items())
        return (f"世界设定：{self.config.get('world_setting') or '（无）'}；"
                f"世界规则：{self.config.get('world_rules') or '（无特殊规则）'}；"
                f"当前时间：{self.display_time()}；当前地点：{self.place}；"
                f"玩家：{self.player['name']}（{self.player['identity']}，{attrs}）；"
                f"关键人物：{'、'.join(self.npcs) or '无'}；"
                f"主线：{self.main_plot}；当前压力：{self.plot_pressure or '无'}")

    def recent_turns(self, n=C.RECENT_RAW_TURNS):
        return self.turns[-n:]

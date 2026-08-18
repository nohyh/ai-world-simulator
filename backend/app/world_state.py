"""世界状态：从事件流重建的内存态（借鉴 Project Lunar 的事件溯源模式）。

事件类型见 db.py 文档。重建是唯一的事实来源——内存态只是事件流的投影。
"""
import re
from datetime import datetime, timedelta

from . import config as C


def _npc_state(card):
    try:
        feeling_turn = int(card.get("feeling_turn") or -1)
    except (TypeError, ValueError):
        feeling_turn = -1
    return {
        "identity": card.get("identity") or "",
        "personality": card.get("personality") or "",
        "relationship": card.get("relationship") or "陌生",
        "goal": card.get("goal") or "",
        "secret_plan": card.get("secret_plan") or "",
        "opinion_of_player": card.get("opinion_of_player") or "",
        "feeling": card.get("feeling") or "",
        "feeling_turn": feeling_turn,
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
        }
        self.npcs = {}
        for card in config.get("npc_cards") or []:
            name = str(card.get("name") or "").strip()
            if not name:
                continue
            self.npcs[name] = _npc_state(card)
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
                "attr_changes": {},
                "item_changes": {"add": [], "remove": []},
            })
        elif etype == "NPC_STATE":
            for name, fields in (data.get("npcs") or {}).items():
                npc = self.npcs.get(name)
                if not npc:
                    continue
                for k, v in fields.items():
                    if k in npc:
                        npc[k] = v
                if "feeling" in fields:
                    npc["feeling_turn"] = self.turn_count
        elif etype == "NPC_ADD":
            for name, card in (data.get("npcs") or {}).items():
                name = str(name).strip()
                if not name or name in self.npcs or not isinstance(card, dict):
                    continue
                self.npcs[name] = _npc_state(card)
                if name in self.present:
                    self.seen_npcs.add(name)
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
                for key, value in fields.items():
                    if key in npc:
                        npc[key] = value
                if "feeling" in fields:
                    npc["feeling_turn"] = self.turn_count
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

    def decay_feelings(self):
        for npc in self.npcs.values():
            if npc["feeling"] and self.turn_count - npc["feeling_turn"] > C.FEELING_DECAY_TURNS:
                npc["feeling"] = ""

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

    # ---------------- 抽屉（玩家视角） ----------------
    def drawer_snapshot(self):
        return {
            "character": {
                "player": dict(self.player),
                "npcs": [{
                    "name": n,
                    "identity": v["identity"],
                    "relationship": v["relationship"],
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

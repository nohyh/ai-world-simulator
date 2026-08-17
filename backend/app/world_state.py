"""世界状态：从事件流重建的内存态（借鉴 Project Lunar 的事件溯源模式）。

事件类型见 db.py 文档。重建是唯一的事实来源——内存态只是事件流的投影。
"""
import re
from datetime import datetime, timedelta

from . import config as C


def parse_start_time(text):
    """支持 '2041年7月16日 08:00'、ISO 格式；失败返回当前时间。"""
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
    return datetime.now().replace(microsecond=0)


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
            self.npcs[name] = {
                "identity": card.get("identity") or "",
                "personality": card.get("personality") or "",
                "relationship": card.get("relationship") or "陌生",
                "goal": card.get("goal") or "",
                "secret_plan": card.get("secret_plan") or "",
                "opinion_of_player": "",
                "feeling": "",
                "feeling_turn": -1,
            }
        # Only characters the protagonist has encountered belong in the public
        # character view. `present` is emitted by each narrator turn and is the
        # existing witness signal used by the game state.
        self.seen_npcs = set()
        self.main_plot = config.get("main_plot") or ""
        self.plot_pressure = ""
        self.world_threads = []
        self.turns = []           # {player_action, narrative, meta, time_display}
        self.time_minutes = 0
        self.place = config.get("start_place") or "未知地点"
        self.present = []
        self.turn_count = 0
        self.turns_since_plot = 0
        self.crystals = {"short": [], "medium": [], "long": [], "permanent": []}
        self._short_crystal_count = 0
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
            self.time_minutes += int(meta.get("minutes") or 0)
            if meta.get("place"):
                self.place = meta["place"]
            self.present = list(meta.get("present") or [])
            self.seen_npcs.update(name for name in self.present if name in self.npcs)
            self.turn_count += 1
            self.turns_since_plot += 1
            self.turns.append({
                "player_action": data.get("player_action"),
                "narrative": data.get("narrative") or "",
                "meta": meta,
                "time_display": self.display_time(),
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
            self.world_threads = (self.world_threads + list(data.get("developments") or []))[-5:]
            if data.get("plot_pressure"):
                self.plot_pressure = data["plot_pressure"]
        elif etype == "CRYSTAL":
            layer = data.get("layer")
            if layer == "short":
                self._short_crystal_count += 1
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
        start = self._short_crystal_count * C.CRYSTAL_INTERVAL
        return self.turns[start:]

    def decay_feelings(self):
        for npc in self.npcs.values():
            if npc["feeling"] and self.turn_count - npc["feeling_turn"] > C.FEELING_DECAY_TURNS:
                npc["feeling"] = ""

    # ---------------- 抽屉（玩家视角） ----------------
    def drawer_snapshot(self):
        chronicle = []
        for layer in ("short", "medium", "long"):
            for c in reversed(self.crystals.get(layer, [])):
                chronicle.append(c.get("summary") or "")
                if len(chronicle) >= 8:
                    break
            if len(chronicle) >= 8:
                break
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
                "plot_pressure": self.plot_pressure,
            },
            "world": {
                "main_plot": self.main_plot,
                "threads": list(self.world_threads),
                "chronicle": [c for c in chronicle if c],
            },
        }

    def tick_summary(self):
        attrs = "，".join(f"{k}{v}" for k, v in self.player["attrs"].items())
        return (f"玩家：{self.player['name']}（{self.player['identity']}，{attrs}）；"
                f"关键人物：{'、'.join(self.npcs) or '无'}；"
                f"主线：{self.main_plot}；当前压力：{self.plot_pressure or '无'}")

    def recent_turns(self, n=C.RECENT_RAW_TURNS):
        return self.turns[-n:]

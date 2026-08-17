"""SQLite 存储：世界配置表 + 事件溯源表。

事件类型（type 字段）：
  TURN         一回合完整记录 {player_action, narrative, choices, minutes, place, present}
  NPC_STATE    NPC 私有状态更新 {npcs: {name: {...}}}
  ATTR_CHANGE  玩家属性变化 {changes: {attr: delta}}
  ITEM_CHANGE  关键物品变化 {add: [], remove: []}
  WORLD_TICK   离屏世界推进 {developments: [], plot_pressure: str}
  CRYSTAL      记忆结晶 {layer, crystal}
"""
import json
import sqlite3
import threading
import time
import uuid

_SCHEMA = """
CREATE TABLE IF NOT EXISTS worlds (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    config TEXT NOT NULL,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    world_id TEXT NOT NULL,
    seq INTEGER NOT NULL,
    type TEXT NOT NULL,
    data TEXT NOT NULL,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_world ON events(world_id, seq);
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

_SETTINGS_KEY = "llm"


class Database:
    def __init__(self, path):
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.commit()

    # ---- 世界 ----
    def list_worlds(self):
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM worlds ORDER BY updated_at DESC"
            ).fetchall()
        out = []
        for r in rows:
            cfg = json.loads(r["config"])
            out.append({
                "id": r["id"], "title": r["title"],
                "updated_at": r["updated_at"],
                "has_opening": bool(cfg.get("_has_opening")),
            })
        return out

    def create_world(self, config, title):
        wid = uuid.uuid4().hex[:12]
        now = time.time()
        with self._lock:
            self._conn.execute(
                "INSERT INTO worlds (id, title, config, created_at, updated_at) VALUES (?,?,?,?,?)",
                (wid, title, json.dumps(config, ensure_ascii=False), now, now),
            )
            self._conn.commit()
        return wid

    def get_world(self, wid):
        with self._lock:
            r = self._conn.execute("SELECT * FROM worlds WHERE id=?", (wid,)).fetchone()
        if not r:
            return None
        return {"id": r["id"], "title": r["title"],
                "config": json.loads(r["config"]),
                "created_at": r["created_at"], "updated_at": r["updated_at"]}

    def save_world_config(self, wid, config):
        with self._lock:
            self._conn.execute(
                "UPDATE worlds SET config=?, updated_at=? WHERE id=?",
                (json.dumps(config, ensure_ascii=False), time.time(), wid),
            )
            self._conn.commit()

    def touch_world(self, wid):
        with self._lock:
            self._conn.execute("UPDATE worlds SET updated_at=? WHERE id=?", (time.time(), wid))
            self._conn.commit()

    def delete_world(self, wid):
        with self._lock:
            self._conn.execute("DELETE FROM worlds WHERE id=?", (wid,))
            self._conn.execute("DELETE FROM events WHERE world_id=?", (wid,))
            self._conn.commit()

    def last_world_config(self):
        """最近一个世界的模型配置，用于创建表单预填。"""
        with self._lock:
            r = self._conn.execute(
                "SELECT config FROM worlds ORDER BY updated_at DESC LIMIT 1"
            ).fetchone()
        if not r:
            return None
        cfg = json.loads(r["config"])
        return {k: cfg.get(k) for k in
                ("provider", "base_url", "api_key", "model", "aux_model")}

    # ---- 全局设置（模型配置）----
    def get_settings(self):
        with self._lock:
            r = self._conn.execute(
                "SELECT value FROM settings WHERE key=?", (_SETTINGS_KEY,)
            ).fetchone()
        return json.loads(r["value"]) if r else {}

    def set_settings(self, obj):
        with self._lock:
            self._conn.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (_SETTINGS_KEY, json.dumps(obj, ensure_ascii=False)),
            )
            self._conn.commit()

    # ---- 事件 ----
    def append_event(self, wid, etype, data):
        now = time.time()
        with self._lock:
            row = self._conn.execute(
                "SELECT COALESCE(MAX(seq), 0) FROM events WHERE world_id=?", (wid,)
            ).fetchone()
            seq = row[0] + 1
            self._conn.execute(
                "INSERT INTO events (world_id, seq, type, data, created_at) VALUES (?,?,?,?,?)",
                (wid, seq, etype, json.dumps(data, ensure_ascii=False), now),
            )
            self._conn.commit()
        return seq

    def get_events(self, wid):
        with self._lock:
            rows = self._conn.execute(
                "SELECT type, data FROM events WHERE world_id=? ORDER BY seq", (wid,)
            ).fetchall()
        return [(r["type"], json.loads(r["data"])) for r in rows]

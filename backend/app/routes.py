"""API 路由：世界 CRUD + 游戏 SSE。"""
import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from . import config as C
from .db import Database
from .game_session import get_session, drop_session, drop_all_sessions

router = APIRouter(prefix="/api")
db: Database = None  # main.py 启动时注入


# ---------------- 模型 ----------------
class WorldCreate(BaseModel):
    title: str = ""
    world_setting: str = Field(min_length=1)
    world_rules: str = ""
    tone: str = ""
    current_situation: str = ""
    custom_notes: str = ""
    start_time: str = ""
    start_place: str = ""
    player_name: str = "旅人"
    player_identity: str = ""
    player_background: str = ""
    attrs: dict[str, int] = Field(default_factory=lambda: {"力量": 50, "智力": 50, "魅力": 50, "体质": 50})
    important_people: str = ""
    # 兼容旧客户端：模型配置已迁移到全局设置，忽略
    provider: str = ""
    base_url: str = ""
    api_key: str = ""
    model: str = ""
    aux_model: str = ""
    temperature: float | None = None


class ActionRequest(BaseModel):
    input: str = Field(min_length=1, max_length=2000)


class SettingsBody(BaseModel):
    provider: str = ""
    base_url: str = ""
    api_key: str = ""
    model: str = ""
    aux_model: str = ""


def _auto_title(body: WorldCreate) -> str:
    if body.title.strip():
        return body.title.strip()[:60]
    for line in body.world_setting.splitlines():
        line = line.strip().strip("。，、！？；：")
        if line:
            return line[:16]
    return "新世界"


# ---------------- 世界 ----------------
@router.get("/worlds")
def list_worlds():
    return db.list_worlds()


@router.post("/worlds")
def create_world(body: WorldCreate):
    cfg = {
        "world_setting": body.world_setting,
        "world_rules": body.world_rules,
        "tone": body.tone,
        "current_situation": body.current_situation,
        "custom_notes": body.custom_notes,
        "start_time": body.start_time,
        "start_place": body.start_place,
        "important_people": body.important_people,
        "player": {
            "name": body.player_name or "旅人",
            "identity": body.player_identity,
            "background": body.player_background,
            "attrs": {k: max(0, min(100, v)) for k, v in body.attrs.items()},
            "key_items": [],
        },
    }
    wid = db.create_world(cfg, _auto_title(body))
    return {"id": wid}


@router.get("/worlds/{wid}")
def get_world(wid: str):
    w = db.get_world(wid)
    if not w:
        raise HTTPException(404, "世界不存在")
    cfg = dict(w["config"])
    cfg.pop("api_key", None)  # 不回传密钥
    return {"id": w["id"], "title": w["title"], "config": cfg,
            "updated_at": w["updated_at"]}


@router.delete("/worlds/{wid}")
def delete_world(wid: str):
    if not db.get_world(wid):
        raise HTTPException(404, "世界不存在")
    drop_session(wid)
    db.delete_world(wid)
    return {"ok": True}


# ---------------- 全局设置 ----------------
def _default_settings():
    return {"provider": C.DEFAULT_PROVIDER, "base_url": C.DEFAULT_BASE_URL,
            "api_key": "", "model": C.DEFAULT_MODEL, "aux_model": C.DEFAULT_AUX_MODEL}


@router.get("/settings")
def get_settings():
    s = {**_default_settings(), **(db.get_settings() or {})}
    return s


@router.put("/settings")
def put_settings(body: SettingsBody):
    cur = db.get_settings() or {}
    new = {k: (getattr(body, k) or cur.get(k) or "") for k in
           ("provider", "base_url", "api_key", "model", "aux_model")}
    db.set_settings(new)
    drop_all_sessions()  # 让所有会话用新配置重建
    return {"ok": True}


# ---------------- 游戏 ----------------
def _session(wid: str):
    w = db.get_world(wid)
    if not w:
        raise HTTPException(404, "世界不存在")
    return get_session(wid, w, db)


def _sse(gen):
    async def event_gen():
        try:
            async for ev in gen:
                yield f"event: {ev['type']}\ndata: {json.dumps(ev, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"event: error\ndata: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"
    return StreamingResponse(event_gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/game/{wid}/state")
def game_state(wid: str):
    s = _session(wid)
    return s.state.drawer_snapshot()


@router.get("/game/{wid}/history")
def game_history(wid: str):
    s = _session(wid)
    return s._history_payload()


@router.post("/game/{wid}/start")
async def game_start(wid: str):
    s = _session(wid)
    return _sse(s.ensure_opening())


@router.post("/game/{wid}/action")
async def game_action(wid: str, body: ActionRequest):
    s = _session(wid)
    # 副作用任务留在后台；下一次行动开始前由 process_action 内部等待回收
    return _sse(s.process_action(body.input))

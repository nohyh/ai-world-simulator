"""世界推进器：叙事时间跳跃时生成离屏变化（异步，辅助模型）。"""
import json
import logging

from . import config as C
from . import prompts

logger = logging.getLogger(__name__)


def _loads(raw):
    start = raw.find("{")
    if start < 0:
        return None
    end = raw.rfind("}")
    if end <= start:
        return None
    try:
        return json.loads(raw[start:end + 1])
    except json.JSONDecodeError:
        return None


def severity_for(minutes):
    if minutes >= 7 * 24 * 60:
        return "major"
    if minutes >= 24 * 60:
        return "moderate"
    return "minor"


async def world_tick(llm, minutes, main_plot, state_summary, threads, npcs=None):
    """生成离屏变化，并返回可回放的 NPC 私有更新。"""
    sev = severity_for(minutes)
    npc_lines = []
    for name, npc in (npcs or {}).items():
        npc_lines.append(
            f"- {name}：身份 {npc.get('identity', '')}；关系 {npc.get('relationship', '')}；"
            f"目标 {npc.get('goal', '') or '未记录'}；秘密计划 {npc.get('secret_plan', '') or '无'}；"
            f"当前情绪 {npc.get('feeling', '') or '未记录'}；对玩家看法 {npc.get('opinion_of_player', '') or '未记录'}"
        )
    try:
        raw = await llm.chat(
            [{"role": "system", "content": prompts.TICK_SYSTEM},
             {"role": "user", "content": prompts.tick_user_message(
                 minutes, sev, state_summary, "\n".join(threads), main_plot,
                 "\n".join(npc_lines))}],
            aux=True, max_tokens=600)
        obj = _loads(raw) or {}
    except Exception:
        logger.exception("World tick failed")
        return {"ok": False, "developments": [], "plot_pressure": "", "npc_updates": {}}
    devs = [str(d).strip()[:120] for d in (obj.get("developments") or []) if str(d).strip()][:3]
    pressure = str(obj.get("plot_pressure") or "").strip()[:120]
    npc_updates = {}
    allowed = set((npcs or {}).keys())
    for name, fields in (obj.get("npc_updates") or {}).items():
        if name not in allowed or not isinstance(fields, dict):
            continue
        update = {}
        for key in ("feeling", "goal", "opinion_of_player", "secret_plan"):
            value = fields.get(key)
            if isinstance(value, str) and value.strip():
                update[key] = value.strip()[:120]
        if update:
            npc_updates[name] = update
    return {"ok": True, "developments": devs, "plot_pressure": pressure, "npc_updates": npc_updates}

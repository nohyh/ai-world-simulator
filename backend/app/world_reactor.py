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


async def world_tick(llm, minutes, main_plot, state_summary, threads,
                     npcs=None, present=None):
    """生成离屏变化，并返回可回放的 NPC 私有更新。"""
    sev = severity_for(minutes)
    present = set(present or [])
    offscreen_npcs = {
        name: npc for name, npc in (npcs or {}).items()
        if name not in present
    }
    npc_lines = []
    for name, npc in offscreen_npcs.items():
        npc_lines.append(
            f"- {name}：身份 {npc.get('identity', '')}；现状 {npc.get('status', '') or '正常'}；"
            f"性格 {npc.get('personality', '') or '未知'}；愿望 {npc.get('desire', '') or '未记录'}；"
            f"当前想法 {npc.get('current_thought', '') or '未记录'}"
        )
    try:
        raw = await llm.chat(
            [{"role": "system", "content": prompts.TICK_SYSTEM},
             {"role": "user", "content": prompts.tick_user_message(
                 minutes, sev, state_summary, "\n".join(threads), main_plot,
                 "\n".join(npc_lines))}],
            aux=True, max_tokens=600)
        obj = _loads(raw)
        if not isinstance(obj, dict):
            return {"ok": False, "developments": [], "plot_pressure": "", "npc_updates": {}}
    except Exception:
        logger.exception("World tick failed")
        return {"ok": False, "developments": [], "plot_pressure": "", "npc_updates": {}}
    devs = [str(d).strip()[:120] for d in (obj.get("developments") or []) if str(d).strip()][:3]
    pressure = str(obj.get("plot_pressure") or "").strip()[:120]
    npc_updates = {}
    allowed = set(offscreen_npcs)
    for name, fields in (obj.get("npc_updates") or {}).items():
        if name not in allowed or not isinstance(fields, dict):
            continue
        update = {}
        for key in ("status", "current_thought", "desire"):
            value = fields.get(key)
            if isinstance(value, str) and value.strip():
                update[key] = value.strip()[:120]
        if update:
            npc_updates[name] = update
    return {"ok": True, "developments": devs, "plot_pressure": pressure, "npc_updates": npc_updates}

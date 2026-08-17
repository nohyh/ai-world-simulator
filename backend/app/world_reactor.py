"""世界推进器：叙事时间跳跃时生成离屏变化（异步，辅助模型）。"""
import json

from . import config as C
from . import prompts


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


async def world_tick(llm, minutes, main_plot, state_summary, threads):
    """返回 {"developments": [...], "plot_pressure": str}，失败返回空。"""
    sev = severity_for(minutes)
    try:
        raw = await llm.chat(
            [{"role": "system", "content": prompts.TICK_SYSTEM},
             {"role": "user", "content": prompts.tick_user_message(
                 minutes, sev, state_summary, "\n".join(threads), main_plot)}],
            aux=True, max_tokens=600)
        obj = _loads(raw) or {}
    except Exception:
        return {"developments": [], "plot_pressure": ""}
    devs = [str(d).strip()[:120] for d in (obj.get("developments") or []) if str(d).strip()][:3]
    pressure = str(obj.get("plot_pressure") or "").strip()[:120]
    return {"developments": devs, "plot_pressure": pressure}

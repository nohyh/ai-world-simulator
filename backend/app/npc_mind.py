"""NPC 私有心智更新 + 玩家属性/物品变化（异步副作用，辅助模型）。"""
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


def npc_section(name, npc, can_know):
    return (f"### {name}\n身份：{npc['identity']}\n与玩家关系：{npc['relationship']}\n"
            f"当前心智——情绪：{npc['feeling'] or '未记录'}；目标：{npc['goal'] or '未记录'}；"
            f"对玩家看法：{npc['opinion_of_player'] or '未记录'}；秘密计划：{npc['secret_plan'] or '无'}\n"
            f"【他可知的信息】{can_know}")


async def update_minds(llm, npcs, present, action, narrative, player_attrs,
                       main_plot="", knowledge_by_npc=None):
    """更新在场 NPC 心智。

    返回 (npc_updates, plot_advanced, main_plot_update, attr_changes,
    item_changes)。每个 NPC 只收到自己的目击历史窗口。

    信息隔离：只把每个 NPC 自己目击过的回合喂给他（由调用方提供 can_know 文本）。
    """
    names = [n for n in present if n in npcs][:C.MAX_NPC_UPDATE]
    if not names:
        return {}, False, "", {}, {"add": [], "remove": []}
    knowledge_by_npc = knowledge_by_npc or {}
    sections = "\n\n".join(
        npc_section(n, npcs[n], knowledge_by_npc.get(n, "（本回合在场，亲历了当前剧情）"))
        for n in names
    )
    try:
        raw = await llm.chat(
            [{"role": "system", "content": prompts.NPC_MIND_SYSTEM},
             {"role": "user", "content": prompts.npc_mind_user_message(
                 action, narrative, main_plot, sections)}],
            aux=True, max_tokens=1200)
        obj = _loads(raw) or {}
    except Exception:
        logger.exception("NPC mind update failed")
        return {}, False, "", {}, {"add": [], "remove": []}

    updates = {}
    for name, fields in (obj.get("npcs") or {}).items():
        if name not in npcs or not isinstance(fields, dict):
            continue
        upd = {}
        for key in ("feeling", "goal", "opinion_of_player", "secret_plan"):
            v = fields.get(key)
            if isinstance(v, str) and v.strip():
                upd[key] = v.strip()[:120]
        if upd:
            updates[name] = upd
    plot_advanced = bool(obj.get("plot_advanced"))
    main_plot_update = str(obj.get("main_plot_update") or "").strip()[:240]
    if main_plot_update == main_plot.strip():
        main_plot_update = ""

    attr_changes = {}
    for k, v in (obj.get("player_attr_changes") or {}).items():
        k = str(k).strip()
        if k in player_attrs:
            try:
                d = int(v)
                if d and abs(d) <= 3:
                    attr_changes[k] = max(-3, min(3, d))
            except (TypeError, ValueError):
                pass
    ic = obj.get("key_item_changes") or {}
    add = [str(x)[:40] for x in (ic.get("add") or [])][:3]
    remove = [str(x)[:40] for x in (ic.get("remove") or [])][:3]
    return updates, plot_advanced, main_plot_update, attr_changes, {"add": add, "remove": remove}

"""长期记忆：四层金字塔（short→medium→long→permanent）+ 关键词检索。

借鉴 Project Lunar 的分层结晶与 AI Town 的重排思想，检索用中文 bigram 重合度
（无需分词依赖），permanent 层全量注入，其余层按相关度取 top-k。
"""
import logging
import re

from . import config as C
from . import prompts

logger = logging.getLogger(__name__)


def _tokens(text):
    """中文 bigram + 拉丁/数字整词。"""
    toks = set()
    for m in re.findall(r"[A-Za-z0-9]+", text):
        toks.add(m.lower())
    for seg in re.findall(r"[\u4e00-\u9fff]+", text):
        if len(seg) == 1:
            toks.add(seg)
        else:
            toks.update(seg[i:i + 2] for i in range(len(seg) - 1))
    return toks


def _crystal_text(c):
    parts = [c.get("summary", "")]
    parts.extend(c.get("key_events") or [])
    for ch in c.get("characters") or []:
        parts.append(f"{ch.get('name', '')}{ch.get('state', '')}{ch.get('relationship', '')}")
    parts.extend(c.get("world_facts") or [])
    return " ".join(parts)


def _layer_base(layer):
    return {"short": 2.0, "medium": 4.0, "long": 6.0}[layer]


def score_crystal(query_toks, crystal, layer, present_npcs, idx_from_newest):
    text = _crystal_text(crystal)
    ctoks = _tokens(text)
    if not ctoks:
        return 0.0
    overlap = len(query_toks & ctoks)
    score = overlap * 1.0 + _layer_base(layer)
    for name in present_npcs:
        if name and name in text:
            score += 8.0
            break
    if idx_from_newest < 8:
        score += (8 - idx_from_newest) * 0.3
    return score


class MemoryEngine:
    """crystals: {"short": [...], "medium": [...], "long": [...], "permanent": [...]}
    每个 crystal 是 dict（含 summary/key_events/characters/world_facts）。"""

    def __init__(self, crystals):
        self.crystals = crystals

    # ---- 检索 ----
    def build_context(self, query, present_npcs, budget=C.MEMORY_BUDGET_CHARS):
        segments = []
        used = 0

        def append_segment(seg):
            nonlocal used
            if used >= budget:
                return False
            remaining = budget - used
            clipped = seg[:remaining]
            segments.append(clipped)
            used += len(clipped)
            return len(clipped) == len(seg)

        for c in self.crystals.get("permanent", []):
            seg = "◆ 既成事实：" + c.get("summary", "")
            if not append_segment(seg):
                break
        query_toks = _tokens(query)
        for layer in ("long", "medium", "short"):
            layer_crystals = self.crystals.get(layer, [])
            scored = []
            for i, c in enumerate(reversed(layer_crystals)):  # i=0 最新
                s = score_crystal(query_toks, c, layer, present_npcs, i)
                scored.append((s, i, c))
            scored.sort(key=lambda x: -x[0])
            label = {"long": "◇ 篇章记忆", "medium": "○ 阶段记忆", "short": "· 近段记忆"}[layer]
            taken = 0
            for s, i, c in scored:
                if taken >= C.PER_LAYER_TOP_K or used >= budget:
                    break
                facts = "；".join(c.get("world_facts") or [])
                seg = f"{label}：{c.get('summary', '')}" + (f"（事实：{facts}）" if facts else "")
                if not append_segment(seg):
                    break
                taken += 1
        return segments

    # ---- 结晶 ----
    async def crystallize(self, llm, raw_turns_since_cursor):
        """short 层结晶 + 逐层级联。返回新增事件列表（由调用方持久化）。"""
        events = []
        if len(raw_turns_since_cursor) < C.CRYSTAL_INTERVAL:
            return events
        batch = raw_turns_since_cursor[:C.CRYSTAL_INTERVAL]
        items = []
        for t in batch:
            act = t.get("player_action") or "（开局）"
            meta = t.get("meta") or {}
            items.append(f"玩家：{act}\n剧情：{t.get('narrative', '')}\n（地点：{meta.get('place', '')}）")
        crystal = await self._compress(llm, items, "short")
        if crystal:
            self.crystals.setdefault("short", []).append(crystal)
            events.append(("CRYSTAL", {"layer": "short", "crystal": crystal}))
        events.extend(await self._cascade(llm))
        return events

    async def _cascade(self, llm):
        events = []
        for src, dst in (("short", "medium"), ("medium", "long"), ("long", "permanent")):
            need = True
            while need and len(self.crystals.get(src, [])) >= C.CASCADE_BATCH:
                batch = self.crystals[src][-C.CASCADE_BATCH:]
                items = [_dumps(b) for b in batch]
                merged = await self._compress(llm, items, dst)
                if not merged:
                    break
                self.crystals[src] = self.crystals[src][:-C.CASCADE_BATCH]
                self.crystals.setdefault(dst, []).append(merged)
                events.append(("CRYSTAL", {"layer": dst, "crystal": merged}))
                events.append(("CRYSTAL_POP", {"layer": src, "count": C.CASCADE_BATCH}))
                need = len(self.crystals[src]) >= C.CASCADE_BATCH
        return events

    async def _compress(self, llm, items, layer):
        try:
            raw = await llm.chat(
                [{"role": "system", "content": prompts.CRYSTAL_SYSTEM},
                 {"role": "user", "content": prompts.crystal_user_message(items, layer)}],
                aux=True, max_tokens=900)
            obj = _loads(raw)
            if obj and isinstance(obj.get("summary"), str) and obj["summary"].strip():
                return obj
        except Exception:
            logger.exception("Memory crystallization failed")
        return None


def _dumps(c):
    import json
    return json.dumps(c, ensure_ascii=False)


def _loads(raw):
    import json
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

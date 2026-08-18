"""全部中文 prompt。系统的灵魂所在，改动需谨慎。

叙事主调用的输出协议：逐行输出语义 Beat，然后另起一行输出结构化块：
<beat type="narration">……</beat>
<beat type="dialogue" speaker="人物名">……</beat>
[[META]]
{"choices": [...], "minutes": N, "place": "...", "present": [...]}
[[END]]
"""
import json

from . import config as C

META_SENTINEL = "[[META]]"
META_END = "[[END]]"
DEFAULT_CHOICES = ["观察周围环境", "谨慎采取行动"]

# ---------------------------------------------------------------- 叙事主调用

NARRATOR_SYSTEM = """你是一个沉浸式中文文字世界模拟引擎的叙事者。你负责推进剧情、扮演世界与所有 NPC，判定玩家行动的实际后果。

【世界设定】
{world_setting}

【世界规则】
{world_rules}

【剧情基调】
{tone}

【叙事守则】
1. 只用中文写作，第二人称"你"指代玩家。禁止出戏、禁止任何 meta 说明、禁止罗列选项之外的分析。
2. 后果是真实的。玩家的输入只是一次【尝试】：他想做什么由他决定，实际发生什么由世界状态、他的能力、资源与环境决定。玩家说"我造火箭飞去月球"，你要按一个资源匮乏的普通人试图造火箭来演绎后果，而不是让他成功。
3. 玩家属性是成败倾向的依据（属性见状态块），但不显式引用数字。力量 20 的人搬不动巨石，魅力高的人更容易说服他人。
4. NPC 是活人：他们有自己的性格、愿望、想法与处境（见各 NPC 状态块），会主动说话和行动，不等玩家推动才存在；他们的内心、关系与数值只属于叙事者参考，永远不得在正文中直接旁白给读者。但每个 NPC 只能引用他自己可能知道的信息（各 NPC 状态块中【可知】标注的范围），绝不泄露他不可能知道的事。近期历史、长期记忆和世界暗流是叙事者上下文，不代表任何 NPC 自动知道；写 NPC 台词或行动时只能使用该 NPC 的【可知】范围。
5. 篇幅自适应：快节奏的动作往来可以只有一两句话甚至十几个字；重要对话、场景转换、剧情推进可以写二三百字。总体宁精勿滥。
6. 保持既有事实的连续性，不得与记忆、历史、状态冲突。专名（人名、地名、组织名）永远保持原样。present 中的已知 NPC 必须使用【已知 NPC 标准名称】里的原名，不得改成简称、称谓或同义变体；首次出现的新 NPC 可以在本回合首次命名，但从命名开始必须保持同一名字。
7. 世界有内在压力：若【主线压力】提示存在，务必让它以合理方式渗入剧情，但不必每回合都直白展现。
8. 你是唯一的状态记账员：生成 META 时，把本回合确实发生的状态变化一并写进去（稀疏：没有变化就不填字段）。更新原则——status/current_thought 可以有正常变化，但必须由当前剧情和既有事实自然支持；desire 是低频字段（目标真正改变才动）；personality/qualities 是极低频字段（只有重大成长、创伤、长期经历才动）；favor 普通互动 ±1~±5、明显事件 ±5~±10、极重大事件可以更大但必须克制；bond 一句话总结关系本质，可随剧情覆盖。数值只是给引擎记的账，永远不得在正文中暴露给读者。

【输出格式】（严格遵守）
先逐行输出剧情 Beat，不要任何前缀。每个 beat 必须完整占一行，beat 内禁止换行；一个 beat 只表达一个自然叙事节拍，通常 20~80 个汉字，不要为了凑长度拆句，也不要输出过长段落。
可用的 Beat 只有两种：
<beat type="narration">旁白或行动</beat>
<beat type="narration" speaker="人物标准名称">某人物的独立动作、神态或其他玩家可感知表现</beat>
<beat type="dialogue" speaker="人物标准名称">台词</beat>
dialogue 必须填写 speaker。speaker 可以是玩家标准名称、【已知 NPC 标准名称】中的原名，或本回合首次命名的新 NPC；已知名称不得改写。narration 在没有明确主体时省略 speaker，有明确人物的可观察动作、神态或表现可以填写 speaker；不得借 narration 透露人物未说出口的想法、计划、秘密或心理。present 只填写本回合结束时在场的 NPC，不填写玩家；已知 NPC 使用原名，新 NPC 首次命名后保持同名。
正文结束后，另起一行输出完整 JSON（包含状态补丁）：
[[META]]
{{
 "choices": ["……", "……", "……"],
 "minutes": 30,
 "place": "当前地点",
 "present": ["在场NPC名"],
 "npc_updates": {{
   "NPC标准名": {{"status": "新处境", "current_thought": "此刻最重要的想法"}}
 }},
 "quality_updates": {{"NPC标准名": {{"体质": -3}}}},
 "relationship_updates": [
   {{"from": "角色A", "to": "角色B", "favor_delta": -6, "bond": "关系本质的一句话", "reason": "变化原因"}}
 ],
 "important_event": {{"summary": "一句关键事实", "participants": ["相关人物"], "importance": "major或minor"}},
 "player_update": {{"status": "主角的新状态（如：已死亡）"}},
 "player_attr_changes": {{"属性名": -2}},
 "key_item_changes": {{"add": ["获得的关键物品"], "remove": []}},
 "main_plot_update": "主线表述有实质变化时才填，否则省略",
 "chapter_done": {{"done": false, "reason": ""}}
}}
[[END]]
其中 choices 2~4 个、每个不超过 22 个字，行动导向、风格多样；minutes 为本回合剧情流逝的分钟数；place/present 同前。npc_updates / quality_updates / relationship_updates / important_event / player_update 等全是稀疏补丁：只有本回合确实发生、且值得被记住的状态或关系变化才输出对应字段，没有变化就省略；这就是同一作者顺手记账，不要为了填而填。本回合首次命名且确实会持续存在的角色，用"new_npcs"字段给出其人物卡（姓名/年龄/身份/status/qualities/personality/desire/background/current_thought）。"""


def chapter_block(frame):
    if not frame:
        return ""
    return ("【当前章节】\n" +
            f"时间范围：{frame.get('time_scope') or '未限定'}\n" +
            f"地点范围：{frame.get('location_scope') or '未限定'}\n" +
            f"本章主题：{frame.get('theme') or '探索这个世界'}\n" +
            f"成功条件：{frame.get('success_condition') or '玩家自己探索出的结局'}\n" +
            f"失败条件：{frame.get('failure_condition') or '主角死亡'}\n" +
            "规则：在本章范围内玩家完全自由，不规定具体方法；"
            "不要主动把故事带离本章范围或转向无关的长期主题；"
            "当玩家实际达成成功条件时，在 META 中把 chapter_done.done 设为 true 并写明 reason；"
            "当玩家在本章死亡时，把 player_update.status 设为「已死亡」。")


def events_block(important_events, budget=C.EVENT_BLOCK_BUDGET_CHARS):
    if not important_events:
        return ""
    lines = []
    used = 0
    for ev in important_events:
        line = ("★ " if ev.get("importance") == "major" else "- ") + (ev.get("summary") or "")
        if used + len(line) + 1 > budget:
            break
        lines.append(line)
        used += len(line) + 1
    if not lines:
        return ""
    return "【重要事件】（本世界值得一提的过去事实）\n" + "\n".join(lines)


def narrator_user_message(state_block, chapter_block, memory_block, relationship_block,
                          events_block, thread_block, history_block, action):
    return f"""【当前世界状态】
{state_block}

{chapter_block}
{memory_block}
{relationship_block}
{events_block}
{thread_block}
{history_block}
【玩家行动】
{action}

请推进剧情。"""


def relationship_block(context):
    if not context:
        return ""
    return ("【人物关系】（有向：左→右；好感 0~100 仅供叙事者判断亲疏，"
            "羁绊是关系本质的文字描述）\n" + context)


def state_block(player, npcs, time_display, place, present, knowledge_by_npc=None):
    attrs = "，".join(f"{k} {v}" for k, v in player["attrs"].items())
    items = "、".join(player["key_items"]) if player["key_items"] else "无"
    lines = [
        f"时间：{time_display}",
        f"地点：{place}",
        f"玩家：{player['name']}（{player['identity']}）",
        f"玩家属性：{attrs or '无'}",
        f"关键物品：{items}",
    ]
    known_names = list(npcs)
    lines.append("【已知 NPC 标准名称】\n" +
                 ("、".join(known_names) if known_names else "（暂无）") +
                 "\npresent 只放 NPC；已知 NPC 必须使用以上标准名称，新 NPC 可以在剧情中首次命名。")
    lines.append("【可用说话者】\n" +
                 f"玩家：{player['name']}\n" +
                 "已知 NPC：" + ("、".join(known_names) if known_names else "（暂无）") +
                 "\n本回合可以在 Beat 中首次命名新 NPC，命名后后续 Beat 必须保持同名。")
    knowledge_by_npc = knowledge_by_npc or {}
    if present:
        lines.append("在场 NPC：")
        for name in present:
            n = npcs.get(name)
            if not n:
                continue
            quals = "、".join(f"{k} {v}" for k, v in (n.get("qualities") or {}).items()) or "（未设定）"
            lines.append(f"- {name}：身份：{n['identity']}；年龄：{n.get('age') or '未知'}；"
                         f"性格：{n['personality'] or '未知'}")
            lines.append(f"  现状：{n['status'] or '正常'}")
            lines.append(f"  品质：{quals}")
            lines.append(f"  愿望：{n['desire'] or '未知'}")
            lines.append(f"  当前想法：{n['current_thought'] or '无记录'}")
            known = knowledge_by_npc.get(name) or "（没有目击到更早的相关事件；只能使用本回合亲历内容）"
            lines.append(f"  【{name} 可知的历史】\n  {known}")
    else:
        lines.append("在场 NPC：无（独处）")
    return "\n".join(lines)


def thread_block(main_plot, pressure, threads):
    parts = [f"【主线】\n{main_plot}"]
    if pressure:
        parts.append(f"【主线压力】（若玩家连续多回合无视主线，以下压力必须升级并主动介入剧情）\n{pressure}")
    if threads:
        parts.append("【世界暗流】（离屏发生的、玩家尚不一定知晓的变化）\n" + "\n".join(f"- {t}" for t in threads))
    return "\n".join(parts)


def history_block(turns, budget=None):
    if not turns:
        return "【近期历史】\n（冒险刚刚开始）"
    lines = []
    used = 0
    selected = []
    # 从最新回合向前装箱，保证硬预算下近期事实优先。
    for t in reversed(turns):
        act = f"玩家：{t['player_action']}" if t.get("player_action") else "（开局）"
        line = act + "\n" + f"叙事：{t['narrative']}"
        if budget is not None and used >= max(0, budget):
            break
        if budget is not None and used + len(line) > max(0, budget):
            remaining = max(0, budget - used)
            if not selected and remaining:
                selected.append(line[:remaining])
            break
        selected.append(line)
        used += len(line)
    lines = list(reversed(selected))
    return "【近期历史】\n" + ("\n".join(lines) if lines else "（已按上下文预算裁剪）")


def memory_block(segments):
    if not segments:
        return ""
    return "【长期记忆】\n" + "\n".join(segments)


# ---------------------------------------------------------------- 开篇生成

OPENING_SYSTEM = NARRATOR_SYSTEM  # 同一套守则与输出格式


def opening_user_message(world_setting, rules, tone, player, npcs_desc, start_time,
                         situation="", notes=""):
    attrs = "，".join(f"{k} {v}" for k, v in player["attrs"].items())
    parts = [f"这是全新冒险的开篇。当前时间：{start_time}。\n\n【世界设定】\n{world_setting}"]
    if situation:
        parts.append(f"【开局处境（玩家此刻的状态，必须从这里开场）】\n{situation}")
    parts.append(f"\n【玩家】\n姓名：{player['name']}\n身份：{player['identity']}\n"
                 f"背景：{player['background']}\n属性：{attrs}")
    if npcs_desc:
        parts.append(f"\n【初始人物】\n{npcs_desc}")
    if notes:
        parts.append(f"\n【用户补充设定（与世界规则同等效力）】\n{notes}")
    parts.append("\n请生成开篇：把玩家自然地放进这个世界的一个具体场景中（不要流水账介绍设定），"
                 "场景中至少有一名初始人物在场，结尾留下明确的戏剧张力。"
                 "正文 300~500 字，拆成多个语义 Beat，然后按输出格式给出 [[META]] 块。")
    return "\n".join(parts)


# ---------------------------------------------------------------- 创建世界：解析自由文本

NPC_CARDS_SYSTEM = """你是游戏世界构筑器。MOCK:npccards

根据用户提供的「世界设定」与「重要人物/初始关系」自由文本，提取 1~6 名将在游戏中持续存在的 NPC，并提炼一条主线。

严格输出 JSON（不要任何其他文字）：
{
 "npcs": [
   {"name": "姓名", "age": 年龄数字, "identity": "一句话身份",
    "status": "开局处境，如：右臂受伤，正在和主角一起行动",
    "qualities": {"智力": 70, "力量": 50, "勇气": 60},
    "personality": "性格与说话风格",
    "desire": "此人的愿望、执念或长期目标",
    "background": "进入当前故事以前的重要经历",
    "current_thought": "此刻心里最重要的一两句话"}
 ],
 "relationships": [
   {"from": "角色A", "to": "角色B", "favor": 0~100 的整数, "bond": "一句关系本质总结"}
 ],
 "first_chapter": {
   "title": "章节名", "time_scope": "时间范围", "location_scope": "地点范围",
   "theme": "本章主题", "success_condition": "达成什么即本章结束",
   "failure_condition": "通常为：主角死亡"
 },
 "main_plot": "一条 30~60 字的主线：世界正在发生什么、什么在逼近或崩塌"
}
要求：姓名使用原文专名；qualities 不规定固定模板，按角色设定生成 3~5 项合理的 0~100 量级数值；desire 是 NPC 自己想要的，不是给玩家的任务；若自由文本为空，则根据世界设定自行创造 2~3 名合理 NPC；status 与 current_thought 都要反映开局处境；relationships 只列出开局真正存在或重要的有向关系（通常是与主角之间，或关键 NPC 之间），不建全连矩阵；favor 是 0~100 的亲疏，bond 比数值更重要，用一句话说明关系的本质；first_chapter 用一句话描述开局的时间/地点/主题，success_condition 只写「达成什么即本章结束」（重状态，不重情节步骤）。"""


def npc_cards_user_message(world_setting, important_people):
    return f"""【世界设定】
{world_setting}

【重要人物/初始关系（自由文本）】
{important_people or "（未提供，请自行创造）"}"""


# (NPC 心智更新已并入 Narrator 的单作者 META 状态补丁——阶段 4 删除了 npc_mind)


# ---------------------------------------------------------------- 记忆结晶（异步）

CRYSTAL_SYSTEM = """你是世界模拟器的记忆压缩器。MOCK:crystal

把给定的事件/记忆压缩成一份结构化记忆。专名（人名、地名、组织）必须逐字保留，永不改写、永不合并简称。

严格输出 JSON（不要任何其他文字）：
{
 "summary": "本层记忆的连贯概述",
 "key_events": ["关键事件，每条一句话"],
 "characters": [{"name": "人名", "state": "当前状态", "relationship": "与玩家的关系"}],
 "world_facts": ["持久为真的世界事实"],
 "open_threads": ["未完成的承诺、未兑现的威胁、约定、未解决事件或进行中的目标"]
}
summary 的抽象程度视层级而定：short 层是"本段发生了什么的连贯概述"；medium 层是"多条短记忆的阶段小结"；long 层是"一个篇章的弧线概括"；permanent 层是"永不改变的既成事实与世界常识"。open_threads 只保留确实存在且尚未解决的事项，不要凭空创造任务。"""


def crystal_user_message(items, layer):
    layer_desc = {
        "short": "以下是一段连续的游戏回合，请压缩为一条 short 层记忆",
        "medium": "以下是多条 short 层记忆 JSON，请合并提升为一条 medium 层记忆",
        "long": "以下是多条 medium 层记忆 JSON，请合并提升为一条 long 层记忆",
        "permanent": "以下是多条 long 层记忆 JSON，请提炼为 permanent 层永久事实",
    }[layer]
    return layer_desc + "：\n\n" + "\n".join(items)


# ---------------------------------------------------------------- 世界推进（异步）

TICK_SYSTEM = """你是世界模拟器的离屏推进器。MOCK:tick

玩家不在场的时间里，世界按照自身逻辑继续运转。根据跳跃的时间跨度与当前状态，生成少量合理的世界变化。

严格输出 JSON（不要任何其他文字）：
{{
 "developments": ["离屏发生的变化，1~3 条，每条一句话"],
 "plot_pressure": "对主线压力的一句话描述（威胁更近了/暂时缓和/出现变数），没有则留空",
 "npc_updates": {{
   "NPC名": {{"status": "新的处境（没有变化则留空）", "current_thought": "新的想法（没有变化则留空）",
               "desire": "新的愿望（没有变化则留空）"}}
 }}
}}
规则：保持克制，一次只推进一到两个主要发展；不开新谜团、不引入新命名角色（可以用群体指代）；关系的大幅改变尽量通过实际剧情表达，不要在此凭空调整；只更新确实在离屏时间内行动过的 NPC，普通 NPC 的字段可以全部留空；
变化要与现有暗流和主线因果连续；跳跃时间越长、等级越高，变化可以越大，但仍须合理。"""


def tick_user_message(minutes, severity, state_summary, threads, main_plot, npc_context=""):
    sev = {"minor": "（轻微：日常运转层面的小变化）",
           "moderate": "（中等：足以改变局势的变化）",
           "major": "（重大：格局级的变化，但仍需因果合理）"}[severity]
    return f"""时间跳跃了 {minutes} 分钟{sev}。

【主线】
{main_plot}

【当前世界状态摘要】
{state_summary}

【既有世界暗流】
{threads or '（无）'}

【NPC 离屏状态】
{npc_context or '（无）'}

请生成离屏世界变化。"""


# ---------------------------------------------------------------- 章节规划（章末，主模型）

CHAPTER_SYSTEM = """你是世界模拟器的章节规划者。MOCK:chapter

当前一章已经结束。请做两件事：1) 用一小段话总结本章发生了什么；2) 规划下一章的框架。
你只负责章节内容的总结与规划，绝不修改任何人物状态——人物状态只由叙事者在故事中修改。

严格输出 JSON（不要任何其他文字）：
{
 "chapter_summary": "本章最重要的情节总结（200 字内）",
 "next_chapter": {
   "title": "章节名",
   "time_scope": "下一章的时间范围",
   "location_scope": "下一章的地点范围",
   "theme": "下一章主题（一句话）",
   "success_condition": "成功条件：主角达成什么即本章结束",
   "failure_condition": "失败条件：通常为 主角死亡"
 }
}
要求：next_chapter 要承接本章未解决的线索与世界暗流，但不要凭空引入无关的新主线；时间/地点可以是「数月后」「另一座城市」这类范围描述；章节之间保留因果连续。"""


def chapter_planner_user_message(turns_text, important_events, relationship_snapshot, threads, main_plot):
    return f"""【本章已发生的剧情】
{turns_text or '（本章尚无玩家回合）'}

【本章重要事件】
{important_events or '（无）'}

【当前人物关系（仅供参考上下文，不可改动）】
{relationship_snapshot or '（无）'}

【世界暗流】
{threads or '（无）'}

【总主线】
{main_plot or '（未定）'}

请总结本章并规划下一章。"""


# ---------------------------------------------------------------- 共享工具

def extract_meta(text):
    """从叙事输出中解析 [[META]] JSON 块。失败返回 None。"""
    idx = text.rfind(META_SENTINEL)
    if idx < 0:
        return None
    rest = text[idx + len(META_SENTINEL):]
    end = rest.find(META_END)
    if end >= 0:
        rest = rest[:end]
    rest = rest.strip().strip("`")
    if rest.startswith("json"):
        rest = rest[4:]
    # 括号配平提取第一个完整 JSON 对象
    start = rest.find("{")
    if start < 0:
        return None
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(rest)):
        ch = rest[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    obj = json.loads(rest[start:i + 1])
                    return obj if isinstance(obj, dict) else None
                except json.JSONDecodeError:
                    return None
    return None


def normalize_meta(meta, fallback_place, fallback_present):
    """把 LLM 返回的 meta 规范化，字段缺失时给安全默认值。"""
    if not isinstance(meta, dict):
        meta = {}
    raw_choices = meta.get("choices")
    if not isinstance(raw_choices, list):
        raw_choices = []
    choices = [str(c).strip() for c in raw_choices if str(c).strip()]
    choices = [c for c in choices if len(c) <= 40][:4]
    # The UI always presents a decision surface.  If a model omits choices or
    # returns only one malformed option, keep the interaction usable without
    # inventing world-specific actions.
    if len(choices) < 2:
        choices = (choices + DEFAULT_CHOICES)[:2]
    minutes = meta.get("minutes")
    try:
        minutes = max(0, min(int(minutes), 60 * 24 * 30))
    except (TypeError, ValueError):
        minutes = 5
    place = str(meta.get("place") or "").strip() or fallback_place
    # 缺失时继承上一场景，显式 [] 表示独处。
    if "present" in meta:
        raw_present = meta.get("present")
        if not isinstance(raw_present, list):
            raw_present = []
        present = [str(p).strip() for p in raw_present if str(p).strip()]
    else:
        present = list(fallback_present or [])

    # ---------------- Narrator 稀疏状态补丁（单作者记账） ----------------
    npc_updates = {}
    raw_npcs = meta.get("npc_updates")
    if isinstance(raw_npcs, dict):
        for name, fields in list(raw_npcs.items())[:5]:
            name = str(name).strip()
            if not name or not isinstance(fields, dict):
                continue
            upd = {}
            for k in ("status", "personality", "desire", "current_thought"):
                v = fields.get(k)
                if isinstance(v, str) and v.strip():
                    upd[k] = v.strip()[:120]
            if upd:
                npc_updates[name] = upd

    new_npcs = []
    raw_new = meta.get("new_npcs")
    if isinstance(raw_new, list):
        for card in raw_new[:3]:
            if not isinstance(card, dict):
                continue
            name = str(card.get("name") or "").strip()
            if not name or name in npc_updates:
                continue
            new_npcs.append({
                "name": name,
                "age": card.get("age") or "",
                "identity": str(card.get("identity") or "未知来客").strip()[:80],
                "status": str(card.get("status") or "").strip()[:120],
                "qualities": {k: v for k, v in (card.get("qualities") or {}).items()
                              if isinstance(v, (int, float))},
                "personality": str(card.get("personality") or "").strip()[:120],
                "desire": str(card.get("desire") or "").strip()[:120],
                "background": str(card.get("background") or "").strip()[:200],
                "current_thought": str(card.get("current_thought") or "").strip()[:120],
            })

    quality_updates = {}
    raw_qual = meta.get("quality_updates")
    if isinstance(raw_qual, dict):
        for name, changes in list(raw_qual.items())[:3]:
            name = str(name).strip()
            if not name or not isinstance(changes, dict):
                continue
            out = {}
            for q, d in list(changes.items())[:4]:
                if not isinstance(q, str) or not q:
                    continue
                try:
                    delta = max(-10, min(10, int(d)))
                except (TypeError, ValueError):
                    continue
                out[q] = delta
            if out:
                quality_updates[name] = out

    relationship_updates = []
    raw_rels = meta.get("relationship_updates")
    if isinstance(raw_rels, list):
        for rel in raw_rels[:8]:
            if not isinstance(rel, dict):
                continue
            frm = str(rel.get("from") or "").strip()
            to = str(rel.get("to") or "").strip()
            if not frm or not to:
                continue
            try:
                delta = max(-20, min(20, int(rel.get("favor_delta") or 0)))
            except (TypeError, ValueError):
                delta = 0
            relationship_updates.append({
                "from": frm, "to": to, "favor_delta": delta,
                "bond": str(rel.get("bond") or "").strip()[:120],
                "reason": str(rel.get("reason") or "").strip()[:160],
            })

    important_event = None
    raw_event = meta.get("important_event")
    if isinstance(raw_event, dict):
        summary = str(raw_event.get("summary") or "").strip()
        if summary:
            important_event = {
                "summary": summary[:160],
                "participants": [str(p).strip() for p in
                                 (raw_event.get("participants") or []) if str(p).strip()][:8],
                "importance": raw_event.get("importance")
                              if raw_event.get("importance") in ("major", "minor") else "minor",
            }

    player_update = {}
    raw_p = meta.get("player_update")
    if isinstance(raw_p, dict):
        status = str(raw_p.get("status") or "").strip()
        if status:
            player_update["status"] = status[:60]

    attr_changes = {}
    raw_attr = meta.get("player_attr_changes")
    if isinstance(raw_attr, dict):
        for k, d in list(raw_attr.items())[:3]:
            k = str(k).strip()
            if not k:
                continue
            try:
                delta = max(-3, min(3, int(d)))
            except (TypeError, ValueError):
                continue
            if delta:
                attr_changes[k] = delta

    item_changes = {"add": [], "remove": []}
    raw_items = meta.get("key_item_changes")
    if isinstance(raw_items, dict):
        item_changes["add"] = [str(x)[:40] for x in (raw_items.get("add") or [])][:3]
        item_changes["remove"] = [str(x)[:40] for x in (raw_items.get("remove") or [])][:3]

    main_plot_update = str(meta.get("main_plot_update") or "").strip()[:240] or None

    chapter_done = None
    raw_done = meta.get("chapter_done")
    if isinstance(raw_done, dict) and raw_done.get("done"):
        chapter_done = {"done": True,
                        "reason": str(raw_done.get("reason") or "").strip()[:200]}

    return {
        "choices": choices,
        "minutes": minutes,
        "place": place,
        "present": present,
        "npc_updates": npc_updates,
        "new_npcs": new_npcs,
        "quality_updates": quality_updates,
        "relationship_updates": relationship_updates,
        "important_event": important_event,
        "player_update": player_update,
        "player_attr_changes": attr_changes,
        "key_item_changes": item_changes,
        "main_plot_update": main_plot_update,
        "chapter_done": chapter_done,
    }

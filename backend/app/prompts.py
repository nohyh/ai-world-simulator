"""全部中文 prompt。系统的灵魂所在，改动需谨慎。

叙事主调用的输出协议：正文先流式输出，然后另起一行输出结构化块：
[[META]]
{"choices": [...], "minutes": N, "place": "...", "present": [...]}
[[END]]
"""
import json

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
4. NPC 是活人：他们有自己的目标、情绪与秘密，会主动说话和行动，不等玩家推动才存在。但每个 NPC 只能引用他自己可能知道的信息（各 NPC 状态块中【可知】标注的范围），绝不泄露他不可能知道的事。近期历史、长期记忆和世界暗流是叙事者上下文，不代表任何 NPC 自动知道；写 NPC 台词或行动时只能使用该 NPC 的【可知】范围。
5. 篇幅自适应：快节奏的动作往来可以只有一两句话甚至十几个字；重要对话、场景转换、剧情推进可以写二三百字。总体宁精勿滥。
6. 保持既有事实的连续性，不得与记忆、历史、状态冲突。专名（人名、地名、组织名）永远保持原样。
7. 世界有内在压力：若【主线压力】提示存在，务必让它以合理方式渗入剧情，但不必每回合都直白展现。

【输出格式】（严格遵守）
先直接输出剧情正文，不要任何前缀。正文结束后，另起一行输出：
[[META]]
{{"choices": ["……", "……", "……"], "minutes": 30, "place": "当前地点", "present": ["在场NPC名"]}}
[[END]]
其中 choices 为 2~4 个下一步行动选项，每个不超过 22 个字，行动导向、风格多样（可包含试探、对话、等待、时间流逝类如"休息到天亮"）；minutes 为本回合剧情流逝的分钟数（快对话 2~10，普通行动 15~60，长途移动或休息可为数百上千）；place 为本回合结束时的地点；present 为本回合在场的 NPC 名列表（无人则为空数组）。"""


def narrator_user_message(state_block, memory_block, thread_block, history_block, action):
    return f"""【当前世界状态】
{state_block}

{memory_block}
{thread_block}
{history_block}
【玩家行动】
{action}

请推进剧情。"""


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
    knowledge_by_npc = knowledge_by_npc or {}
    if present:
        lines.append("在场 NPC：")
        for name in present:
            n = npcs.get(name)
            if not n:
                continue
            pub = f"身份：{n['identity']}；性格：{n['personality']}；与玩家关系：{n['relationship']}"
            known = knowledge_by_npc.get(name) or "（没有目击到更早的相关事件；只能使用本回合亲历内容）"
            priv = (f"【仅叙事者可知，玩家与其它 NPC 不可知】此刻心理：{n['feeling'] or '不明'}；"
                    f"目标：{n['goal'] or '不明'}；对玩家看法：{n['opinion_of_player'] or '不明'}；"
                    f"秘密计划：{n['secret_plan'] or '无'}")
            lines.append(f"- {name}：{pub}")
            lines.append(f"  【{name} 可知的历史】\n  {known}")
            lines.append(f"  【私有心智，仅叙事者可见】{priv}")
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
                 "正文 300~500 字，然后按输出格式给出 [[META]] 块。")
    return "\n".join(parts)


# ---------------------------------------------------------------- 创建世界：解析自由文本

NPC_CARDS_SYSTEM = """你是游戏世界构筑器。MOCK:npccards

根据用户提供的「世界设定」与「重要人物/初始关系」自由文本，提取 1~6 名将在游戏中持续存在的 NPC，并提炼一条主线。

严格输出 JSON（不要任何其他文字）：
{
 "npcs": [
   {"name": "姓名", "identity": "一句话身份", "personality": "性格与说话风格",
    "relationship": "与玩家的初始关系", "goal": "此人的目标或动机",
    "secret_plan": "他隐藏的秘密或计划，没有则留空字符串"}
 ],
 "main_plot": "一条 30~60 字的主线：世界正在发生什么、什么在逼近或崩塌"
}
要求：姓名使用原文专名；goal 是 NPC 自己想要的，不是给玩家的任务；若自由文本为空，则根据世界设定自行创造 2~3 名合理 NPC；secret_plan 只有在设定确实支持秘密或隐性计划时才填写，普通 NPC 可以留空，不要为了戏剧性硬造。"""


def npc_cards_user_message(world_setting, important_people):
    return f"""【世界设定】
{world_setting}

【重要人物/初始关系（自由文本）】
{important_people or "（未提供，请自行创造）"}"""


# ---------------------------------------------------------------- NPC 心智更新（异步）

NPC_MIND_SYSTEM = """你是世界模拟器的后台状态更新器。MOCK:npcmind

根据本回合剧情，更新在场 NPC 的私有心智，并判断玩家属性/物品是否发生值得记录的变化。
每个 NPC 只能基于他自己可知晓的信息更新（他不在场的事他不知道）。【本回合剧情】和【他可知的信息】之外的内容一律不可当作记忆。

严格输出 JSON（不要任何其他文字）：
{
 "npcs": {
   "NPC名": {"feeling": "此刻情绪（短语）", "goal": "当前目标（可保持原值）",
             "opinion_of_player": "对玩家的看法（短语）", "relationship": "与玩家关系（有变化才填）",
             "secret_plan": "秘密计划（可保持原值）"}
 },
 "new_npcs": [
   {"name": "本回合首次出现且在 present 中的 NPC", "identity": "身份", "personality": "性格",
    "relationship": "与玩家关系", "goal": "目标", "secret_plan": "秘密计划；没有则留空"}
 ],
 "main_plot_update": "如主线发生了可确认的实质变化，给出更新后的主线；没有变化则留空字符串",
 "plot_advanced": true/false,
 "player_attr_changes": {"属性名": +1 或 -2},
 "key_item_changes": {"add": ["获得的关键物品"], "remove": ["失去的关键物品"]}
}
规则：当前主线会在用户消息中明确给出。plot_advanced 仅当本回合主线有实质推进（获得关键信息/化解威胁/关系质变）才为 true；main_plot_update 只在主线表述需要更新时填写完整的新主线，否则留空；new_npcs 只填写本回合确实首次出现、且 narrator 的 present 已列出的未知人物，不要凭空扩充人物表；
属性变化只在显著事件时给出（长期训练、重伤、领悟），每次至多 2 项、幅度 ≤3；
key_item 只记录对剧情有意义的物品（关键道具、信物、武器），不要记普通消耗品；
没有变化就输出空对象，不要硬凑。"""


def npc_mind_user_message(action, narrative, main_plot, npc_sections):
    return f"""【玩家行动】
{action}

【本回合剧情】
{narrative}

【当前主线】
{main_plot or '（尚未形成）'}

【待更新的 NPC 当前状态】
{npc_sections}"""


# ---------------------------------------------------------------- 记忆结晶（异步）

CRYSTAL_SYSTEM = """你是世界模拟器的记忆压缩器。MOCK:crystal

把给定的事件/记忆压缩成一份结构化记忆。专名（人名、地名、组织）必须逐字保留，永不改写、永不合并简称。

严格输出 JSON（不要任何其他文字）：
{
 "summary": "本层记忆的连贯概述",
 "key_events": ["关键事件，每条一句话"],
 "characters": [{"name": "人名", "state": "当前状态", "relationship": "与玩家的关系"}],
 "world_facts": ["持久为真的世界事实"]
}
summary 的抽象程度视层级而定：short 层是"本段发生了什么的连贯概述"；medium 层是"多条短记忆的阶段小结"；long 层是"一个篇章的弧线概括"；permanent 层是"永不改变的既成事实与世界常识"。"""


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
   "NPC名": {{"feeling": "新的情绪（没有变化则留空）", "goal": "新的目标（没有变化则留空）",
               "opinion_of_player": "新的看法（没有变化则留空）", "secret_plan": "新的秘密计划（没有变化则留空）"}}
 }}
}}
规则：保持克制，一次只推进一到两个主要发展；不开新谜团、不引入新命名角色（可以用群体指代）；只更新确实在离屏时间内行动过的 NPC，普通 NPC 的字段可以全部留空；不要凭空给普通 NPC 添加秘密；
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
    # Missing `present` means the narrator omitted the field and may safely
    # inherit the previous scene. An explicit [] means the protagonist is
    # alone; never replace it with the previous NPC list.
    if "present" in meta:
        raw_present = meta.get("present")
        if not isinstance(raw_present, list):
            raw_present = []
        present = [str(p).strip() for p in raw_present if str(p).strip()]
    else:
        present = list(fallback_present or [])
    return {"choices": choices, "minutes": minutes, "place": place, "present": present}

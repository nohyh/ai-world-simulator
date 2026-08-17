# 三个开源项目研究笔记（2026-08-16）

目的：为「极简 Web 版 AI 世界模拟文字游戏引擎」选定实现路径。三个仓库已 clone 到本目录（`project-lunar/`、`ai-town/`、`SillyTavern/`），以下为代码级分析结论。路径引用均相对各自仓库根。

---

## 0. 一句话结论

- **Project Lunar**：底座确认可行。事件溯源 + 可插拔引擎的架构质量高，裁剪点清晰；但每回合 8~14 次 LLM 调用、无选项生成、无鉴权、葡语残留，这些要靠我们自己处理。
- **AI Town**：借鉴三件事——「在途操作槽」（同步循环永不被 LLM 阻塞）、记忆管道（总结→重要性→向量→重排→阈值反思）、对话节奏控制器（typing 锁 + 行为预算）。其空间模拟和多世界设施不抄。真相：原版 NPC「自主决策」全是规则+随机数，LLM 只管说话。
- **SillyTavern**：借鉴 World Info 的极简子集（keys+content+constant+position）、具名插槽式 prompt 组装 + 逐段 token 记账（历史最后裁剪）、滚动总结锚定消息存储。AGPL，只借鉴设计不搬代码。

---

## 1. Project Lunar 深度分析

### 1.1 架构概况

- 后端：Python 3.10+ / FastAPI / **litellm** 统一多 provider（anthropic SDK 直连保留 cache_control）。无 SQLAlchemy，**原生 sqlite3 三个库**：`events.db`（事件溯源主库）、`scenarios.db`、`traces.db`（LLM 取证）。Neo4j 为可选依赖（缺席自动降级）。
- 前端：React 19 + Vite + zustand + Tailwind，无 TypeScript。
- 通信：**无 WebSocket**。玩家行动 `POST /api/game/action` 走 **SSE**，控制信号内联标签：`[MODE] [JOURNAL] [CRYSTAL] [PLOT_AUTO] [INVENTORY] [USAGE] [TRACE] [DONE]`（前端解析 `frontend/src/api.js:120-190`）。
- 体量：backend/app 约 10,353 行 py（tests 4,238 行），frontend/src 4,746 行。复杂度集中在 `backend/app/services/game_session.py`（**3,032 行**）。
- 单分支 master，最近提交 2026-08-11，活跃。有 pytest 覆盖每个 engine。
- 已知问题：无多用户/鉴权（`_sessions` 进程内 dict，只能单 worker）；代理路径下「流式」是伪流式；双语仅 en/pt-br，其他语言只加一句 hint；大量葡语注释与实验残留文件。

### 1.2 一次玩家回合的端到端流程（`game_session.py:1108-1173`）

同步阻塞部分（约 3~5 次 LLM）：
1. （campaign 首回合）玩家力量评估 1 次。
2. **detect_mode**（`narrator_engine.py:41-99`，辅助模型，256 tok）→ `{mode: NARRATIVE|COMBAT|META, ...}`，失败退回关键词启发式。
3. COMBAT 分支：anti-griefing 检查 → 三维打分 → 本地掷骰 → FAIL 时把 `[SYSTEM]` 指令注入玩家输入。
4. 上下文组装：记忆 RAG 窗口、NPC STATES、journal 最近 16 条、story cards RAG、narrator hints（剧情种子/NPC 种子/知识边界）、三区 prompt 缓存（zone0 稳定 / zone1 带 1h TTL / zone2 易变）。
5. **主叙事调用**（orchestrator 模型）→ 可能截断续写 1 次。
6. **审计员**（`auditor_engine.py:279-390`，超时 210s，术后修正 player agency / 连续性 / NPC 知识违规）。

异步副作用（剧情发出后 `asyncio.create_task`，约 5~9 次 LLM）：目击者抽取 → journal 评估 → NPC 心智更新 → 实体/关系抽取进 Neo4j → 条件性记忆结晶 → 力量评估；另有 world tick（叙事时间 ≥1h 时）+ 条件性 auto-plot。

**关键缺口：主回合流程中没有「生成 2~4 个选项」。** 唯一的 choices 生成在 `plot_generator.py:194-253` 的随机事件里，且只能手动触发。要做我们产品形态的选项，需自己新增一个 LLM 调用点。

### 1.3 引擎清单与裁剪评估

所有引擎以 `=None` 可选参数注入 GameSession，使用处有守卫——本身就是可插拔模式。

| 砍什么 | 改动面 | 收益 |
|---|---|---|
| Graph/Graphiti（去 Neo4j） | routes/game_session/memory 各几处 + 前端 WorldMapModal + react-force-graph-2d 依赖 | 去掉 Docker 依赖，每回合省 1-2 次 LLM。**性价比最高** |
| Combat | 已有软开关 `combat_enabled`（campaign 级）；彻底删涉 ~6 处 + CombatOverlay + 4 个测试文件 | 省 2-3 次 LLM |
| Journal | game_session 约 8 处调用 + prompt 的 STORY LOG 段 | 省 1 次 LLM |
| Inventory | 标签解析 + prompt 里 6 条 `[ITEM_*]` 规则 + auditor 守卫 | 机械但繁琐 |
| Auditor / trace / devtools | 各 1 次 LLM/回合 | 降低延迟与成本 |

保留核心：narrator + memory + npc_mind + world_reactor + plot_generator + scenario/event store + llm_router。主回合可压到 2 次 LLM。

### 1.4 长期记忆（`memory_engine.py`）

- 四层金字塔：SHORT（4 行动→压缩 JSON）→ MEDIUM（4 合 1）→ LONG → MEMORY（永久世界事实，**永不参与打分、全量注入**）。级联 `cascade_consolidation`。
- 结晶产物是**结构化 JSON**（events/characters/state/relationship/knows_player_as/items/promises/world_facts + 可读 summary），带完整性规则（专名永不变形）。
- 检索：**无向量库，纯关键词 RAG**——关键词重合×5 + 在场 NPC 名×50 + 地点×30 + 新近度；每层预算 = 上下文 10%；末尾附最近 10 条未结晶原始事件（DELTA）。
- 开场景窗口：已结晶旧场景不再以原始散文进 history。

### 1.5 NPC 私有状态与信息隔离（`npc_mind_engine.py`）

- 字段：`feeling/mood/emotion`（5 回合衰减）、`goal/opinion_of_player/secret_plan`（永不过期）。持久化为 `NPC_THOUGHT` 事件。
- 隔离三层：① 每回合 LLM 抽取「哪些 NPC 物理在场」盖 `witnessed_by` 章；② NPC 记忆窗口只给 witnessed_by 命中的条目（MEMORY 层=公共常识除外）；③ prompt 里显式 `NPC KNOWLEDGE BOUNDARIES` 块 + auditor 再查一遍。
- 防串号：泛型名过滤 + SequenceMatcher 模糊候选 + LLM 确认同名。

### 1.6 离屏推进 + 自动剧情线

- World Reactor 按叙事时间分级（<1h 跳过 / 1h-1d / 1d-1w / 1w-1mo / >1mo），各级有对应篇幅 prompt，规则「一次一个主要发展，不开新谜团」。
- Auto-Plot 冷却表（`plot_generator.py:73-101`）：micro_hook（5 回合起，冷 6 回合，≤8 次）、npc（8 回合起，冷 10 回合，≤6 次）、plot_arc（12 回合起，冷 14 回合，≤4 次）。
- **Plot lock**：活动剧情元素未「消费」前（4 回合）阻止一切新 auto-plot；NPC 种子要求叙事中真出现（名字子串校验）。防止主线被冲掉。

### 1.7 行动合理性

**没有通用 judge 模块**。叙事模式完全靠 narrator prompt 约束（"Consequences are real"）+ auditor 拦硬冲突；只有战斗模式有显式判定管线（anti-griefing → 打分 → 掷骰）。我们要的「造火箭=尝试而非成功」目前只由 prompt 承担。

### 1.8 Scenario 格式

最小必填只有 `scenario.title`。核心字段：tone_instructions、opening_narrative（或 `opening_mode:"ai"` + 指令）、lore_text、setup_questions（text/choice，带 var_name 插值）、story_cards（NPC/LOCATION/FACTION/ITEM/LORE，含 `known_by`、`power_level`、`trigger_keys`）。`{var_name}` 插值贯穿全文。

---

## 2. AI Town：值得借鉴的五个模式

1. **在途操作槽**（`convex/aiTown/agent.ts:238-257` + agentOperations.ts）：tick 循环永不被 LLM 阻塞；需要 LLM 时发起异步操作，agent 同时只挂一个在途操作（120s 超时自动清）；LLM 结果不直接改状态，而是作为 input 回流确定性循环生效。→ 我们的世界推进可以照搬为「主循环 + 每 NPC 一个在途动作槽」。
2. **记忆管道**（`convex/agent/memory.ts`）：对话结束→第一人称总结（1 次 LLM）→ importance 打分 0-9（1 次 LLM，temp 0）→ embedding 入库；检索 = 向量近邻 10 倍超采 → relevance+importance+recency(`0.99^h`) 归一化重排 top3；importance 累计超 500 才触发「反思」生成带溯源的高层洞察。
3. **对话节奏控制器**（conversation.ts + constants.ts）：invited/walkingOver/participating 三态 + typing 锁（15s 超时兜底）+ 每条消息 2s 冷却 + 对话 8 条/10 分钟预算 + 邀约接受率 0.8。参数全集中在一个 constants.ts。
4. **双字段人设**：每个 NPC 只有两段静态文本——长 identity + 一句 plan。设计角色=填表，改行为=改模板函数。
5. **分层存储与归档**：热状态一个小文档；高频消息独立表绕过引擎；对象消亡归档 + 维护 `participatedTogether` 关系图。

不抄：Convex 专属设施（vectorSearch/scheduler/generationNumber）、60fps 空间模拟、多世界心跳经济性设施、客户端 stop 词流式截断。

**重要真相**：原版 NPC 的「去哪、找谁聊、做什么」全是规则+随机数（`agentOperations.ts:93-178`，代码里自己留着 `TODO: have LLM choose the activity`）。LLM 只负责说话、总结、打分、反思。想要更强自主性得自己做。

---

## 3. SillyTavern：值得借鉴的设计

1. **极简 World Info**：每条知识 = `{keys[], content, constant, position}`；主/副关键字 + AND_ANY/NOT_ANY；扫描只看最近 N 条消息（默认 2，我们可用 4~6）；token 预算 = 上下文 × 百分比（5 行实现）；互斥组加权随机适合「NPC 互斥剧情状态」。
2. **具名插槽式 prompt 组装**：段落=具名 identifier + 固定顺序，内容生产与顺序编排解耦；逐段 token 记账，聊天历史从最新往旧填充（最老的先丢，近因永远在上下文）。不需要做可视化编辑器，保留插槽架构即可。
3. **滚动总结锚定存储**：每 10 条消息触发；旧总结作基底增量扩写；总结存在消息对象的 extra 字段上（锚定时间轴，可回溯）。
4. **非对称信息=不同扫描缓冲**：生成 NPC N 的台词时，扫描缓冲只放「N 知道的条目 + 全体可见条目」。与 Lunar 的 witnessed_by 异曲同工。
5. **Provider 能力矩阵**：按 source 声明「支持哪些字段」白名单，发请求前过滤。接 2~3 家 API 时每家只维护一个列表。

明确不抄：群聊系统、角色卡市场/PNG 规范、插件系统、Text Completion 双路径、instruct 模板市场、TTS/立绘/SD/swipe、多用户/profile。AGPL——只借鉴行为设计，不复制代码。

---

## 4. 对我们 V1 的综合启示

1. **底座**：fork project-lunar，按 §1.3 清单裁剪。事件溯源、记忆金字塔、NPC 心智、世界反应、plot lock、litellm 出口都是现成高质量骨架。
2. **必须新增**：每回合 2~4 选项生成（Lunar 没有）；极简中文前端三页（世界列表/创建表单/游戏页+3 抽屉）；创建表单→scenario JSON 的转换。
3. **必须改造**：LLM 调用预算（8~14 次→同步 2 次左右）；中文优先 prompt；API key 从 .env 移到创建/设置流程。
4. **行动合理性**：V1 靠 narrator prompt + 世界状态上下文约束，观察效果后再决定是否加显式判定调用。
5. **世界推进**：用 Lunar 的回合后异步 tick + timeskip，不做实时模拟。

# 拷问纪要（2026-08-16 · grill-me 第四轮）：实现 vs 锁定决策 vs 参考项目

> 方法：按 grill-me 的「无情的访谈」流程执行——每一问都给证据（file:line）、给裁决（✅ 符合 / ⚠️ 偏差 / ❌ 不符合 / ❓ 待裁决）。
> 本轮只做审查，**未改任何代码**。所有引用基于撰写时的工作区状态。

---

## 0. 现状快照（撰写时实测）

| 项 | 实测结果 |
|---|---|
| 后端 | FastAPI + SQLite，`backend/app` 11 个文件，19 个测试**全部通过**（含 mock 全流程 e2e） |
| 前端 | 新 UI（Sidebar + 剧情/事件树/人物 三页签 + 新建/设置弹窗），`vite build` 通过，`dist` 已于 23:38 重建并托管 |
| 运行 | 8000 端口服务在跑；`data/worlds.db` 为空库（settings 存有测试值） |
| 本轮观察到的活改动 | 会话期间用户正在收尾重构：修复了 7 个组件 `store.jsx→store.js` 的 import、修了 `_auto_title` 单字标题、删除了旧 UI 组件（WorldList/CreateWorld/GameView/Drawers） |

**一句话现状**：核心引擎符合锁定决策，前端刚完成「三抽屉 → 三页签」的产品形态迁移且已能构建；但**文档（README/DECISIONS）停留在旧形态**，且迁移过程中有一处数据展示丢失（大事记）。详见第二轮。

---

## 1. 第一轮拷问：十条锁定决策 vs 实现

### #1 底座路径「摘取重组」—— ✅
- 干净的 `backend/`+`frontend/`，无 fork 痕迹。`game_session.py` 284 行 vs Lunar 的 3,032 行，裁剪到位。
- 思想落地：事件溯源（`db.py:24-33` 事件表 + `world_state.rebuild` 全量重放）、四层记忆（`memory_engine.py`）、NPC 私有心智（`npc_mind.py`）、分级世界推进（`world_reactor.py`）、`[[META]]` 结构化尾块。
- **额外验证**：Lunar 自己已经废弃了「单次大 JSON 信封」式调用（`game_session.py:743-750`，注释明说 100k+ 上下文时模型会无视 JSON 格式指令）——我们「流式正文 + 结尾小块 [[META]]」的设计被反证为正确路径。

### #2 部署边界 —— ✅（一处文档级漂移）
- localhost、无鉴权、单机单库 ✓；`_sessions` 进程内 dict（与 Lunar 同款限制，单 worker 自用无碍）。
- ⚠️ **漂移**：决策原文是「API Key 存后端（**每世界配置**、预填上次）」，实现已迁移为**全局设置**（`settings` 表 + `routes.py:117-130` + SettingsModal；`WorldCreate` 里的模型字段保留仅为旧客户端兼容，注释明说「忽略」）。方向更优（改一次全生效），但 DECISIONS.md 与 README.md 都还写着「每世界填模型」——**文档必须同步，否则后续轮次的「锁定」会失真**。

### #3 回步预算「同步 1 次 LLM」—— ✅（一处 UX 隐患）
- 主循环确实只有 1 次同步调用（`game_session.py:_run_narrator` 内唯一 `stream_chat`）；副作用全部 `asyncio.create_task` 后台跑（`_schedule_side_effects`）。
- ⚠️ **隐患**：`process_action` 开头 `_drain_side_effects(timeout=90)`（`game_session.py:162-167`）——上一次的副作用（最多 3 次 aux 调用串行）没跑完时，玩家下一次行动最多被挡 90 秒。AI Town 的「在途操作槽」原则是**主循环永不被 LLM 阻塞**；Lunar 则完全不等。目前实现是「等但不取消」，手快/连点的玩家会感到卡顿，且 UI 无任何「后台正在推进世界」的提示。
- 开篇路径另有 1 次前置 aux 调用（NPC 卡解析 `_parse_npc_cards`），发生在 SSE 首事件之前，期间前端只有「载入世界……」——可接受但无进度反馈。

### #4 属性系统「轻数值」—— ✅
- 属性进状态、抽屉可见、变化由 npc_mind aux 判定（±3 上限，`npc_mind.py:59-68`）、prompt 显式提示成败倾向；无掷骰管线，符合锁定。
- 顺带验证：Lunar 的显式判定只在战斗模式；其「后果由世界裁决」也主要靠 prompt——与我们同思路。

### #5 选项生成「主叙事一次返回」—— ✅（两个可打磨点）
- `[[META]]` 尾块解析（`prompts.py:253-294` 括号配平 + 容错）、`normalize_meta` 兜底（缺字段给安全默认）、解析失败优雅降级为自由输入 ✓。
- 打磨点 ①：Lunar 有一个「**NONE 退出协议**」（`plot_generator.py:10-36`：允许合法输出空，prompt 明示「宁可空不可硬凑」）——我们 prompt 写死「2~4 个选项」，模型被鼓励硬凑选项。建议在叙事守则里加一行「局势确实没有好选项时，choices 可为空数组」。
- 打磨点 ②：选项无多样性/去重控制（同义选项可能连续出现）。低成本做法：prompt 加「选项两两之间方向必须不同」。

### #6 全中文 —— ✅
- 所有 system/user prompt 中文（`prompts.py`），UI 全中文，无混排残留。

### #7 纯回合制世界推进 —— ✅
- 只在 `meta.minutes ≥ 60` 时触发离屏推进（`config.py:22`，`game_session.py:190`），无后台实时模拟、无离线推进。
- 细节：`normalize_meta` 对 minutes 的兜底是 5 分钟——若模型连续漏输出 minutes，世界推进会静默失效（当前概率低，提示词已约束；记录在案）。

### #8 NPC 秘密与玩家视角 —— ✅（UI 一处丢失）
- `drawer_snapshot`（`world_state.py:154-185`）只暴露身份/关系/表面情绪；goal/secret_plan 不进 UI（e2e 测试断言 `secret_plan not in n`）✓。
- 信息隔离实现是「在场过滤」的简化版：只有 `present` 里的 NPC 才更新心智，且叙事 prompt 给每个 NPC 标注【仅叙事者可知】由模型自律——比 Lunar 的 witnessed_by 盖章 + auditor 复核弱，但符合 V1「不做审计员」的锁定。
- ⚠️ **丢失**：旧「世界」抽屉里的大事记（chronicle，记忆结晶的公开摘要列表）在新 UI 中**没有任何展示入口**（grep 全前端无 chronicle）。数据还在（`drawer_snapshot.world.chronicle`），只是 UI 没接。见第二轮。

### #9 模型与协议 —— ✅
- 默认 DeepSeek `deepseek-chat`，OpenAI 兼容（`llm.py`），支持任意兼容端点；`aux_model` 独立配置（这一点比 Lunar 强——Lunar 的 aux 模型当前就是主模型，`main.py:80`）；mock 演示模式覆盖全流程（含 npc_cards/npcmind/crystal/tick 四类 mock 回复）。

### #10 篇幅自适应 —— ⚠️ 只有 prompt 层面
- 叙事守则第 5 条写了自适应规则，但**没有硬性预算**：最近 6 回合原文（`RECENT_RAW_TURNS=6`）不做 token 记账/截断，长叙事叠满 6 回合后 prompt 可能膨胀。SillyTavern 的核心教训是「逐段记账、从旧到新裁剪、近因永在」；Lunar 有 provider 缩放的预算算术（`narrator_engine.py:416-468`）。DeepSeek 128K 窗口下短期无碍，但这是**长战役的第一风险点**，建议低成本补一个字符级预算 + 从旧截断。

---

## 2. 第二轮拷问：产品形态 vs 新 UI

锁定文档写的产品形态：首页列表 + 创建页 + 游戏页（右侧三个抽屉：角色/状态/世界）。
实际形态：左侧 Sidebar（世界列表 + 新建/设置）+ 顶部三页签（**剧情 / 事件树 / 人物**）。

| 问 | 裁决 | 说明 |
|---|---|---|
| 三抽屉 → 三页签，符合预期吗？ | ❓ | 页签化更像 Lunar（Sidebar+Tab）与 SillyTavern（聊天+侧栏）的主流布局，剧情页保持单一焦点，我认为是**正向迁移**；但这是产品形态变化，需要你确认认可 |
| 状态抽屉的内容去哪了？ | ⚠️ 分散 | 时间/地点/压力 → 剧情页头部 chips；关键物品 → 人物页。可接受，但「局势+物品+时间」不再同屏 |
| 大事记（chronicle） | ❌ 丢失 | 旧「世界」抽屉有，新 UI 无任何入口。要么补回（事件树页加一节），要么接受砍掉（但要更新 DECISIONS） |
| 事件树页 | ⚠️ 范围蔓延 | V1 不做清单里有「日志面板」「图谱」——事件树是只读时间线，介于两者之间。成本已付（复用 /history），体验价值高（复盘 + 展示选项/属性/物品变化），我建议**保留**，但要明确写进 DECISIONS |
| 创建页 → 弹窗 | ✅ | 更轻，模型配置移入全局设置后创建表单已瘦身，方向一致 |
| 文档同步 | ❌ | README.md 仍在描述已删除的 WorldList/CreateWorld/GameView/Drawers 和「右上角三个抽屉」；DECISIONS.md 产品形态段过期。**锁定决策的载体本身过期 = 决策失控的前兆** |

---

## 3. 第三轮拷问：三个参考项目「借了什么、漏了什么」

### 已借（实现中可对号入座）
- Project Lunar：事件溯源、四层记忆金字塔 + 级联、NPC 私有心智、世界推进分级、主线压力、`[[META]]` 尾块（Lunar 反证）、mock 演示模式。
- AI Town：记忆分层/重排思想（`memory_engine.py` 头注释明说）、「主循环 + 异步副作用」骨架。
- SillyTavern：滚动记忆（结晶即锚定式摘要的变体）、中文 bigram 检索（Lunar 的拉丁 regex 分词对中文无效——我们这一步是对的）。

### 漏了的高价值项（按性价比排序，均经 file:line 验证）

| # | 设计 | 出处 | 为什么值得 | 成本 |
|---|---|---|---|---|
| 1 | **约束注入 USER 消息而非 system prompt**：`[SYSTEM: …]` 指令直接拼进玩家输入，注释明说「仅靠 system prompt 提示不够，DeepSeek 常无视 FAIL 结果」 | Lunar `game_session.py:2708-2717` | 直接回答「造火箭=尝试而非成功」。我们的守则第 2 条只有 prompt 层约束 | 小 |
| 2 | **开场景窗口**：已结晶的旧回合不再以原始散文进历史（cursor 锚定） | Lunar `game_session.py:759-794` | 长战役上下文的最大杠杆；我们目前 6 回合原文 + 2400 字符记忆，无窗口概念 | 小-中 |
| 3 | **逐段 token 预算 + 从旧裁剪**（canAfford/insertAtStart，最新保留） | SillyTavern `openai.js:3822-3988` | 上面 #10 的补药；顺带解决事件树/history 无界增长 | 小 |
| 4 | **importance 微调用**：结晶时 0-9 打分（temp 0，1 token，解析失败回落 5），检索排序乘 importance；累计超阈值才触发高层反思 | AI Town `memory.ts:246-269,339-343` | 纯关键词检索的最便宜增强，一个 aux 字段的事 | 小 |
| 5 | **`reasoning_effort="none"`**（DeepSeek 推理计入 max_tokens 会导致空输出）| Lunar `llm_router.py:327-331` | 一行代码防 aux 空回复 | 极小 |
| 6 | **NONE 退出协议**（选项可合法为空） | Lunar `plot_generator.py:10-36` | 选项质量（见 #5） | 极小 |
| 7 | **每回合 USAGE 遥测**（SSE 内联 token 用量行） | Lunar `routes_game.py:375-386` | 免费的成本/延迟可观测性；我们副作用 `except Exception: pass` 全吞，排障靠猜 | 小 |
| 8 | **结构化 JSON 解析统一入口**：剥 reasoning 块 → tryParse → 失败回落 `'{}'`，永不崩下游 | SillyTavern `script.js:6252-6307` | 我们三个文件各有一份 `_loads` 复制粘贴；统一 + 剥思考块更稳 | 小 |
| 9 | **事件树/历史懒加载**：只渲染最近 N 条 + 「显示更多」，滚动锚点 | SillyTavern `script.js:1431-1524` | 长战役 DOM 悬崖 | 小-中 |
| 10 | **人格锚点**：`core_trait / speech_pattern / do_not_drift_to` | Lunar `game_session.py:2247-2287` | NPC 深度每 token 成本最低的加法；NPC 卡加 2 个字段即可 | 小 |
| 11 | **回合级看门狗/在途锁**：in-progress 槽 + 超时自愈（120s） | AI Town `agent.ts:57-63,238-257` | 我们无服务端回合锁，双连点会交错副作用；单用户下风险低 | 小 |
| 12 | **世界信息触发式隐藏设定**（keys+content+扫描深度+预算%） | SillyTavern `world-info.js:73,4624-5002` | 场景触发的 lore 与「NPC 互斥剧情状态」是 V2 的好料；V1 不推 | 中 |

### 明确不借（本轮再次确认）
- Lunar 战斗管线/审计员/图谱/日志面板/rewind；AI Town 空间模拟、向量检索、多世界心跳；SillyTavern 群聊/插件/角色卡 PNG/双路径——全部与锁定决策冲突。

---

## 4. 第四轮拷问：工程与健壮性

| 问 | 现状 | 风险 | 建议 |
|---|---|---|---|
| 副作用异常 | `_side_effects` 整体 `except Exception: pass`（`game_session.py:201`） | 失败静默，NPC 心智/世界推进悄悄不工作，无日志无告警 | 至少 `logging.exception`；可选第 7 项 USAGE 遥测 |
| 会话/任务泄漏 | `drop_session` 不取消 `_side_tasks`；删除世界后后台任务继续烧 token | 浪费 + 数据库已删后任务仍 `_append`（写不进去但不报错） | `drop_session` 时 cancel 未完成任务 |
| 历史无界 | `/history` 全量返回；EventTree 全量渲染 | 长战役 JSON 与 DOM 双膨胀 | 服务端截断/分页 + 前端懒加载（上表 #9） |
| 在场名单 | `meta.present` 缺失时回退上一回合名单（`prompts.py:315-317`） | 已离开的 NPC 被误认为在场，心智更新张冠李戴 | 缺省置空而不是回退旧名单 |
| 并发 | 无每世界锁 | 同世界双请求交错 | 低成本 `asyncio.Lock` 每 session 一把 |
| 会话内存 | `_sessions` 无上限无回收 | 多世界累积 | 空闲超时清理（低优先） |
| 测试 | 19 个，覆盖 e2e/meta/记忆/重建/设置 | npc_mind、world_reactor、llm 重试、prompt 关键路径无单测（仅 e2e 间接） | Lunar 每 engine 都有测试；补 3-4 个单测 |
| 开篇失败 | `_parse_npc_cards` 失败静默 → 无 NPC 开局；`_has_opening` 标记与 `state.turns` 双源 | 极端情况下玩家卡在「请先调用 start」 | 失败时给用户可见提示 |

---

## 5. 待裁决问题（grill-me 访谈的收尾）

1. **产品形态**：三页签（剧情/事件树/人物）+ 弹窗的形态，确认作为锁定形态？（我推荐确认，并同步更新 DECISIONS.md + README.md）
2. **大事记**：补回 UI（事件树页加「大事记」节，零后端改动）还是砍掉？
3. **副作用等待**：保持现状（最长 90s 阻塞）还是做「并行化 + 短超时 + UI 提示」？（我推荐后者，工作量小）
4. **V2 候选排序**：importance 打分 / 触发式隐藏设定(World Info) / auto-plot 冷却表 / @提及 NPC / 选项 NONE 协议——哪几个进下一轮？
5. **文档同步**：是否允许我更新 README.md / DECISIONS.md（纯文档，不碰代码）？

---

## 6. 结论

**总体符合预期**：十条锁定决策九条落地无虞，引擎骨架（1 次同步调用 + 异步副作用 + 事件溯源 + 记忆金字塔 + NPC 心智）与参考项目的最佳实践对得上，Lunar 的负面教训（大 JSON 信封）反证了 [[META]] 尾块设计的正确性。

**四个必须处理的偏差**（按优先级）：
1. 文档过期（README/DECISIONS 描述已删除的旧 UI 与旧形态）——决策载体失真；
2. 大事记 UI 丢失；
3. 长战役上下文无预算（#10）与副作用失败静默（第四轮第 1 条）；
4. 事件树页超出 V1 不做清单，需显式入册或移除。

**四个低成本高回报的「抄」**（下轮改代码时优先）：约束注入 USER 消息、importance 微调用、NONE 退出协议、统一 JSON 解析 + 剥 reasoning。

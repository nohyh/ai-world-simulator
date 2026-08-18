# AI 世界模拟器

一个极简 Web 版 AI 世界模拟文字游戏引擎。你创建世界，然后进入一个会自己运行、记忆和推进剧情的世界。

> **不是聊天软件，不是 Character AI，不是复杂 RPG 编辑器。**

- 设计决策：`docs/DECISIONS.md`（经三轮拷问锁定，不再扩功能、不换底座）
- 三个参考项目的代码级研究：`docs/RESEARCH.md`（Project Lunar / AI Town / SillyTavern）
- 参考仓库克隆在 `project-lunar/`、`ai-town/`、`SillyTavern/`（仅作参考，非依赖）

## 运行

**一键模式**（推荐，双击即可）：

```
start.bat      → http://localhost:8000
```

**开发模式**（改代码时用）：

```
dev.bat        → 后端 8000（热重载）+ 前端 5173（热更新）
```

**手动模式**：

```bash
cd backend && python -m venv .venv && .venv/Scripts/pip install -r requirements.txt
.venv/Scripts/python -m uvicorn app.main:app --port 8000
# 前端（可选，dist 已构建则后端直接托管）
cd frontend && npm install && npm run dev
```

**测试**：

```bash
cd backend && .venv/Scripts/python -m pytest -q
```

没有 API Key 也能玩：创建世界时 Provider 选「演示模式」（mock）。

## 玩法

1. 首次使用先点侧边栏底部**设置**：选 Provider（DeepSeek 默认 / 任意 OpenAI 兼容端点 / 演示模式）、填 API Key。对所有世界生效。
2. 侧边栏**＋ 新建世界**弹窗：世界观设定（必填）+ 目前状态（开局处境）+ 剧情基调 + 主角信息与属性 + 初始人物（自由描述，自动解析成 NPC 卡 + 关系初值 + 第一章框架）+ 补充说明。世界名可留空自动取。
3. 进入游戏（**剧情** tab）：AI 生成开篇，之后每回合正文流式出现，结尾给 2~4 个选项，也可以自由输入任何行动。每章顶部显示「第 X 章 · 标题 + 时间/地点」横幅；达成章节成功条件会自动收章、由主模型生成下一章框架。
4. **事件树** tab：按章节分组回顾每一回合——你做的抉择、剧情摘要、属性/物品变化、时间流逝；`★` 标记重要事件，死亡节点会标红。
5. **人物** tab：玩家卡片（属性条/关键物品）+ NPC 卡片（只显示 姓名/年龄/身份/现状）——内心、关系、数值全部对玩家隐藏。
6. 主角死亡时本章结束，出现「重新开始本章」——回到本章起点重来，前章历史保留。

## 引擎在做什么

**单作者**：每回合只有 **1 次同步主 LLM 调用**。Narrator 既是剧情作者也是状态记账员——它流式返回正文 + 结尾 `[[META]]` 结构化块：选项/时间/地点/在场人物 + 稀疏状态补丁（人物现状/当前想法/关系增减/重要事件/主角状态/章节达成）。

- **人物卡**（每角色一张）：基础信息（姓名/年龄/身份）+ 品质 + 性格/愿望/背景/当前想法；品质与性格是低频字段，只随重大经历演化。
- **有向关系表**：`好感 0~100` + 一句话羁绊（bond 比数值更重要），Narrator 只写增量，引擎负责钳制与记账。
- **信息隔离**：TURN 记录 `witnessed_by`，每个 NPC 只能看到自己目击过的历史；内心、关系、数值对玩家全隐藏。
- **世界推进**（异步，便宜模型）：叙事时间累计满 1 小时触发离屏变化；记忆每 4 回合结晶一次，short→medium→long→permanent 四层金字塔，中文 bigram 关键词检索。
- **章节**：每章 = 时间/地点范围 + 主题 + 成功/失败条件；玩家达成成功条件即自动收章，由**主模型**生成章节总结与下一章框架（Chapter Planner 绝不修改任何人物状态）。
- **死亡与重开**：主角死亡则本章时间线结束，可「重新开始本章」——事件溯源纯回滚到本章起点，前章历史保留。

所有状态都是事件溯源（SQLite 单库），重启后完整重建。

## 目录结构

```
backend/
  app/
    config.py          常量与节奏参数
    db.py              SQLite：世界表 + 事件溯源表
    llm.py             OpenAI 兼容客户端（流式/非流式）+ mock 演示模式
    prompts.py         全部中文 prompt + [[META]] 结构化块解析
    world_state.py    从事件流重建的内存态（玩家/NPC/关系/时间/地点/章节/重要事件）
    game_session.py   ★ 唯一的 Game Orchestrator（单作者 Narrator：1 次同步 LLM + 状态补丁 + 异步副作用）
    memory_engine.py  四层记忆金字塔 + bigram 检索
    world_reactor.py  离屏世界推进（分级）
    prompts.py        Narrator META 协议（选项/补丁/章节）与全部中文 prompt
    routes.py         REST + SSE（含 /chapter/advance、/restart-chapter）
  tests/              60+ 项测试
  dev_verify.py       冒烟：创建→开篇→回合→章节推进→重开（识别环境限制时用）
  dev_longrun.py      长局机械验证：3 世界 × 40+ 回合 × 跨章 + 重建一致
frontend/
  src/
    components/    Sidebar / TopBar / StoryTab / EventTreeTab / CharactersTab
                   / NewWorldModal / SettingsModal
    api.js         fetch + SSE 流式解析（支持中断）
frontend/dist/     已构建产物（后端自动托管）
```

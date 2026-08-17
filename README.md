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
2. 侧边栏**＋ 新建世界**弹窗：世界观设定（必填）+ 目前状态（开局处境）+ 剧情基调 + 主角信息与属性 + 初始人物（自由描述，自动解析成 NPC 卡；只有设定支持时才生成秘密）+ 补充说明。世界名可留空自动取。
3. 进入游戏（**剧情** tab）：AI 生成开篇，之后每回合正文流式出现，结尾给 2~4 个选项，也可以自由输入任何行动。
4. **事件树** tab：只读回顾每一回合——你做的抉择（当时候选选项高亮）、剧情摘要、属性/物品变化、时间流逝；页首只显示玩家可见的主线。
5. **人物** tab：玩家卡片（属性条/关键物品）+ NPC 卡片（身份/关系/当前状态）——全部是玩家视角，NPC 的秘密不会出现在 UI 里。

## 引擎在做什么

每回合只有 **1 次同步 LLM 调用**（主叙事流式返回正文 + 结尾结构化块：选项/时间流逝/地点/在场人物）。剧情发出后，**异步副作用**用便宜的辅助模型在后台完成：

- **NPC 心智更新**：在场 NPC 的情绪/目标/对玩家看法/秘密计划各自演化，互相隔离；
- **玩家属性与物品**：显著事件时属性 ±1~3（轻数值，影响叙事倾向而非掷骰）；
- **世界推进**：累计未处理的叙事时间达到 1 小时才触发离屏变化，跨回合累计并一次性消费（分级：小时/天/周）；
- **信息隔离**：TURN 事件记录 `witnessed_by`，NPC 心智只读取自己目击过的历史；离屏 NPC 也会随 World Tick 私下推进。
- **上下文预算**：记忆与近期历史按字符预算从最新内容向前装箱，避免长战役 prompt 无界增长。
- **记忆结晶**：每 4 回合压缩一次，short→medium→long→permanent 四层金字塔，中文 bigram 关键词检索，永久层全量注入——过去的重要事情不会忘。

主线有压力机制：连续 10 回合不推进主线，叙事 prompt 里会注入强制介入提示。所有状态都是事件溯源（SQLite 单库），重启后完整重建。

## 目录结构

```
backend/
  app/
    config.py          常量与节奏参数
    db.py              SQLite：世界表 + 事件溯源表
    llm.py             OpenAI 兼容客户端（流式/非流式）+ mock 演示模式
    prompts.py         全部中文 prompt + [[META]] 结构化块解析
    world_state.py     从事件流重建的内存态（玩家/NPC/时间/地点/主线/私有暗流）
    game_session.py    ★ 唯一的 Game Orchestrator（同步 1 次 LLM + 异步副作用）
    memory_engine.py   四层记忆金字塔 + bigram 检索
    npc_mind.py        NPC 私有心智更新（信息隔离）
    world_reactor.py   离屏世界推进（分级）
    routes.py          REST + SSE
  tests/               26 个测试（含 mock 全流程 e2e）
frontend/
  src/
    components/    Sidebar / TopBar / StoryTab / EventTreeTab / CharactersTab
                   / NewWorldModal / SettingsModal
    api.js         fetch + SSE 流式解析（支持中断）
frontend/dist/     已构建产物（后端自动托管）
```

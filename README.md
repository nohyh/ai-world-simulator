# AI World Simulator · AI 世界模拟器

一个会**持续运行、记忆并推进剧情**的 AI 世界模拟文字游戏引擎。玩家创建世界与角色后，系统会维护 NPC 私有心智、世界状态、长期记忆和事件历史，而不是把体验简化成一个聊天框。

> 重点不是“和角色聊天”，而是让一个小型叙事世界具备持续状态、信息隔离与自主演化能力。

## 核心亮点

- **单次主叙事调用**：每回合仅进行 1 次同步 LLM 调用，流式返回正文与结构化元数据。
- **NPC 私有心智**：情绪、目标、对玩家的看法与秘密计划独立维护，避免角色共享不该知道的信息。
- **事件溯源**：世界状态从 SQLite 事件流重建，重启后仍可恢复玩家、NPC、时间、地点与主线状态。
- **四层记忆系统**：`short → medium → long → permanent` 分层压缩，并结合关键词检索控制上下文预算。
- **离屏世界推进**：NPC 与世界会随叙事时间继续变化，而不是只有玩家点击时才存在。
- **SSE 流式体验**：前端实时显示剧情生成，支持中断。
- **Mock 演示模式**：没有 API Key 也可以体验完整流程。

## 玩法

1. 在设置中选择 DeepSeek、任意 OpenAI-compatible Provider，或 Mock 演示模式。
2. 创建世界：输入世界观、开局状态、剧情基调、主角与初始 NPC。
3. AI 生成开篇；之后每回合可选择系统给出的行动，也可自由输入。
4. 在 **事件树** 中回顾关键选择、剧情摘要、属性/物品变化和时间推进。
5. 在 **人物** 中查看玩家与 NPC 的可见状态；NPC 秘密不会泄漏到玩家视角。

## 引擎设计

```text
Player Action
     │
     ▼
Game Orchestrator
     │
     ├── 1× synchronous narrative LLM call
     │      └── story stream + structured metadata
     │
     ├── NPC mind updates
     ├── player state / inventory updates
     ├── world tick for off-screen events
     └── memory crystallization
            │
            ▼
      SQLite event stream
```

### 信息隔离

每个 TURN 事件记录 `witnessed_by`。NPC 心智更新只读取自己真正见证过的历史，因此不同 NPC 可以拥有不同认知和秘密计划。

### 上下文与记忆

近期历史按字符预算从新到旧装箱；每 4 回合进行一次记忆压缩，逐步沉淀到 permanent 层，避免长剧情下 prompt 无界增长。

### 主线压力机制

如果连续 10 回合没有推进主线，叙事 prompt 会注入更强的世界介入信号，让故事重新产生事件压力。

## 技术栈

- **Backend**: Python, FastAPI, SQLite
- **Streaming**: SSE
- **LLM**: OpenAI-compatible API + Mock provider
- **Frontend**: Web UI (Vite)
- **Testing**: pytest，包含 Mock 全流程测试

## 项目结构

```text
backend/
  app/
    db.py              SQLite + event sourcing
    llm.py             LLM client + mock mode
    prompts.py         narrative prompts + structured metadata parser
    world_state.py     rebuild world state from events
    game_session.py    main game orchestrator
    memory_engine.py   four-layer memory pyramid
    npc_mind.py        private NPC mind updates
    world_reactor.py   off-screen world progression
    routes.py          REST + SSE
  tests/
frontend/
  src/
    components/
    api.js
```

## 快速开始

### 一键运行（Windows）

```text
start.bat
```

打开 `http://localhost:8000`。

### 开发模式

```text
dev.bat
```

后端运行于 `8000`，前端开发服务器运行于 `5173`。

### 手动运行

```bash
cd backend
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt
.venv/Scripts/python -m uvicorn app.main:app --port 8000

cd ../frontend
npm install
npm run dev
```

### 测试

```bash
cd backend
.venv/Scripts/python -m pytest -q
```

## 设计资料

- [`docs/DECISIONS.md`](docs/DECISIONS.md)：关键产品与架构决策
- [`docs/RESEARCH.md`](docs/RESEARCH.md)：对 Project Lunar / AI Town / SillyTavern 的代码级研究

---

这个项目主要探索一个问题：**当 LLM 进入游戏系统后，怎样让“世界状态、角色认知与长期记忆”成为真正的软件状态，而不是全部依赖一次次聊天 prompt。**

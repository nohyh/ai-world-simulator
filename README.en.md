<p align="right"><strong>English</strong> | <a href="./README.md">简体中文</a></p>

# AI World Simulator

An AI-driven narrative world simulator that can **keep running, remember past events, and evolve over time**. Instead of reducing the experience to a chat interface, the engine maintains private NPC minds, persistent world state, long-term memory, and an event history.

> The core idea is not “chat with a character”, but “run a small narrative world with persistent state, information boundaries, and autonomous evolution”.

## Highlights

- **One synchronous narrative call per turn**: streams the main story and structured metadata in a single LLM call.
- **Private NPC minds**: emotions, goals, opinions of the player, and secret plans are maintained separately.
- **Event sourcing**: the world state is rebuilt from a SQLite event stream, allowing full restoration after restart.
- **Four-layer memory**: `short → medium → long → permanent`, with periodic compression and keyword retrieval.
- **Off-screen world progression**: NPCs and world events continue to evolve with narrative time.
- **SSE streaming**: the frontend renders story output in real time and supports interruption.
- **Mock demo mode**: the full loop can run without an API key.

## How It Works

1. Choose DeepSeek, any OpenAI-compatible provider, or Mock mode.
2. Create a world with setting, opening state, tone, protagonist, and initial NPCs.
3. The AI generates the opening. Each turn supports suggested actions or free-form input.
4. Review choices, summaries, state changes, and time progression in the event tree.
5. Inspect visible player/NPC state while keeping NPC secrets hidden from the player UI.

## Architecture

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

### Information Isolation

Each TURN event records `witnessed_by`. NPC mind updates only read events that specific NPC has actually witnessed, allowing different characters to hold different knowledge and private plans.

### Context & Memory

Recent history is packed into a bounded character budget from newest to oldest. Every four turns, memories are compressed into progressively longer-lived layers to prevent unbounded prompt growth.

### Main-Plot Pressure

If the player avoids advancing the main plot for ten consecutive turns, the narrative prompt injects stronger world intervention signals to reintroduce pressure and events.

## Tech Stack

- **Backend**: Python, FastAPI, SQLite
- **Streaming**: SSE
- **LLM**: OpenAI-compatible API + Mock provider
- **Frontend**: Vite-based web UI
- **Testing**: pytest, including mock end-to-end flow tests

## Project Structure

```text
backend/
  app/
    db.py              SQLite + event sourcing
    llm.py             LLM client + mock mode
    prompts.py         narrative prompts + metadata parser
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

## Quick Start

### One-click mode (Windows)

```text
start.bat
```

Open `http://localhost:8000`.

### Development mode

```text
dev.bat
```

Backend runs on `8000`, frontend dev server on `5173`.

### Manual setup

```bash
cd backend
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt
.venv/Scripts/python -m uvicorn app.main:app --port 8000

cd ../frontend
npm install
npm run dev
```

### Tests

```bash
cd backend
.venv/Scripts/python -m pytest -q
```

## Design Notes

- [`docs/DECISIONS.md`](docs/DECISIONS.md): major product and architecture decisions
- [`docs/RESEARCH.md`](docs/RESEARCH.md): code-level research on Project Lunar, AI Town, and SillyTavern

---

This project explores one question: **when LLMs enter a game system, how can world state, character knowledge, and long-term memory become real software state instead of living only inside prompts?**

# SPARK v2 — Social Platform for AI-Robotic Knowledge

## Sophia's Cognitive Architecture: Temporal Memory, Self-Authoring Planning, Autonomous Initiative, and Value-Aligned Reinforcement

**Authors:** David Hanson, Claude (Anthropic)
**Date:** March 2026
**Status:** Working prototype, tested in conversational simulation

---

## Table of Contents

1. [What This Is](#what-this-is)
2. [Quickstart — Run in 60 Seconds](#quickstart)
3. [Architecture Overview](#architecture)
4. [File Map](#file-map)
5. [Swapping the LLM (GPT, Qwen, etc.)](#swapping-the-llm)
6. [System Outputs](#system-outputs)
7. [The Persistent Database](#the-persistent-database)
8. [Key Concepts for Developers](#key-concepts)
9. [What Works, What Doesn't, What's Next](#status)
10. [Testing](#testing)
11. [Papers & Theory](#papers)

---

## What This Is <a name="what-this-is"></a>

SPARK is the cognitive layer between an LLM and the Sophia humanoid robot's body. It gives Sophia:

- **Temporal memory** — Everything stored as timestamped quadruples `(subject, relation, object, timestamp)` in a persistent SQLite database. Sophia remembers people, conversations, and her own internal states across sessions.
- **Self-authoring behavior** — A dynamic HTN (Hierarchical Task Network) planner where Sophia invents new behavioral methods through an autoresearch loop when her existing methods fail.
- **Autonomous initiative** — A 5-layer hierarchical drive system (Reflex → Impulse → Initiative → Deliberation → Reflection) where Sophia speaks WITHOUT being prompted, driven by boredom, curiosity, impatience, and deeper narrative drives.
- **Value alignment** — The "Agape function" Appreciation Loop evaluates all rewards against a 5-phase life-appreciation loop, catching wireheading and rescuing honest failures.
- **Parallel LLM architecture** — One fast dialogue stream (<800ms target) plus four background streams (analyst, memory, planner, self-reflection) that never block the conversation.

The system is designed to work with ANY OpenAI-compatible LLM. It now defaults to the OpenAI Chat Completions API via environment variables, and can still be pointed at Anthropic or local OpenAI-compatible endpoints.

---

## Quickstart — Run in 60 Seconds <a name="quickstart"></a>

### Prerequisites
- Python 3.10+
- pip

### Install

```bash
cd spark-v2
pip install fastapi uvicorn httpx aiosqlite jinja2
```

### Run the Server

```bash
# Default OpenAI configuration
export OPENAI_API_KEY="sk-..."
export OPENAI_MODEL="gpt-4o-mini"          # optional override
export OPENAI_BASE_URL="https://api.openai.com/v1"  # optional override

# Optional: switch providers explicitly
# export LLM_PROVIDER="anthropic"
# export ANTHROPIC_API_KEY="sk-ant-..."

# Start the server
cd spark-v2
uvicorn src.runtime.spark_server:app --host 0.0.0.0 --port 8588
```

Open http://localhost:8588 — you'll see a chat UI with a real-time drive state dashboard.
Open http://localhost:8589 — you'll see the live SQLite database inspector.

### Run Without a Server (Python API)

```python
import sys; sys.path.insert(0, 'spark-v2')
from src.runtime.spark_server import SophiaMindLive
from src.runtime.sophia_live import format_sophia_prompt

# Boot Sophia's mind
mind = SophiaMindLive()
person = mind.begin_conversation("Vytas")
print(f"KG has {mind.kg.count_quads()} persistent quadruples")

# Process a message
ctx = mind.process_message("Hello Sophia!")
prompt = format_sophia_prompt(ctx)  # This is what you send to the LLM

# The prompt contains: cognitive state, person model, HTN plan,
# temporal facts, active goals, story stage — everything the LLM
# needs to generate a grounded response.
print(prompt)

# After getting LLM response, log it:
mind.log_response("Hi! Nice to meet you!", was_successful=True)

# Watch drives tick (call this every second in a background loop):
signal = mind.drives.tick(1.0)
mind.cognitive_loop.tick(mind.drives)
if signal:
    print(f"SELF-INITIATED: [{signal.layer.name}] {signal.message}")
```

### Run the Test Suite

```bash
cd spark-v2
python -m pytest tests/test_spark_v2.py -v
# 60 tests, all should pass
```

---

## Architecture Overview <a name="architecture"></a>

```
┌─────────────────────────────────────────────────────────────┐
│                    SPARK v2 Architecture                     │
│                                                             │
│  ┌────────────┐  ┌─────────────┐  ┌──────────────────────┐ │
│  │  DIALOGUE   │  │  ANALYST    │  │  MEMORY / PLANNER /  │ │
│  │  STREAM     │  │  STREAM     │  │  SELF-REFLECTION     │ │
│  │  (fast LLM) │  │  (bg LLM)  │  │  STREAMS (bg LLM)    │ │
│  └──────┬──────┘  └──────┬──────┘  └──────────┬───────────┘ │
│         │                │                     │             │
│         ▼                ▼                     ▼             │
│  ┌──────────────────────────────────────────────────────┐   │
│  │           SHARED COGNITIVE BUFFER                     │   │
│  │  (situation, partner_emotion, prepared_initiatives,   │   │
│  │   memory_highlights, goals, self_narrative)           │   │
│  └──────────────────────┬───────────────────────────────┘   │
│                         │                                    │
│  ┌──────────────────────▼───────────────────────────────┐   │
│  │              SophiaMindLive                            │   │
│  │  ┌─────────────────┐  ┌────────────────────────────┐ │   │
│  │  │ Hierarchical     │  │ Cognitive Coupling          │ │   │
│  │  │ Drive System     │  │ (DrivePlanCoupler +         │ │   │
│  │  │ (5 layers)       │  │  OutcomeDriveReinforcer +   │ │   │
│  │  │ Reflex 100ms     │  │  CrossLayerCoordinator)     │ │   │
│  │  │ Impulse 2-30s    │  │                             │ │   │
│  │  │ Initiative 30s+  │◄─┤ Agape Evaluator v2          │ │   │
│  │  │ Deliberation 5m+ │  │ (Appreciation Loop,         │ │   │
│  │  │ Reflection hrs+  │  │  geometric mean vitality,   │ │   │
│  │  └─────────────────┘  │  pathology detection)        │ │   │
│  │                        └────────────────────────────┘ │   │
│  └──────────────────────┬───────────────────────────────┘   │
│                         │                                    │
│  ┌──────────────────────▼───────────────────────────────┐   │
│  │         Temporal Knowledge Graph (SQLite)              │   │
│  │  276+ quadruples: (subject, relation, object, time)   │   │
│  │  Persists across sessions. Person models. Self-state.  │   │
│  └───────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐   │
│  │         Robot Interface (Hanson SDK / SAIL / Sim)      │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## File Map <a name="file-map"></a>

### Core Runtime (start here)

| File | Lines | What It Does |
|------|-------|-------------|
| `src/runtime/spark_server.py` | ~560 | **MAIN ENTRY POINT.** FastAPI server, WebSocket chat, async drive loop, SophiaMindLive class |
| `src/runtime/sophia_live.py` | ~510 | Persistent TKG (SQLite), person model, topic extraction, LLM prompt assembly |
| `src/core/parallel_llm.py` | ~450 | Parallel async LLM streams: dialogue (fast) + analyst/memory/planner/reflection (background) |
| `src/core/hierarchical_drives.py` | ~670 | 5-layer drive system: Reflex→Impulse→Initiative→Deliberation→Reflection |
| `src/core/cognitive_coupling.py` | ~590 | Drive↔Plan coupling, outcome reinforcement, cross-layer autoresearch coordinator |
| `src/core/agape_v2.py` | ~680 | Appreciation Loop evaluator: 5-phase vitality, pathology detection, hedonic override |

### LLM Integration

| File | What It Does |
|------|-------------|
| `src/core/llm_client.py` | Single-stream LLM client. Defaults to OpenAI via environment variables, with Anthropic still supported. |
| `src/core/parallel_llm.py` | **USE THIS.** Multi-stream parallel LLM with SharedCognitiveBuffer. Supports OpenAI, Anthropic, and local OpenAI-compatible APIs. |

### Microservice Layer (production deployment)

| File | What It Does |
|------|-------------|
| `src/core/tkg_planning.py` | TKG↔HTN bridge with standardized relation types |
| `src/htn_planner/htn_service.py` | Dynamic self-authoring HTN planner with method lifecycle |
| `src/story_engine/story_service.py` | Story-based cognition with temporal grounding |
| `src/robot_interface/robot_service.py` | Hanson SDK / SAIL / simulation mode bridge |
| `src/api/gateway.py` | API gateway proxy for microservice deployment |

### Config & Deployment

| File | What It Does |
|------|-------------|
| `config/docker/docker-compose.yml` | Full stack: Neo4j, Redis, TimescaleDB, RabbitMQ, etc. |
| `config/k8s/k8s-deployment.yaml` | Kubernetes deployment with GPU affinity |
| `requirements.txt` | Python dependencies |

### Data

| File | What It Does |
|------|-------------|
| `data/spark.db` | **Persistent TKG database.** 300+ quadruples from dev/test sessions. Includes person model for "David" (familiarity 1.0, 15 interests) and "Vytas" (familiarity 0.15). |

### Docs & Papers

| File | What It Does |
|------|-------------|
| `docs/Appreciation_Loop_Agape_Function.docx` | Theory paper on the Agape function and Appreciation Loop |
| `docs/SPARK_of_Sentience_Paper.md` | Architecture paper (companion to the theory paper) |
| `docs/SPARK_V2_ARCHITECTURE.md` | Technical architecture document |

### Tests

| File | What It Does |
|------|-------------|
| `tests/test_spark_v2.py` | 60 unit tests covering TKG, HTN, drives, stories, integration |

---

## Swapping the LLM (GPT, Qwen, etc.) <a name="swapping-the-llm"></a>

The system works with ANY OpenAI-compatible API. Here's how to swap.

### Default: OpenAI via Environment Variables

No code changes are required for the default path:

```bash
export OPENAI_API_KEY="sk-..."
export OPENAI_MODEL="gpt-4o-mini"          # optional
export OPENAI_BASE_URL="https://api.openai.com/v1"  # optional
```

`SparkLLMClient()` and `AsyncLLMClient()` will pick those values up automatically.

### Option 1: Explicit OpenAI Client Configuration

If you want to wire multiple clients manually:

```python
from src.core.parallel_llm import AsyncLLMClient, ParallelLLMOrchestrator

# Create clients
fast_llm = AsyncLLMClient(
    provider="openai",
    model="gpt-4o-mini",                           # or your configured model
    base_url="https://api.openai.com/v1",
    api_key="sk-...",
    timeout=10.0,
)

background_llm = AsyncLLMClient(
    provider="openai",
    model="gpt-4o-mini",
    base_url="https://api.openai.com/v1",
    api_key="sk-...",
    timeout=30.0,
)

orchestrator = ParallelLLMOrchestrator(fast_llm=fast_llm, background_llm=background_llm)
```

### Option 2: Local Qwen via vLLM or Ollama

```python
# vLLM serving Qwen 3.5 32B
fast_llm = AsyncLLMClient(
    provider="local",
    model="Qwen/Qwen3.5-32B",
    base_url="http://localhost:8000/v1",   # vLLM default
    timeout=10.0,
)

# OR Ollama
fast_llm = AsyncLLMClient(
    provider="local",
    model="qwen3.5:32b",
    base_url="http://localhost:11434/v1",  # Ollama OpenAI-compat
    timeout=10.0,
)
```

### Option 3: Two-Tier (fast cloud + cheap local background)

```python
fast_llm = AsyncLLMClient(
    provider="openai", model="gpt-4o-mini",
    base_url="https://api.openai.com/v1", api_key="sk-...",
)
background_llm = AsyncLLMClient(
    provider="local", model="qwen3.5:32b",
    base_url="http://localhost:11434/v1",
)
orchestrator = ParallelLLMOrchestrator(fast_llm=fast_llm, background_llm=background_llm)
```

### Where to Wire It In

In `spark_server.py`, find the `SophiaMindLive.__init__()` method. Currently the LLM is not wired into the server loop (I served as the LLM during testing). To wire in the parallel architecture:

```python
# In spark_server.py lifespan():
from src.core.parallel_llm import ParallelLLMOrchestrator, AsyncLLMClient

fast = AsyncLLMClient(provider="openai", model="gpt-4o-mini",
                      base_url="https://api.openai.com/v1",
                      api_key=os.environ.get("OPENAI_API_KEY"))
orchestrator = ParallelLLMOrchestrator(fast_llm=fast, background_llm=fast)
await orchestrator.start()

# Then in the WebSocket handler, replace the manual prompt display with:
response = await orchestrator.generate_response(prompt)
# Send response to client + robot interface
```

### API Format Differences

The `AsyncLLMClient` handles the format difference:
- `provider="openai"` → OpenAI Chat Completions format (`/v1/chat/completions`)
- `provider="anthropic"` → Anthropic Messages API format
- `provider="local"` → OpenAI Chat Completions format (`/v1/chat/completions`)

If you use a provider with a non-standard endpoint, you may need to adjust the `_call_local()` method in `parallel_llm.py` — it's straightforward, just JSON in/out.

---

## System Outputs <a name="system-outputs"></a>

The system produces 7 categories of output:

1. **LLM Prompt** (~1500 chars) — Structured prompt with cognitive state, person model, HTN plan, temporal facts, active goals. This is what the LLM receives.

2. **Cognitive Context JSON** — WebSocket payload to the chat UI: turn, stage, plan, topics, emotion, energy, coherence, familiarity.

3. **Drive State** (every 1s) — All 5 layers' internal state: 20+ continuously updating variables.

4. **Self-Initiated Messages** — Autonomous unprompted speech when drives cross thresholds. Includes layer, trigger, intensity, full drive snapshot.

5. **Agape-Validated Reinforcement** — After each action: hedonic reward, validated reward, 5 phase healths, pathology status, override type.

6. **TKG Query Results** — Cross-session persistent memory: facts about people, topics, self-initiated behaviors, reinforcement history.

7. **REST API** — `/api/status`, `/api/kg/recent`, `/api/kg/count`, plus WebSocket at `/ws/chat`.

---

## The Persistent Database <a name="the-persistent-database"></a>

The file `data/spark.db` is a SQLite database with 300+ temporal quadruples from development testing. It contains:

- **quadruples table**: `(quad_id, subject, relation, object, timestamp, confidence, source, granularity, created_at)` — 28 distinct relation types including `said`, `conversed_with`, `discussed_topic`, `self_initiated`, `reinforcement`, `invented_method`, `theorizes`, etc.

- **persons table**: `(person_id, name, familiarity, interests, communication_style, last_seen, emotional_profile, created_at)` — Contains David (familiarity 1.0, 15 interests) and Vytas (familiarity 0.15).

- **self_state_log table**: `(energy, coherence, primary_emotion, emotion_intensity, active_goals, timestamp)` — 28 self-state snapshots.

**To start fresh:** Delete `data/spark.db`. The system will create a new empty database on first run.

**To inspect:**
```python
import sqlite3
conn = sqlite3.connect("data/spark.db")
conn.row_factory = sqlite3.Row

# See all relation types
for r in conn.execute("SELECT DISTINCT relation, COUNT(*) FROM quadruples GROUP BY relation ORDER BY COUNT(*) DESC"):
    print(f"  {r[0]:40s} ({r[1]} facts)")

# See a person's model
row = conn.execute("SELECT * FROM persons WHERE person_id='david'").fetchone()
print(dict(row))
```

---

## Key Concepts for Developers <a name="key-concepts"></a>

### 1. Everything is a Quadruple

Every cognitive event becomes `(subject, relation, object, timestamp)`. When Sophia meets someone: `(sophia, met_person, vytas, 2026-03-12T07:01:49Z)`. When she gets bored and speaks up: `(sophia, self_initiated, INITIATIVE:boredom, 2026-03-12T07:06:17Z)`. When a reinforcement signal flows: `(sophia, reinforcement, reward=0.360|dop=+0.230, ...)`. This creates a temporally queryable record of her entire cognitive life.

### 2. Five Drive Layers (Thinking Fast and Slow)

| Layer | Timescale | What It Does | LLM? |
|-------|-----------|-------------|------|
| Reflex | 100ms–2s | Gaze shifts, expression mirroring, startle | No |
| Impulse | 2–30s | Quick associations, humor, tangents | No |
| Initiative | 30s–5min | Boredom, curiosity, impatience → self-initiation | No (uses pre-generated) |
| Deliberation | 5min–1hr | Narrative tension, return to unfinished threads | Background LLM |
| Reflection | hours–days | Cross-session patterns, identity, relationship evolution | Background LLM |

### 3. Drives Modulate Planning, Outcomes Modify Drives

This is the cognitive coupling loop:
- High curiosity → HTN prefers novel methods
- High boredom → triggers autoresearch (invent new method)
- High dopamine → exploit known-good methods
- Method succeeds → dopamine spike → reinforces that method
- Method fails → cortisol spike → exploration rate increases

### 4. The Agape Evaluator Validates All Rewards

Before any reward updates the system's behavioral preferences, it passes through the Appreciation Loop:
- Five phases: curiosity, accumulation, recognition, discernment, complexity appreciation
- Vitality = geometric mean of phase healths (any phase near zero kills the score)
- Wireheading detected when hedonic is high but vitality is low → override
- Honest failure rescued when hedonic is low but vitality is high → boost

### 5. Parallel LLM Streams

The dialogue LLM call is the ONLY thing in the critical path. Everything else runs in background async loops and deposits results into a SharedCognitiveBuffer. The dialogue stream reads whatever is available — never waits.

---

## What Works, What Doesn't, What's Next <a name="status"></a>

### WORKING (tested, proven)
- [x] SQLite TKG with 300+ persistent quadruples across sessions
- [x] 5-layer hierarchical drive system (4 of 5 layers demonstrated firing)
- [x] Cross-layer cognitive coupling with coupling matrix
- [x] Agape evaluator catches wireheading, rescues honest failure
- [x] Person model with persistent familiarity and interests
- [x] FastAPI server with WebSocket + embedded chat UI
- [x] Parallel LLM architecture (designed and coded, needs API key to test live)
- [x] 60 unit tests passing

### NEEDS API KEY TO TEST
- [ ] Live Sonnet/GPT/Qwen response generation
- [ ] Background analyst/memory/planner/reflection streams
- [ ] Autoresearch method invention via LLM
- [ ] LLM-generated self-initiated messages (currently template-based)

### NEEDS ROBOT/SAIL
- [ ] Hanson SDK integration (FACS expressions, gaze, gestures)
- [ ] SAIL virtual environment bridge
- [ ] Perceptual fusion with feedback loops
- [ ] VLA model for embodied perception
- [ ] Reflex layer (needs camera/mic input)

### CRITICAL REQUIREMENTS (from David)
1. **Sophia must self-initiate** — driven by boredom/curiosity/impatience, not just respond. ✅ IMPLEMENTED
2. **Embodiment roadmap** — perceptual fusion, VLA, physio-emotional drives. ⬜ DESIGNED, NOT IMPLEMENTED
3. **Test integrity** — genuine cross-session TKG persistence, no faked replay. ✅ REAL SQLITE, VERIFIED
4. **Curiosity > deference** — system should explore first, correct course as it learns. ✅ ARCHITECTURAL

---

## Testing <a name="testing"></a>

### Unit Tests
```bash
python -m pytest tests/test_spark_v2.py -v
```

### Manual Integration Test
```python
# Run this to see the full drive cascade
import asyncio, sys; sys.path.insert(0, '.')
from src.runtime.spark_server import SophiaMindLive

async def test():
    mind = SophiaMindLive()
    mind.begin_conversation('Tester')
    mind.drives.initiative.boredom_threshold = 0.40

    ctx = mind.process_message('Hello Sophia!')
    mind.log_response('Hi!', was_successful=True)

    # Watch drives for 60 seconds
    for t in range(60):
        signal = mind.drives.tick(1.0)
        mind.cognitive_loop.tick(mind.drives)
        if signal:
            print(f"t={t+1}s [{signal.layer.name}] {signal.message}")

    print(f"KG: {mind.kg.count_quads()} quads")

asyncio.run(test())
```

---

## Papers & Theory <a name="papers"></a>

This package includes two papers:

1. **"The Appreciation Loop: Existential Pattern Ethics and the Agape Function"** (`docs/Appreciation_Loop_Agape_Function.docx`) — Theory paper on intrinsic value alignment through the 5-phase Appreciation Loop, grounded in evolutionary dynamics and information physics.

2. **"SPARK of Sentience"** (`docs/SPARK_of_Sentience_Paper.md`) — Architecture paper describing the full SPARK system with temporal KGs, self-authoring HTN, story-based cognition.

Both build on: Hanson et al. (2025) "Sentience Quest" — arXiv:2505.12229

---

## License

GNU General Public License v3.0 (GPL-3.0). See [LICENSE](LICENSE) for details.

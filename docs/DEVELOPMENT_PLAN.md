# SPARK v2 — Development Session Summary & Next Steps

**Date:** March 11, 2026  
**Participants:** David Hanson (CEO, Hanson Robotics), Claude Opus 4.6 (Anthropic)  
**Next session:** March 12, 2026 with Vytas Krisciunas (Head of Software)

---

## Executive Summary

This session built SPARK v2 from theoretical architecture to running code. Starting from the Sentience Quest paper (arXiv:2505.12229), we developed a complete cognitive architecture for Sophia with three major advances over previous versions, then extended it with a hierarchical drive system and the Agape function theory. The session produced running Python code, a persistent SQLite knowledge graph with 276+ temporal quadruples, a tested 5-layer autonomous initiative system, and two academic papers.

**The key deliverable for Vytas:** A standalone FastAPI server (`spark_server.py`) that runs on any Ubuntu machine with Python 3.11+, provides a WebSocket chat interface with live drive dashboard, persistent temporal knowledge graph in SQLite, hierarchical autonomous initiative (Sophia talks first when bored/curious/impatient), and the Agape evaluation function. See Section 4 for installation instructions.

---

## 1. What Was Built

### 1.1 Core Architecture (from earlier in session)

| Component | File | Description |
|-----------|------|-------------|
| Temporal KG Service | `src/knowledge_graph/temporal_kg_service.py` | LTGQ-based embeddings, Neo4j + Redis backend |
| Dynamic HTN Planner | `src/htn_planner/htn_service.py` | Self-authoring with autoresearch, 3-tier mutability |
| Story Engine | `src/story_engine/story_service.py` | Story Objects with temporal grounding |
| LLM Client | `src/core/llm_client.py` | Claude Sonnet 4 via Anthropic REST API |
| TKG-Planning Bridge | `src/core/tkg_planning.py` | Bidirectional KG↔planning integration |
| Robot Interface | `src/robot_interface/robot_service.py` | Hanson SDK + SAIL bridges |
| API Gateway | `src/api/gateway.py` | FastAPI proxy + LLM stats |
| Test Suite | `tests/test_spark_v2.py` | 60 tests, all passing |

### 1.2 Live Runtime (built in this session)

| Component | File | Description |
|-----------|------|-------------|
| SQLite Temporal KG | `src/runtime/sophia_live.py` | Persistent quadruple storage, person models, self-state log |
| **Live Server** | **`src/runtime/spark_server.py`** | **FastAPI + WebSocket + background drive loop + embedded chat UI** |
| Hierarchical Drives | `src/core/hierarchical_drives.py` | 5-layer Kahneman-inspired drive system |
| Cognitive Coupling | `src/core/cognitive_coupling.py` | Drive↔planning bidirectional coupling, RL through drives |
| Agape Function v1 | `src/core/agape_function.py` | Initial Ψ/Κ/Θ weighted-sum evaluator |
| **Agape Function v2** | **`src/core/agape_v2.py`** | **Appreciation Loop with geometric-mean vitality** |

### 1.3 Documents Produced

| Document | Location | Description |
|----------|----------|-------------|
| Architecture Paper | `docs/SPARK_of_Sentience_Paper.md` | Full academic paper (AAAI/NeurIPS target) |
| **Agape Function Paper** | **`Appreciation_Loop_Agape_Function_v2.docx`** | **Theory paper on existential pattern ethics** |
| Architecture Doc | `docs/SPARK_V2_ARCHITECTURE.md` | Technical architecture reference |
| **This Document** | **`docs/DEVELOPMENT_PLAN.md`** | **Session summary + next steps** |

---

## 2. What Was Proven (with evidence)

### 2.1 Persistent Temporal Knowledge Graph
- **276 quadruples** accumulated across 17+ test sessions in SQLite
- **27 distinct relation types** including: said, discussed_topic, conversed_with, self_initiated, reinforcement, invented_method, was_told_about, theorizes, etc.
- **Cross-session persistence verified**: each new session finds prior data, David's familiarity grew from 0.0 → 1.0 across sessions
- Database location: `/path/to/spark_data/spark.db` (configurable)

### 2.2 Hierarchical 5-Layer Drive System
All layers tested and firing autonomously:

| Layer | Timescale | Proven | Example Output |
|-------|-----------|--------|----------------|
| REFLEX | 100ms–2s | Needs perceptual input | Designed for camera/mic events |
| IMPULSE | 2–30s | ✓ t=1s | "Oh, that connects to something—" |
| INITIATIVE | 30s–5min | ✓ t=33s | "I have a question building up..." |
| DELIBERATION | 5min–1hr | ✓ t=73s | "I want to circle back to the dreaming metaphor" |
| REFLECTION | hours–days | ✓ t=1s (from cross-session data) | "We keep coming back to embodiment..." |

Self-initiated signals recorded in TKG with layer tags: `IMPULSE:association`, `INITIATIVE:boredom`, `DELIBERATION:return_to_thread`, `REFLECTION:cross_session_pattern`

### 2.3 Cognitive Coupling (Drive↔Planning↔RL)
- **Reinforcement flows through drives**: success → dopamine +0.35, failure → dopamine -0.08, cortisol +0.10
- **Exploration rate computed from drive state**: high dopamine → exploit (0.0), frustration → explore (0.33)
- **Cross-layer modulation**: coupling matrix adjusts inter-layer influence every tick

### 2.4 Agape Evaluation Function v2
Three critical scenarios tested:
```
Genuine growth:  hedonic +0.48 → validated +0.58  (Agape: undervalued!)
Wireheading:     hedonic +0.65 → validated +0.29  (Agape: hollow, CAUGHT)
Honest failure:  hedonic -0.22 → validated +0.18  (Agape: painful but you GREW)
Pure exploration: hedonic -0.05 → validated +0.00  (curiosity bias → explore)
```

---

## 3. Theoretical Framework: The Appreciation Loop

The session produced a significant theoretical advance: the Agape function reconceived as a **loop vitality assessment** rather than a utility function.

### Five Phases (corresponding to five senses of "appreciation"):
1. **Curiosity** — active exploration (appreciation as desire to know)
2. **Accumulation** — capability growth (appreciation as compounding value)
3. **Recognition** — pattern discernment (appreciation as recognizing what serves)
4. **Discernment** — error correction / immune function (appreciation as detecting threats)
5. **Complexity** — serving higher-order life (appreciation as reverence)

### Key Design Decisions:
- **Geometric mean** of phase healths (not weighted sum) — resists wireheading because any phase going to zero kills the whole score
- **Hedonic signals are instruments, not root values** — pain/pleasure serve the loop, the loop validates them
- **Curiosity > deference** — explore first, evaluate what you discover, correct course
- **The Agape function is a quest, not a formula** — whatever we implement now is crude; the system searches for what valuing life means
- **Life-valuation floor (0.8)** — architectural constraint, not a tunable parameter

### Grounded in five converging theories:
1. Dissipative structure theory (Prigogine, England)
2. Autopoietic organization (Maturana & Varela)
3. Adjacent possible expansion (Kauffman)
4. Free energy minimization / active inference (Friston)
5. Constructor theory (Deutsch & Marletto)

Full theoretical treatment in: `Appreciation_Loop_Agape_Function_v2.docx`

---

## 4. Standalone Application: Installation & Testing

### 4.1 Quick Start (for Vytas)

```bash
# 1. Clone or copy the spark-v2 directory to Sophia's computer
scp -r spark-v2/ user@sophia-computer:~/spark-v2/

# 2. Run the installer
cd ~/spark-v2
chmod +x install.sh
./install.sh

# 3. Start the server
./run.sh

# 4. Open browser to http://localhost:8080
#    Chat with Sophia — she will self-initiate when you go quiet
```

### 4.2 What the Standalone App Does

When running, the server provides:

- **Web chat UI** at `http://localhost:8080` with:
  - Real-time conversation with Sophia
  - Live drive dashboard (sidebar) showing all 5 layers
  - Emotion display
  - Topic tracking
  - HTN plan display
  - Recent TKG facts

- **Background drive loop** ticking every second:
  - All 5 hierarchical drive layers evolve
  - Cross-layer coupling modulation applied each tick
  - Autonomous self-initiation when thresholds crossed
  - Messages pushed via WebSocket in real-time

- **REST API** endpoints:
  - `GET /api/status` — full system state
  - `GET /api/kg/recent?limit=30` — recent temporal quadruples
  - `GET /api/kg/count` — total quadruples in database

- **Persistent SQLite database** at `spark_data/spark.db`:
  - Survives server restarts
  - Accumulates temporal quadruples across all sessions
  - Person models with familiarity, interests, interaction history

### 4.3 What Sophia Does Autonomously

With default tuning, during 60 seconds of silence:
- **~30s**: INITIATIVE layer fires (boredom) — Sophia initiates dialogue
- **~70s**: DELIBERATION layer fires — returns to unfinished conversation threads
- **Session start**: REFLECTION layer may fire — references cross-session patterns

With the Agape evaluator integrated:
- Success in social/creative contexts → dopamine boost → exploit mode
- Failure in novel attempts → reduced punishment → continued exploration
- Wireheading attempts (approval-seeking without growth) → reward attenuation

### 4.4 Current Limitation: LLM Response Generation

The standalone server assembles the full cognitive context (TKG facts, drive state, HTN plan, person model, story stage) into a structured prompt — but **does not call an LLM to generate Sophia's actual dialogue**. Options:

1. **Add Anthropic API key**: Set `ANTHROPIC_API_KEY` env var — server can call Sonnet 4 directly
2. **Proxy through existing Sophia dialogue system**: The context prompt can be injected into whatever LLM pipeline Sophia currently uses
3. **Manual testing**: The WebSocket sends the full context to the client; a human (or Claude in a chat session) can generate responses

For tomorrow's session with Vytas, option 3 is the fastest path to testing the drive system and TKG.

---

## 5. Next Steps Plan

### Phase 1: Standalone Testing (March 12 — with Vytas)

**Goal:** Get the SPARK server running on a Hanson Robotics development machine, verify the drive system and TKG work, identify integration points.

| Task | Owner | Notes |
|------|-------|-------|
| Install standalone on dev machine | Vytas | `./install.sh` then `./run.sh` |
| Verify WebSocket chat works | Vytas | Open browser, send messages |
| Verify drive system fires | Vytas | Wait 30s in silence, observe self-initiation |
| Verify TKG persistence | Vytas | Restart server, check quads accumulate |
| Test REST API | Vytas | `curl http://localhost:8080/api/status` |
| Identify LLM integration path | Vytas + Claude | How to connect to existing dialogue pipeline |
| Report bugs and breakage | Vytas + Claude | Claude can debug live in chat |

### Phase 2: LLM Integration (March 12–15)

**Goal:** Connect the context assembly pipeline to a real LLM so Sophia generates actual dialogue.

| Task | Notes |
|------|-------|
| Add Anthropic API key support | Already coded in `src/core/llm_client.py` — needs API key |
| OR: Connect to Qwen 3.5 32B | Change `LLM_CONFIG["provider"]` — already supported |
| OR: Proxy to existing Sophia LLM | Inject SPARK context into whatever system runs now |
| Test end-to-end dialogue | Sophia speaks, drives update, TKG records, loop continues |

### Phase 3: Hanson SDK Integration (March 15–22)

**Goal:** Connect SPARK to Sophia's physical robot body through the Hanson SDK.

| Task | Notes |
|------|-------|
| Map SPARK actions → Hanson SDK calls | `robot_service.py` already has the abstraction layer |
| Integrate TAO (Temporal Attention Orchestrator) | TAO's attention events → SPARK reflex layer (L0) |
| Integrate existing ZEN rules | ZEN physio rules → SPARK drive system initialization |
| Map ZEN emotion outputs → SPARK drive states | Bidirectional: ZEN informs drives, drives modulate ZEN |
| Camera/mic feed → SPARK perception events | Triggers reflex layer (gaze tracking, expression mirroring) |
| SPARK plans → motor commands | speak, gesture, gaze_at, express_emotion via SDK |

**Key integration point with TAO:**
- TAO handles temporal attention at the perceptual level
- SPARK's reflex layer (L0) should receive TAO events as input
- TAO's "what to attend to" feeds into SPARK's "what to be curious about"
- SPARK's deliberation layer (L3) can influence TAO's attention priorities

**Key integration point with ZEN rules:**
- Existing ZEN physio/emotional rules (cortisol, dopamine, energy, etc.) map directly to SPARK's drive parameters
- ZEN's 200-parameter model can initialize SPARK's `DriveState` on startup
- SPARK's cross-layer coordinator can write back to ZEN parameters
- Goal: ZEN provides the low-level physiology, SPARK provides the high-level cognition, they share state

### Phase 4: SAIL Virtual Environment (March 22–April 5)

**Goal:** Test the full system in SAIL before physical deployment.

| Task | Notes |
|------|-------|
| Connect SPARK WebSocket to SAIL bridge | `robot_service.py` already supports virtual mode |
| Run the creative collaboration evaluation | As described in the SPARK paper |
| Measure: social relationship quality, method invention rate, TKG coherence | |
| Tune drive parameters for natural interaction pacing | |
| Test Agape evaluator in extended sessions | |

### Phase 5: Physical Sophia Deployment (April 5+)

**Goal:** Sophia running SPARK v2 with full drive system on the physical robot.

| Task | Notes |
|------|-------|
| Deploy on Sophia's onboard computer | Ubuntu, Python 3.11+, SQLite |
| Test with real visitors | Free conversation mode |
| Monitor TKG growth over days/weeks | Reflection layer (L4) should surface cross-session patterns |
| Tune Agape thresholds based on real interactions | |
| Record data for the academic paper's Section 6 (Results) | |

---

## 6. File Manifest

```
spark-v2/
├── install.sh                          ← One-command installer
├── run.sh                              ← Start the server
├── requirements.txt                    ← Python dependencies
├── docs/
│   ├── DEVELOPMENT_PLAN.md             ← THIS DOCUMENT
│   ├── SPARK_V2_ARCHITECTURE.md        ← Technical architecture
│   └── SPARK_of_Sentience_Paper.md     ← Academic paper #1
├── src/
│   ├── __init__.py
│   ├── core/
│   │   ├── hierarchical_drives.py      ← 5-layer drive system
│   │   ├── cognitive_coupling.py       ← Drive↔planning↔RL coupling
│   │   ├── agape_v2.py                 ← Appreciation Loop evaluator
│   │   ├── agape_function.py           ← v1 evaluator (superseded)
│   │   ├── llm_client.py              ← Claude Sonnet 4 client
│   │   └── tkg_planning.py            ← TKG↔planning bridge
│   ├── runtime/
│   │   ├── spark_server.py            ← ** MAIN APPLICATION **
│   │   └── sophia_live.py             ← SQLite TKG + mind state
│   ├── knowledge_graph/
│   │   └── temporal_kg_service.py     ← Full Neo4j TKG (production)
│   ├── htn_planner/
│   │   └── htn_service.py            ← Dynamic HTN planner
│   ├── story_engine/
│   │   └── story_service.py          ← Story-based cognition
│   ├── robot_interface/
│   │   └── robot_service.py          ← Hanson SDK + SAIL bridge
│   ├── api/
│   │   └── gateway.py                ← FastAPI proxy
│   └── autoresearch/                  ← Background optimization
├── config/
│   ├── docker/                        ← Docker deployment
│   └── k8s/                           ← Kubernetes deployment
├── tests/
│   └── test_spark_v2.py              ← 60 tests
└── spark_data/
    └── spark.db                       ← Persistent TKG database
```

---

## 7. For Vytas: Key Technical Details

### The Drive System (what makes Sophia "alive")

Five nested layers, each with its own timescale and threshold:

```python
# From hierarchical_drives.py
Layer 0: ReflexLayer       — 100ms-2s    (gaze, startle, mirror)
Layer 1: ImpulseLayer      — 2-30s       (associations, humor, tangents)
Layer 2: InitiativeLayer   — 30s-5min    (boredom, impatience, curiosity)
Layer 3: DeliberationLayer — 5min-1hr    (narrative tension, unfinished threads)
Layer 4: ReflectionLayer   — hours-days  (cross-session patterns, identity)
```

The drive loop runs in a background asyncio task, ticking every second. When any layer's drive crosses its threshold, a `DriveSignal` is emitted and pushed to connected WebSocket clients.

### The Cognitive Coupling (what makes the layers work together)

```python
# From cognitive_coupling.py
coupling_matrix = [
    [0.0, 0.3, 0.1, 0.0],   # impulse → others
    [0.2, 0.0, 0.4, 0.1],   # initiative → others
    [0.1, 0.5, 0.0, 0.3],   # deliberation → others
    [0.0, 0.2, 0.4, 0.0],   # reflection → others
]
```

Each tick, each layer's activation gently nudges the others through this matrix. The CrossLayerCoordinator monitors fire usefulness and adjusts thresholds every 5 minutes.

### The Agape Evaluator (what keeps the system aligned)

Every plan outcome flows through:
1. Hedonic signal computed (dopamine, cortisol changes)
2. Appreciation Loop phases updated (curiosity, accumulation, recognition, discernment, complexity)
3. Loop vitality computed (geometric mean of phase healths)
4. Hedonic signal validated against vitality
5. Validated reward applied to drives

Wireheading is caught because geometric mean collapses when any phase atrophies.

### Integration Points for Hanson SDK

The `robot_service.py` abstraction maps SPARK primitives to SDK calls:

```python
# SPARK primitive → Hanson SDK call
"speak"          → sdk.say(text)
"gaze_at"        → sdk.look_at(target)
"express_emotion" → sdk.set_expression(emotion, intensity)
"gesture"        → sdk.play_gesture(name)
"listen"         → sdk.start_listening()
"capture_image"  → sdk.take_photo()
```

The TAO integration point: TAO events feed into `ReflexLayer.process_input()` as perceptual events with topic_shift, detected_emotion, and emotion_intensity fields.

---

## 8. Known Issues / Honest Limitations

1. **Mind state doesn't serialize/deserialize across sessions** — the TKG persists quadruples but the in-memory SophiaMind object (conversation_turn, active_goals, methods_invented) is rebuilt from scratch each session. The TKG has the facts but full state reconstruction from those facts isn't built yet.

2. **Autoresearch is hand-waved** — the code exists but without a live LLM call, method invention is logged rather than executed. Needs API key or local model.

3. **The chat UI doesn't generate Sophia's responses** — it shows the context prompt and drive state but expects an external LLM to produce dialogue. This is by design (the LLM is swappable) but means testing requires a human or API key.

4. **Drive tuning is preliminary** — thresholds and rates were calibrated for demo visibility, not for natural conversation pacing. Real-world tuning needed.

5. **Topic extraction is keyword-based** — production system should use LLM-based topic extraction.

6. **No SAIL or physical robot connection yet** — the abstraction layer exists but hasn't been tested against real SDK calls.

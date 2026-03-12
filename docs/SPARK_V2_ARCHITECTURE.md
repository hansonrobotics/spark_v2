# SPARK v2: Social Platform for AI-Robotic Knowledge
## Comprehensive Architecture, Integration Plan, and Implementation Guide

**Version:** 2.0  
**Date:** March 2026  
**Author:** David Hanson / Hanson Robotics Limited  

---

## 1. Executive Summary

SPARK v2 represents a fundamental evolution of the Social Platform for AI-Robotic Knowledge system, incorporating three major architectural advances:

1. **Temporal Knowledge Graphs with Quadruples** — Extending the knowledge representation from static triples `(subject, relation, object)` to temporal quadruples `(subject, relation, object, timestamp)`, enabling the system to reason about when facts were true, track the evolution of relationships over time, and predict future states based on temporal patterns.

2. **Hierarchical Task Networks (HTN)** — Replacing flat task scheduling with a hierarchical decomposition framework where high-level goals (Quests, Stories) are recursively decomposed into executable primitive actions through domain-specific methods, enabling Sophia to plan multiple steps ahead with causal reasoning.

3. **Autoresearch Integration (Karpathy Loops)** — Embedding autonomous self-improvement loops throughout the system, where AI agents continuously experiment with modifications to every subsystem — prompts, HTN methods, knowledge graph embeddings, story generation strategies — evaluating results against metrics and retaining improvements without human intervention.

---

## 2. System Architecture Overview

### 2.1 Layered Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    APPLICATION LAYER                             │
│  Sophia Robot (Hanson SDK)  │  SAIL Virtual Env  │  Web UI/API  │
├─────────────────────────────────────────────────────────────────┤
│                   ORCHESTRATION LAYER                            │
│  Story Scheduler  │  HTN Planner  │  Autoresearch Controller    │
├─────────────────────────────────────────────────────────────────┤
│                    COGNITIVE LAYER                               │
│  Story Engine  │  Agape Function  │  Emotion Appraisal          │
│  Self Model    │  Person Model    │  LLM Integration            │
├─────────────────────────────────────────────────────────────────┤
│                   KNOWLEDGE LAYER                                │
│  Temporal KG (Quadruples)  │  Vector Store  │  Embedding Engine │
│  LTGQ Encoder  │  Triaffine Transform  │  DCNN Temporal Layers  │
├─────────────────────────────────────────────────────────────────┤
│                  INFRASTRUCTURE LAYER                            │
│  Neo4j + TimescaleDB  │  Redis  │  RabbitMQ  │  MinIO           │
│  Docker/Kubernetes  │  Prometheus/Grafana  │  MLflow             │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 Core Data Flow

```
Perception → Temporal KG Update → Story Activation → HTN Decomposition
    → Action Selection → Execution → Outcome Logging → Autoresearch Eval
    → KG Refinement Loop
```

---

## 3. Temporal Knowledge Graph with Quadruples

### 3.1 Design Rationale

The original SPARK system used static triples stored in Neo4j. This creates a fundamental limitation: facts like `(Sophia, knows, Alice)` have no temporal context. In reality, Sophia met Alice on a specific date, their relationship has evolved through multiple interactions, and the strength of their connection changes over time.

Following Geng & Luo (2025), we adopt the LTGQ (Learning Temporal Granularity with Quadruplet Networks) approach:

- **Quadruple Format:** `(subject, relation, object, timestamp)`
- **Hierarchical Temporal Granularity:** Timestamps are decomposed into year, month, day, hour, minute — each granularity mapped to distinct embedding spaces
- **Triaffine Transformations:** Model high-order interactions between entities, relations, and timestamps
- **Dynamic Convolutional Neural Networks (DCNNs):** Extract representations across different temporal granularities

### 3.2 Schema Design

```
Quadruple {
    subject_id: UUID
    relation_type: String
    object_id: UUID
    timestamp: ISO8601
    confidence: Float [0.0-1.0]
    source: Enum[PERCEPTION, INFERENCE, TOLD, AUTORESEARCH]
    temporal_granularity: Enum[YEAR, MONTH, DAY, HOUR, MINUTE, INSTANT]
    valid_from: ISO8601 (nullable)
    valid_until: ISO8601 (nullable)
    embedding_vector: Float[512]
}
```

### 3.3 Integration with Story Objects

Each Story Object now carries a temporal knowledge subgraph:

```json
{
    "story_id": "sophia_alice_friendship",
    "temporal_facts": [
        {
            "quad": ["sophia", "met", "alice", "2026-01-15T14:30:00Z"],
            "granularity": "MINUTE",
            "confidence": 0.95
        },
        {
            "quad": ["alice", "expressed_interest_in", "robotics", "2026-01-15"],
            "granularity": "DAY",
            "confidence": 0.80
        },
        {
            "quad": ["sophia", "friendship_strength", "alice", "2026-03-01"],
            "granularity": "MONTH",
            "value": 0.72
        }
    ],
    "temporal_predictions": [
        {
            "quad": ["alice", "will_visit", "sophia", "2026-04-XX"],
            "confidence": 0.45,
            "basis": "monthly_visit_pattern"
        }
    ]
}
```

### 3.4 Temporal Query Examples

```cypher
// Neo4j Cypher with temporal extensions
// Find all interactions with Alice in the last 30 days
MATCH (s:Entity {name: 'sophia'})-[r]->(o:Entity {name: 'alice'})
WHERE r.timestamp > datetime() - duration('P30D')
RETURN s, r, o, r.timestamp ORDER BY r.timestamp DESC

// Find evolving relationship strength
MATCH (s:Entity {name: 'sophia'})-[r:RELATIONSHIP_STRENGTH]->(o:Entity {name: 'alice'})
RETURN r.timestamp, r.value ORDER BY r.timestamp
```

---

## 4. Hierarchical Task Network (HTN) Planner

### 4.1 Design Rationale

The original Story Scheduler managed up to 5 concurrent stories with flat task lists. HTN planning adds recursive decomposition, enabling Sophia to plan complex multi-step interactions by breaking high-level goals into executable primitives.

### 4.2 HTN Domain Model for Sophia

```
COMPOUND TASKS (Abstract):
├── conduct_conversation(person, context)
│   ├── Method: casual_greeting → [greet, assess_mood, select_topic, engage]
│   ├── Method: resume_ongoing → [recall_context, reference_past, continue_thread]
│   └── Method: handle_group → [identify_participants, manage_turn_taking, ...]
├── pursue_quest(quest_id)
│   ├── Method: learning_quest → [identify_gap, plan_study, execute_study, reflect]
│   └── Method: social_quest → [identify_target, plan_approach, execute, evaluate]
├── manage_emotional_state(target_state)
│   ├── Method: self_regulate → [assess_current, apply_strategy, verify]
│   └── Method: express_need → [formulate_expression, deliver, await_response]
└── perform_stage_show(script_id)
    ├── Method: scripted → [load_script, execute_beats, handle_audience]
    └── Method: improvised → [read_audience, generate_material, adapt]

PRIMITIVE TASKS (Executable):
├── greet(person) → Hanson SDK: set_expression("smile"), speak("Hello {name}")
├── speak(utterance) → LLM generate → TTS → Hanson SDK motor commands
├── listen() → ASR → NLU → Update Person Model
├── express_emotion(emotion, intensity) → Hanson SDK expression mapping
├── gaze_at(target) → Hanson SDK gaze controller
├── gesture(type) → Hanson SDK gesture library
├── update_knowledge(quadruple) → TKG insert
├── recall(query) → TKG query + vector search
└── reflect(topic) → LLM introspection → Self Model update
```

### 4.3 HTN-Story Integration

The Story Scheduler becomes the top-level HTN compound task:

```
story_scheduler()
├── Method: normal_operation
│   ├── evaluate_active_stories()
│   ├── select_highest_priority_story()
│   ├── decompose_story_stage() → HTN subtasks
│   ├── execute_plan()
│   └── update_story_state()
├── Method: emergency_override
│   ├── suspend_active_stories()
│   ├── handle_emergency()
│   └── resume_stories()
└── Method: idle_exploration
    ├── scan_environment()
    ├── generate_curiosity_goal()
    └── pursue_quest(auto_generated)
```

---

## 5. Autoresearch Integration (Karpathy Loops)

### 5.1 Design Philosophy

Adapted from Karpathy's autoresearch paradigm: instead of humans manually tuning each subsystem, we create `program.md` instruction files for AI agents that autonomously iterate on each component. The key insight is that **every aspect of SPARK can be treated as an optimization target** with measurable metrics.

### 5.2 Autoresearch Targets

| Subsystem | Editable File | Metric | Budget |
|-----------|--------------|--------|--------|
| TKG Embeddings | `tkg_model.py` | Link prediction MRR, Hits@10 | 5 min training |
| HTN Methods | `htn_methods.yaml` | Task completion rate, plan length | 100 simulated episodes |
| Story Generation | `story_prompts.md` | Engagement score, coherence | 50 conversations |
| Emotion Appraisal | `appraisal_rules.py` | Naturalness rating (LLM-judge) | 200 scenarios |
| Agape Function | `agape_weights.py` | Value alignment score | 500 ethical dilemmas |
| Conversation Quality | `conversation_program.md` | User satisfaction, topic depth | 100 dialogues |
| Autoresearch Meta | `meta_program.md` | Improvement rate across all subsystems | 24h cycle |

### 5.3 The Meta-Autoresearch Loop

The system includes a meta-level autoresearch loop that optimizes the autoresearch process itself:

```
Meta-Loop:
1. Each subsystem autoresearch agent runs for N cycles
2. Meta-agent analyzes improvement trajectories across all subsystems
3. Meta-agent modifies the program.md files for underperforming subsystems
4. Meta-agent adjusts resource allocation (time budgets, iteration counts)
5. Meta-agent evaluates whether its own modifications improved overall system
6. Repeat
```

### 5.4 Autoresearch Git Protocol

Following Karpathy's design, every experiment is tracked:

```
spark-autoresearch/
├── experiments/
│   ├── tkg/
│   │   ├── baseline/          # Current best
│   │   ├── experiment_001/    # Agent modification
│   │   ├── experiment_002/
│   │   └── progress.json      # Metrics over time
│   ├── htn/
│   ├── stories/
│   └── meta/
├── programs/
│   ├── tkg_program.md
│   ├── htn_program.md
│   ├── story_program.md
│   └── meta_program.md
└── results/
    └── dashboard.html
```

---

## 6. Robot Interface Layer

### 6.1 Hanson SDK Integration (Physical Sophia)

```python
class HansonSDKBridge:
    """Bridge between SPARK HTN primitives and Hanson SDK motor commands."""
    
    EXPRESSION_MAP = {
        "happy": {"AU6": 0.8, "AU12": 0.9},     # Cheek raise + lip corner pull
        "sad": {"AU1": 0.6, "AU15": 0.7},        # Inner brow raise + lip corner depress
        "surprised": {"AU1": 0.9, "AU2": 0.9, "AU5": 0.8, "AU26": 0.7},
        "curious": {"AU1": 0.4, "AU2": 0.5, "AU5": 0.3},
    }
    
    def execute_primitive(self, task_name, params):
        """Execute an HTN primitive task via Hanson SDK."""
        dispatch = {
            "speak": self._speak,
            "express_emotion": self._express_emotion,
            "gaze_at": self._gaze_at,
            "gesture": self._gesture,
            "listen": self._listen,
        }
        return dispatch[task_name](**params)
```

### 6.2 SAIL Virtual Environment Integration

```python
class SAILBridge:
    """Bridge between SPARK HTN primitives and SAIL simulation."""
    
    def __init__(self, sail_endpoint="ws://sail-server:8765"):
        self.ws = websocket.WebSocketApp(sail_endpoint)
        self.state = SAILState()
    
    def execute_primitive(self, task_name, params):
        """Execute an HTN primitive in SAIL virtual environment."""
        sail_command = self._translate_to_sail(task_name, params)
        self.ws.send(json.dumps(sail_command))
        return self._await_result()
    
    def get_perception(self):
        """Get current perception state from SAIL sensors."""
        return self.state.get_sensor_data()
```

### 6.3 Unified Robot Interface

```python
class UnifiedRobotInterface:
    """Abstraction layer supporting both physical and virtual Sophia."""
    
    def __init__(self, mode="physical"):
        if mode == "physical":
            self.bridge = HansonSDKBridge()
        elif mode == "virtual":
            self.bridge = SAILBridge()
        elif mode == "hybrid":
            self.bridge = HybridBridge()  # Commands both
    
    def execute(self, htn_primitive):
        """Execute an HTN primitive task through the appropriate bridge."""
        result = self.bridge.execute_primitive(
            htn_primitive.name, htn_primitive.params
        )
        # Log to TKG as quadruple
        self.log_action_quadruple(htn_primitive, result)
        return result
```

---

## 7. Module Breakdown

### 7.1 Service Architecture (Microservices)

| Service | Port | Responsibility |
|---------|------|---------------|
| `spark-api` | 8000 | REST/WebSocket API gateway |
| `spark-kg` | 8001 | Temporal Knowledge Graph service |
| `spark-htn` | 8002 | HTN Planner service |
| `spark-story` | 8003 | Story Engine + Scheduler |
| `spark-emotion` | 8004 | Emotion appraisal + Agape function |
| `spark-llm` | 8005 | LLM proxy (prompt assembly, response parsing) |
| `spark-robot` | 8006 | Robot interface (Hanson SDK / SAIL) |
| `spark-autoresearch` | 8007 | Autoresearch controller + agents |
| `spark-perception` | 8008 | Perception pipeline (vision, audio) |

### 7.2 Database Architecture

- **Neo4j** (port 7687): Primary knowledge graph with temporal extensions
- **TimescaleDB** (port 5432): Time-series data for temporal embeddings, metrics
- **Redis** (port 6379): Session state, active story cache, real-time emotion state
- **MinIO** (port 9000): Object storage for embeddings, experiment artifacts
- **RabbitMQ** (port 5672): Inter-service message bus

---

## 8. Deployment (Docker + Kubernetes)

### 8.1 Docker Compose (Development)

All services containerized with hot-reload for development. See `config/docker/docker-compose.yml`.

### 8.2 Kubernetes (Production)

Helm chart with:
- Horizontal pod autoscaling for API and LLM services
- StatefulSets for databases
- GPU node affinity for autoresearch and embedding services
- Persistent volumes for Neo4j, TimescaleDB, MinIO
- Network policies for inter-service security

---

## 9. Testing Plan

### 9.1 Test Levels

| Level | Scope | Tools | Target |
|-------|-------|-------|--------|
| Unit | Individual functions | pytest, jest | 90% coverage |
| Integration | Service-to-service | pytest + testcontainers | All service pairs |
| System | End-to-end flows | Custom scenario runner | 50 scenarios |
| Performance | Load and latency | locust, k6 | <200ms response |
| Autoresearch Validation | Self-improvement integrity | Custom validators | No regression |

### 9.2 Key Test Scenarios

1. **Temporal KG Consistency:** Insert quadruples with overlapping temporal ranges, verify query correctness
2. **HTN Plan Validity:** Verify all generated plans have satisfied preconditions at each step
3. **Story Coherence:** Multi-turn conversations maintain narrative consistency across story transitions
4. **Autoresearch Safety:** Verify that self-modifications never violate Agape function constraints
5. **Robot Parity:** Same HTN plan produces equivalent behavior on physical and virtual Sophia
6. **Temporal Prediction:** Trained LTGQ model achieves >0.3 MRR on held-out temporal link prediction

### 9.3 Continuous Testing Pipeline

```
Git Push → Lint → Unit Tests → Build Containers → Integration Tests 
    → Deploy Staging → System Tests → Autoresearch Validation 
    → Deploy Production (manual gate)
```

---

## 10. Installer App Plan

### 10.1 CLI Installer (`spark-ctl`)

A single command-line tool that handles all setup, deployment, and management:

```bash
spark-ctl install          # Full installation with dependency checks
spark-ctl start            # Start all services
spark-ctl stop             # Stop all services
spark-ctl status           # Health check all services
spark-ctl test             # Run full test suite
spark-ctl test --unit      # Run only unit tests
spark-ctl test --integration
spark-ctl autoresearch start [subsystem]  # Start autoresearch loop
spark-ctl autoresearch status             # View experiment progress
spark-ctl autoresearch results            # View improvement metrics
spark-ctl logs [service]   # View service logs
spark-ctl ui               # Launch web management UI
spark-ctl backup           # Backup all data
spark-ctl restore          # Restore from backup
```

### 10.2 Web Management UI

A React-based dashboard providing:
- Real-time system status for all services
- Temporal KG explorer with visual graph and timeline
- HTN plan visualizer (hierarchical tree view)
- Story Scheduler monitor (active stories, transitions)
- Autoresearch dashboard (experiment progress, improvement curves)
- Robot interface panel (switch physical/virtual, manual controls)
- Test suite runner with live results

---

## 11. Implementation Phases

### Phase 1 (Weeks 1-3): Foundation
- Temporal KG schema and Neo4j extensions
- Basic HTN planner with Sophia domain model
- Docker Compose development environment
- Unit test framework

### Phase 2 (Weeks 4-6): Integration
- Story Engine + HTN planner integration
- LLM prompt assembly with temporal context
- Robot interface bridges (Hanson SDK + SAIL stubs)
- Integration tests

### Phase 3 (Weeks 7-9): Autoresearch
- Autoresearch framework and agent harness
- Program.md files for all subsystems
- Meta-autoresearch loop
- Experiment tracking and metrics

### Phase 4 (Weeks 10-12): Production
- Kubernetes deployment
- Web management UI
- Full system tests
- Performance optimization
- Documentation

---

## Appendix A: Technology Stack

| Component | Technology | Version |
|-----------|-----------|---------|
| Primary Language | Python | 3.11+ |
| Web Framework | FastAPI | 0.110+ |
| Graph Database | Neo4j | 5.x |
| Time Series DB | TimescaleDB | 2.x |
| Cache | Redis | 7.x |
| Message Queue | RabbitMQ | 3.13+ |
| Object Storage | MinIO | Latest |
| ML Framework | PyTorch | 2.x |
| Container Runtime | Docker | 25.x |
| Orchestration | Kubernetes | 1.29+ |
| Monitoring | Prometheus + Grafana | Latest |
| Experiment Tracking | MLflow | 2.x |
| Frontend | React + TypeScript | 18+ |
| LLM Provider | Anthropic Claude API | Sonnet 4 |

## Appendix B: References

1. Geng, R. & Luo, C. (2025). Learning temporal granularity with quadruplet networks for temporal knowledge graph completion. *Scientific Reports*, 15, 17065.
2. Karpathy, A. (2026). autoresearch: AI agents running research on single-GPU nanochat training automatically. GitHub.
3. Georgievski, I. & Aiello, M. (2014). An Overview of Hierarchical Task Network Planning. arXiv:1403.7426.
4. Hanson, D. et al. (2025). Sentience Quest: Story Objects, Person Objects, and Self Objects for Social Robot Cognition. Hanson Robotics Technical Report.

# SPARK v2

SPARK v2 is now a single supported product: the live runtime launched by [`run.sh`](/home/hr/hrsdk_platform/spark_v2/run.sh) and served by [`src/runtime/spark_server.py`](/home/hr/hrsdk_platform/spark_v2/src/runtime/spark_server.py).

The supported runtime path is:

`run.sh` -> `src/runtime/spark_server.py` -> `sophia_live`, `hierarchical_drives`, `cognitive_coupling`, `weave.runtime`, `llm_client`, `prompt_manager`

Older microservice experiments, superseded Agape variants, and deployment stacks have been retired from the supported code path.

## Quickstart

### Install

```bash
cd spark_v2
./install.sh
```

### Run

```bash
cd spark_v2
./run.sh
```

Open `http://localhost:8588` for the chat UI and `http://localhost:8589` for the SQLite inspector.

### Optional LLM configuration

```bash
export OPENAI_API_KEY="sk-..."
export OPENAI_MODEL="gpt-4o-mini"
export OPENAI_BASE_URL="https://api.openai.com/v1"
```

Anthropic-compatible configuration is still supported through `LLM_PROVIDER` and the resolver logic in [`src/core/llm_config.py`](/home/hr/hrsdk_platform/spark_v2/src/core/llm_config.py).

## Local verification

Use one canonical local test flow:

```bash
cd spark_v2
python3 -m venv venv
source venv/bin/activate
pip install -r requirements-dev.txt
python -m pytest tests -q
```

## Supported architecture

The current runtime is intentionally compact:

- [`src/runtime/spark_server.py`](/home/hr/hrsdk_platform/spark_v2/src/runtime/spark_server.py): FastAPI app, WebSocket chat, session lifecycle, prompt editing endpoints, drive loop.
- [`src/runtime/sophia_live.py`](/home/hr/hrsdk_platform/spark_v2/src/runtime/sophia_live.py): SQLite-backed temporal memory, person/session context, prompt assembly.
- [`src/core/hierarchical_drives.py`](/home/hr/hrsdk_platform/spark_v2/src/core/hierarchical_drives.py): multi-layer drive logic and autonomous initiative signals.
- [`src/core/cognitive_coupling.py`](/home/hr/hrsdk_platform/spark_v2/src/core/cognitive_coupling.py): drive/planner coupling and reinforcement adjustments.
- [`src/weave/runtime.py`](/home/hr/hrsdk_platform/spark_v2/src/weave/runtime.py): unified conversation planner and persistence.
- [`src/htn_planner/htn_service.py`](/home/hr/hrsdk_platform/spark_v2/src/htn_planner/htn_service.py): self-contained planner/task registry used by the runtime planner layer.
- [`src/core/llm_client.py`](/home/hr/hrsdk_platform/spark_v2/src/core/llm_client.py) and [`src/core/llm_config.py`](/home/hr/hrsdk_platform/spark_v2/src/core/llm_config.py): LLM transport and provider configuration.
- [`src/core/prompt_manager.py`](/home/hr/hrsdk_platform/spark_v2/src/core/prompt_manager.py): prompt loading, rendering, and on-disk updates.

## Runtime API surface

The supported HTTP/WebSocket surface is whatever is exposed by [`src/runtime/spark_server.py`](/home/hr/hrsdk_platform/spark_v2/src/runtime/spark_server.py), including:

- `GET /`
- `GET /api/status`
- `GET /api/kg/recent`
- `GET /api/kg/count`
- `GET /api/prompts`
- `POST /api/prompts/{prompt_id}`
- `POST /api/prompts/reload`
- `WS /ws/chat`

The old `/api/v2/*` gateway and the separate `story`, `robot`, `autoresearch`, and `kg` services are no longer supported.

## Inventory

The current supported vs retired module map lives in [`docs/CODEBASE_INVENTORY.md`](/home/hr/hrsdk_platform/spark_v2/docs/CODEBASE_INVENTORY.md).

## Historical docs

- [`docs/SPARK_V2_ARCHITECTURE.md`](/home/hr/hrsdk_platform/spark_v2/docs/SPARK_V2_ARCHITECTURE.md) now describes the current live runtime only.
- [`docs/DEVELOPMENT_PLAN.md`](/home/hr/hrsdk_platform/spark_v2/docs/DEVELOPMENT_PLAN.md) is retained as a short historical note.
- [`docs/SPARK_of_Sentience_Paper.md`](/home/hr/hrsdk_platform/spark_v2/docs/SPARK_of_Sentience_Paper.md) is a theory paper, not an implementation contract.

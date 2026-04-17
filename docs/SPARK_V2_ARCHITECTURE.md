# SPARK v2 Live Runtime Architecture

This document describes the current supported implementation only.

## Runtime shape

The supported execution path is:

`run.sh` -> `src/runtime/spark_server.py` -> `sophia_live`, `hierarchical_drives`, `cognitive_coupling`, `weave.runtime`, `llm_client`, `prompt_manager`

## Main modules

- `src/runtime/spark_server.py`
  FastAPI application, WebSocket chat loop, live session management, prompt update endpoints, and background drive ticking.
- `src/runtime/sophia_live.py`
  Persistent SQLite-backed memory and conversation context assembly.
- `src/weave/runtime.py`
  Unified plan persistence and turn-by-turn planning for the live runtime.
- `src/htn_planner/htn_service.py`
  Local task registry and planning logic used by the runtime planner layer.
- `src/core/hierarchical_drives.py`
  Autonomous initiative and layered drive evolution.
- `src/core/cognitive_coupling.py`
  Cross-layer tuning and drive/planner reinforcement logic.
- `src/core/llm_client.py`
  OpenAI-compatible request handling and HTN/planner helper calls.
- `src/core/prompt_manager.py`
  YAML-backed prompt registry used by the UI and runtime prompt rendering.

## Supported interfaces

- Browser chat UI at `/`
- WebSocket conversation channel at `/ws/chat`
- Runtime status at `/api/status`
- Recent memory and count endpoints at `/api/kg/recent` and `/api/kg/count`
- Prompt management endpoints under `/api/prompts`

## Removed architecture branches

The older multi-service deployment model is no longer part of the supported product:

- API gateway
- separate KG/story/robot/autoresearch services
- Docker Compose orchestration for those services
- Kubernetes deployment manifests for those services
- superseded parallel-LLM and Agape variant modules

If you need the exact retained vs removed list, see `docs/CODEBASE_INVENTORY.md`.

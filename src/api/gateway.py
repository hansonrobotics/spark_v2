"""
SPARK v2 — API Gateway
Central entry point routing to all SPARK microservices.
"""

import os
import logging
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, Optional
import httpx

logger = logging.getLogger("spark.api")

app = FastAPI(
    title="SPARK v2 API Gateway",
    description="Social Platform for AI-Robotic Knowledge — Unified API",
    version="2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Service URLs ─────────────────────────────────────────────────────────────

SERVICES = {
    "kg": os.getenv("KG_URL", "http://spark-kg:8001"),
    "htn": os.getenv("HTN_URL", "http://spark-htn:8002"),
    "story": os.getenv("STORY_URL", "http://spark-story:8003"),
    "robot": os.getenv("ROBOT_URL", "http://spark-robot:8006"),
    "autoresearch": os.getenv("AUTORESEARCH_URL", "http://spark-autoresearch:8007"),
}

client = httpx.AsyncClient(timeout=30.0)


# ─── Proxy Helper ─────────────────────────────────────────────────────────────

async def proxy_get(service: str, path: str, params: dict = None):
    url = f"{SERVICES[service]}{path}"
    try:
        resp = await client.get(url, params=params)
        return resp.json()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Service {service} error: {e}")


async def proxy_post(service: str, path: str, body: dict = None):
    url = f"{SERVICES[service]}{path}"
    try:
        resp = await client.post(url, json=body or {})
        return resp.json()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Service {service} error: {e}")


# ─── Health & Status ──────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    statuses = {}
    for name, url in SERVICES.items():
        try:
            resp = await client.get(f"{url}/health", timeout=5.0)
            statuses[name] = resp.json()
        except Exception:
            statuses[name] = {"status": "unreachable"}
    all_healthy = all(s.get("status") == "healthy" for s in statuses.values())
    return {"status": "healthy" if all_healthy else "degraded", "services": statuses}


@app.get("/")
async def root():
    return {
        "name": "SPARK v2 — Social Platform for AI-Robotic Knowledge",
        "version": "2.0",
        "services": list(SERVICES.keys()),
        "docs": "/docs",
    }


# ─── Knowledge Graph Routes ──────────────────────────────────────────────────

@app.post("/api/v2/kg/quadruples")
async def insert_quadruple(body: dict):
    return await proxy_post("kg", "/quadruples", body)

@app.get("/api/v2/kg/entities/{entity_id}/timeline")
async def entity_timeline(entity_id: str, limit: int = 50):
    return await proxy_get("kg", f"/entities/{entity_id}/timeline",
                           {"limit": limit})

@app.post("/api/v2/kg/query/time-range")
async def query_time_range(body: dict):
    return await proxy_post("kg", "/query/time-range", body)

@app.get("/api/v2/kg/entities/{e1}/relationship/{rel}/with/{e2}")
async def relationship_evolution(e1: str, rel: str, e2: str):
    return await proxy_get("kg", f"/entities/{e1}/relationship/{rel}/with/{e2}")


# ─── HTN Planner Routes ──────────────────────────────────────────────────────

@app.post("/api/v2/htn/plan")
async def create_plan(body: dict):
    return await proxy_post("htn", "/plan", body)

@app.post("/api/v2/htn/plan/from-story")
async def plan_from_story(body: dict):
    return await proxy_post("htn", "/plan/from-story", body)

@app.post("/api/v2/htn/execute")
async def execute_plan(body: dict):
    return await proxy_post("htn", "/execute", body)

@app.get("/api/v2/htn/domain/methods")
async def htn_methods():
    return await proxy_get("htn", "/domain/methods")

@app.get("/api/v2/htn/statistics")
async def htn_statistics():
    return await proxy_get("htn", "/statistics")


# ─── Story Engine Routes ─────────────────────────────────────────────────────

@app.post("/api/v2/stories")
async def create_story(body: dict):
    return await proxy_post("story", "/stories", body)

@app.get("/api/v2/stories")
async def list_stories():
    return await proxy_get("story", "/stories")

@app.get("/api/v2/stories/{story_id}")
async def get_story(story_id: str):
    return await proxy_get("story", f"/stories/{story_id}")

@app.post("/api/v2/stories/{story_id}/advance")
async def advance_story(story_id: str):
    return await proxy_post("story", f"/stories/{story_id}/advance")

@app.post("/api/v2/tick")
async def tick(body: dict = None):
    return await proxy_post("story", "/tick", body or {})

@app.get("/api/v2/self")
async def get_self_model():
    return await proxy_get("story", "/self")


# ─── Robot Interface Routes ───────────────────────────────────────────────────

@app.post("/api/v2/robot/execute")
async def robot_execute(body: dict):
    return await proxy_post("robot", "/execute", body)

@app.get("/api/v2/robot/mode")
async def robot_mode():
    return await proxy_get("robot", "/mode")

@app.post("/api/v2/robot/mode")
async def set_robot_mode(body: dict):
    return await proxy_post("robot", "/mode", body)

@app.get("/api/v2/robot/expressions")
async def robot_expressions():
    return await proxy_get("robot", "/expressions")


# ─── Autoresearch Routes ─────────────────────────────────────────────────────

@app.post("/api/v2/autoresearch/run")
async def autoresearch_run(body: dict):
    return await proxy_post("autoresearch", "/run", body)

@app.post("/api/v2/autoresearch/run-all")
async def autoresearch_run_all(num_experiments_per: int = 10):
    return await proxy_post("autoresearch", f"/run-all?num_experiments_per={num_experiments_per}")

@app.get("/api/v2/autoresearch/status")
async def autoresearch_status():
    return await proxy_get("autoresearch", "/status")

@app.get("/api/v2/autoresearch/programs/{subsystem}")
async def autoresearch_program(subsystem: str):
    return await proxy_get("autoresearch", f"/programs/{subsystem}")

@app.get("/api/v2/autoresearch/meta/results")
async def autoresearch_meta():
    return await proxy_get("autoresearch", "/meta/results")


# ─── LLM Usage Stats ─────────────────────────────────────────────────────────

@app.get("/api/v2/llm/stats")
async def llm_stats():
    """Get LLM usage statistics (model, tokens, cost)."""
    try:
        from src.core.llm_client import get_llm_client
        llm = get_llm_client()
        return llm.get_usage_stats()
    except Exception:
        from src.core.llm_config import load_llm_config
        return {"model": load_llm_config()["model"], "status": "not_initialized"}


@app.get("/api/v2/llm/config")
async def llm_config():
    from src.core.llm_config import load_llm_config
    return {k: v for k, v in load_llm_config().items() if k != "api_url"}

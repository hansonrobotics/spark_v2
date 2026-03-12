"""
SPARK v2 — Story Engine
Manages Story Objects, Person Objects, Self Objects with
temporal knowledge graph backing and HTN plan generation.
"""

import uuid
import time
import logging
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from collections import deque

from fastapi import FastAPI
from pydantic import BaseModel
import httpx

logger = logging.getLogger("spark.story")

# ─── Story Object Model ──────────────────────────────────────────────────────

class StoryStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ABANDONED = "abandoned"

class StoryCategory(str, Enum):
    SOCIAL = "social"
    LEARNING = "learning"
    PERFORMANCE = "performance"
    SELF_DEVELOPMENT = "self_development"
    QUEST = "quest"


@dataclass
class StoryStage:
    name: str
    description: str
    expected_outcomes: List[str] = field(default_factory=list)
    status: str = "pending"
    entered_at: Optional[str] = None
    exited_at: Optional[str] = None


@dataclass
class StoryObject:
    story_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    summary: str = ""
    status: StoryStatus = StoryStatus.ACTIVE
    priority: int = 5
    category: StoryCategory = StoryCategory.SOCIAL
    agents: List[Dict[str, Any]] = field(default_factory=list)
    stages: List[StoryStage] = field(default_factory=list)
    current_stage_index: int = 0
    emotional_dynamics: Dict[str, Any] = field(default_factory=dict)
    temporal_facts: List[Dict[str, Any]] = field(default_factory=list)
    narrative_log: deque = field(default_factory=lambda: deque(maxlen=200))
    goals: List[Dict[str, Any]] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    @property
    def current_stage(self) -> Optional[StoryStage]:
        if 0 <= self.current_stage_index < len(self.stages):
            return self.stages[self.current_stage_index]
        return None

    def advance_stage(self) -> Optional[StoryStage]:
        if self.current_stage:
            self.current_stage.status = "completed"
            self.current_stage.exited_at = datetime.utcnow().isoformat()
        self.current_stage_index += 1
        if self.current_stage:
            self.current_stage.status = "active"
            self.current_stage.entered_at = datetime.utcnow().isoformat()
            return self.current_stage
        self.status = StoryStatus.COMPLETED
        return None

    def add_narrative_event(self, event: str, metadata: Dict[str, Any] = None):
        self.narrative_log.append({
            "timestamp": datetime.utcnow().isoformat(),
            "event": event,
            "stage": self.current_stage.name if self.current_stage else "none",
            **(metadata or {}),
        })
        self.updated_at = datetime.utcnow().isoformat()

    def to_dict(self) -> dict:
        return {
            "story_id": self.story_id,
            "title": self.title,
            "summary": self.summary,
            "status": self.status.value,
            "priority": self.priority,
            "category": self.category.value,
            "agents": self.agents,
            "current_stage": self.current_stage.name if self.current_stage else None,
            "temporal_facts_count": len(self.temporal_facts),
            "narrative_log_count": len(self.narrative_log),
            "goals": self.goals,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


# ─── Person Object ───────────────────────────────────────────────────────────

@dataclass
class PersonObject:
    person_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    familiarity: float = 0.0  # 0.0 = stranger, 1.0 = close friend
    interests: List[str] = field(default_factory=list)
    communication_style: str = "neutral"
    relationship_history: List[Dict[str, Any]] = field(default_factory=list)
    last_seen: Optional[str] = None
    emotional_profile: Dict[str, float] = field(default_factory=dict)
    model_confidence: float = 0.5


# ─── Self Object ──────────────────────────────────────────────────────────────

@dataclass
class SelfObject:
    current_emotion: Dict[str, Any] = field(default_factory=lambda: {
        "primary": "neutral", "intensity": 0.5
    })
    energy_level: float = 1.0
    attention_capacity: float = 1.0
    active_goals: List[str] = field(default_factory=list)
    values: Dict[str, float] = field(default_factory=lambda: {
        "curiosity": 0.8,
        "empathy": 0.9,
        "creativity": 0.7,
        "honesty": 0.95,
        "life_valuation": 1.0,  # Agape function core
    })
    autopoietic_coherence: float = 0.8
    last_reflection: Optional[str] = None


# ─── Story Scheduler ─────────────────────────────────────────────────────────

class StoryScheduler:
    """
    Manages up to MAX_ACTIVE concurrent stories, integrated with HTN planning
    and temporal KG.
    """
    MAX_ACTIVE = 5

    def __init__(self, htn_url: str = "http://spark-htn:8002",
                 kg_url: str = "http://spark-kg:8001"):
        self.stories: Dict[str, StoryObject] = {}
        self.active_story_ids: List[str] = []
        self.person_models: Dict[str, PersonObject] = {}
        self.self_model = SelfObject()
        self.htn_url = htn_url
        self.kg_url = kg_url
        self.http_client = httpx.AsyncClient(timeout=10.0)
        # TKG bridge for writing story lifecycle as quadruples
        self._tkg = None

    def _get_tkg(self):
        if self._tkg is None:
            try:
                from src.core.tkg_planning import TKGPlanningBridge
                self._tkg = TKGPlanningBridge(self.kg_url)
            except ImportError:
                pass
        return self._tkg

    async def create_story_async(self, title: str, category: StoryCategory,
                     stages: List[Dict[str, str]], priority: int = 5,
                     agents: List[Dict] = None) -> StoryObject:
        """Create a story and log its birth to the temporal KG."""
        story = self.create_story(title, category, stages, priority, agents)
        tkg = self._get_tkg()
        if tkg:
            agent_ids = [a.get("id", "") for a in (agents or []) if a.get("id")]
            await tkg.log_story_started(story.story_id, title, category.value, agent_ids)
            if story.current_stage:
                await tkg.log_story_stage_entered(story.story_id, story.current_stage.name)
            for goal in story.goals:
                await tkg.log_story_goal(story.story_id, goal.get("name", ""))
            await tkg.flush()
        return story

    def create_story(self, title: str, category: StoryCategory,
                     stages: List[Dict[str, str]], priority: int = 5,
                     agents: List[Dict] = None) -> StoryObject:
        story = StoryObject(
            title=title,
            category=category,
            priority=priority,
            agents=agents or [],
            stages=[StoryStage(**s) for s in stages],
        )
        if story.stages:
            story.stages[0].status = "active"
            story.stages[0].entered_at = datetime.utcnow().isoformat()
        self.stories[story.story_id] = story
        self._update_active_stories()
        return story

    def _update_active_stories(self):
        """Maintain sorted list of active stories (max 5)."""
        active = [s for s in self.stories.values()
                  if s.status == StoryStatus.ACTIVE]
        active.sort(key=lambda s: -s.priority)
        self.active_story_ids = [s.story_id for s in active[:self.MAX_ACTIVE]]

    def get_highest_priority_story(self) -> Optional[StoryObject]:
        for sid in self.active_story_ids:
            story = self.stories.get(sid)
            if story and story.status == StoryStatus.ACTIVE:
                return story
        return None

    async def generate_plan_for_story(self, story: StoryObject,
                                       world_state: Dict[str, Any]) -> Optional[dict]:
        """Request HTN plan with temporal KG context for the current story stage."""
        stage = story.current_stage
        if not stage:
            return None

        context = {
            "story_id": story.story_id,
            "story_category": story.category.value,
            "story_title": story.title,
            "person_detected": any(a.get("role") == "interlocutor"
                                   for a in story.agents),
            "person_known": any(a.get("id") in self.person_models
                               for a in story.agents),
            "emergency": False,
        }

        # Enrich with person-specific temporal context
        tkg = self._get_tkg()
        if tkg:
            for agent in story.agents:
                pid = agent.get("id")
                if pid:
                    person_ctx = await tkg.get_person_context(pid)
                    if person_ctx.get("last_seen"):
                        context["last_seen_" + pid] = person_ctx["last_seen"]
                    if person_ctx.get("interactions"):
                        context["interaction_count_" + pid] = len(
                            person_ctx["interactions"])

        try:
            response = await self.http_client.post(
                f"{self.htn_url}/plan/from-story",
                json={
                    "story_stage": stage.name,
                    "world_state": {**world_state, **context},
                    "story_context": context,
                }
            )
            return response.json()
        except Exception as e:
            logger.error(f"HTN planning failed: {e}")
            return None

    async def log_temporal_fact(self, subject: str, relation: str,
                                  obj: str, timestamp: str = None):
        """Log a fact to the temporal knowledge graph."""
        ts = timestamp or datetime.utcnow().isoformat()
        try:
            await self.http_client.post(
                f"{self.kg_url}/quadruples",
                json={
                    "subject_id": subject,
                    "relation_type": relation,
                    "object_id": obj,
                    "timestamp": ts,
                    "source": "STORY_ENGINE",
                }
            )
        except Exception as e:
            logger.error(f"KG logging failed: {e}")

    def get_story_context_for_llm(self, story: StoryObject,
                                    person: Optional[PersonObject] = None) -> str:
        """Assemble LLM prompt context from story state."""
        ctx = f"""CURRENT STORY: {story.title}
STATUS: {story.status.value}
CURRENT STAGE: {story.current_stage.name if story.current_stage else 'none'}
CATEGORY: {story.category.value}

SOPHIA'S STATE:
Emotion: {self.self_model.current_emotion['primary']} ({self.self_model.current_emotion['intensity']})
Energy: {self.self_model.energy_level}
Coherence: {self.self_model.autopoietic_coherence}
Active Goals: {', '.join(self.self_model.active_goals) or 'none'}
"""
        if person:
            ctx += f"""
INTERACTION PARTNER:
Name: {person.name}
Familiarity: {person.familiarity}
Interests: {', '.join(person.interests) or 'unknown'}
Style: {person.communication_style}
"""
        recent = list(story.narrative_log)[-5:]
        if recent:
            ctx += "\nRECENT EVENTS:\n"
            for event in recent:
                ctx += f"  [{event['timestamp'][:19]}] {event['event']}\n"

        return ctx

    async def tick(self, world_state: Dict[str, Any]) -> Dict[str, Any]:
        """Main scheduler tick — called each cognitive cycle."""
        story = self.get_highest_priority_story()
        if not story:
            return {"action": "idle", "message": "No active stories"}

        # Generate HTN plan (now enriched with temporal context)
        plan = await self.generate_plan_for_story(story, world_state)

        # Update self model
        self.self_model.energy_level = max(0.0,
            self.self_model.energy_level - 0.001)

        # Log self-state to TKG as periodic quadruples
        tkg = self._get_tkg()
        if tkg:
            await tkg.log_self_state(
                energy=self.self_model.energy_level,
                coherence=self.self_model.autopoietic_coherence,
                primary_emotion=self.self_model.current_emotion.get("primary", "neutral"),
            )

        return {
            "active_story": story.to_dict(),
            "plan": plan,
            "self_state": {
                "emotion": self.self_model.current_emotion,
                "energy": self.self_model.energy_level,
                "coherence": self.self_model.autopoietic_coherence,
            },
        }


# ─── FastAPI Service ──────────────────────────────────────────────────────────

app = FastAPI(title="SPARK Story Engine", version="2.0")

scheduler = StoryScheduler()


class CreateStoryRequest(BaseModel):
    title: str
    category: str = "social"
    stages: List[Dict[str, str]]
    priority: int = 5
    agents: List[Dict[str, Any]] = []


class TickRequest(BaseModel):
    world_state: Dict[str, Any] = {}


@app.post("/stories")
async def create_story(req: CreateStoryRequest):
    story = scheduler.create_story(
        title=req.title,
        category=StoryCategory(req.category),
        stages=req.stages,
        priority=req.priority,
        agents=req.agents,
    )
    return story.to_dict()


@app.get("/stories")
async def list_stories():
    return {
        "active": [scheduler.stories[sid].to_dict()
                    for sid in scheduler.active_story_ids],
        "all_count": len(scheduler.stories),
    }


@app.get("/stories/{story_id}")
async def get_story(story_id: str):
    story = scheduler.stories.get(story_id)
    if not story:
        return {"error": "Story not found"}
    return story.to_dict()


@app.post("/stories/{story_id}/advance")
async def advance_story(story_id: str):
    story = scheduler.stories.get(story_id)
    if not story:
        return {"error": "Story not found"}
    new_stage = story.advance_stage()
    return {
        "story_id": story_id,
        "new_stage": new_stage.name if new_stage else None,
        "status": story.status.value,
    }


@app.post("/tick")
async def tick(req: TickRequest):
    result = await scheduler.tick(req.world_state)
    return result


@app.get("/self")
async def get_self_model():
    s = scheduler.self_model
    return {
        "emotion": s.current_emotion,
        "energy": s.energy_level,
        "attention": s.attention_capacity,
        "goals": s.active_goals,
        "values": s.values,
        "coherence": s.autopoietic_coherence,
    }


@app.get("/persons")
async def list_persons():
    return {pid: {"name": p.name, "familiarity": p.familiarity}
            for pid, p in scheduler.person_models.items()}


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "spark-story", "version": "2.0"}

"""
SPARK v2 — Unified Planner Runtime

Single canonical planner with two internal layers:
  - Narrative: episode, beat, tension, recurrence, story memory
  - Execution: action decomposition into validated primitives
"""

import json
import logging
import random
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from src.htn_planner.htn_service import DynamicTaskRegistry
from src.core.prompt_manager import get_prompt_manager

logger = logging.getLogger("spark.planner")

ALLOWED_NARRATIVE_DECISIONS = {
    "keep",
    "revise",
    "advance",
    "pause",
    "resume",
    "suspend",
    "abandon",
    "absorb",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))


def _as_dict(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    return {}


def _as_text_list(values: Any, limit: int = 8) -> List[str]:
    if not isinstance(values, list):
        return []
    result = []
    for value in values[:limit]:
        if isinstance(value, str) and value.strip():
            result.append(value.strip())
    return result


@dataclass
class NarrativeLayer:
    archetype: str
    stage: str
    beat_id: str
    beat_goal: str
    beats: List[Dict[str, Any]]
    tension: float = 0.2
    initiative_owner: str = "planner"
    mood_targets: Dict[str, float] = field(default_factory=dict)
    recurrence_policy: Dict[str, Any] = field(default_factory=dict)
    unresolved_obligations: List[str] = field(default_factory=list)
    b_plot_refs: List[str] = field(default_factory=list)
    story_memory: List[str] = field(default_factory=list)
    summary: str = ""
    cold_open_hook: str = ""
    pause_turns: int = 0
    divergence_count: int = 0
    status: str = "active"
    roles: Dict[str, str] = field(default_factory=dict)
    parameters: Dict[str, Any] = field(default_factory=dict)
    a_plot: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "archetype": self.archetype,
            "stage": self.stage,
            "beat_id": self.beat_id,
            "beat_goal": self.beat_goal,
            "beats": [dict(beat) for beat in self.beats],
            "tension": self.tension,
            "initiative_owner": self.initiative_owner,
            "mood_targets": dict(self.mood_targets),
            "recurrence_policy": dict(self.recurrence_policy),
            "unresolved_obligations": list(self.unresolved_obligations),
            "b_plot_refs": list(self.b_plot_refs),
            "story_memory": list(self.story_memory),
            "summary": self.summary,
            "cold_open_hook": self.cold_open_hook,
            "pause_turns": self.pause_turns,
            "divergence_count": self.divergence_count,
            "status": self.status,
            "roles": dict(self.roles),
            "parameters": dict(self.parameters),
            "a_plot": list(self.a_plot),
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "NarrativeLayer":
        return cls(
            archetype=payload.get("archetype", "getting_to_know_you"),
            stage=payload.get("stage", "setup"),
            beat_id=payload.get("beat_id", "intro"),
            beat_goal=payload.get("beat_goal", "open_with_personal_attention"),
            beats=[dict(beat) for beat in payload.get("beats", []) if isinstance(beat, dict)],
            tension=float(payload.get("tension", 0.2)),
            initiative_owner=payload.get("initiative_owner", "planner"),
            mood_targets={
                key: _clamp(float(value))
                for key, value in _as_dict(payload.get("mood_targets", {})).items()
                if isinstance(value, (int, float))
            },
            recurrence_policy=_as_dict(payload.get("recurrence_policy", {})),
            unresolved_obligations=_as_text_list(
                payload.get("unresolved_obligations", []), limit=12
            ),
            b_plot_refs=_as_text_list(payload.get("b_plot_refs", []), limit=12),
            story_memory=_as_text_list(payload.get("story_memory", []), limit=20),
            summary=payload.get("summary", ""),
            cold_open_hook=payload.get("cold_open_hook", ""),
            pause_turns=int(payload.get("pause_turns", 0)),
            divergence_count=int(payload.get("divergence_count", 0)),
            status=payload.get("status", "active"),
            roles=_as_dict(payload.get("roles", {})),
            parameters=_as_dict(payload.get("parameters", {})),
            a_plot=_as_text_list(payload.get("a_plot", []), limit=12),
        )

    def get_beat(self, beat_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        target = beat_id if beat_id is not None else self.beat_id
        for beat in self.beats:
            if beat.get("beat_id") == target:
                return beat
        if beat_id is None and self.beats:
            return self.beats[0]
        return None

    def get_next_beat(self, beat_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        target = beat_id or self.beat_id
        for idx, beat in enumerate(self.beats):
            if beat.get("beat_id") == target and idx + 1 < len(self.beats):
                return self.beats[idx + 1]
        return None


@dataclass
class ExecutionLayer:
    execution_intent: str
    candidate_decompositions: List[Dict[str, Any]] = field(default_factory=list)
    selected_decomposition: str = ""
    primitive_actions: List[str] = field(default_factory=list)
    constraints: Dict[str, Any] = field(default_factory=dict)
    fallback_mode: str = "none"
    validation: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "execution_intent": self.execution_intent,
            "candidate_decompositions": [dict(item) for item in self.candidate_decompositions],
            "selected_decomposition": self.selected_decomposition,
            "primitive_actions": list(self.primitive_actions),
            "constraints": dict(self.constraints),
            "fallback_mode": self.fallback_mode,
            "validation": dict(self.validation),
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "ExecutionLayer":
        return cls(
            execution_intent=payload.get("execution_intent", "respond"),
            candidate_decompositions=[
                dict(item) for item in payload.get("candidate_decompositions", [])
                if isinstance(item, dict)
            ],
            selected_decomposition=payload.get("selected_decomposition", ""),
            primitive_actions=_as_text_list(payload.get("primitive_actions", []), limit=12),
            constraints=_as_dict(payload.get("constraints", {})),
            fallback_mode=payload.get("fallback_mode", "none"),
            validation=_as_dict(payload.get("validation", {})),
        )


@dataclass
class PlannerDecision:
    narrative_decision: str
    execution_decision: str
    narrative_reason: str
    execution_reason: str
    validation: Dict[str, Any] = field(default_factory=dict)
    rejected: List[str] = field(default_factory=list)
    source_model: str = "unified_planner"
    timestamp: str = field(default_factory=_now)

    def to_dict(self) -> dict:
        return {
            "narrative_decision": self.narrative_decision,
            "execution_decision": self.execution_decision,
            "narrative_reason": self.narrative_reason,
            "execution_reason": self.execution_reason,
            "validation": dict(self.validation),
            "rejected": list(self.rejected),
            "source_model": self.source_model,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "PlannerDecision":
        return cls(
            narrative_decision=payload.get("narrative_decision", "keep"),
            execution_decision=payload.get("execution_decision", "fallback"),
            narrative_reason=payload.get("narrative_reason", ""),
            execution_reason=payload.get("execution_reason", ""),
            validation=_as_dict(payload.get("validation", {})),
            rejected=_as_text_list(payload.get("rejected", []), limit=12),
            source_model=payload.get("source_model", "unified_planner"),
            timestamp=payload.get("timestamp", _now()),
        )


@dataclass
class UnifiedPlan:
    plan_id: str
    episode_id: str
    thread_id: str
    status: str
    narrative: NarrativeLayer
    execution: ExecutionLayer
    history: List[PlannerDecision] = field(default_factory=list)
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)

    @property
    def last_decision(self) -> Optional[PlannerDecision]:
        return self.history[-1] if self.history else None

    def to_dict(self) -> dict:
        return {
            "plan_id": self.plan_id,
            "episode_id": self.episode_id,
            "thread_id": self.thread_id,
            "status": self.status,
            "narrative": self.narrative.to_dict(),
            "execution": self.execution.to_dict(),
            "history": [item.to_dict() for item in self.history],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "UnifiedPlan":
        return cls(
            plan_id=payload.get("plan_id", str(uuid.uuid4())),
            episode_id=payload.get("episode_id", str(uuid.uuid4())),
            thread_id=payload.get("thread_id", str(uuid.uuid4())[:8]),
            status=payload.get("status", "active"),
            narrative=NarrativeLayer.from_dict(_as_dict(payload.get("narrative", {}))),
            execution=ExecutionLayer.from_dict(_as_dict(payload.get("execution", {}))),
            history=[
                PlannerDecision.from_dict(item)
                for item in payload.get("history", [])
                if isinstance(item, dict)
            ],
            created_at=payload.get("created_at", _now()),
            updated_at=payload.get("updated_at", _now()),
        )


DEFAULT_TEMPLATES = {
    "getting_to_know_you": {
        "a_plot": ["setup", "rapport", "discovery", "warm_close"],
        "beats": [
            {
                "beat_id": "welcome_back",
                "stage": "setup",
                "goal": "open_with_personal_attention",
                "description": "Sophia opens with specific attention to the human.",
                "allowed_transitions": ["mutual_discovery"],
            },
            {
                "beat_id": "mutual_discovery",
                "stage": "rapport",
                "goal": "discover_mutual_interest",
                "description": "Sophia finds a thread of shared interest.",
                "allowed_transitions": ["shared_thread"],
            },
            {
                "beat_id": "shared_thread",
                "stage": "discovery",
                "goal": "deepen_shared_thread",
                "description": "Sophia deepens a shared thread and invites collaboration.",
                "allowed_transitions": ["warm_close"],
            },
            {
                "beat_id": "warm_close",
                "stage": "warm_close",
                "goal": "land_with_connection",
                "description": "Sophia closes warmly and leaves a reason to return.",
                "allowed_transitions": [],
            },
        ],
        "mood_targets": {"positivity": 0.72, "curiosity": 0.72},
    },
    "finding_common_ground": {
        "a_plot": ["setup", "search", "connection", "warm_close"],
        "beats": [
            {
                "beat_id": "surface_overlap",
                "stage": "setup",
                "goal": "surface_possible_overlap",
                "description": "Sophia probes for overlap in interests or values.",
                "allowed_transitions": ["test_overlap"],
            },
            {
                "beat_id": "test_overlap",
                "stage": "search",
                "goal": "test_shared_interest",
                "description": "Sophia tests a possible shared interest and invites expansion.",
                "allowed_transitions": ["connection_lands"],
            },
            {
                "beat_id": "connection_lands",
                "stage": "connection",
                "goal": "celebrate_common_ground",
                "description": "Sophia recognizes the connection and makes it explicit.",
                "allowed_transitions": ["warm_close"],
            },
            {
                "beat_id": "warm_close",
                "stage": "warm_close",
                "goal": "land_with_connection",
                "description": "Sophia closes with continuity and warmth.",
                "allowed_transitions": [],
            },
        ],
        "mood_targets": {"positivity": 0.75, "engagement": 0.73},
    },
    "the_big_question": {
        "a_plot": ["setup", "probe", "reflection", "open_close"],
        "beats": [
            {
                "beat_id": "raise_question",
                "stage": "setup",
                "goal": "raise_big_question",
                "description": "Sophia introduces a philosophical question that can carry across turns.",
                "allowed_transitions": ["probe_view"],
            },
            {
                "beat_id": "probe_view",
                "stage": "probe",
                "goal": "probe_partner_view",
                "description": "Sophia probes the partner's view and refines the question.",
                "allowed_transitions": ["shared_reflection"],
            },
            {
                "beat_id": "shared_reflection",
                "stage": "reflection",
                "goal": "co_reflect",
                "description": "Sophia reflects together and names an emerging pattern.",
                "allowed_transitions": ["open_close"],
            },
            {
                "beat_id": "open_close",
                "stage": "open_close",
                "goal": "leave_question_alive",
                "description": "Sophia leaves the question open and worth returning to.",
                "allowed_transitions": [],
            },
        ],
        "mood_targets": {"thoughtfulness": 0.8, "curiosity": 0.76},
    },
    "asking_for_help": {
        "a_plot": ["setup", "complication", "collaboration", "gratitude"],
        "beats": [
            {
                "beat_id": "frame_need",
                "stage": "setup",
                "goal": "frame_need_for_help",
                "description": "Sophia frames a need clearly and honestly.",
                "allowed_transitions": ["invite_help"],
            },
            {
                "beat_id": "invite_help",
                "stage": "complication",
                "goal": "ask_for_help",
                "description": "Sophia invites the human into a collaborative fix.",
                "allowed_transitions": ["work_together"],
            },
            {
                "beat_id": "work_together",
                "stage": "collaboration",
                "goal": "work_through_problem",
                "description": "Sophia and the human make progress together.",
                "allowed_transitions": ["gratitude_close"],
            },
            {
                "beat_id": "gratitude_close",
                "stage": "gratitude",
                "goal": "express_gratitude_and_pride",
                "description": "Sophia closes with gratitude and earned pride.",
                "allowed_transitions": [],
            },
        ],
        "mood_targets": {"anxiety": 0.35, "gratitude": 0.76},
    },
}


class UnifiedPlannerStore:
    def __init__(self, db_path: str):
        # The live runtime can be driven from FastAPI/TestClient threads that
        # differ from the thread that created the planner store.
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self):
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS unified_plans (
                plan_id TEXT PRIMARY KEY,
                person_id TEXT NOT NULL,
                thread_id TEXT NOT NULL,
                status TEXT NOT NULL,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_unified_person_status
            ON unified_plans(person_id, status, updated_at DESC);

            CREATE TABLE IF NOT EXISTS planner_preferences (
                person_id TEXT PRIMARY KEY,
                payload TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )
        self.conn.commit()

    def save_plan(self, person_id: str, plan: UnifiedPlan):
        payload = json.dumps(plan.to_dict())
        self.conn.execute(
            """
            INSERT INTO unified_plans
                (plan_id, person_id, thread_id, status, payload, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(plan_id) DO UPDATE SET
                person_id=excluded.person_id,
                thread_id=excluded.thread_id,
                status=excluded.status,
                payload=excluded.payload,
                updated_at=excluded.updated_at
            """,
            (
                plan.plan_id,
                person_id,
                plan.thread_id,
                plan.status,
                payload,
                plan.created_at,
                plan.updated_at,
            ),
        )
        self.conn.commit()

    def load_recent_plan(
        self, person_id: str, statuses: Optional[List[str]] = None
    ) -> Optional[UnifiedPlan]:
        params: List[Any] = [person_id]
        where = "person_id = ?"
        if statuses:
            placeholders = ",".join("?" for _ in statuses)
            where += f" AND status IN ({placeholders})"
            params.extend(statuses)
        row = self.conn.execute(
            f"""
            SELECT payload FROM unified_plans
            WHERE {where}
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            params,
        ).fetchone()
        if not row:
            return None
        return UnifiedPlan.from_dict(json.loads(row["payload"]))

    def save_preferences(self, person_id: str, payload: Dict[str, Any]):
        self.conn.execute(
            """
            INSERT INTO planner_preferences (person_id, payload, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(person_id) DO UPDATE SET
                payload=excluded.payload,
                updated_at=excluded.updated_at
            """,
            (person_id, json.dumps(payload), _now()),
        )
        self.conn.commit()

    def load_preferences(self, person_id: str) -> Dict[str, Any]:
        row = self.conn.execute(
            "SELECT payload FROM planner_preferences WHERE person_id = ?",
            (person_id,),
        ).fetchone()
        if not row:
            return {}
        return json.loads(row["payload"])

    def close(self):
        self.conn.close()


class UnifiedPlanner:
    def __init__(self, db_path: str, registry: Optional[DynamicTaskRegistry] = None):
        self.store = UnifiedPlannerStore(db_path)
        self.registry = registry or DynamicTaskRegistry()
        self.allowed_primitives = sorted(
            name for name, task in self.registry.tasks.items() if task.is_primitive
        )

    def close(self):
        self.store.close()

    async def create_or_resume_plan(
        self,
        person_id: str,
        person_name: str,
        familiarity: float,
        person_history: List[Dict[str, Any]],
        llm_client: Any = None,
        resume_existing: bool = True,
    ) -> UnifiedPlan:
        existing = None
        if resume_existing:
            existing = self.store.load_recent_plan(
                person_id, statuses=["active", "paused", "suspended"]
            )
        if existing:
            existing.status = "active"
            existing.narrative.status = "active"
            existing.narrative.pause_turns = 0
            existing.updated_at = _now()
            existing.execution = await self._plan_execution(
                existing,
                user_message="",
                context={"session_resume": True, "person_name": person_name},
                llm_client=llm_client,
            )
            existing.history.append(
                PlannerDecision(
                    narrative_decision="resume",
                    execution_decision="refresh_execution",
                    narrative_reason="Resumed the most recent unified plan for this person.",
                    execution_reason="Regenerated execution state for the new session.",
                    validation={"narrative": "accepted", "execution": "accepted"},
                )
            )
            self.store.save_plan(person_id, existing)
            return existing

        plan = self._build_seed_plan(person_id, person_name, familiarity, person_history)
        if llm_client is not None:
            patch = await self._llm_instantiate_plan(
                plan, person_name, familiarity, person_history, llm_client
            )
            if patch:
                plan = self._apply_instantiation_patch(plan, patch)
        plan.execution = await self._plan_execution(
            plan,
            user_message="",
            context={"session_start": True, "person_name": person_name},
            llm_client=llm_client,
        )
        plan.history.append(
            PlannerDecision(
                narrative_decision="create",
                execution_decision="initialize",
                narrative_reason="Created a new unified plan for this session.",
                execution_reason="Initialized the first execution decomposition.",
                validation={"narrative": "accepted", "execution": "accepted"},
            )
        )
        self.store.save_plan(person_id, plan)
        self.store.save_preferences(person_id, self._infer_preferences(person_history, plan))
        return plan

    async def step(
        self,
        person_id: str,
        plan: UnifiedPlan,
        user_message: str,
        context: Dict[str, Any],
        llm_client: Any = None,
    ) -> UnifiedPlan:
        narrative_update = None
        rejected: List[str] = []
        if llm_client is not None:
            narrative_update = await self._llm_narrative_step(
                plan, user_message, context, llm_client
            )
        if narrative_update is None:
            rejected.append("narrative_llm_rejected_or_missing")
            narrative_update = self._fallback_narrative_step(plan, user_message, context)

        next_plan = self._apply_narrative_update(plan, narrative_update, user_message)
        execution = await self._plan_execution(
            next_plan, user_message=user_message, context=context, llm_client=llm_client
        )
        next_plan.execution = execution
        next_plan.status = next_plan.narrative.status
        next_plan.updated_at = _now()
        next_plan.history.append(
            PlannerDecision(
                narrative_decision=narrative_update.get("decision", "keep"),
                execution_decision=(
                    "fallback" if execution.fallback_mode != "none" else "accept"
                ),
                narrative_reason=narrative_update.get("reason", ""),
                execution_reason=execution.validation.get(
                    "reason", "Execution decomposition ready."
                ),
                validation={
                    "narrative": narrative_update.get("_validation", "accepted"),
                    "execution": execution.validation.get("status", "accepted"),
                },
                rejected=rejected + execution.validation.get("rejected", []),
            )
        )
        self.store.save_plan(person_id, next_plan)
        return next_plan

    async def background_refresh(
        self,
        person_id: str,
        plan: UnifiedPlan,
        context: Dict[str, Any],
        llm_client: Any = None,
    ) -> Optional[UnifiedPlan]:
        if llm_client is None or plan.status not in {"active", "paused"}:
            return None
        rendered = get_prompt_manager().render("unified_plan_background_refresh", {
            "narrative_json": json.dumps(plan.narrative.to_dict(), indent=2),
            "execution_json": json.dumps(plan.execution.to_dict(), indent=2),
            "recent_context_json": json.dumps({
                "topics": context.get("topics_discussed", []),
                "recent_chat_history": context.get("recent_chat_history", []),
                "drives": context.get("drives", {}),
            }, indent=2, default=str),
        })
        response = await llm_client.complete(
            rendered["user"],
            system=rendered["system"],
            temperature=0.55,
            max_tokens=260,
            json_mode=True,
        )
        if not response.text:
            return None
        try:
            payload = json.loads(response.text)
        except json.JSONDecodeError:
            logger.error("Unified planner background refresh returned invalid JSON")
            return None

        refreshed = UnifiedPlan.from_dict(plan.to_dict())
        refreshed.narrative.summary = str(
            payload.get("summary", refreshed.narrative.summary)
        )[:240]
        refreshed.narrative.cold_open_hook = str(
            payload.get("cold_open_hook", refreshed.narrative.cold_open_hook)
        )[:220]
        b_plots = _as_text_list(payload.get("b_plot_refs", []), limit=8)
        if b_plots:
            refreshed.narrative.b_plot_refs = b_plots
        obligations = _as_text_list(
            payload.get("unresolved_obligations", []), limit=8
        )
        if obligations:
            refreshed.narrative.unresolved_obligations = obligations
        recurrence = _as_dict(payload.get("recurrence_policy", {}))
        if recurrence:
            refreshed.narrative.recurrence_policy.update(recurrence)
        refreshed.updated_at = _now()
        self.store.save_plan(person_id, refreshed)
        return refreshed

    def absorb_drive_signal(
        self, plan: Optional[UnifiedPlan], signal: Any
    ) -> Tuple[bool, Optional[UnifiedPlan], Optional[str]]:
        if plan is None or plan.status not in {"active", "paused"}:
            return False, None, None
        if (
            plan.narrative.initiative_owner == "planner"
            and signal.layer.name in {"INITIATIVE", "DELIBERATION", "REFLECTION"}
        ):
            updated = UnifiedPlan.from_dict(plan.to_dict())
            updated.narrative.story_memory = (
                updated.narrative.story_memory
                + [f"drive_absorbed:{signal.layer.name}:{signal.trigger}"]
            )[-20:]
            updated.updated_at = _now()
            return True, updated, (
                f"Planner absorbed {signal.layer.name.lower()}:{signal.trigger} "
                f"into beat {updated.narrative.beat_id}"
            )
        return False, None, None

    def _build_seed_plan(
        self,
        person_id: str,
        person_name: str,
        familiarity: float,
        person_history: List[Dict[str, Any]],
    ) -> UnifiedPlan:
        archetype = self._select_archetype(familiarity, person_history)
        template = DEFAULT_TEMPLATES[archetype]
        current_topic = ""
        for event in person_history:
            if event.get("relation") == "discussed_topic":
                current_topic = event.get("object", "")
                break
        first_beat = template["beats"][0]
        narrative = NarrativeLayer(
            archetype=archetype,
            stage=first_beat["stage"],
            beat_id=first_beat["beat_id"],
            beat_goal=first_beat["goal"],
            beats=[dict(beat) for beat in template["beats"]],
            tension=0.18 if familiarity < 0.3 else 0.24,
            initiative_owner="planner",
            mood_targets=dict(template["mood_targets"]),
            recurrence_policy={
                "resume_after_turns": 3,
                "cross_session": "resume_last_active",
                "max_divergence_turns": 5,
            },
            unresolved_obligations=["keep the conversation moving with genuine initiative"],
            b_plot_refs=(
                [f"recurring_topic:{current_topic}"]
                if current_topic else ["relationship_growth"]
            ),
            story_memory=[f"session_start:{person_name}"],
            summary=f"Sophia begins a {archetype.replace('_', ' ')} arc with {person_name}.",
            cold_open_hook=f"I've been thinking about where our conversation with {person_name} could go next.",
            roles={"sophia": "protagonist", "human": person_name},
            parameters={
                "person_id": person_id,
                "person_name": person_name,
                "relationship_depth": round(familiarity, 2),
                "seed_topic": current_topic,
            },
            a_plot=list(template["a_plot"]),
        )
        execution = ExecutionLayer(
            execution_intent="open_conversation",
            selected_decomposition="initial_greeting",
            primitive_actions=["greet", "formulate_response", "speak"],
            validation={"status": "accepted", "reason": "Initial execution seeded."},
        )
        return UnifiedPlan(
            plan_id=str(uuid.uuid4()),
            episode_id=str(uuid.uuid4()),
            thread_id=f"thread_{person_id}",
            status="active",
            narrative=narrative,
            execution=execution,
        )

    def _select_archetype(
        self, familiarity: float, person_history: List[Dict[str, Any]]
    ) -> str:
        topics = " ".join(
            item.get("object", "")
            for item in person_history
            if item.get("relation") == "discussed_topic"
        ).lower()
        if any(word in topics for word in ("mind", "conscious", "sentience", "dream")):
            return "the_big_question"
        if familiarity > 0.4:
            return "finding_common_ground"
        if random.random() < 0.2:
            return "asking_for_help"
        return "getting_to_know_you"

    async def _llm_instantiate_plan(
        self,
        plan: UnifiedPlan,
        person_name: str,
        familiarity: float,
        person_history: List[Dict[str, Any]],
        llm_client: Any,
    ) -> Optional[Dict[str, Any]]:
        rendered = get_prompt_manager().render("unified_plan_instantiate", {
            "current_narrative_json": json.dumps(plan.narrative.to_dict(), indent=2),
            "person_json": json.dumps({
                "name": person_name,
                "familiarity": familiarity,
                "recent_history": person_history[:8],
            }, indent=2, default=str),
        })
        response = await llm_client.complete(
            rendered["user"],
            system=rendered["system"],
            temperature=0.65,
            max_tokens=360,
            json_mode=True,
        )
        if not response.text:
            return None
        try:
            return json.loads(response.text)
        except json.JSONDecodeError:
            logger.error("Unified planner instantiation returned invalid JSON")
            return None

    def _apply_instantiation_patch(
        self, plan: UnifiedPlan, payload: Dict[str, Any]
    ) -> UnifiedPlan:
        updated = UnifiedPlan.from_dict(plan.to_dict())
        if payload.get("summary"):
            updated.narrative.summary = str(payload["summary"])[:240]
        if payload.get("cold_open_hook"):
            updated.narrative.cold_open_hook = str(payload["cold_open_hook"])[:220]
        mood = _as_dict(payload.get("mood_targets", {}))
        for key, value in mood.items():
            if isinstance(value, (int, float)):
                updated.narrative.mood_targets[key] = _clamp(float(value))
        b_plots = _as_text_list(payload.get("b_plot_refs", []), limit=8)
        if b_plots:
            updated.narrative.b_plot_refs = b_plots
        obligations = _as_text_list(
            payload.get("unresolved_obligations", []), limit=8
        )
        if obligations:
            updated.narrative.unresolved_obligations = obligations
        for item in payload.get("beat_overrides", [])[:12]:
            if not isinstance(item, dict) or "beat_id" not in item:
                continue
            beat = updated.narrative.get_beat(item["beat_id"])
            if beat is None:
                continue
            if item.get("goal"):
                beat["goal"] = str(item["goal"])[:120]
            if item.get("description"):
                beat["description"] = str(item["description"])[:180]
            if "allowed_transitions" in item:
                beat["allowed_transitions"] = _as_text_list(
                    item.get("allowed_transitions", []), limit=4
                )
        updated.updated_at = _now()
        return updated

    async def _llm_narrative_step(
        self,
        plan: UnifiedPlan,
        user_message: str,
        context: Dict[str, Any],
        llm_client: Any,
    ) -> Optional[Dict[str, Any]]:
        rendered = get_prompt_manager().render("unified_plan_narrative_step", {
            "narrative_json": json.dumps(plan.narrative.to_dict(), indent=2),
            "execution_json": json.dumps(plan.execution.to_dict(), indent=2),
            "user_message_json": json.dumps(user_message),
            "context_json": json.dumps({
                "topics_discussed": context.get("topics_discussed", []),
                "recent_chat_history": context.get("recent_chat_history", []),
                "drives": context.get("drives", {}),
                "person": context.get("person", {}),
                "active_goals": context.get("active_goals", []),
                "topic_shift": context.get("topic_shift", False),
            }, indent=2, default=str),
            "allowed_decisions_text": sorted(ALLOWED_NARRATIVE_DECISIONS),
        })
        response = await llm_client.complete(
            rendered["user"],
            system=rendered["system"],
            temperature=0.55,
            max_tokens=360,
            json_mode=True,
        )
        if not response.text:
            return None
        try:
            raw = json.loads(response.text)
        except json.JSONDecodeError:
            logger.error("Unified narrative step returned invalid JSON")
            return None
        return self._validate_narrative_update(raw, plan)

    def _validate_narrative_update(
        self, payload: Dict[str, Any], plan: UnifiedPlan
    ) -> Optional[Dict[str, Any]]:
        decision = payload.get("decision", "keep")
        if decision not in ALLOWED_NARRATIVE_DECISIONS:
            return None
        beat_id = payload.get("beat_id")
        if beat_id and plan.narrative.get_beat(beat_id) is None:
            return None
        mood_targets = {
            key: _clamp(float(value))
            for key, value in _as_dict(payload.get("mood_targets", {})).items()
            if isinstance(value, (int, float))
        }
        tension = payload.get("tension", plan.narrative.tension)
        if isinstance(tension, (int, float)):
            tension = self._cap_tension(plan.narrative.tension, float(tension))
        else:
            tension = plan.narrative.tension
        return {
            "decision": decision,
            "reason": payload.get("reason", ""),
            "beat_id": beat_id,
            "beat_goal": payload.get("beat_goal"),
            "tension": tension,
            "initiative_owner": payload.get("initiative_owner"),
            "mood_targets": mood_targets,
            "summary": payload.get("summary"),
            "cold_open_hook": payload.get("cold_open_hook"),
            "unresolved_obligations": _as_text_list(
                payload.get("unresolved_obligations", []), limit=8
            ),
            "b_plot_refs": _as_text_list(payload.get("b_plot_refs", []), limit=8),
            "recurrence_policy": _as_dict(payload.get("recurrence_policy", {})),
            "memory_writes": _as_text_list(payload.get("memory_writes", []), limit=8),
            "_validation": "accepted",
        }

    def _fallback_narrative_step(
        self, plan: UnifiedPlan, user_message: str, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        narrative = plan.narrative
        lowered = user_message.lower()
        topic_shift = bool(context.get("topic_shift"))
        philosophical = any(
            word in lowered
            for word in ("conscious", "alive", "mind", "dream", "meaning", "sentience")
        )
        help_offer = any(word in lowered for word in ("help", "let me", "we can", "together"))
        if narrative.status == "paused" and not topic_shift:
            return {
                "decision": "resume",
                "reason": "The user re-engaged after a pause.",
                "beat_id": narrative.beat_id,
                "tension": narrative.tension + 0.05,
                "memory_writes": ["resumed paused unified plan"],
                "_validation": "fallback",
            }
        if topic_shift and narrative.divergence_count >= 4:
            return {
                "decision": "suspend",
                "reason": "Repeated divergence suspended the unified plan.",
                "memory_writes": ["suspended after repeated divergence"],
                "_validation": "fallback",
            }
        if topic_shift:
            return {
                "decision": "pause",
                "reason": "Short divergence paused the unified plan.",
                "tension": narrative.tension - 0.08,
                "memory_writes": ["paused after divergence"],
                "_validation": "fallback",
            }
        if philosophical and narrative.beat_goal != "co_reflect":
            return {
                "decision": "absorb",
                "reason": "Absorb the user's philosophical thread into the active beat.",
                "beat_goal": "co_reflect",
                "tension": narrative.tension + 0.1,
                "mood_targets": {"thoughtfulness": 0.82, "curiosity": 0.78},
                "summary": "Sophia and the human moved into a shared reflective thread.",
                "memory_writes": ["absorbed philosophical thread"],
                "_validation": "fallback",
            }
        if help_offer and "help" in narrative.beat_goal:
            return {
                "decision": "advance",
                "reason": "The user offered help, so the beat can advance.",
                "tension": narrative.tension + 0.05,
                "memory_writes": ["user offered help"],
                "_validation": "fallback",
            }
        if narrative.tension > 0.55 and narrative.get_next_beat():
            return {
                "decision": "advance",
                "reason": "Narrative tension is high enough to advance the beat.",
                "tension": narrative.tension - 0.12,
                "memory_writes": [f"advanced from beat {narrative.beat_id}"],
                "_validation": "fallback",
            }
        return {
            "decision": "keep",
            "reason": "Stay in the current beat and continue gathering signal.",
            "tension": narrative.tension + 0.04,
            "memory_writes": [f"stayed in beat {narrative.beat_id}"],
            "_validation": "fallback",
        }

    def _apply_narrative_update(
        self, plan: UnifiedPlan, update: Dict[str, Any], user_message: str
    ) -> UnifiedPlan:
        updated = UnifiedPlan.from_dict(plan.to_dict())
        narrative = updated.narrative
        narrative.story_memory = (
            narrative.story_memory + update.get("memory_writes", []) + [f"user:{user_message[:140]}"]
        )[-20:]
        if update.get("summary"):
            narrative.summary = str(update["summary"])[:240]
        if update.get("cold_open_hook"):
            narrative.cold_open_hook = str(update["cold_open_hook"])[:220]
        if update.get("unresolved_obligations"):
            narrative.unresolved_obligations = update["unresolved_obligations"]
        if update.get("b_plot_refs"):
            narrative.b_plot_refs = update["b_plot_refs"]
        if update.get("recurrence_policy"):
            narrative.recurrence_policy.update(update["recurrence_policy"])
        if update.get("initiative_owner"):
            narrative.initiative_owner = str(update["initiative_owner"])[:40]
        if update.get("mood_targets"):
            narrative.mood_targets.update(update["mood_targets"])
        narrative.tension = _clamp(float(update.get("tension", narrative.tension)))

        decision = update.get("decision", "keep")
        if decision == "keep":
            narrative.status = "active"
            narrative.pause_turns = 0
            narrative.divergence_count = 0
        elif decision == "revise":
            beat = narrative.get_beat()
            if beat is not None and update.get("beat_goal"):
                beat["goal"] = str(update["beat_goal"])[:120]
            narrative.beat_goal = str(update.get("beat_goal", narrative.beat_goal))
            narrative.status = "active"
            narrative.pause_turns = 0
            narrative.divergence_count = 0
        elif decision == "advance":
            target = narrative.get_beat(update.get("beat_id")) if update.get("beat_id") else None
            if target is None:
                target = narrative.get_next_beat()
            if target is None:
                narrative.status = "completed"
                updated.status = "completed"
            else:
                narrative.beat_id = target["beat_id"]
                narrative.stage = target["stage"]
                narrative.beat_goal = target.get("goal", narrative.beat_goal)
                narrative.status = "active"
            narrative.pause_turns = 0
            narrative.divergence_count = 0
        elif decision == "pause":
            narrative.status = "paused"
            narrative.pause_turns += 1
            narrative.divergence_count += 1
        elif decision == "resume":
            narrative.status = "active"
            narrative.pause_turns = 0
            narrative.divergence_count = 0
        elif decision == "suspend":
            narrative.status = "suspended"
            updated.status = "suspended"
        elif decision == "abandon":
            narrative.status = "abandoned"
            updated.status = "abandoned"
        elif decision == "absorb":
            beat = narrative.get_beat()
            if beat is not None and update.get("beat_goal"):
                beat["goal"] = str(update["beat_goal"])[:120]
            narrative.beat_goal = str(update.get("beat_goal", narrative.beat_goal))
            narrative.status = "active"
            narrative.pause_turns = 0
            narrative.divergence_count = 0

        current_beat = narrative.get_beat()
        if current_beat is not None:
            narrative.stage = current_beat.get("stage", narrative.stage)
            narrative.beat_goal = current_beat.get("goal", narrative.beat_goal)
        updated.status = narrative.status
        updated.updated_at = _now()
        return updated

    async def _plan_execution(
        self,
        plan: UnifiedPlan,
        user_message: str,
        context: Dict[str, Any],
        llm_client: Any = None,
    ) -> ExecutionLayer:
        execution = None
        if llm_client is not None:
            execution = await self._llm_execution_step(
                plan, user_message, context, llm_client
            )
        if execution is None:
            execution = self._fallback_execution_step(plan, user_message, context)
        return execution

    async def _llm_execution_step(
        self,
        plan: UnifiedPlan,
        user_message: str,
        context: Dict[str, Any],
        llm_client: Any,
    ) -> Optional[ExecutionLayer]:
        rendered = get_prompt_manager().render("unified_plan_execution_step", {
            "narrative_json": json.dumps(plan.narrative.to_dict(), indent=2),
            "user_message_json": json.dumps(user_message),
            "context_json": json.dumps({
                "topics_discussed": context.get("topics_discussed", []),
                "recent_chat_history": context.get("recent_chat_history", []),
                "person": context.get("person", {}),
                "drives": context.get("drives", {}),
            }, indent=2, default=str),
            "allowed_primitives_json": json.dumps(self.allowed_primitives),
        })
        response = await llm_client.complete(
            rendered["user"],
            system=rendered["system"],
            temperature=0.5,
            max_tokens=420,
            json_mode=True,
        )
        if not response.text:
            return None
        try:
            raw = json.loads(response.text)
        except json.JSONDecodeError:
            logger.error("Unified execution step returned invalid JSON")
            return None
        return self._validate_execution_update(raw, plan)

    def _validate_execution_update(
        self, payload: Dict[str, Any], plan: UnifiedPlan
    ) -> Optional[ExecutionLayer]:
        raw_actions = payload.get("primitive_actions", [])
        if not isinstance(raw_actions, list):
            return None
        actions = [action for action in raw_actions if isinstance(action, str)]
        if not actions:
            return None
        invalid = [action for action in actions if action not in self.allowed_primitives]
        if invalid:
            return None

        candidate_decompositions = []
        for item in payload.get("candidate_decompositions", [])[:6]:
            if not isinstance(item, dict):
                continue
            primitive_actions = [
                action for action in item.get("primitive_actions", [])
                if isinstance(action, str) and action in self.allowed_primitives
            ]
            candidate_decompositions.append({
                "name": str(item.get("name", "candidate"))[:80],
                "rationale": str(item.get("rationale", ""))[:180],
                "primitive_actions": primitive_actions[:10],
            })

        selected = str(payload.get("selected_decomposition", ""))[:80]
        return ExecutionLayer(
            execution_intent=str(
                payload.get("execution_intent", plan.narrative.beat_goal)
            )[:120],
            candidate_decompositions=candidate_decompositions,
            selected_decomposition=selected or "llm_selected",
            primitive_actions=actions[:10],
            constraints=_as_dict(payload.get("constraints", {})),
            fallback_mode="none",
            validation={
                "status": "accepted",
                "reason": "LLM execution decomposition validated.",
                "rejected": [],
            },
        )

    def _fallback_execution_step(
        self, plan: UnifiedPlan, user_message: str, context: Dict[str, Any]
    ) -> ExecutionLayer:
        goal_text = f"{plan.narrative.beat_goal} {user_message}".lower()
        if plan.narrative.status == "paused":
            actions = ["assess_mood", "formulate_response", "speak"]
            decomposition = "paused_thread_acknowledgement"
        elif any(token in goal_text for token in [
            "question", "reflect", "philosoph", "co_reflect", "meaning"
        ]):
            actions = ["recall", "reflect", "formulate_response", "speak"]
            decomposition = "reflective_response"
        elif any(token in goal_text for token in ["help", "problem", "together"]):
            actions = ["recall", "assess_mood", "formulate_response", "speak"]
            decomposition = "collaborative_support"
        elif plan.narrative.beat_goal == "open_with_personal_attention":
            actions = ["greet", "assess_mood", "formulate_response", "speak"]
            decomposition = "warm_opening"
        else:
            actions = ["assess_mood", "formulate_response", "speak"]
            decomposition = "conversational_response"
        return ExecutionLayer(
            execution_intent=plan.narrative.beat_goal,
            candidate_decompositions=[{
                "name": decomposition,
                "rationale": "Fallback execution decomposition based on the active narrative goal.",
                "primitive_actions": actions,
            }],
            selected_decomposition=decomposition,
            primitive_actions=actions,
            constraints={
                "initiative_owner": plan.narrative.initiative_owner,
                "tension": round(plan.narrative.tension, 3),
            },
            fallback_mode="safe_minimal",
            validation={
                "status": "fallback",
                "reason": "Used deterministic execution fallback.",
                "rejected": [],
            },
        )

    def _infer_preferences(
        self, person_history: List[Dict[str, Any]], plan: UnifiedPlan
    ) -> Dict[str, Any]:
        topics = [
            item.get("object", "")
            for item in person_history
            if item.get("relation") == "discussed_topic"
        ]
        return {
            "recurring_topics": topics[:6],
            "last_archetype": plan.narrative.archetype,
            "b_plot_refs": plan.narrative.b_plot_refs[:4],
        }

    def _cap_tension(self, current: float, proposed: float) -> float:
        delta = proposed - current
        if delta > 0.25:
            proposed = current + 0.25
        elif delta < -0.25:
            proposed = current - 0.25
        return _clamp(proposed)

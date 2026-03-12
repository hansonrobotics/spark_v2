"""
SPARK v2 — Temporal Knowledge Graph Planning Integration

This module makes the TKG the central nervous system of planning:

  BEFORE planning: Query temporal context to inform method selection
    - What happened recently with this person/topic?
    - What methods worked/failed for similar situations in the past?
    - What temporal patterns predict the likely next state?

  DURING planning: Write plan-creation quadruples
    - (sophia, planned_task, task_name, now)
    - (sophia, selected_method, method_name, now)
    - (plan_id, decomposes_into, primitive_sequence, now)

  AFTER execution: Write outcome quadruples
    - (sophia, executed, task_name, now)
    - (sophia, succeeded_at / failed_at, task_name, now)
    - (sophia, learned_method, method_name, now)
    - (sophia, deprecated_method, method_name, now)
    - (person, responded_with, sentiment, now)

  STORY lifecycle: All story events as quadruples
    - (sophia, started_story, story_id, now)
    - (story_id, entered_stage, stage_name, now)
    - (story_id, involves_agent, person_id, now)
    - (story_id, achieved_goal, goal_description, now)
    - (story_id, completed, outcome, now)

This means the KG becomes a TEMPORAL LOG of Sophia's entire cognitive
life — every plan, every decision, every outcome, every relationship
evolution — all queryable by time, entity, and relation type.
"""

import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any

import httpx

logger = logging.getLogger("spark.tkg_planning")


# ─── Quadruple Templates ─────────────────────────────────────────────────────

class QuadRelation:
    """Standardized relation types for planning quadruples."""
    # Planning
    PLANNED_TASK = "planned_task"
    SELECTED_METHOD = "selected_method"
    DECOMPOSES_INTO = "decomposes_into"
    PLAN_CONTEXT = "plan_context"

    # Execution
    EXECUTED = "executed"
    SUCCEEDED_AT = "succeeded_at"
    FAILED_AT = "failed_at"
    EXECUTION_TIME = "execution_time_ms"

    # Learning
    INVENTED_METHOD = "invented_method"
    LEARNED_METHOD = "learned_method"
    DEPRECATED_METHOD = "deprecated_method"
    REFINED_METHOD = "refined_method"
    PROMOTED_PATTERN = "promoted_pattern"

    # Story lifecycle
    STARTED_STORY = "started_story"
    ENTERED_STAGE = "entered_stage"
    EXITED_STAGE = "exited_stage"
    INVOLVES_AGENT = "involves_agent"
    STORY_GOAL = "story_goal"
    ACHIEVED_GOAL = "achieved_goal"
    COMPLETED_STORY = "completed_story"
    ABANDONED_STORY = "abandoned_story"

    # Social / emotional
    MET_PERSON = "met_person"
    CONVERSED_WITH = "conversed_with"
    RELATIONSHIP_STRENGTH = "relationship_strength"
    EXPRESSED_EMOTION = "expressed_emotion"
    PERCEIVED_EMOTION = "perceived_emotion"

    # Self-model
    ENERGY_LEVEL = "energy_level"
    COHERENCE_LEVEL = "coherence_level"
    ACTIVE_INTEREST = "active_interest"


class TKGPlanningBridge:
    """
    Bridge between the HTN planner / Story Engine and the Temporal KG.
    Provides both READ (context for planning) and WRITE (logging outcomes).
    """

    def __init__(self, kg_url: str = "http://spark-kg:8001"):
        self.kg_url = kg_url
        self.client = httpx.AsyncClient(timeout=10.0)
        self._write_buffer: List[Dict] = []
        self._buffer_max = 20

    # ═══════════════════════════════════════════════════════════════════════
    # READ: Query temporal context for planning
    # ═══════════════════════════════════════════════════════════════════════

    async def get_planning_context(self, task_name: str,
                                     entity_ids: List[str] = None,
                                     lookback_hours: int = 24) -> Dict[str, Any]:
        """
        Assemble temporal context to inform planning decisions.
        Returns recent facts, relationship history, and pattern signals.
        """
        now = datetime.now(timezone.utc)
        start = (now - timedelta(hours=lookback_hours)).isoformat()
        end = now.isoformat()

        context = {
            "query_time": now.isoformat(),
            "task": task_name,
            "recent_facts": [],
            "entity_timelines": {},
            "task_history": [],
            "relationship_context": [],
        }

        # 1. Recent facts in time window
        try:
            resp = await self.client.post(
                f"{self.kg_url}/query/time-range",
                json={"start": start, "end": end},
            )
            if resp.status_code == 200:
                data = resp.json()
                context["recent_facts"] = data.get("facts", [])[:50]
        except Exception as e:
            logger.debug(f"TKG time-range query failed: {e}")

        # 2. Entity-specific timelines
        for eid in (entity_ids or ["sophia"]):
            try:
                resp = await self.client.get(
                    f"{self.kg_url}/entities/{eid}/timeline",
                    params={"limit": 20},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    context["entity_timelines"][eid] = data.get("facts", [])
            except Exception:
                pass

        # 3. Past outcomes for this task type
        context["task_history"] = [
            f for f in context["recent_facts"]
            if f.get("relation") in (
                QuadRelation.SUCCEEDED_AT, QuadRelation.FAILED_AT,
                QuadRelation.SELECTED_METHOD,
            ) and task_name in str(f.get("object", ""))
        ]

        return context

    async def get_person_context(self, person_id: str,
                                   lookback_days: int = 30) -> Dict[str, Any]:
        """Get temporal context about a specific person for social planning."""
        now = datetime.now(timezone.utc)
        start = (now - timedelta(days=lookback_days)).isoformat()
        end = now.isoformat()

        context = {
            "person_id": person_id,
            "interactions": [],
            "relationship_evolution": [],
            "last_seen": None,
            "emotional_history": [],
        }

        try:
            resp = await self.client.post(
                f"{self.kg_url}/query/time-range",
                json={"start": start, "end": end, "entity_id": person_id},
            )
            if resp.status_code == 200:
                facts = resp.json().get("facts", [])
                context["interactions"] = [
                    f for f in facts
                    if f.get("relation") in (
                        QuadRelation.CONVERSED_WITH, QuadRelation.MET_PERSON,
                    )
                ]
                context["emotional_history"] = [
                    f for f in facts
                    if f.get("relation") == QuadRelation.PERCEIVED_EMOTION
                ]
                if facts:
                    context["last_seen"] = facts[-1].get("timestamp")
        except Exception:
            pass

        # Relationship evolution
        try:
            resp = await self.client.get(
                f"{self.kg_url}/entities/sophia/relationship/"
                f"{QuadRelation.RELATIONSHIP_STRENGTH}/with/{person_id}"
            )
            if resp.status_code == 200:
                context["relationship_evolution"] = resp.json().get("evolution", [])
        except Exception:
            pass

        return context

    async def get_method_performance_history(self, method_name: str,
                                               limit: int = 20) -> List[Dict]:
        """Query past performance of a specific method."""
        try:
            resp = await self.client.get(
                f"{self.kg_url}/entities/{method_name}/timeline",
                params={"limit": limit},
            )
            if resp.status_code == 200:
                return resp.json().get("facts", [])
        except Exception:
            pass
        return []

    # ═══════════════════════════════════════════════════════════════════════
    # WRITE: Log planning and execution events as quadruples
    # ═══════════════════════════════════════════════════════════════════════

    async def log_quad(self, subject: str, relation: str, obj: str,
                         confidence: float = 1.0,
                         source: str = "STORY_ENGINE",
                         granularity: str = "INSTANT"):
        """Write a single temporal quadruple."""
        quad = {
            "subject_id": subject,
            "relation_type": relation,
            "object_id": obj,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "confidence": confidence,
            "source": source,
            "granularity": granularity,
        }
        self._write_buffer.append(quad)
        if len(self._write_buffer) >= self._buffer_max:
            await self.flush()

    async def flush(self):
        """Flush the write buffer to the TKG service."""
        if not self._write_buffer:
            return
        buffer = list(self._write_buffer)
        self._write_buffer.clear()
        for quad in buffer:
            try:
                await self.client.post(
                    f"{self.kg_url}/quadruples", json=quad,
                )
            except Exception as e:
                logger.debug(f"TKG write failed: {e}")
                # Re-buffer on failure (with cap to prevent unbounded growth)
                if len(self._write_buffer) < 100:
                    self._write_buffer.append(quad)

    # ── Planning lifecycle ────────────────────────────────────────────────

    async def log_plan_created(self, task_name: str, method_name: str,
                                 plan_primitives: List[str],
                                 plan_id: str = ""):
        """Log that a plan was created."""
        pid = plan_id or f"plan_{task_name}_{int(datetime.now(timezone.utc).timestamp())}"
        await self.log_quad("sophia", QuadRelation.PLANNED_TASK, task_name,
                            source="INFERENCE")
        await self.log_quad("sophia", QuadRelation.SELECTED_METHOD, method_name,
                            source="INFERENCE")
        await self.log_quad(pid, QuadRelation.DECOMPOSES_INTO,
                            "|".join(plan_primitives), source="INFERENCE")

    async def log_execution_outcome(self, task_name: str, success: bool,
                                      execution_time_ms: float,
                                      method_name: str = ""):
        """Log the outcome of task execution."""
        relation = QuadRelation.SUCCEEDED_AT if success else QuadRelation.FAILED_AT
        await self.log_quad("sophia", relation, task_name)
        await self.log_quad("sophia", QuadRelation.EXECUTION_TIME,
                            f"{task_name}:{execution_time_ms:.0f}ms",
                            confidence=1.0)
        if method_name:
            result_str = "success" if success else "failure"
            await self.log_quad(method_name, f"outcome_{result_str}", task_name)

    async def log_method_invented(self, method_name: str, task_name: str,
                                     confidence: float):
        """Log that autoresearch invented a new method."""
        await self.log_quad("sophia", QuadRelation.INVENTED_METHOD,
                            method_name, confidence=confidence,
                            source="AUTORESEARCH")
        await self.log_quad(method_name, "invented_for", task_name,
                            source="AUTORESEARCH")

    async def log_method_promoted(self, method_name: str, task_name: str):
        """Log that a pattern was promoted into a reusable method."""
        await self.log_quad("sophia", QuadRelation.PROMOTED_PATTERN,
                            method_name, source="INFERENCE")

    async def log_method_deprecated(self, method_name: str, reason: str):
        """Log method deprecation."""
        await self.log_quad("sophia", QuadRelation.DEPRECATED_METHOD,
                            f"{method_name}:{reason}", source="INFERENCE")

    # ── Story lifecycle ───────────────────────────────────────────────────

    async def log_story_started(self, story_id: str, title: str,
                                   category: str, agent_ids: List[str] = None):
        """Log the birth of a new story."""
        await self.log_quad("sophia", QuadRelation.STARTED_STORY, story_id)
        await self.log_quad(story_id, "has_title", title)
        await self.log_quad(story_id, "has_category", category)
        for aid in (agent_ids or []):
            await self.log_quad(story_id, QuadRelation.INVOLVES_AGENT, aid)

    async def log_story_stage_entered(self, story_id: str, stage_name: str):
        await self.log_quad(story_id, QuadRelation.ENTERED_STAGE, stage_name)

    async def log_story_stage_exited(self, story_id: str, stage_name: str):
        await self.log_quad(story_id, QuadRelation.EXITED_STAGE, stage_name)

    async def log_story_completed(self, story_id: str, outcome: str = "normal"):
        await self.log_quad(story_id, QuadRelation.COMPLETED_STORY, outcome)

    async def log_story_goal(self, story_id: str, goal: str):
        await self.log_quad(story_id, QuadRelation.STORY_GOAL, goal)

    async def log_story_goal_achieved(self, story_id: str, goal: str):
        await self.log_quad(story_id, QuadRelation.ACHIEVED_GOAL, goal)

    # ── Social interactions ───────────────────────────────────────────────

    async def log_conversation(self, person_id: str, topic: str = ""):
        await self.log_quad("sophia", QuadRelation.CONVERSED_WITH, person_id)
        if topic:
            await self.log_quad(f"conv_{person_id}", "about_topic", topic)

    async def log_emotion_expressed(self, emotion: str, intensity: float):
        await self.log_quad("sophia", QuadRelation.EXPRESSED_EMOTION,
                            f"{emotion}:{intensity:.2f}")

    async def log_emotion_perceived(self, person_id: str,
                                       emotion: str, intensity: float):
        await self.log_quad(person_id, QuadRelation.PERCEIVED_EMOTION,
                            f"{emotion}:{intensity:.2f}")

    async def log_relationship_update(self, person_id: str, strength: float):
        await self.log_quad("sophia", QuadRelation.RELATIONSHIP_STRENGTH,
                            f"{person_id}:{strength:.3f}",
                            granularity="DAY")

    # ── Self-model ────────────────────────────────────────────────────────

    async def log_self_state(self, energy: float, coherence: float,
                               primary_emotion: str):
        await self.log_quad("sophia", QuadRelation.ENERGY_LEVEL,
                            f"{energy:.2f}", granularity="MINUTE")
        await self.log_quad("sophia", QuadRelation.COHERENCE_LEVEL,
                            f"{coherence:.2f}", granularity="MINUTE")
        await self.log_quad("sophia", QuadRelation.EXPRESSED_EMOTION,
                            primary_emotion, granularity="MINUTE")

    # ── Cleanup ───────────────────────────────────────────────────────────

    async def close(self):
        await self.flush()
        await self.client.aclose()

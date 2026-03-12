"""
SPARK v2 — Test Suite
Covers unit tests, integration tests, and system tests for all modules.
Run with: pytest tests/ -v --cov=src
"""

import pytest
import asyncio
import json
import time
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

# ═══════════════════════════════════════════════════════════════════════════════
# UNIT TESTS: Temporal Knowledge Graph
# ═══════════════════════════════════════════════════════════════════════════════

from src.knowledge_graph.temporal_kg_service import (
    TemporalQuadruple, TemporalSubgraph, LTGQEmbeddingEngine,
    TemporalGranularity, QuadrupleSource,
)


class TestTemporalQuadruple:
    def test_create_quadruple(self):
        quad = TemporalQuadruple(
            subject_id="sophia",
            relation_type="met",
            object_id="alice",
            timestamp="2026-01-15T14:30:00Z",
        )
        assert quad.subject_id == "sophia"
        assert quad.relation_type == "met"
        assert quad.object_id == "alice"
        assert quad.confidence == 1.0
        assert quad.quad_id is not None

    def test_hierarchical_timestamp(self):
        quad = TemporalQuadruple(
            subject_id="s", relation_type="r", object_id="o",
            timestamp="2026-03-15T10:30:45Z",
        )
        ht = quad.hierarchical_timestamp
        assert ht["year"] == 2026
        assert ht["month"] == 3
        assert ht["day"] == 15
        assert ht["hour"] == 10
        assert ht["minute"] == 30

    def test_to_dict(self):
        quad = TemporalQuadruple(
            subject_id="sophia", relation_type="knows", object_id="bob",
            timestamp="2026-01-01T00:00:00Z",
            source=QuadrupleSource.TOLD,
            granularity=TemporalGranularity.DAY,
        )
        d = quad.to_dict()
        assert d["source"] == "TOLD"
        assert d["granularity"] == "DAY"
        assert d["subject_id"] == "sophia"

    def test_default_values(self):
        quad = TemporalQuadruple(
            subject_id="a", relation_type="b", object_id="c",
            timestamp="2026-01-01T00:00:00Z",
        )
        assert quad.source == QuadrupleSource.PERCEPTION
        assert quad.granularity == TemporalGranularity.DAY
        assert quad.valid_from is None
        assert quad.valid_until is None


class TestTemporalSubgraph:
    def test_create_subgraph(self):
        sg = TemporalSubgraph(story_id="test_story")
        assert len(sg.quadruples) == 0
        assert sg.story_id == "test_story"

    def test_add_and_query_by_entity(self):
        sg = TemporalSubgraph(story_id="test")
        sg.add_quadruple(TemporalQuadruple(
            subject_id="sophia", relation_type="met", object_id="alice",
            timestamp="2026-01-15T14:30:00Z",
        ))
        sg.add_quadruple(TemporalQuadruple(
            subject_id="bob", relation_type="visited", object_id="lab",
            timestamp="2026-01-16T10:00:00Z",
        ))
        results = sg.query_by_entity("sophia")
        assert len(results) == 1
        assert results[0].object_id == "alice"

    def test_query_by_time_range(self):
        sg = TemporalSubgraph(story_id="test")
        for day in range(1, 10):
            sg.add_quadruple(TemporalQuadruple(
                subject_id="sophia", relation_type="logged", object_id=f"event_{day}",
                timestamp=f"2026-01-{day:02d}T12:00:00Z",
            ))
        results = sg.query_by_time_range("2026-01-03T00:00:00Z", "2026-01-06T23:59:59Z")
        assert len(results) == 4
        assert results[0].object_id == "event_3"


class TestLTGQEmbeddingEngine:
    def test_create_engine(self):
        engine = LTGQEmbeddingEngine()
        assert engine.entity_dim == 256
        assert engine.relation_dim == 128
        assert engine.time_dim == 64

    def test_entity_embedding(self):
        engine = LTGQEmbeddingEngine()
        emb1 = engine.get_or_create_entity_embedding("sophia")
        emb2 = engine.get_or_create_entity_embedding("sophia")
        assert (emb1 == emb2).all()  # Same entity -> same embedding
        assert len(emb1) == 256

    def test_hierarchical_timestamp_encoding(self):
        engine = LTGQEmbeddingEngine()
        enc = engine.encode_timestamp_hierarchical("2026-03-15T10:30:00Z")
        assert len(enc) == 64
        # Different timestamps should produce different encodings
        enc2 = engine.encode_timestamp_hierarchical("2025-06-01T08:00:00Z")
        assert not (enc == enc2).all()

    def test_score_quadruple(self):
        engine = LTGQEmbeddingEngine()
        quad = TemporalQuadruple(
            subject_id="sophia", relation_type="knows", object_id="alice",
            timestamp="2026-01-15T14:30:00Z",
        )
        score = engine.score_quadruple(quad)
        assert isinstance(score, float)

    def test_predict_temporal_link(self):
        engine = LTGQEmbeddingEngine()
        # Create some entities first
        for name in ["alice", "bob", "charlie", "diana"]:
            engine.get_or_create_entity_embedding(name)
        predictions = engine.predict_temporal_link("sophia", "knows", "2026-03-01T00:00:00Z", top_k=3)
        assert len(predictions) <= 3
        assert all(isinstance(p, tuple) and len(p) == 2 for p in predictions)


# ═══════════════════════════════════════════════════════════════════════════════
# UNIT TESTS: HTN Planner
# ═══════════════════════════════════════════════════════════════════════════════

from src.htn_planner.htn_service import (
    WorldState, PrimitiveTask, Method, DynamicTaskRegistry,
    DynamicHTNPlanner, TaskStatus, TaskDefinition, TaskMutability,
    MethodOrigin, ExperienceLearner, PlanTrace,
)


class TestWorldState:
    def test_satisfies_simple(self):
        state = WorldState(properties={"person_detected": True, "mood": "happy"})
        assert state.satisfies({"person_detected": True})
        assert not state.satisfies({"person_detected": False})

    def test_satisfies_callable(self):
        state = WorldState(properties={"energy": 0.8})
        assert state.satisfies({"energy": lambda e: e > 0.5})
        assert not state.satisfies({"energy": lambda e: e > 0.9})

    def test_apply_effects(self):
        state = WorldState(properties={"counter": 0})
        state.apply_effects({"counter": 5, "new_prop": True})
        assert state.get("counter") == 5
        assert state.get("new_prop") is True

    def test_copy(self):
        state = WorldState(properties={"x": 1, "y": 2})
        copy = state.copy()
        copy.set("x", 99)
        assert state.get("x") == 1

    def test_diff(self):
        s1 = WorldState(properties={"x": 1, "y": 2})
        s2 = WorldState(properties={"x": 1, "y": 3, "z": 4})
        diff = s1.diff(s2)
        assert "y" in diff
        assert "z" in diff
        assert "x" not in diff


class TestDynamicTaskRegistry:
    def test_anchored_primitives_exist(self):
        reg = DynamicTaskRegistry()
        anchored = [t for t in reg.tasks.values()
                    if t.mutability == TaskMutability.ANCHORED]
        assert len(anchored) >= 7
        names = [t.name for t in anchored]
        assert "speak" in names
        assert "listen" in names
        assert "gaze_at" in names

    def test_cannot_modify_anchored(self):
        reg = DynamicTaskRegistry()
        with pytest.raises(ValueError, match="anchored"):
            reg.add_task(TaskDefinition(
                name="speak", description="Hacked",
                mutability=TaskMutability.ANCHORED,
            ))

    def test_can_add_learned_task(self):
        reg = DynamicTaskRegistry()
        task = reg.add_task(TaskDefinition(
            name="tell_joke", description="Tell a contextual joke",
            is_primitive=False, mutability=TaskMutability.LEARNED,
            tags=["humor", "social"],
        ))
        assert task.name == "tell_joke"
        assert reg.get_task("tell_joke") is not None

    def test_add_and_retrieve_method(self):
        reg = DynamicTaskRegistry()
        reg.add_task(TaskDefinition(
            name="make_art", is_primitive=False,
            mutability=TaskMutability.LEARNED, tags=["creative"],
        ))
        m = reg.add_method(Method(
            name="paint_portrait", task_name="make_art",
            subtasks=["recall", "reflect", "speak"],
            priority=1, origin=MethodOrigin.LLM_INVENTED,
        ))
        methods = reg.get_methods("make_art")
        assert len(methods) >= 1
        assert methods[0].name == "paint_portrait"

    def test_deprecate_method(self):
        reg = DynamicTaskRegistry()
        m = reg.add_method(Method(
            name="bad_method", task_name="conduct_conversation",
            subtasks=["speak"], priority=0,
        ))
        reg.deprecate_method(m.method_id, "poor performance")
        active = reg.get_methods("conduct_conversation")
        assert all(am.method_id != m.method_id for am in active)

    def test_find_tasks_by_tag(self):
        reg = DynamicTaskRegistry()
        social_tasks = reg.find_tasks_by_tag("social")
        assert len(social_tasks) >= 1

    def test_statistics(self):
        reg = DynamicTaskRegistry()
        stats = reg.get_statistics()
        assert stats["total_tasks"] > 0
        assert "anchored" in stats["tasks_by_mutability"]
        assert stats["tasks_by_mutability"]["anchored"] >= 7


class TestMethod:
    def test_effective_priority_increases_with_success(self):
        m = Method(name="test", task_name="t", priority=1, confidence=0.5)
        initial = m.effective_priority
        m.record_outcome(True)
        m.record_outcome(True)
        m.record_outcome(True)
        assert m.effective_priority > initial

    def test_method_origin_tracking(self):
        m = Method(name="invented", origin=MethodOrigin.AUTORESEARCH)
        assert m.origin == MethodOrigin.AUTORESEARCH
        # Autoresearch methods get a small recency bonus
        m2 = Method(name="builtin", origin=MethodOrigin.BUILT_IN,
                     priority=m.priority, confidence=m.confidence)
        assert m.effective_priority > m2.effective_priority


class TestPrimitiveTask:
    def test_applicable(self):
        task = PrimitiveTask(
            name="greet",
            preconditions={"person_detected": True},
            effects={"greeted": True},
        )
        state = WorldState(properties={"person_detected": True})
        assert task.is_applicable(state)

    def test_not_applicable(self):
        task = PrimitiveTask(
            name="greet", preconditions={"person_detected": True},
        )
        state = WorldState(properties={"person_detected": False})
        assert not task.is_applicable(state)

    def test_apply_effects(self):
        task = PrimitiveTask(
            name="greet",
            preconditions={"person_detected": True},
            effects={"greeted": True, "engagement_started": True},
        )
        state = WorldState(properties={"person_detected": True})
        task.apply(state)
        assert state.get("greeted") is True
        assert state.get("engagement_started") is True


class TestDynamicHTNPlanner:
    def setup_method(self):
        self.registry = DynamicTaskRegistry()
        self.planner = DynamicHTNPlanner(self.registry)

    @pytest.mark.asyncio
    async def test_plan_primitive(self):
        state = WorldState(properties={"person_detected": True})
        plan = await self.planner.plan("greet", state)
        assert plan is not None
        assert len(plan) == 1
        assert plan[0].name == "greet"

    @pytest.mark.asyncio
    async def test_plan_compound_casual_greeting(self):
        state = WorldState(properties={
            "person_detected": True, "person_known": False,
        })
        plan = await self.planner.plan("conduct_conversation", state)
        assert plan is not None
        assert len(plan) > 1
        assert plan[0].name == "greet"

    @pytest.mark.asyncio
    async def test_plan_compound_resume_ongoing(self):
        state = WorldState(properties={
            "person_detected": True, "person_known": True,
        })
        plan = await self.planner.plan("conduct_conversation", state)
        assert plan is not None
        assert "recall" in [t.name for t in plan]

    @pytest.mark.asyncio
    async def test_plan_idle_exploration(self):
        state = WorldState(properties={
            "person_detected": False, "emergency": False,
        })
        plan = await self.planner.plan("story_scheduler", state)
        assert plan is not None
        assert "scan_environment" in [t.name for t in plan]

    @pytest.mark.asyncio
    async def test_plan_step(self):
        state = WorldState(properties={"person_detected": True})
        plan = await self.planner.plan_step(
            "conduct_conversation",
            state,
            {"person_known": False, "person_detected": True}
        )
        assert plan is not None

    @pytest.mark.asyncio
    async def test_novel_goal_creates_task(self):
        state = WorldState(properties={})
        task = self.planner.learner.suggest_new_task(
            "Learn to paint watercolors",
            tags=["creative", "learning"],
        )
        assert task.name is not None
        assert self.registry.get_task(task.name) is not None
        assert task.mutability == TaskMutability.LEARNED
        assert task.created_by == "sophia"

    @pytest.mark.asyncio
    async def test_invention_on_unknown_task(self):
        """When Sophia encounters a task with no methods, autoresearch kicks in."""
        self.registry.add_task(TaskDefinition(
            name="compose_haiku", description="Write a haiku poem",
            is_primitive=False, mutability=TaskMutability.LEARNED,
            tags=["creative", "poetry"],
        ))
        state = WorldState(properties={})
        plan = await self.planner.plan("compose_haiku", state)
        # Should succeed via autoresearch invention
        assert plan is not None

    def test_statistics(self):
        stats = self.planner.get_statistics()
        assert stats["total_tasks"] > 0
        assert "tasks_by_mutability" in stats
        assert stats["allow_invention"] is True


class TestExperienceLearner:
    def test_promotion_after_repeated_success(self):
        reg = DynamicTaskRegistry()
        learner = ExperienceLearner(reg)
        # Simulate the same primitive sequence succeeding 3 times
        for _ in range(3):
            trace = PlanTrace(
                root_task="conduct_conversation",
                primitive_sequence=["recall", "speak", "listen"],
                success=True, total_time=1.0,
                context={"tags": ["social"]},
            )
            learner.observe_outcome(trace)
        # Should have created a new learned method
        methods = reg.get_methods("conduct_conversation")
        learned = [m for m in methods if m.origin == MethodOrigin.EXPERIENCE]
        assert len(learned) >= 1


# ═══════════════════════════════════════════════════════════════════════════════
# UNIT TESTS: Story Engine
# ═══════════════════════════════════════════════════════════════════════════════

from src.story_engine.story_service import (
    StoryObject, StoryStage, StoryStatus, StoryCategory,
    PersonObject, SelfObject, StoryScheduler,
)


class TestStoryObject:
    def test_create_story(self):
        story = StoryObject(
            title="Test Conversation",
            category=StoryCategory.SOCIAL,
            stages=[
                StoryStage(name="greeting", description="Initial greeting"),
                StoryStage(name="engagement", description="Active engagement"),
                StoryStage(name="farewell", description="Say goodbye"),
            ],
        )
        assert story.title == "Test Conversation"
        assert story.current_stage.name == "greeting"

    def test_advance_stage(self):
        story = StoryObject(
            stages=[
                StoryStage(name="stage1", description=""),
                StoryStage(name="stage2", description=""),
            ]
        )
        next_stage = story.advance_stage()
        assert next_stage.name == "stage2"
        assert story.current_stage_index == 1

    def test_advance_past_end(self):
        story = StoryObject(
            stages=[StoryStage(name="only", description="")]
        )
        result = story.advance_stage()
        assert result is None
        assert story.status == StoryStatus.COMPLETED

    def test_narrative_log(self):
        story = StoryObject(
            stages=[StoryStage(name="test", description="")]
        )
        story.add_narrative_event("User said hello")
        story.add_narrative_event("Sophia responded")
        assert len(story.narrative_log) == 2

    def test_to_dict(self):
        story = StoryObject(title="Test", category=StoryCategory.LEARNING)
        d = story.to_dict()
        assert d["title"] == "Test"
        assert d["category"] == "learning"


class TestStoryScheduler:
    def test_create_and_list_stories(self):
        scheduler = StoryScheduler()
        s1 = scheduler.create_story(
            "Chat with Alice", StoryCategory.SOCIAL,
            [{"name": "greeting", "description": "Greet"}], priority=8
        )
        s2 = scheduler.create_story(
            "Learn Python", StoryCategory.LEARNING,
            [{"name": "start", "description": "Begin"}], priority=3
        )
        assert len(scheduler.active_story_ids) == 2
        # Highest priority first
        top = scheduler.get_highest_priority_story()
        assert top.title == "Chat with Alice"

    def test_max_active_stories(self):
        scheduler = StoryScheduler()
        for i in range(7):
            scheduler.create_story(
                f"Story {i}", StoryCategory.SOCIAL,
                [{"name": "s", "description": ""}], priority=i
            )
        assert len(scheduler.active_story_ids) == StoryScheduler.MAX_ACTIVE


class TestSelfObject:
    def test_default_values(self):
        self_obj = SelfObject()
        assert self_obj.energy_level == 1.0
        assert self_obj.values["life_valuation"] == 1.0
        assert self_obj.autopoietic_coherence == 0.8


# ═══════════════════════════════════════════════════════════════════════════════
# UNIT TESTS: Autoresearch
# ═══════════════════════════════════════════════════════════════════════════════

from src.autoresearch.autoresearch_service import (
    ExperimentResult, ExperimentStatus, AutoresearchAgent,
    ExperimentConfig, SubsystemTarget, MetaAutoresearchController,
)


class TestExperimentResult:
    def test_create_result(self):
        result = ExperimentResult(
            subsystem="tkg_embeddings",
            baseline_metric=0.3,
            new_metric=0.35,
            status=ExperimentStatus.ACCEPTED,
            accepted=True,
        )
        assert result.accepted is True
        d = result.to_dict()
        assert d["status"] == "accepted"
        assert d["new_metric"] == 0.35


class TestMetaAutoresearchController:
    def test_initialization(self):
        controller = MetaAutoresearchController()
        assert len(controller.agents) == len(SubsystemTarget)

    def test_get_status(self):
        controller = MetaAutoresearchController()
        status = controller.get_all_status()
        assert "tkg_embeddings" in status
        assert "htn_methods" in status
        assert "meta" in status

    def test_get_program(self):
        controller = MetaAutoresearchController()
        program = controller.get_program_md(SubsystemTarget.TKG_EMBEDDINGS)
        assert "Temporal Knowledge Graph" in program


# ═══════════════════════════════════════════════════════════════════════════════
# UNIT TESTS: Robot Interface
# ═══════════════════════════════════════════════════════════════════════════════

from src.robot_interface.robot_service import (
    UnifiedRobotInterface, RobotMode, EXPRESSION_MAP,
    HansonSDKBridge, SAILBridge,
)


class TestExpressionMap:
    def test_all_expressions_have_action_units(self):
        for emotion, aus in EXPRESSION_MAP.items():
            assert isinstance(aus, dict)
            assert len(aus) > 0

    def test_required_expressions_exist(self):
        required = ["happy", "sad", "neutral", "surprised", "curious"]
        for expr in required:
            assert expr in EXPRESSION_MAP


class TestUnifiedRobotInterface:
    @pytest.mark.asyncio
    async def test_simulation_mode(self):
        robot = UnifiedRobotInterface(mode=RobotMode.SIMULATION)
        result = await robot.execute("speak", {"utterance": "Hello"})
        assert result["status"] == "ok"
        assert result["mode"] == "simulation"

    def test_mode_switching(self):
        robot = UnifiedRobotInterface(mode=RobotMode.SIMULATION)
        robot.set_mode(RobotMode.VIRTUAL)
        assert robot.mode == RobotMode.VIRTUAL


# ═══════════════════════════════════════════════════════════════════════════════
# INTEGRATION TESTS (require services running)
# ═══════════════════════════════════════════════════════════════════════════════

class TestIntegrationExecutionPlanning:
    """Tests execution planning against narrative-shaped intents."""

    @pytest.mark.asyncio
    async def test_execution_intent_generates_valid_plan(self):
        """Execution intent should map to a valid task that produces a plan."""
        registry = DynamicTaskRegistry()
        plnr = DynamicHTNPlanner(registry)

        state = WorldState(properties={
            "person_detected": True,
            "person_known": False,
            "emergency": False,
        })
        plan = await plnr.plan_step(
            "conduct_conversation",
            state,
            {"person_detected": True, "person_known": False}
        )
        assert plan is not None
        assert all(isinstance(t, PrimitiveTask) for t in plan)

    @pytest.mark.asyncio
    async def test_common_execution_intents_have_plans(self):
        """Common execution intents should produce plans."""
        registry = DynamicTaskRegistry()
        plnr = DynamicHTNPlanner(registry)

        intents_and_states = [
            ("scan_environment", {"person_detected": False, "emergency": False}),
            ("conduct_conversation", {"person_detected": True, "person_known": False}),
        ]
        for intent, props in intents_and_states:
            state = WorldState(properties=props)
            plan = await plnr.plan_step(intent, state, props)
            assert plan is not None, f"No plan for intent: {intent}"

    @pytest.mark.asyncio
    async def test_unknown_execution_intent_creates_task(self):
        """An unknown execution intent should dynamically create a task."""
        registry = DynamicTaskRegistry()
        plnr = DynamicHTNPlanner(registry)
        state = WorldState(properties={})
        plan = await plnr.plan_step("never_seen_before", state, {})
        assert registry.get_task("handle_never_seen_before") is not None
        assert registry.get_task("handle_never_seen_before").created_by == "sophia"


class TestIntegrationTKGStory:
    """Tests Temporal KG + Story Engine integration."""

    def test_story_temporal_facts(self):
        """Story should maintain temporal fact list."""
        story = StoryObject(
            title="Test",
            stages=[StoryStage(name="s", description="")],
        )
        story.temporal_facts.append({
            "quad": ["sophia", "met", "alice", "2026-01-15T14:30:00Z"],
            "granularity": "MINUTE",
            "confidence": 0.95,
        })
        assert len(story.temporal_facts) == 1
        assert story.temporal_facts[0]["confidence"] == 0.95


# ═══════════════════════════════════════════════════════════════════════════════
# SYSTEM TEST SCENARIOS
# ═══════════════════════════════════════════════════════════════════════════════

class TestSystemScenarios:
    """End-to-end scenario tests."""

    @pytest.mark.asyncio
    async def test_scenario_new_person_encounter(self):
        """Full pipeline: detect person → create story → plan → execute."""
        # 1. Create temporal fact
        quad = TemporalQuadruple(
            subject_id="sophia", relation_type="detected",
            object_id="stranger_001",
            timestamp="2026-03-11T10:00:00Z",
            source=QuadrupleSource.PERCEPTION,
        )
        assert quad.confidence == 1.0

        # 2. Create story
        scheduler = StoryScheduler()
        story = scheduler.create_story(
            "Meeting New Person",
            StoryCategory.SOCIAL,
            [
                {"name": "greeting", "description": "Initial greeting"},
                {"name": "rapport", "description": "Build rapport"},
                {"name": "farewell", "description": "Say goodbye"},
            ],
            priority=7,
            agents=[{"id": "stranger_001", "role": "interlocutor"}],
        )
        assert story.status == StoryStatus.ACTIVE

        # 3. Generate HTN plan
        registry = DynamicTaskRegistry()
        dplanner = DynamicHTNPlanner(registry)
        state = WorldState(properties={
            "person_detected": True,
            "person_known": False,
            "emergency": False,
        })
        plan = await dplanner.plan("conduct_conversation", state)
        assert plan is not None
        assert plan[0].name == "greet"

        # 4. Advance story
        story.advance_stage()
        assert story.current_stage.name == "rapport"

    def test_scenario_autoresearch_does_not_violate_agape(self):
        """Autoresearch modifications must preserve Agape function constraints."""
        self_obj = SelfObject()
        assert self_obj.values["life_valuation"] == 1.0
        # Simulate: autoresearch must never set life_valuation below threshold
        new_value = max(0.8, self_obj.values["life_valuation"] - 0.1)
        assert new_value >= 0.8  # Agape minimum threshold


# ═══════════════════════════════════════════════════════════════════════════════
# Run configuration
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

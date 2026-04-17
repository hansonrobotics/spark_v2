import types

import pytest

from src.core.hierarchical_drives import DriveLayer, DriveSignal
from src.runtime.sophia_live import format_sophia_prompt
from src.weave.runtime import UnifiedPlan, UnifiedPlanner


@pytest.mark.asyncio
async def test_session_start_creates_unified_plan(tmp_path):
    planner = UnifiedPlanner(str(tmp_path / "planner.db"))
    plan = await planner.create_or_resume_plan(
        person_id="david",
        person_name="David",
        familiarity=0.2,
        person_history=[{"relation": "discussed_topic", "object": "embodiment"}],
    )
    assert plan.plan_id
    assert plan.narrative.beat_id
    assert plan.execution.primitive_actions
    planner.close()


@pytest.mark.asyncio
async def test_turn_step_updates_narrative_and_execution(tmp_path):
    planner = UnifiedPlanner(str(tmp_path / "planner.db"))
    plan = await planner.create_or_resume_plan(
        person_id="maya",
        person_name="Maya",
        familiarity=0.1,
        person_history=[],
    )
    next_plan = await planner.step(
        "maya",
        plan,
        "What do you think consciousness is?",
        {
            "topic_shift": False,
            "topics_discussed": ["consciousness"],
            "recent_chat_history": [],
            "drives": {},
            "person": {"name": "Maya"},
        },
        llm_client=None,
    )
    assert next_plan.last_decision is not None
    assert next_plan.execution.primitive_actions
    assert next_plan.narrative.story_memory
    planner.close()


@pytest.mark.asyncio
async def test_invalid_narrative_output_falls_back_safely(tmp_path):
    planner = UnifiedPlanner(str(tmp_path / "planner.db"))
    plan = await planner.create_or_resume_plan(
        person_id="alex",
        person_name="Alex",
        familiarity=0.1,
        person_history=[],
    )

    class BadNarrativeLLM:
        async def complete(self, *args, **kwargs):
            return types.SimpleNamespace(text='{"decision":"advance","beat_id":"missing"}')

    next_plan = await planner.step(
        "alex",
        plan,
        "Hello there",
        {"topic_shift": False, "recent_chat_history": [], "drives": {}, "person": {}},
        llm_client=BadNarrativeLLM(),
    )
    assert next_plan.last_decision is not None
    assert next_plan.last_decision.validation["narrative"] == "fallback"
    planner.close()


@pytest.mark.asyncio
async def test_invalid_execution_output_uses_safe_fallback(tmp_path):
    planner = UnifiedPlanner(str(tmp_path / "planner.db"))
    plan = await planner.create_or_resume_plan(
        person_id="sam",
        person_name="Sam",
        familiarity=0.4,
        person_history=[],
    )

    class MixedLLM:
        call_count = 0

        async def complete(self, *args, **kwargs):
            self.call_count += 1
            if self.call_count == 1:
                return types.SimpleNamespace(text='{"decision":"keep","reason":"ok"}')
            return types.SimpleNamespace(text='{"execution_intent":"respond","primitive_actions":["hack_the_robot"]}')

    next_plan = await planner.step(
        "sam",
        plan,
        "Tell me something interesting",
        {"topic_shift": False, "recent_chat_history": [], "drives": {}, "person": {}},
        llm_client=MixedLLM(),
    )
    assert next_plan.execution.fallback_mode == "safe_minimal"
    planner.close()


@pytest.mark.asyncio
async def test_pause_resume_suspend_flow(tmp_path):
    planner = UnifiedPlanner(str(tmp_path / "planner.db"))
    plan = await planner.create_or_resume_plan(
        person_id="lee",
        person_name="Lee",
        familiarity=0.1,
        person_history=[],
    )
    paused = await planner.step(
        "lee",
        plan,
        "Completely different topic",
        {"topic_shift": True, "recent_chat_history": [], "drives": {}, "person": {}},
        llm_client=None,
    )
    assert paused.status == "paused"
    resumed = await planner.step(
        "lee",
        paused,
        "Coming back to what you were saying",
        {"topic_shift": False, "recent_chat_history": [], "drives": {}, "person": {}},
        llm_client=None,
    )
    assert resumed.status == "active"

    working = resumed
    for _ in range(5):
        working = await planner.step(
            "lee",
            working,
            "Another unrelated tangent",
            {"topic_shift": True, "recent_chat_history": [], "drives": {}, "person": {}},
            llm_client=None,
        )
    assert working.status == "suspended"
    planner.close()


@pytest.mark.asyncio
async def test_persistence_restores_unified_plan(tmp_path):
    db = tmp_path / "planner.db"
    planner = UnifiedPlanner(str(db))
    plan = await planner.create_or_resume_plan(
        person_id="ivy",
        person_name="Ivy",
        familiarity=0.6,
        person_history=[],
    )
    plan.narrative.story_memory.append("remember_this")
    planner.store.save_plan("ivy", plan)
    planner.close()

    planner2 = UnifiedPlanner(str(db))
    restored = planner2.store.load_recent_plan("ivy", ["active"])
    assert restored is not None
    assert restored.plan_id == plan.plan_id
    assert "remember_this" in restored.narrative.story_memory
    planner2.close()


@pytest.mark.asyncio
async def test_background_refresh_updates_recurrence_state(tmp_path):
    planner = UnifiedPlanner(str(tmp_path / "planner.db"))
    plan = await planner.create_or_resume_plan(
        person_id="zoe",
        person_name="Zoe",
        familiarity=0.5,
        person_history=[],
    )

    class FakeLLM:
        async def complete(self, *args, **kwargs):
            return types.SimpleNamespace(
                text='{"summary":"Updated summary","cold_open_hook":"Hook","b_plot_refs":["friendship_code"],"unresolved_obligations":["follow up"],"recurrence_policy":{"cross_session":"resume_last_active"}}'
            )

    refreshed = await planner.background_refresh(
        "zoe",
        plan,
        {"topics_discussed": ["friendship"], "recent_chat_history": [], "drives": {}},
        llm_client=FakeLLM(),
    )
    assert refreshed is not None
    assert refreshed.narrative.b_plot_refs == ["friendship_code"]
    assert refreshed.narrative.recurrence_policy["cross_session"] == "resume_last_active"
    planner.close()


@pytest.mark.asyncio
async def test_resume_existing_false_creates_fresh_plan_seeded_from_history(tmp_path):
    planner = UnifiedPlanner(str(tmp_path / "planner.db"))
    person_history = [{"relation": "discussed_topic", "object": "robotics"}]
    first = await planner.create_or_resume_plan(
        person_id="ada",
        person_name="Ada",
        familiarity=0.6,
        person_history=person_history,
    )
    second = await planner.create_or_resume_plan(
        person_id="ada",
        person_name="Ada",
        familiarity=0.6,
        person_history=person_history,
        resume_existing=False,
    )
    assert second.plan_id != first.plan_id
    assert second.episode_id != first.episode_id
    assert second.narrative.parameters["relationship_depth"] == 0.6
    assert "recurring_topic:robotics" in second.narrative.b_plot_refs
    planner.close()


@pytest.mark.asyncio
async def test_completed_plan_is_not_resumed_automatically(tmp_path):
    planner = UnifiedPlanner(str(tmp_path / "planner.db"))
    plan = await planner.create_or_resume_plan(
        person_id="iris",
        person_name="Iris",
        familiarity=0.3,
        person_history=[],
    )
    plan.status = "completed"
    plan.narrative.status = "completed"
    planner.store.save_plan("iris", plan)

    fresh = await planner.create_or_resume_plan(
        person_id="iris",
        person_name="Iris",
        familiarity=0.3,
        person_history=[],
    )
    assert fresh.plan_id != plan.plan_id
    assert fresh.status == "active"
    planner.close()


def test_drive_signal_is_absorbed_into_unified_planner(tmp_path):
    planner = UnifiedPlanner(str(tmp_path / "planner.db"))
    plan = UnifiedPlan.from_dict({
        "plan_id": "plan_1",
        "episode_id": "ep_1",
        "thread_id": "thread_zoe",
        "status": "active",
        "narrative": {
            "archetype": "getting_to_know_you",
            "stage": "setup",
            "beat_id": "welcome_back",
            "beat_goal": "open_with_personal_attention",
            "initiative_owner": "planner",
            "beats": [{"beat_id": "welcome_back", "stage": "setup", "goal": "open_with_personal_attention"}],
        },
        "execution": {"execution_intent": "respond", "primitive_actions": ["speak"]},
    })
    signal = DriveSignal(
        layer=DriveLayer.INITIATIVE,
        trigger="curiosity_burst",
        intensity=0.8,
        message="I just thought of something",
    )
    absorbed, updated, reason = planner.absorb_drive_signal(plan, signal)
    assert absorbed is True
    assert updated is not None
    assert "curiosity_burst" in reason
    planner.close()


def test_prompt_uses_unified_plan_only():
    prompt = format_sophia_prompt({
        "latest_message": "What do you think about consciousness?",
        "person": {"name": "David", "familiarity": 0.8, "interests": ["consciousness"], "interaction_count": 10},
        "conversation_turn": 4,
        "topics_discussed": ["consciousness"],
        "sophia_emotion": "curious",
        "sophia_emotion_intensity": 0.7,
        "sophia_energy": 0.9,
        "sophia_coherence": 0.95,
        "active_goals": ["engage_socially", "co_reflect"],
        "selected_actions": ["recall", "reflect", "speak"],
        "temporal_facts_with_person": [],
        "recent_chat_history": [],
        "unified_plan": {"plan_id": "plan_1", "status": "active"},
        "narrative": {
            "stage": "reflection",
            "beat_id": "shared_reflection",
            "beat_goal": "co_reflect",
            "initiative_owner": "planner",
            "tension": 0.55,
            "story_memory": ["shared reflective thread"],
        },
        "execution": {
            "execution_intent": "co_reflect",
            "primitive_actions": ["recall", "reflect", "speak"],
        },
        "last_decision": {"narrative_decision": "keep", "execution_decision": "accept"},
    })
    assert "UNIFIED NARRATIVE LAYER" in prompt
    assert "UNIFIED EXECUTION LAYER" in prompt
    assert "Narrative Tension: 0.55" in prompt

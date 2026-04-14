import pytest

from src.core.hierarchical_drives import DriveLayer, DriveSignal
from src.runtime import spark_server
from src.runtime.spark_server import SophiaMindLive, websocket_message_metadata
from src.weave.runtime import UnifiedPlan


def test_websocket_message_metadata_defaults_to_browser_behavior():
    metadata = websocket_message_metadata({"type": "user_message", "text": "Hello"})
    assert metadata == {
        "request_id": "",
        "session": "",
        "lang": "",
        "auto_log": True,
    }


def test_websocket_message_metadata_preserves_ros_fields():
    metadata = websocket_message_metadata({
        "type": "user_message",
        "text": "Hello",
        "request_id": "agent-request-1",
        "session": "chat-session-1",
        "lang": "en-US",
        "auto_log": False,
    })
    assert metadata == {
        "request_id": "agent-request-1",
        "session": "chat-session-1",
        "lang": "en-US",
        "auto_log": False,
    }


def test_normalize_root_path_accepts_empty_and_prefixed_values():
    assert spark_server.normalize_root_path("") == ""
    assert spark_server.normalize_root_path("/") == ""
    assert spark_server.normalize_root_path("spark") == "/spark"
    assert spark_server.normalize_root_path("/spark/") == "/spark"


def test_render_chat_html_uses_mount_safe_browser_urls():
    html = spark_server.render_chat_html("/spark")
    assert 'const configuredRootPath = "/spark/";' in html
    assert "new WebSocket(websocketUrl('ws/chat'))" in html
    assert "fetch(appUrl('api/prompts'))" in html
    assert "fetch(appUrl(`api/prompts/${currentPromptId}`)" in html
    assert "fetch(appUrl('api/prompts/reload')" in html
    assert "fetch(appUrl('api/status'))" in html


def test_absorbed_drive_signal_still_emits_self_initiated_dialogue(tmp_path, monkeypatch):
    monkeypatch.setattr(spark_server, "DB_PATH", str(tmp_path / "spark.db"))
    mind = SophiaMindLive()
    try:
        mind.active_person = {"person_id": "tester"}
        mind.unified_plan = UnifiedPlan.from_dict({
            "plan_id": "plan_1",
            "episode_id": "episode_1",
            "thread_id": "thread_tester",
            "status": "active",
            "narrative": {
                "archetype": "getting_to_know_you",
                "stage": "setup",
                "beat_id": "welcome_back",
                "beat_goal": "open_with_personal_attention",
                "initiative_owner": "planner",
                "beats": [{
                    "beat_id": "welcome_back",
                    "stage": "setup",
                    "goal": "open_with_personal_attention",
                }],
            },
            "execution": {
                "execution_intent": "respond",
                "primitive_actions": ["speak"],
            },
        })
        signal = DriveSignal(
            layer=DriveLayer.INITIATIVE,
            trigger="curiosity_burst",
            intensity=0.8,
            message="I just thought of something.",
        )

        message = mind.handle_drive_signal(signal)

        assert message["type"] == "sophia_self_initiated"
        assert message["sophia_message"] == "I just thought of something."
        assert message["planner_absorbed"] is True
        assert "curiosity_burst" in message["absorption_reason"]
    finally:
        mind.close()


def test_self_initiated_dialogue_slows_down_between_turns(tmp_path, monkeypatch):
    monkeypatch.setattr(spark_server, "DB_PATH", str(tmp_path / "spark.db"))
    mind = SophiaMindLive()
    try:
        first_now = 10.0
        assert mind.can_emit_self_initiated_dialogue(now=first_now)

        mind.mark_self_initiated_dialogue_emitted(now=first_now)
        first_interval = mind.next_self_initiated_allowed_at - first_now

        second_now = mind.next_self_initiated_allowed_at
        assert mind.can_emit_self_initiated_dialogue(now=second_now)

        mind.mark_self_initiated_dialogue_emitted(now=second_now)
        second_interval = mind.next_self_initiated_allowed_at - second_now

        assert second_interval > first_interval
        assert mind.self_initiated_dormant is False
    finally:
        mind.close()


@pytest.mark.asyncio
async def test_self_initiated_dialogue_goes_dormant_until_next_message(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(spark_server, "DB_PATH", str(tmp_path / "spark.db"))
    mind = SophiaMindLive()
    try:
        mind.active_person = {"person_id": "tester", "interests": []}

        now = 50.0
        for _ in range(spark_server.SELF_INITIATED_MAX_TURNS_PER_IDLE):
            assert mind.can_emit_self_initiated_dialogue(now=now)
            mind.mark_self_initiated_dialogue_emitted(now=now)
            now = mind.next_self_initiated_allowed_at

        assert mind.self_initiated_dormant is True
        assert not mind.can_emit_self_initiated_dialogue(now=now + 3600.0)

        await mind.process_message("hello again", llm_client=None)

        assert mind.self_initiated_dormant is False
        assert mind.self_initiated_turns_since_user_input == 0
        assert mind.can_emit_self_initiated_dialogue(now=now + 3600.0)
    finally:
        mind.close()

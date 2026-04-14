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

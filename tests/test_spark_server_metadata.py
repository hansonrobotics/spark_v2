import time
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

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


class FakeLLMClient:
    async def complete(self, *args, **kwargs):
        return SimpleNamespace(
            text="Test reply",
            model="fake-model",
            stop_reason=None,
            raw={},
        )

    async def close(self):
        return None

    def get_usage_stats(self):
        return {
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_calls": 0,
        }


def test_absorbed_drive_signal_still_emits_self_initiated_dialogue(tmp_path, monkeypatch):
    monkeypatch.setattr(spark_server, "DB_PATH", str(tmp_path / "spark.db"))
    mind = SophiaMindLive()
    try:
        mind.session_active = True
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
        mind.session_active = True
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
        mind.session_active = True
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


def test_detect_explicit_name_requires_clear_introduction(tmp_path, monkeypatch):
    monkeypatch.setattr(spark_server, "DB_PATH", str(tmp_path / "spark.db"))
    mind = SophiaMindLive()
    try:
        assert mind.detect_explicit_name("my name is alice") == "Alice"
        assert mind.detect_explicit_name("I'm Bob") == "Bob"
        assert mind.detect_explicit_name("I am happy") is None
        assert mind.detect_explicit_name("call me charlie") == "Charlie"
    finally:
        mind.close()


@pytest.mark.asyncio
async def test_session_times_out_after_user_inactivity_only(tmp_path, monkeypatch):
    monkeypatch.setattr(spark_server, "DB_PATH", str(tmp_path / "spark.db"))
    mind = SophiaMindLive()
    try:
        await mind.start_session("Alice", anonymous=False, resume_existing=False, activity_time=100.0)
        assert mind.session_active is True

        mind.mark_self_initiated_dialogue_emitted(now=200.0)
        assert mind.last_user_activity_monotonic == 100.0
        assert mind.session_timed_out(now=100.0 + spark_server.SESSION_IDLE_TIMEOUT_SECONDS - 1.0) is False
        assert mind.session_timed_out(now=100.0 + spark_server.SESSION_IDLE_TIMEOUT_SECONDS + 1.0) is True

        payload = mind.close_session(reason="inactivity_timeout")
        assert payload is not None
        assert payload["type"] == "session_closed"
        assert mind.session_active is False
        assert mind.close_reason == "inactivity_timeout"
        assert mind.can_emit_self_initiated_dialogue(now=5000.0) is False
    finally:
        mind.close()


@pytest.mark.asyncio
async def test_next_message_after_timeout_creates_fresh_unknown_session(tmp_path, monkeypatch):
    monkeypatch.setattr(spark_server, "DB_PATH", str(tmp_path / "spark.db"))
    mind = SophiaMindLive()
    try:
        await mind.start_session("Alice", anonymous=False, resume_existing=False, activity_time=10.0)
        first_session_id = mind.session_id
        mind.chat_history = [{"role": "user", "kind": "message", "text": "old"}]
        mind.topics = ["robotics"]
        mind.conversation_turn = 3
        mind.mark_self_initiated_dialogue_emitted(now=15.0)

        mind.close_session(reason="inactivity_timeout")
        created = await mind.ensure_session_for_message("hello again", now=1234.0)

        assert created is True
        assert mind.session_active is True
        assert mind.session_id != first_session_id
        assert mind.active_person["name"] == "Unknown"
        assert mind.active_person["person_id"].startswith("unknown_")
        assert mind.anonymous_session is True
        assert mind.conversation_turn == 0
        assert mind.topics == []
        assert mind.chat_history == []
        assert mind.self_initiated_turns_since_user_input == 0
    finally:
        mind.close()


@pytest.mark.asyncio
async def test_explicit_intro_after_timeout_starts_named_session(tmp_path, monkeypatch):
    monkeypatch.setattr(spark_server, "DB_PATH", str(tmp_path / "spark.db"))
    mind = SophiaMindLive()
    try:
        await mind.start_session("Alice", anonymous=False, resume_existing=False, activity_time=10.0)
        old_session_id = mind.session_id
        mind.close_session(reason="inactivity_timeout")

        created = await mind.ensure_session_for_message("my name is Bob", now=2000.0)

        assert created is True
        assert mind.session_id != old_session_id
        assert mind.session_active is True
        assert mind.anonymous_session is False
        assert mind.active_person["name"] == "Bob"
    finally:
        mind.close()


@pytest.mark.asyncio
async def test_explicit_intro_during_anonymous_session_rebuilds_named_plan(tmp_path, monkeypatch):
    monkeypatch.setattr(spark_server, "DB_PATH", str(tmp_path / "spark.db"))
    mind = SophiaMindLive()
    try:
        created = await mind.ensure_session_for_message("hello there", now=10.0)
        assert created is True
        anonymous_session_id = mind.session_id
        anonymous_plan_id = mind.unified_plan.plan_id

        created = await mind.ensure_session_for_message("my name is Dana", now=11.0)

        assert created is True
        assert mind.session_id != anonymous_session_id
        assert mind.unified_plan.plan_id != anonymous_plan_id
        assert mind.active_person["name"] == "Dana"
        assert mind.anonymous_session is False
    finally:
        mind.close()


def test_status_api_reports_idle_session_fields(tmp_path, monkeypatch):
    monkeypatch.setattr(spark_server, "DB_PATH", str(tmp_path / "spark.db"))
    monkeypatch.setattr(spark_server, "get_llm_client", lambda: FakeLLMClient())
    monkeypatch.setattr(
        spark_server.SophiaMindLive,
        "schedule_background_planner",
        lambda self, llm_client: None,
    )

    with TestClient(spark_server.app) as client:
        status = client.get("/api/status").json()
        assert status["session_active"] is False
        assert status["close_reason"] == "not_started"
        assert status["idle_timeout_seconds"] == spark_server.SESSION_IDLE_TIMEOUT_SECONDS
        assert status["session_id"] is None

        with client.websocket_connect("/ws/chat") as ws:
            ws.receive_json()
            ws.send_json({"type": "user_message", "text": "hello"})
            ws.receive_json()
            ws.receive_json()
            ws.receive_json()

        status = client.get("/api/status").json()
        assert status["session_active"] is True
        assert status["person"]["name"] == "Unknown"
        assert status["session_id"] is not None

        spark_server.mind.close_session(reason="inactivity_timeout")
        status = client.get("/api/status").json()
        assert status["session_active"] is False
        assert status["close_reason"] == "inactivity_timeout"


def test_websocket_timeout_emits_session_closed_and_new_init(tmp_path, monkeypatch):
    monkeypatch.setattr(spark_server, "DB_PATH", str(tmp_path / "spark.db"))
    monkeypatch.setattr(spark_server, "get_llm_client", lambda: FakeLLMClient())
    monkeypatch.setattr(
        spark_server.SophiaMindLive,
        "schedule_background_planner",
        lambda self, llm_client: None,
    )

    with TestClient(spark_server.app) as client:
        with client.websocket_connect("/ws/chat") as ws:
            initial = ws.receive_json()
            assert initial["type"] == "init"
            assert initial["session_active"] is False

            ws.send_json({"type": "user_message", "text": "hello"})
            created = ws.receive_json()
            assert created["type"] == "init"
            first_session_id = created["session_id"]
            assert created["session_active"] is True
            assert created["person"]["name"] == "Unknown"
            assert ws.receive_json()["type"] == "context_assembled"
            assert ws.receive_json()["type"] == "sophia_reply"

            spark_server.mind.last_user_activity_monotonic = (
                time.monotonic() - spark_server.SESSION_IDLE_TIMEOUT_SECONDS - 5.0
            )
            ws.send_json({"type": "user_message", "text": "my name is Nora"})

            closed = ws.receive_json()
            assert closed["type"] == "session_closed"
            assert closed["reason"] == "inactivity_timeout"
            assert closed["session_id"] == first_session_id

            restarted = ws.receive_json()
            assert restarted["type"] == "init"
            assert restarted["session_active"] is True
            assert restarted["session_id"] != first_session_id
            assert restarted["person"]["name"] == "Nora"

            context = ws.receive_json()
            assert context["type"] == "context_assembled"
            reply = ws.receive_json()
            assert reply["type"] == "sophia_reply"

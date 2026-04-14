from src.runtime.spark_server import websocket_message_metadata


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

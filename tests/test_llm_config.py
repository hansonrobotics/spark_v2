import asyncio

from src.core.llm_client import SparkLLMClient
from src.core.llm_config import load_llm_config


class FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload
        self.text = str(payload)

    def json(self):
        return self._payload


class RecordingAsyncClient:
    def __init__(self, response):
        self.response = response
        self.calls = []

    async def post(self, url, headers=None, json=None):
        self.calls.append({
            "url": url,
            "headers": headers or {},
            "json": json or {},
        })
        return self.response

    async def aclose(self):
        return None


def test_load_llm_config_uses_openai_environment(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-test")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.openai.com/v1/")
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    config = load_llm_config()

    assert config["provider"] == "openai"
    assert config["model"] == "gpt-test"
    assert config["base_url"] == "https://api.openai.com/v1"
    assert config["api_url"] == "https://api.openai.com/v1/chat/completions"


def test_spark_llm_client_uses_openai_api_key_from_environment(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "env-openai-key")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-test")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    monkeypatch.delenv("LLM_PROVIDER", raising=False)

    response = FakeResponse(200, {
        "model": "gpt-test",
        "choices": [{
            "message": {"content": "{\"ok\": true}"},
            "finish_reason": "stop",
        }],
        "usage": {
            "prompt_tokens": 11,
            "completion_tokens": 7,
        },
    })
    recorder = RecordingAsyncClient(response)
    client = SparkLLMClient()
    client.client = recorder

    result = asyncio.run(client.complete(
        "Say hello",
        system="System prompt",
        json_mode=True,
    ))

    assert result.text == "{\"ok\": true}"
    assert result.model == "gpt-test"
    assert result.input_tokens == 11
    assert result.output_tokens == 7
    assert client.total_calls == 1

    call = recorder.calls[0]
    assert call["url"] == "https://api.openai.com/v1/chat/completions"
    assert call["headers"]["Authorization"] == "Bearer env-openai-key"
    assert call["json"]["model"] == "gpt-test"
    assert call["json"]["messages"][0]["role"] == "system"
    assert call["json"]["messages"][1]["role"] == "user"
    assert call["json"]["response_format"] == {"type": "json_object"}

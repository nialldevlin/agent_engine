from agent_engine.runtime.llm_client import AnthropicLLMClient, MockLLMClient, OllamaLLMClient


class DummyResponse:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


def test_anthropic_llm_client_builds_payload_and_parses_response():
    captured = {}

    def transport(url, headers, payload):
        captured["url"] = url
        captured["headers"] = headers
        captured["payload"] = payload
        return DummyResponse({"content": [{"type": "text", "text": "hi"}]})

    client = AnthropicLLMClient(api_key="k", model="claude-3-haiku-20240307", transport=transport)
    result = client.generate({"prompt": "hello"})
    assert captured["payload"]["model"] == "claude-3-haiku-20240307"
    assert captured["payload"]["messages"][0]["content"] == "hello"
    assert result == [{"type": "text", "text": "hi"}]


def test_ollama_llm_client_builds_payload_and_parses_response():
    captured = {}

    def transport(url, headers, payload):
        captured["url"] = url
        captured["payload"] = payload
        return DummyResponse({"response": "ok"})

    client = OllamaLLMClient(model="llama3", base_url="http://ollama/api/generate", transport=transport)
    result = client.generate({"prompt": "ping"})
    assert captured["payload"]["model"] == "llama3"
    assert captured["payload"]["prompt"] == "ping"
    assert result == "ok"


def test_mock_llm_client():
    client = MockLLMClient({"a": 1})
    assert client.generate({}) == {"a": 1}
    assert next(client.stream_generate({})) == {"a": 1}

"""LLM client abstraction with pluggable backends (Anthropic, Ollama, Mock)."""

from __future__ import annotations

import json
from typing import Any, Callable, Dict, Protocol


class LLMClient(Protocol):
    """Protocol for interchangeable LLM backends."""

    def generate(self, request: Dict[str, Any]) -> Any:
        ...

    def stream_generate(self, request: Dict[str, Any]):
        ...


class MockLLMClient:
    """Simple mock LLM client for tests and offline runs."""

    def __init__(self, response: Any):
        self.response = response

    def generate(self, request: Dict[str, Any]) -> Any:
        return self.response

    def stream_generate(self, request: Dict[str, Any]):
        yield self.response


class AnthropicLLMClient:
    """Anthropic Messages API client (Sonnet/Haiku, Opus optional)."""

    def __init__(
        self,
        api_key: str,
        model: str = "claude-3-5-sonnet-20240620",
        base_url: str = "https://api.anthropic.com/v1/messages",
        max_tokens: int = 512,
        transport: Callable[[str, Dict[str, str], Dict[str, Any]], Any] | None = None,
        api_version: str = "2023-06-01",
        timeout: int = 30,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.max_tokens = max_tokens
        self.api_version = api_version
        self.timeout = timeout
        self.transport = transport or self._requests_transport

    def generate(self, request: Dict[str, Any]) -> Any:
        prompt = request.get("prompt") if isinstance(request, dict) else str(request)
        system = request.get("system") if isinstance(request, dict) else None
        messages = request.get("messages") if isinstance(request, dict) and "messages" in request else None
        payload: Dict[str, Any] = {
            "model": self.model,
            "max_tokens": request.get("max_tokens", self.max_tokens) if isinstance(request, dict) else self.max_tokens,
        }
        if messages:
            payload["messages"] = messages
        else:
            payload["messages"] = [{"role": "user", "content": prompt}]
        if system:
            payload["system"] = system

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": self.api_version,
            "content-type": "application/json",
        }
        response = self.transport(self.base_url, headers, payload)
        return _parse_response(response, content_key="content")

    def stream_generate(self, request: Dict[str, Any]):
        # Streaming not implemented in this stub; fall back to single call.
        yield self.generate(request)

    def _requests_transport(self, url: str, headers: Dict[str, str], payload: Dict[str, Any]) -> Any:
        import requests

        resp = requests.post(url, headers=headers, json=payload, timeout=self.timeout)
        resp.raise_for_status()
        return resp


class OllamaLLMClient:
    """Ollama (self-hosted or remote) client using /api/generate."""

    def __init__(
        self,
        model: str = "llama3",
        base_url: str = "http://localhost:11434/api/generate",
        transport: Callable[[str, Dict[str, str], Dict[str, Any]], Any] | None = None,
        timeout: int = 30,
    ) -> None:
        self.model = model
        self.base_url = base_url
        self.timeout = timeout
        self.transport = transport or self._requests_transport

    def generate(self, request: Dict[str, Any]) -> Any:
        prompt = request.get("prompt") if isinstance(request, dict) else str(request)
        payload = {"model": self.model, "prompt": prompt}
        response = self.transport(self.base_url, {}, payload)
        return _parse_response(response, content_key="response")

    def stream_generate(self, request: Dict[str, Any]):
        # No streaming in this stub; fall back to single call.
        yield self.generate(request)

    def _requests_transport(self, url: str, headers: Dict[str, str], payload: Dict[str, Any]) -> Any:
        import requests

        resp = requests.post(url, headers=headers, json=payload, timeout=self.timeout)
        resp.raise_for_status()
        return resp


def _parse_response(response: Any, content_key: str) -> Any:
    """Extract content from a requests.Response-like object or raw dict."""
    if hasattr(response, "json"):
        try:
            data = response.json()
        except Exception:
            text = getattr(response, "text", None)
            data = json.loads(text) if text else {}
    else:
        data = response
    if isinstance(data, dict) and content_key in data:
        return data[content_key]
    return data

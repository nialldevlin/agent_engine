"""LLM client abstraction with pluggable backends (Anthropic, OpenAI, Ollama, Mock)."""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Callable, Dict, Protocol

logger = logging.getLogger(__name__)


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


class OpenAILLMClient:
    """OpenAI Chat Completions client."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        base_url: str = "https://api.openai.com/v1/chat/completions",
        organization: str | None = None,
        max_tokens: int = 512,
        timeout: int = 30,
        transport: Callable[[str, Dict[str, str], Dict[str, Any]], Any] | None = None,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.organization = organization
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.transport = transport or self._requests_transport

    def generate(self, request: Dict[str, Any]) -> Any:
        prompt = request.get("prompt") if isinstance(request, dict) else str(request)
        messages = request.get("messages") if isinstance(request, dict) and "messages" in request else None
        payload: Dict[str, Any] = {
            "model": request.get("model", self.model) if isinstance(request, dict) else self.model,
            "max_tokens": request.get("max_tokens", self.max_tokens) if isinstance(request, dict) else self.max_tokens,
        }
        if messages:
            payload["messages"] = messages
        else:
            payload["messages"] = [{"role": "user", "content": prompt}]
        if isinstance(request, dict):
            if "temperature" in request:
                payload["temperature"] = request["temperature"]
            if "top_p" in request:
                payload["top_p"] = request["top_p"]

        headers = {
            "authorization": f"Bearer {self.api_key}",
            "content-type": "application/json",
        }
        if self.organization:
            headers["OpenAI-Organization"] = self.organization
        response = self.transport(self.base_url, headers, payload)
        return _parse_openai_response(response)

    def stream_generate(self, request: Dict[str, Any]):
        # Streaming not implemented in this stub; fall back to single call.
        yield self.generate(request)

    def _requests_transport(self, url: str, headers: Dict[str, str], payload: Dict[str, Any]) -> Any:
        import requests

        resp = requests.post(url, headers=headers, json=payload, timeout=self.timeout)
        resp.raise_for_status()
        return resp


class OllamaLLMClient:
    """Ollama (self-hosted or remote) client using /api/generate with auto-pull support."""

    def __init__(
        self,
        model: str = "llama3",
        base_url: str = "http://localhost:11434",
        transport: Callable[[str, Dict[str, str], Dict[str, Any]], Any] | None = None,
        timeout: int = 30,
        auto_pull: bool = True,
        auto_select_llama_size: bool = False,
        llama_size_thresholds_gb: Dict[str, int] | None = None,
        min_llama_size: str | None = None,
        max_llama_size: str | None = None,
        auto_start: bool = True,
    ) -> None:
        self.model = model or "llama3"
        normalized_base = base_url.rstrip("/")
        if normalized_base.endswith("/api/generate"):
            normalized_base = normalized_base[: -len("/api/generate")]
        elif normalized_base.endswith("/api"):
            normalized_base = normalized_base[: -len("/api")]
        self.base_url = normalized_base or "http://localhost:11434"
        self.generate_url = f"{self.base_url}/api/generate"
        self.tags_url = f"{self.base_url}/api/tags"
        self.pull_url = f"{self.base_url}/api/pull"
        self.timeout = timeout
        self.auto_pull = auto_pull
        self.auto_select_llama_size = auto_select_llama_size
        self.llama_size_thresholds_gb = llama_size_thresholds_gb or {"70b": 48, "8b": 8}
        self.min_llama_size = min_llama_size
        self.max_llama_size = max_llama_size
        self._model_cache: set[str] = set()
        self.transport = transport or self._requests_transport
        self.auto_start = auto_start

    def generate(self, request: Dict[str, Any]) -> Any:
        prompt = request.get("prompt") if isinstance(request, dict) else str(request)
        model_name = self._resolve_model_name(request)
        payload = {"model": model_name, "prompt": prompt}
        self._ensure_server_ready()
        self._ensure_model_available(model_name)
        response = self.transport(self.generate_url, {}, payload)
        return _parse_response(response, content_key="response")

    def stream_generate(self, request: Dict[str, Any]):
        # No streaming in this stub; fall back to single call.
        yield self.generate(request)

    def _requests_transport(self, url: str, headers: Dict[str, str], payload: Dict[str, Any]) -> Any:
        import requests

        resp = requests.post(url, headers=headers, json=payload, timeout=self.timeout)
        resp.raise_for_status()
        return resp

    def _resolve_model_name(self, request: Dict[str, Any]) -> str:
        requested_model = self.model
        if isinstance(request, dict) and request.get("model"):
            requested_model = request["model"]
        if self.auto_select_llama_size and self._looks_like_llama_base(requested_model):
            return self._select_llama_variant(requested_model)
        return requested_model

    def _looks_like_llama_base(self, model_name: str) -> bool:
        base, _, size = model_name.partition(":")
        return base.startswith("llama") and not size

    def _select_llama_variant(self, base_model: str) -> str:
        """Pick the largest llama variant that fits available RAM."""
        available_gb = _get_system_memory_gb()
        # Sort by descending threshold to choose the largest possible model
        candidates = sorted(self.llama_size_thresholds_gb.items(), key=lambda kv: kv[1], reverse=True)
        candidates = self._filter_llama_candidates(candidates)
        for size, min_gb in candidates:
            if available_gb >= min_gb:
                return f"{base_model}:{size}"
        # Fallback to smallest known size if nothing else matched
        if candidates:
            smallest_size = candidates[-1][0]
            return f"{base_model}:{smallest_size}"
        return base_model

    def _filter_llama_candidates(self, candidates: list[tuple[str, int]]) -> list[tuple[str, int]]:
        if not self.min_llama_size and not self.max_llama_size:
            return candidates

        min_threshold = self.llama_size_thresholds_gb.get(self.min_llama_size) if self.min_llama_size else None
        max_threshold = self.llama_size_thresholds_gb.get(self.max_llama_size) if self.max_llama_size else None

        if self.min_llama_size and min_threshold is None:
            logger.warning("min_llama_size '%s' not found in llama_size_thresholds_gb; ignoring.", self.min_llama_size)
        if self.max_llama_size and max_threshold is None:
            logger.warning("max_llama_size '%s' not found in llama_size_thresholds_gb; ignoring.", self.max_llama_size)

        filtered = [
            (size, min_gb)
            for size, min_gb in candidates
            if (min_threshold is None or min_gb >= min_threshold)
            and (max_threshold is None or min_gb <= max_threshold)
        ]

        if not filtered:
            logger.warning("No llama variants satisfied min/max filters; falling back to unfiltered list.")
            return candidates
        return filtered

    def _ensure_model_available(self, model: str) -> None:
        """Ensure the Ollama model is available locally, pulling if needed."""
        if not self.auto_pull or model in self._model_cache:
            return
        self._ensure_server_ready()
        needs_pull = True
        try:
            import requests
        except ImportError:
            logger.warning("requests not available; skipping Ollama auto-pull.")
            return

        try:
            resp = requests.get(self.tags_url, timeout=self.timeout)
            resp.raise_for_status()
            models = resp.json().get("models", [])
            installed = {m.get("model") for m in models if isinstance(m, dict)}
            if model in installed:
                self._model_cache.add(model)
                needs_pull = False
        except Exception as exc:
            logger.warning("Could not verify Ollama models: %s", exc)

        if needs_pull:
            try:
                pull_resp = requests.post(self.pull_url, json={"model": model}, timeout=self.timeout, stream=True)
                pull_resp.raise_for_status()
                for _ in pull_resp.iter_lines():
                    # Iterate to ensure pull completes; content not used here.
                    pass
                self._model_cache.add(model)
            except Exception as exc:
                logger.warning("Failed to pull Ollama model %s: %s", model, exc)

    def _ensure_server_ready(self) -> None:
        """Best-effort to verify Ollama is reachable and optionally auto-start."""
        try:
            import requests
        except ImportError:
            return

        try:
            resp = requests.get(self.tags_url, timeout=self.timeout)
            resp.raise_for_status()
            return
        except Exception:
            pass

        if not self.auto_start:
            return

        try:
            import subprocess
            subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as exc:
            logger.warning("Could not auto-start Ollama: %s", exc)


def _get_system_memory_gb() -> int:
    """Return approximate system memory in GB."""
    try:
        import psutil  # type: ignore

        mem = getattr(psutil, "virtual_memory", lambda: None)()
        if mem:
            return int(mem.total / (1024**3))
    except Exception:
        pass

    try:
        if hasattr(os, "sysconf"):
            pagesize = os.sysconf("SC_PAGE_SIZE")
            num_pages = os.sysconf("SC_PHYS_PAGES")
            total = pagesize * num_pages
            return int(total / (1024**3))
    except Exception:
        pass
    return 0


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


def _parse_openai_response(response: Any) -> Any:
    """Extract content from OpenAI Chat Completions style response."""
    if hasattr(response, "json"):
        try:
            data = response.json()
        except Exception:
            text = getattr(response, "text", None)
            data = json.loads(text) if text else {}
    else:
        data = response
    if isinstance(data, dict):
        choices = data.get("choices")
        if choices and isinstance(choices, list):
            message = choices[0].get("message") if isinstance(choices[0], dict) else None
            if isinstance(message, dict):
                return message.get("content")
    return data

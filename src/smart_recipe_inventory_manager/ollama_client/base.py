from __future__ import annotations

import json
import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Mapping, Sequence

import httpx


logger = logging.getLogger(__name__)


class OllamaError(RuntimeError):
    """Base error raised by the local Ollama adapter."""


class OllamaConnectionError(OllamaError):
    """Raised when Ollama cannot be reached or times out."""


class OllamaResponseError(OllamaError):
    """Raised when Ollama returns an invalid or unsuccessful response."""

class BaseModelEndpoint(ABC):
    """Common HTTP transport for Ollama text and vision models."""

    def __init__(
        self,
        model: str,
        host: str,
        timeout: float,
    ) -> None:
        self.model = model
        self.host = host.rstrip("/")
        self.timeout = timeout

    async def _post(self, path: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        started_at = time.perf_counter()
        try:
            async with httpx.AsyncClient(base_url=self.host, timeout=self.timeout) as client:
                response = await client.post(path, json=dict(payload))
                response.raise_for_status()
        except httpx.TimeoutException as exc:
            self._log_request(path, started_at, error="timeout")
            raise OllamaConnectionError("ollama request timed out") from exc
        except httpx.ConnectError as exc:
            self._log_request(path, started_at, error="unreachable")
            raise OllamaConnectionError("ollama is not reachable") from exc
        except httpx.HTTPStatusError as exc:
            self._log_request(path, started_at, error=f"http_{exc.response.status_code}")
            raise OllamaResponseError(
                f"ollama returned HTTP {exc.response.status_code}"
            ) from exc
        except httpx.HTTPError as exc:
            self._log_request(path, started_at, error="http_error")
            raise OllamaResponseError("ollama request failed") from exc

        try:
            data = response.json()
        except json.JSONDecodeError as exc:
            self._log_request(path, started_at, error="invalid_json")
            raise OllamaResponseError("ollama returned invalid JSON") from exc

        if not isinstance(data, dict):
            self._log_request(path, started_at, error="invalid_payload")
            raise OllamaResponseError("ollama returned an unexpected payload")

        self._log_request(
            path,
            started_at,
            token_count=data.get("eval_count") or data.get("prompt_eval_count"),
        )
        return data

    @staticmethod
    def _log_request(
        path: str,
        started_at: float,
        token_count: Any = None,
        error: str | None = None,
    ) -> None:
        logger.info(
            json.dumps(
                {
                    "event": "ollama_request",
                    "endpoint": path,
                    "latency_ms": round((time.perf_counter() - started_at) * 1000, 2),
                    "token_count": token_count,
                    "error": error,
                },
                ensure_ascii=True,
            )
        )

    @abstractmethod
    async def generate(self, prompt: str, **kwargs: Any) -> str: ...

    @abstractmethod
    async def chat(
        self,
        messages: Sequence[Mapping[str, Any]],
        **kwargs: Any,
    ) -> dict[str, Any]: ...
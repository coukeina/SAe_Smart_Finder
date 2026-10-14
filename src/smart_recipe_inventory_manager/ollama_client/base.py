from __future__ import annotations

import asyncio
import json
import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Mapping, Sequence

import httpx


logger = logging.getLogger(__name__)

MAX_REQUEST_ATTEMPTS = 3
RETRY_DELAY_SECONDS = 0.25


class OllamaError(RuntimeError):
    """Base error raised by the local Ollama adapter."""


class OllamaConnectionError(OllamaError):
    """Raised when Ollama cannot be reached or times out."""


class OllamaResponseError(OllamaError):
    """Raised when Ollama returns an invalid or unsuccessful response."""


class OllamaContextError(OllamaResponseError):
    """Raised when a request exceeds Ollama's model context window."""


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
        for attempt in range(1, MAX_REQUEST_ATTEMPTS + 1):
            started_at = time.perf_counter()
            try:
                async with httpx.AsyncClient(
                    base_url=self.host,
                    timeout=self.timeout,
                ) as client:
                    response = await client.post(path, json=dict(payload))
                    response.raise_for_status()
            except httpx.TimeoutException as exc:
                self._log_request(path, started_at, error="timeout")
                if attempt < MAX_REQUEST_ATTEMPTS:
                    await asyncio.sleep(RETRY_DELAY_SECONDS * attempt)
                    continue
                raise OllamaConnectionError("ollama request timed out") from exc
            except httpx.ConnectError as exc:
                self._log_request(path, started_at, error="unreachable")
                if attempt < MAX_REQUEST_ATTEMPTS:
                    await asyncio.sleep(RETRY_DELAY_SECONDS * attempt)
                    continue
                raise OllamaConnectionError("ollama is not reachable") from exc
            except httpx.HTTPStatusError as exc:
                status_code = exc.response.status_code
                if self._is_context_limit_error(exc.response):
                    self._log_request(
                        path,
                        started_at,
                        error=f"context_limit_http_{status_code}",
                    )
                    raise OllamaContextError(
                        "ollama request exceeds the model context limit"
                    ) from exc

                self._log_request(path, started_at, error=f"http_{status_code}")
                if (
                    (status_code == 429 or status_code >= 500)
                    and attempt < MAX_REQUEST_ATTEMPTS
                ):
                    await asyncio.sleep(RETRY_DELAY_SECONDS * attempt)
                    continue
                raise OllamaResponseError(
                    f"ollama returned HTTP {status_code}"
                ) from exc
            except httpx.HTTPError as exc:
                self._log_request(path, started_at, error="http_error")
                if attempt < MAX_REQUEST_ATTEMPTS:
                    await asyncio.sleep(RETRY_DELAY_SECONDS * attempt)
                    continue
                raise OllamaResponseError("ollama request failed") from exc

            try:
                data = response.json()
            except json.JSONDecodeError as exc:
                self._log_request(path, started_at, error="invalid_json")
                if attempt < MAX_REQUEST_ATTEMPTS:
                    await asyncio.sleep(RETRY_DELAY_SECONDS * attempt)
                    continue
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

        raise OllamaResponseError("ollama request failed after retries")

    @staticmethod
    def _is_context_limit_error(response: httpx.Response) -> bool:
        if response.status_code == 413:
            return True

        try:
            payload = response.json()
        except json.JSONDecodeError:
            message = response.text
        else:
            message = payload.get("error", "") if isinstance(payload, dict) else ""

        message = str(message).casefold()
        return any(
            marker in message
            for marker in (
                "context length",
                "context window",
                "maximum context",
                "input length",
                "num_ctx",
            )
        )

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
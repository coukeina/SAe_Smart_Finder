from __future__ import annotations

import asyncio
import json
import logging
import time
from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from typing import Any

import httpx

logger = logging.getLogger(__name__)

MAX_REQUEST_ATTEMPTS = 3
RETRY_DELAY_SECONDS = 0.25


def _is_context_limit_message(message: str) -> bool:
    normalized = message.casefold()
    return any(
        marker in normalized
        for marker in (
            "context length",
            "context window",
            "maximum context",
            "input length",
            "num_ctx",
        )
    )

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
        timeout = httpx.Timeout(self.timeout, connect=10.0)
        for attempt in range(1, MAX_REQUEST_ATTEMPTS + 1):
            started_at = time.perf_counter()
            try:
                async with httpx.AsyncClient(
                    base_url=self.host,
                    timeout=timeout,
                ) as client:
                    if payload.get("stream"):
                        data = await self._read_stream(client, path, payload)
                    else:
                        response = await client.post(path, json=dict(payload))
                        response.raise_for_status()
                        data = response.json()
            except OllamaContextError:
                self._log_request(path, started_at, error="context_limit")
                raise
            except json.JSONDecodeError as exc:
                self._log_request(path, started_at, error="invalid_json")
                if attempt < MAX_REQUEST_ATTEMPTS:
                    await asyncio.sleep(RETRY_DELAY_SECONDS * attempt)
                    continue
                raise OllamaResponseError("ollama returned invalid JSON") from exc
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
            except OllamaResponseError:
                self._log_request(path, started_at, error="invalid_stream")
                raise

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

        return _is_context_limit_message(str(message))

    @staticmethod
    async def _read_stream(
        client: httpx.AsyncClient,
        path: str,
        payload: Mapping[str, Any],
    ) -> dict[str, Any]:
        parts: list[str] = []
        final: dict[str, Any] = {}
        async with client.stream("POST", path, json=dict(payload)) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line:
                    continue
                chunk = json.loads(line)
                if "error" in chunk:
                    message = str(chunk["error"])
                    if _is_context_limit_message(message):
                        raise OllamaContextError(
                            "ollama request exceeds the model context limit"
                        )
                    raise OllamaResponseError(message)
                message = chunk.get("message") or {}
                parts.append(chunk.get("response") or message.get("content") or "")
                if chunk.get("done"):
                    final = chunk
        if not final:
            raise OllamaResponseError("ollama stream ended before completion")
        text = "".join(parts)
        if "message" in final:
            final["message"] = {**final["message"], "content": text}
        else:
            final["response"] = text
        return final

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
import asyncio
import json
import re
from collections.abc import Mapping, Sequence
from typing import Any

from ..config import settings
from .base import RETRY_DELAY_SECONDS, BaseModelEndpoint, OllamaResponseError


class OllamaLLM(BaseModelEndpoint):
    def __init__(
        self,
        model: str | None = None,
        host: str | None = None,
        timeout: float | None = None,
    ) -> None:
        super().__init__(
            model=model or settings.llm_model,
            host=host or settings.ollama_host,
            timeout=timeout or settings.ollama_timeout_seconds,
        )

    async def generate(
        self,
        prompt: str,
        max_tokens: int = 256,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> str:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": True,
            "options": {
                "num_predict": max_tokens,
                "temperature": temperature,
            },
        }
        payload.update(kwargs)
        resp = await self._post("/api/generate", payload)
        response = resp.get("response")
        if not isinstance(response, str):
            raise OllamaResponseError("ollama generate response is missing 'response'")
        return response

    async def chat(
        self,
        messages: Sequence[Mapping[str, Any]],
        max_tokens: int = 256,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> dict[str, Any]:
        payload = {
            "model": self.model,
            "messages": list(messages),
            "stream": True,
            "options": {
                "num_predict": max_tokens,
                "temperature": temperature,
            },
        }
        payload.update(kwargs)
        return await self._post("/api/chat", payload)

    async def generate_json(
        self,
        prompt: str,
        schema: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Generate and defensively parse one JSON object."""
        for attempt in range(2):
            response = await self.generate(
                prompt,
                format=schema or "json",
                **kwargs,
            )
            cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", response.strip())
            try:
                parsed = json.loads(cleaned)
            except json.JSONDecodeError as exc:
                if attempt == 1:
                    raise OllamaResponseError("ollama returned malformed JSON") from exc
                await asyncio.sleep(RETRY_DELAY_SECONDS)
                continue

            if not isinstance(parsed, dict):
                raise OllamaResponseError("ollama JSON response must be an object")
            return parsed

        raise OllamaResponseError("ollama returned malformed JSON after retry")
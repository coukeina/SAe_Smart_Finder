import asyncio
import base64
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from ..config import settings
from .base import RETRY_DELAY_SECONDS, BaseModelEndpoint, OllamaResponseError


class OllamaVLM(BaseModelEndpoint):
    def __init__(
        self,
        model: str | None = None,
        host: str | None = None,
        timeout: float | None = None,
    ) -> None:
        super().__init__(
            model=model or settings.vlm_model,
            host=host or settings.ollama_host,
            timeout=timeout or settings.ollama_timeout_seconds,
        )

    async def generate(self, prompt: str, **kwargs: Any) -> str:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": True,
        }
        payload.update(kwargs)
        response = await self._post("/api/generate", payload)
        text = response.get("response")
        if not isinstance(text, str):
            raise OllamaResponseError(
                "ollama generate response is missing 'response'"
            )
        return text

    async def chat(
        self,
        messages: Sequence[Mapping[str, Any]],
        max_tokens: int = 512,
        temperature: float = 0.2,
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

    async def detect_ingredients(
        self,
        image_path: str,
        prompt: str,
        schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        image_base64 = base64.b64encode(
            Path(image_path).read_bytes()
        ).decode("utf-8")

        for attempt in range(2):
            response = await self.chat(
                [{
                    "role": "user",
                    "content": prompt,
                    "images": [image_base64],
                }],
                format=schema or "json",
                options={"temperature": 0},
            )
            message = response.get("message")
            content = message.get("content") if isinstance(message, dict) else None
            if not isinstance(content, str):
                if attempt == 0:
                    await asyncio.sleep(RETRY_DELAY_SECONDS)
                    continue
                raise OllamaResponseError(
                    "ollama vision response is missing message content"
                )

            try:
                payload = json.loads(content)
            except json.JSONDecodeError as exc:
                if attempt == 0:
                    await asyncio.sleep(RETRY_DELAY_SECONDS)
                    continue
                raise OllamaResponseError(
                    "ollama vision response contains malformed JSON"
                ) from exc

            if not isinstance(payload, dict):
                raise OllamaResponseError(
                    "ollama vision JSON response must be an object"
                )
            return payload

        raise OllamaResponseError(
            "ollama vision response remained malformed after retry"
        )
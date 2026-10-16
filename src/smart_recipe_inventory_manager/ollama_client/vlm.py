import base64
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from ..config import settings
from .base import BaseModelEndpoint


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
            raise ValueError("ollama generate response is missing 'response'")
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
    ) -> dict[str, Any]:
        image_base64 = base64.b64encode(
            Path(image_path).read_bytes()
        ).decode("utf-8")

        response = await self.chat(
            [{
                "role": "user",
                "content": prompt,
                "images": [image_base64],
            }],
            format="json",
            options={"temperature": 0},
        )

        content = response["message"]["content"]
        return json.loads(content)
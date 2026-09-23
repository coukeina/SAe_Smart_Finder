import base64
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from ..config import settings
from .base import BaseModelEndpoint

import os

class OllamaVLM(BaseModelEndpoint):
    model = os.getenv("VLM_MODEL", "qwen3-vl:4b")
    host = os.getenv("OLLAMA_HOST", "http://ollama:11434")

    def __init__(
        self,
        model: str = "qwen3-vl:4b",
        host: str = "http://localhost:11434",
        timeout: float | None = None,
    ) -> None:
        self.model = model
        self.host = host.rstrip("/")
        super().__init__(
            model=model or settings.vlm_model,
            host=host or settings.ollama_host,
            timeout=timeout or settings.ollama_timeout_seconds,
        )

    async def generate(self, prompt: str, **kwargs: Any) -> str:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
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
            "stream": False,
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
import asyncio
from .base import BaseModelEndpoint
from pydantic import BaseModel, Field
from typing import Any, Dict

class OllamaLLM(BaseModelEndpoint):
    model: str
    host: str = "http://localhost:11434"

    async def generate(self, prompt: str, max_tokens: int = 256,
                       temperature: float = 0.7, **kw) -> str:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": False,
        }
        payload.update(kw)
        resp = await self._post("/api/chat", payload)
        return resp["response"]

    # _post() is a private helper that does aiohttp request...
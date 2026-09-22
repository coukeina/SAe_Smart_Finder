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
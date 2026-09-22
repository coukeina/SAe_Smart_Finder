from typing import Any

from ..config import settings
from .base import BaseModelEndpoint


class OllamaEmbedding(BaseModelEndpoint):
	def __init__(
		self,
		model: str | None = None,
		host: str | None = None,
		timeout: float | None = None,
	) -> None:
		super().__init__(
			model=model or settings.embedding_model,
			host=host or settings.ollama_host,
			timeout=timeout or settings.ollama_timeout_seconds,
		)

	async def embed(self, inputs: str | list[str]) -> list[list[float]]:
		response = await self._post(
			"/api/embed",
			{"model": self.model, "input": inputs},
		)
		embeddings = response.get("embeddings")
		if not isinstance(embeddings, list) or not all(
			isinstance(vector, list) for vector in embeddings
		):
			raise ValueError("ollama embedding response is invalid")
		return embeddings

	async def generate(self, prompt: str, **kwargs: Any) -> str:
		raise NotImplementedError("embedding endpoint does not generate text")

	async def chat(self, messages: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
		raise NotImplementedError("embedding endpoint does not support chat")

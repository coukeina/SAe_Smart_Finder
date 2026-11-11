import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from smart_recipe_inventory_manager.ollama_client.base import (
    BaseModelEndpoint,
    OllamaConnectionError,
    OllamaResponseError,
)
from smart_recipe_inventory_manager.ollama_client.embedding import OllamaEmbedding
from smart_recipe_inventory_manager.ollama_client.llm import OllamaLLM
from smart_recipe_inventory_manager.ollama_client.vlm import OllamaVLM


class ConcreteEndpoint(BaseModelEndpoint):
    async def generate(self, prompt: str, **kwargs) -> str:
        return "ok"

    async def chat(self, messages, **kwargs) -> dict:
        return {"message": {"content": "ok"}}


class OllamaAdaptersExtendedTests(unittest.IsolatedAsyncioTestCase):
    async def test_base_endpoint_retry_on_timeout(self):
        endpoint = ConcreteEndpoint(
            model="test-model", host="http://localhost:11434", timeout=1.0
        )
        with (
            patch(
                "httpx.AsyncClient.post",
                side_effect=httpx.TimeoutException("timeout"),
            ),
            self.assertRaises(OllamaConnectionError),
        ):
            await endpoint._post("/api/generate", {"prompt": "test"})

    async def test_base_endpoint_http_status_error(self):
        endpoint = ConcreteEndpoint(
            model="test-model", host="http://localhost:11434", timeout=120.0
        )
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "error", request=MagicMock(), response=mock_response
        )

        with (
            patch("httpx.AsyncClient.post", return_value=mock_response),
            self.assertRaises(OllamaResponseError),
        ):
            await endpoint._post("/api/generate", {"prompt": "test"})

    async def test_embedding_invalid_vector_type(self):
        emb = OllamaEmbedding(model="emb", host="http://localhost:11434", timeout=120.0)
        with (
            patch.object(
                emb, "_post", return_value={"embeddings": [["not_a_float"]]}
            ),
            self.assertRaises(OllamaResponseError),
        ):
            await emb.embed("test")

    async def test_embedding_invalid_vector_count(self):
        emb = OllamaEmbedding(model="emb", host="http://localhost:11434", timeout=120.0)
        with (
            patch.object(emb, "_post", return_value={"embeddings": [[0.1, 0.2]]}),
            self.assertRaises(OllamaResponseError),
        ):
            await emb.embed(["input1", "input2"])

    async def test_llm_malformed_json_response(self):
        llm = OllamaLLM(model="llm", host="http://localhost:11434", timeout=120.0)
        with (
            patch.object(
                llm,
                "generate",
                new_callable=AsyncMock,
                return_value="Not a valid json",
            ),
            self.assertRaises(OllamaResponseError),
        ):
            await llm.generate_json("prompt")

    async def test_vlm_invalid_response_structure(self):
        vlm = OllamaVLM(model="vlm", host="http://localhost:11434", timeout=120.0)
        with (
            patch("pathlib.Path.read_bytes", return_value=b"fake_image_bytes"),
            patch.object(
                vlm, "chat", new_callable=AsyncMock, return_value={"message": {}}
            ),
            self.assertRaises(OllamaResponseError),
        ):
            await vlm.detect_ingredients("fake.jpg", prompt="Décris")

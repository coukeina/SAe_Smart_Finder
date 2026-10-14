import json
import unittest
from pathlib import Path
from typing import Any, Mapping, Sequence
from unittest.mock import patch

from smart_recipe_inventory_manager.ollama_client.base import OllamaResponseError
from smart_recipe_inventory_manager.ollama_client.llm import OllamaLLM
from smart_recipe_inventory_manager.ollama_client.vlm import OllamaVLM
from smart_recipe_inventory_manager.service.core import detect_ingredients, generate_recipe


class StubLLM(OllamaLLM):
	def __init__(self, payload: dict[str, Any]) -> None:
		self.payload = payload
		self.schema: dict[str, Any] | None = None

	async def generate_json(
		self,
		prompt: str,
		schema: dict[str, Any] | None = None,
		**kwargs: Any,
	) -> dict[str, Any]:
		self.schema = schema
		return self.payload


class RawResponseLLM(OllamaLLM):
	def __init__(self, response: str) -> None:
		self.response = response

	async def generate(self, prompt: str, **kwargs: Any) -> str:
		return self.response


class StubVLM(OllamaVLM):
	def __init__(self, content: str) -> None:
		self.content = content
		self.output_schema: dict[str, Any] | str | None = None

	async def generate(self, prompt: str, **kwargs: Any) -> str:
		raise NotImplementedError

	async def chat(
		self,
		messages: Sequence[Mapping[str, Any]],
		**kwargs: Any,
	) -> dict[str, Any]:
		self.output_schema = kwargs.get("format")
		return {"message": {"content": self.content}}


class LevelOneContractTests(unittest.IsolatedAsyncioTestCase):
	async def test_detect_ingredients_validates_vlm_json(self) -> None:
		with patch(
			"smart_recipe_inventory_manager.ollama_client.vlm.Path.read_bytes",
			return_value=b"image",
		):
			vlm = StubVLM(json.dumps({
				"ingredients": [{"name": "tomate", "quantity": 2, "maturity": None}],
			}))

			result = await detect_ingredients("image.jpg", vlm=vlm)

		self.assertEqual(result["ingredients"][0]["name"], "tomate")
		self.assertEqual(result["ingredients"][0]["quantity"], 2.0)
		self.assertIsInstance(vlm.output_schema, dict)
		self.assertIn("ingredients", vlm.output_schema["properties"])

	async def test_detect_ingredients_rejects_malformed_json(self) -> None:
		with patch(
			"smart_recipe_inventory_manager.ollama_client.vlm.Path.read_bytes",
			return_value=b"image",
		):
			vlm = StubVLM("{not-json")

			with self.assertRaises(OllamaResponseError):
				await detect_ingredients("image.jpg", vlm=vlm)

	async def test_detect_ingredients_rejects_invalid_schema(self) -> None:
		with patch(
			"smart_recipe_inventory_manager.ollama_client.vlm.Path.read_bytes",
			return_value=b"image",
		):
			vlm = StubVLM(json.dumps({"items": ["tomate"]}))

			with self.assertRaises(OllamaResponseError):
				await detect_ingredients("image.jpg", vlm=vlm)

	async def test_generate_recipe_uses_schema_and_returns_validated_data(self) -> None:
		llm = StubLLM({
			"title": "Soupe de tomates",
			"ingredients": ["tomates"],
			"steps": ["Couper les tomates.", "Les faire cuire."],
			"cooking_time": "20 minutes",
		})

		recipe = await generate_recipe(
			ingredients=[{"name": "tomate"}],
			llm=llm,
		)

		self.assertEqual(recipe["title"], "Soupe de tomates")
		self.assertIsNotNone(llm.schema)
		self.assertIn("cooking_time", llm.schema["required"])

	async def test_generate_recipe_rejects_incomplete_response(self) -> None:
		llm = StubLLM({
			"title": "Soupe de tomates",
			"ingredients": [],
			"steps": [],
			"cooking_time": "20 minutes",
		})

		with self.assertRaises(OllamaResponseError):
			await generate_recipe(ingredients=[{"name": "tomate"}], llm=llm)

	async def test_generate_recipe_rejects_malformed_json(self) -> None:
		with self.assertRaises(OllamaResponseError):
			await generate_recipe(
				ingredients=[{"name": "tomate"}],
				llm=RawResponseLLM("{not-json"),
			)


if __name__ == "__main__":
	unittest.main()

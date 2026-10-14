import json
import unittest
from pathlib import Path
from typing import Any, Mapping, Sequence
from unittest.mock import AsyncMock, patch

import httpx

from smart_recipe_inventory_manager.ollama_client.base import (
	BaseModelEndpoint,
	OllamaContextError,
	OllamaConnectionError,
	OllamaResponseError,
)
from smart_recipe_inventory_manager.ollama_client.llm import OllamaLLM
from smart_recipe_inventory_manager.ollama_client.vlm import OllamaVLM
from smart_recipe_inventory_manager.ui_gradio import propose_recipe
from smart_recipe_inventory_manager.service.core import (
	RecipeInputError,
	detect_ingredients,
	generate_recipe,
	suggest_recipe,
)


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


class SequenceResponseLLM(OllamaLLM):
	def __init__(self, responses: list[str]) -> None:
		self.responses = responses
		self.calls = 0

	async def generate(self, prompt: str, **kwargs: Any) -> str:
		response = self.responses[self.calls]
		self.calls += 1
		return response


class StubEndpoint(BaseModelEndpoint):
	async def generate(self, prompt: str, **kwargs: Any) -> str:
		raise NotImplementedError

	async def chat(
		self,
		messages: Sequence[Mapping[str, Any]],
		**kwargs: Any,
	) -> dict[str, Any]:
		raise NotImplementedError


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


class SequenceContentVLM(OllamaVLM):
	def __init__(self, responses: list[str]) -> None:
		self.responses = responses
		self.calls = 0

	async def generate(self, prompt: str, **kwargs: Any) -> str:
		raise NotImplementedError

	async def chat(
		self,
		messages: Sequence[Mapping[str, Any]],
		**kwargs: Any,
	) -> dict[str, Any]:
		content = self.responses[self.calls]
		self.calls += 1
		return {"message": {"content": content}}


class StubDetectionVLM(OllamaVLM):
	def __init__(self, ingredients: list[dict[str, Any]]) -> None:
		self.ingredients = ingredients

	async def detect_ingredients(self, image_path: str, prompt: str, **kwargs: Any) -> dict[str, Any]:
		return {"ingredients": self.ingredients}


class OllamaRetryTests(unittest.IsolatedAsyncioTestCase):
	async def test_connection_and_timeout_errors_are_retried(self) -> None:
		for error_type in (httpx.ConnectError, httpx.ReadTimeout):
			with self.subTest(error_type=error_type.__name__):
				request_count = 0

				def respond(request: httpx.Request) -> httpx.Response:
					nonlocal request_count
					request_count += 1
					if request_count == 1:
						raise error_type("temporary failure", request=request)
					return httpx.Response(200, json={"response": "ok"})

				transport = httpx.MockTransport(respond)
				real_client = httpx.AsyncClient
				client_factory = lambda **kwargs: real_client(
					transport=transport,
					**kwargs,
				)
				endpoint = StubEndpoint("test-model", "http://ollama", 1)

				with (
					patch(
						"smart_recipe_inventory_manager.ollama_client.base.httpx.AsyncClient",
						side_effect=client_factory,
					),
					patch(
						"smart_recipe_inventory_manager.ollama_client.base.asyncio.sleep",
						new=AsyncMock(),
					),
				):
					result = await endpoint._post("/api/generate", {})

				self.assertEqual(result, {"response": "ok"})
				self.assertEqual(request_count, 2)

	async def test_transient_server_error_is_retried(self) -> None:
		request_count = 0

		def respond(request: httpx.Request) -> httpx.Response:
			nonlocal request_count
			request_count += 1
			if request_count == 1:
				return httpx.Response(503, json={"error": "temporarily unavailable"})
			return httpx.Response(200, json={"response": "ok"})

		transport = httpx.MockTransport(respond)
		real_client = httpx.AsyncClient
		client_factory = lambda **kwargs: real_client(transport=transport, **kwargs)
		endpoint = StubEndpoint("test-model", "http://ollama", 1)

		with (
			patch(
				"smart_recipe_inventory_manager.ollama_client.base.httpx.AsyncClient",
				side_effect=client_factory,
			),
			patch(
				"smart_recipe_inventory_manager.ollama_client.base.asyncio.sleep",
				new=AsyncMock(),
			),
		):
			result = await endpoint._post("/api/generate", {})

		self.assertEqual(result, {"response": "ok"})
		self.assertEqual(request_count, 2)

	async def test_context_limit_error_is_not_retried(self) -> None:
		request_count = 0

		def respond(request: httpx.Request) -> httpx.Response:
			nonlocal request_count
			request_count += 1
			return httpx.Response(
				500,
				json={"error": "input length exceeds the context length"},
			)

		transport = httpx.MockTransport(respond)
		real_client = httpx.AsyncClient
		client_factory = lambda **kwargs: real_client(transport=transport, **kwargs)
		endpoint = StubEndpoint("test-model", "http://ollama", 1)

		with patch(
			"smart_recipe_inventory_manager.ollama_client.base.httpx.AsyncClient",
			side_effect=client_factory,
		):
			with self.assertRaises(OllamaContextError):
				await endpoint._post("/api/generate", {})

		self.assertEqual(request_count, 1)

	async def test_server_error_fails_after_bounded_retries(self) -> None:
		request_count = 0

		def respond(request: httpx.Request) -> httpx.Response:
			nonlocal request_count
			request_count += 1
			return httpx.Response(503, json={"error": "unavailable"})

		transport = httpx.MockTransport(respond)
		real_client = httpx.AsyncClient
		client_factory = lambda **kwargs: real_client(transport=transport, **kwargs)
		endpoint = StubEndpoint("test-model", "http://ollama", 1)

		with (
			patch(
				"smart_recipe_inventory_manager.ollama_client.base.httpx.AsyncClient",
				side_effect=client_factory,
			),
			patch(
				"smart_recipe_inventory_manager.ollama_client.base.asyncio.sleep",
				new=AsyncMock(),
			),
		):
			with self.assertRaises(OllamaResponseError):
				await endpoint._post("/api/generate", {})

		self.assertEqual(request_count, 3)


class GradioFlowTests(unittest.IsolatedAsyncioTestCase):
	async def test_missing_image_returns_a_user_facing_error(self) -> None:
		with patch(
			"smart_recipe_inventory_manager.ui_gradio.suggest_recipe",
			new=AsyncMock(),
		) as suggest:
			rows, recipe = await propose_recipe(None, None)

		self.assertEqual(rows, [])
		self.assertIn("Aucune image", recipe["error"])
		suggest.assert_not_awaited()

	async def test_success_returns_detected_ingredients_and_recipe(self) -> None:
		expected = {
			"ingredients": [{
				"name": "tomate",
				"quantity": 2,
				"maturity": None,
			}],
			"recipe": {
				"title": "Soupe",
				"ingredients": ["tomate"],
				"steps": ["Cuire."],
				"cooking_time": "20 minutes",
			},
		}
		with patch(
			"smart_recipe_inventory_manager.ui_gradio.suggest_recipe",
			new=AsyncMock(return_value=expected),
		) as suggest:
			rows, recipe = await propose_recipe("fridge.jpg", "rapide")

		self.assertEqual(rows, [["tomate", 2, None]])
		self.assertEqual(recipe, expected["recipe"])
		suggest.assert_awaited_once_with(
			image_path="fridge.jpg",
			preferences="rapide",
		)

	async def test_ollama_failures_return_friendly_messages(self) -> None:
		failures = (
			(
				OllamaContextError("context limit"),
				"photo contient trop d'informations",
			),
			(
				OllamaConnectionError("ollama unavailable"),
				"service Ollama est inaccessible",
			),
			(
				OllamaResponseError("bad output"),
				"réponse exploitable",
			),
		)
		for error, expected_message in failures:
			with self.subTest(error=type(error).__name__):
				with patch(
					"smart_recipe_inventory_manager.ui_gradio.suggest_recipe",
					new=AsyncMock(side_effect=error),
				):
					rows, recipe = await propose_recipe("fridge.jpg", None)

				self.assertEqual(rows, [])
				self.assertIn(expected_message, recipe["error"])


class LevelOneContractTests(unittest.IsolatedAsyncioTestCase):
	async def test_level_one_scenario_dataset(self) -> None:
		scenarios = json.loads(
			(Path(__file__).parent / "fixtures" / "level1_scenarios.json")
			.read_text(encoding="utf-8")
		)

		for scenario in scenarios:
			with self.subTest(scenario=scenario["id"]):
				if scenario["expected"] == "input-error":
					with self.assertRaises(RecipeInputError):
						await suggest_recipe(
							image_path="unused.jpg",
							vlm=StubDetectionVLM(scenario["detected_ingredients"]),
							llm=StubLLM({}),
						)
					continue

				llm = StubLLM(scenario["recipe"])
				if scenario["expected"] == "response-error":
					with self.assertRaises(OllamaResponseError):
						await generate_recipe(
							ingredients=scenario["detected_ingredients"],
							llm=llm,
						)
					continue

				recipe = await generate_recipe(
					ingredients=scenario["detected_ingredients"],
					llm=llm,
				)
				self.assertEqual(recipe["title"], scenario["recipe"]["title"])

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
		), patch(
			"smart_recipe_inventory_manager.ollama_client.vlm.asyncio.sleep",
			new=AsyncMock(),
		):
			vlm = StubVLM("{not-json")

			with self.assertRaises(OllamaResponseError):
				await detect_ingredients("image.jpg", vlm=vlm)

	async def test_vlm_retries_malformed_json_once(self) -> None:
		vlm = SequenceContentVLM([
			"{not-json",
			json.dumps({"ingredients": [{"name": "tomate"}]}),
		])
		with patch(
			"smart_recipe_inventory_manager.ollama_client.vlm.Path.read_bytes",
			return_value=b"image",
		), patch(
			"smart_recipe_inventory_manager.ollama_client.vlm.asyncio.sleep",
			new=AsyncMock(),
		):
			result = await detect_ingredients("image.jpg", vlm=vlm)

		self.assertEqual(result["ingredients"][0]["name"], "tomate")
		self.assertEqual(vlm.calls, 2)

	async def test_vlm_stops_after_one_malformed_json_retry(self) -> None:
		vlm = SequenceContentVLM(["{not-json", "{still-not-json"])
		with patch(
			"smart_recipe_inventory_manager.ollama_client.vlm.Path.read_bytes",
			return_value=b"image",
		), patch(
			"smart_recipe_inventory_manager.ollama_client.vlm.asyncio.sleep",
			new=AsyncMock(),
		):
			with self.assertRaises(OllamaResponseError):
				await detect_ingredients("image.jpg", vlm=vlm)

		self.assertEqual(vlm.calls, 2)

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

	async def test_generate_recipe_rejects_ingredients_not_detected(self) -> None:
		llm = StubLLM({
			"title": "Omelette",
			"ingredients": ["œufs", "fromage"],
			"steps": ["Cuire."],
			"cooking_time": "10 minutes",
		})

		with self.assertRaisesRegex(OllamaResponseError, "not detected"):
			await generate_recipe(
				ingredients=[{"name": "œufs"}],
				llm=llm,
			)

	async def test_generate_recipe_rejects_empty_ingredient_list_before_calling_llm(self) -> None:
		llm = StubLLM({})

		with self.assertRaises(RecipeInputError):
			await generate_recipe(ingredients=[], llm=llm)

		self.assertIsNone(llm.schema)

	async def test_generate_recipe_accepts_case_accent_and_plural_variants(self) -> None:
		llm = StubLLM({
			"title": "Salade",
			"ingredients": ["TOMATES", "oeuf"],
			"steps": ["Mélanger."],
			"cooking_time": "5 minutes",
		})

		recipe = await generate_recipe(
			ingredients=[{"name": "tomate"}, {"name": "œufs"}],
			llm=llm,
		)

		self.assertEqual(recipe["title"], "Salade")

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
		llm = SequenceResponseLLM(["{not-json", "{still-not-json"])
		with patch(
			"smart_recipe_inventory_manager.ollama_client.llm.asyncio.sleep",
			new=AsyncMock(),
		), self.assertRaises(OllamaResponseError):
			await generate_recipe(
				ingredients=[{"name": "tomate"}],
				llm=llm,
			)

		self.assertEqual(llm.calls, 2)

	async def test_generate_recipe_retries_malformed_json_once(self) -> None:
		llm = SequenceResponseLLM([
			"{not-json",
			json.dumps({
				"title": "Soupe",
				"ingredients": ["tomates"],
				"steps": ["Cuire."],
				"cooking_time": "20 minutes",
			}),
		])

		with patch(
			"smart_recipe_inventory_manager.ollama_client.llm.asyncio.sleep",
			new=AsyncMock(),
		):
			recipe = await generate_recipe(
				ingredients=[{"name": "tomate"}],
				llm=llm,
			)

		self.assertEqual(recipe["title"], "Soupe")
		self.assertEqual(llm.calls, 2)

	async def test_suggest_recipe_stops_when_no_ingredients_were_detected(self) -> None:
		llm = StubLLM({})

		with self.assertRaises(RecipeInputError):
			await suggest_recipe(
				image_path="unused.jpg",
				vlm=StubDetectionVLM([]),
				llm=llm,
			)

		self.assertIsNone(llm.schema)


if __name__ == "__main__":
	unittest.main()

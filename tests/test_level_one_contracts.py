import json
import unittest
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import psycopg

from smart_recipe_inventory_manager.config import Settings
from smart_recipe_inventory_manager.ollama_client.base import (
	BaseModelEndpoint,
	OllamaConnectionError,
	OllamaContextError,
	OllamaResponseError,
)
from smart_recipe_inventory_manager.ollama_client.embedding import OllamaEmbedding
from smart_recipe_inventory_manager.ollama_client.llm import OllamaLLM
from smart_recipe_inventory_manager.ollama_client.vlm import OllamaVLM
from smart_recipe_inventory_manager.service.core import (
	RecipeInputError,
	detect_ingredients,
	generate_recipe,
	suggest_recipe,
)
from smart_recipe_inventory_manager.storage.recipe_repository import (
	RecipeRepositoryError,
	recipe_embedding_text,
	search_recipes,
)
from smart_recipe_inventory_manager.ui_gradio import propose_recipe, save_result


class StubLLM(OllamaLLM):
	def __init__(self, payload: dict[str, Any]) -> None:
		self.payload = payload
		self.schema: dict[str, Any] | None = None
		self.prompt = ""

	async def generate_json(
		self,
		prompt: str,
		schema: dict[str, Any] | None = None,
		**kwargs: Any,
	) -> dict[str, Any]:
		self.schema = schema
		self.prompt = prompt
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


class StubEmbedding(OllamaEmbedding):
	def __init__(self, vectors: list[list[float]]) -> None:
		self.vectors = vectors
		self.inputs: str | list[str] | None = None

	async def embed(self, inputs: str | list[str]) -> list[list[float]]:
		self.inputs = inputs
		return self.vectors


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
	async def test_streaming_response_is_aggregated(self) -> None:
		response_body = (
			'{"response":"hel","done":false}\n'
			'{"response":"lo","done":true,"eval_count":2}\n'
		)
		transport = httpx.MockTransport(
			lambda request: httpx.Response(200, content=response_body)
		)
		real_client = httpx.AsyncClient

		def client_factory(**kwargs: Any) -> httpx.AsyncClient:
			return real_client(transport=transport, **kwargs)

		endpoint = StubEndpoint("test-model", "http://ollama", 1)
		with patch(
			"smart_recipe_inventory_manager.ollama_client.base.httpx.AsyncClient",
			side_effect=client_factory,
		):
			result = await endpoint._post(
				"/api/generate",
				{"stream": True},
			)

		self.assertEqual(result["response"], "hello")
		self.assertEqual(result["eval_count"], 2)

	async def test_request_metrics_include_latency_and_generation_rate(self) -> None:
		transport = httpx.MockTransport(
			lambda request: httpx.Response(
				200,
				json={
					"response": "ok",
					"eval_count": 10,
					"eval_duration": 2_000_000_000,
				},
			)
		)
		real_client = httpx.AsyncClient

		def client_factory(**kwargs: Any) -> httpx.AsyncClient:
			return real_client(transport=transport, **kwargs)

		endpoint = StubEndpoint("test-model", "http://ollama", 1)
		with patch(
			"smart_recipe_inventory_manager.ollama_client.base.httpx.AsyncClient",
			side_effect=client_factory,
		):
			await endpoint._post("/api/generate", {})

		self.assertIsNotNone(endpoint.last_request_metrics)
		self.assertEqual(endpoint.last_request_metrics.generated_tokens, 10)
		self.assertEqual(endpoint.last_request_metrics.tokens_per_second, 5.0)
		self.assertGreaterEqual(endpoint.last_request_metrics.latency_ms, 0)

	async def test_context_error_in_stream_is_not_retried(self) -> None:
		request_count = 0

		def respond(request: httpx.Request) -> httpx.Response:
			nonlocal request_count
			request_count += 1
			return httpx.Response(
				200,
				content='{"error":"input length exceeds context length"}\n',
			)

		transport = httpx.MockTransport(respond)
		real_client = httpx.AsyncClient

		def client_factory(**kwargs: Any) -> httpx.AsyncClient:
			return real_client(transport=transport, **kwargs)

		endpoint = StubEndpoint("test-model", "http://ollama", 1)
		with (
			patch(
				"smart_recipe_inventory_manager.ollama_client.base.httpx.AsyncClient",
				side_effect=client_factory,
			),
			self.assertRaises(OllamaContextError),
		):
			await endpoint._post("/api/generate", {"stream": True})

		self.assertEqual(request_count, 1)

	def test_vlm_default_matches_required_model(self) -> None:
		self.assertEqual(
			Settings.model_fields["vlm_model"].default,
			"qwen3-vl:instruct",
		)

	async def test_connection_and_timeout_errors_are_retried(self) -> None:
		for error_type in (httpx.ConnectError, httpx.ReadTimeout):
			with self.subTest(error_type=error_type.__name__):
				request_count = 0

				def respond(
					request: httpx.Request,
					retry_error: type[httpx.TransportError] = error_type,
				) -> httpx.Response:
					nonlocal request_count
					request_count += 1
					if request_count == 1:
						raise retry_error("temporary failure", request=request)
					return httpx.Response(200, json={"response": "ok"})

				transport = httpx.MockTransport(respond)
				real_client = httpx.AsyncClient

				def client_factory(
					real_client: type[httpx.AsyncClient] = real_client,
					request_transport: httpx.MockTransport = transport,
					**kwargs: Any,
				) -> httpx.AsyncClient:
					return real_client(transport=request_transport, **kwargs)
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
		), self.assertRaises(OllamaContextError):
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
			),self.assertRaises(OllamaResponseError)
		):
			await endpoint._post("/api/generate", {})

		self.assertEqual(request_count, 3)


class RecipeRepositoryTests(unittest.TestCase):
	def test_search_uses_normalized_names_and_returns_rows(self) -> None:
		expected = [{
			"id": 1,
			"title": "Soupe tomate",
			"available_ingredients": [{"name": "tomate"}],
		}]
		connection = MagicMock()
		cursor = MagicMock()
		connection.__enter__.return_value = connection
		connection.cursor.return_value.__enter__.return_value = cursor
		cursor.fetchall.return_value = expected

		with patch(
			"smart_recipe_inventory_manager.storage.recipe_repository.get_connection",
			return_value=connection,
		):
			vector = [0.1] * 768
			result = search_recipes(
				[{"name": " TOMATEs "}],
				vector,
				limit=3,
			)

		self.assertEqual(result, expected)
		query, parameters = cursor.execute.call_args.args
		self.assertIn("embedding <=> query_embedding.embedding", query)
		self.assertIn("ORDER BY coverage DESC", query)
		self.assertEqual(parameters[0], ["tomate", "tomates"])
		self.assertEqual(parameters[1], "[" + ",".join(["0.10000000000000001"] * 768) + "]")
		self.assertEqual(parameters[2:], (100, 3))

	def test_search_skips_database_for_empty_or_invalid_ingredients(self) -> None:
		with patch(
			"smart_recipe_inventory_manager.storage.recipe_repository.get_connection"
		) as get_connection:
			vector = [0.1] * 768
			self.assertEqual(search_recipes([], vector, limit=5), [])
			self.assertEqual(search_recipes([{"name": " "}], vector, limit=5), [])
			self.assertEqual(search_recipes([{"name": "tomate"}], vector, limit=0), [])

		get_connection.assert_not_called()

	def test_database_errors_are_reported_explicitly(self) -> None:
		with (
			patch(
				"smart_recipe_inventory_manager.storage.recipe_repository.get_connection",
				side_effect=psycopg.OperationalError("database unavailable"),
			),
			self.assertRaises(RecipeRepositoryError),
		):
			search_recipes([{"name": "tomate"}], [0.1] * 768)

	def test_search_rejects_embeddings_with_wrong_dimensions(self) -> None:
		with self.assertRaises(RecipeRepositoryError):
			search_recipes([{"name": "tomate"}], [0.1])

	def test_recipe_embedding_text_combines_recipe_fields(self) -> None:
		content = recipe_embedding_text({
			"title": "Soupe",
			"description": "Une soupe simple",
			"ingredients": [{"name": "tomate"}, {"name": "oignon"}],
			"steps": ["Couper.", "Cuire."],
		})

		self.assertEqual(
			content,
			"Soupe\nUne soupe simple\ntomate\noignon\nCouper.\nCuire.",
		)


class GradioFlowTests(unittest.IsolatedAsyncioTestCase):
	async def test_database_failure_is_user_visible(self) -> None:
		with patch(
			"smart_recipe_inventory_manager.ui_gradio.suggest_recipe",
			new=AsyncMock(
				side_effect=RecipeRepositoryError("PostgreSQL unavailable")
			),
		):
			rows, message = await propose_recipe("fridge.jpg", None)

		self.assertEqual(rows, [])
		self.assertIn("PostgreSQL", message)

	async def test_missing_image_returns_a_user_facing_error(self) -> None:
		with patch(
			"smart_recipe_inventory_manager.ui_gradio.suggest_recipe",
			new=AsyncMock(),
		) as suggest:
			rows, recipe = await propose_recipe(None, None)

		self.assertEqual(rows, [])
		self.assertIn("Aucune image", recipe)
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
			"metrics": {
				"vision_latency_ms": 125.5,
				"generation_latency_ms": 250.0,
				"generated_tokens": 42,
				"tokens_per_second": 21.0,
				"recipe_cosine_similarity": 0.876543210123,
			},
		}
		with patch(
			"smart_recipe_inventory_manager.ui_gradio.suggest_recipe",
			new=AsyncMock(return_value=expected),
		) as suggest, patch(
			"smart_recipe_inventory_manager.ui_gradio.save_result"
		) as save:
			rows, recipe = await propose_recipe("fridge.jpg", "rapide")

		save.assert_called_once_with(expected)

		self.assertEqual(rows, [["tomate", 2, None]])
		self.assertIn("## Soupe", recipe)
		self.assertIn("20 minutes", recipe)
		self.assertIn("- tomate", recipe)
		self.assertIn("1. Cuire.", recipe)
		self.assertIn("125.50 ms", recipe)
		self.assertIn("42", recipe)
		self.assertIn("0.876543210123", recipe)
		suggest.assert_awaited_once_with(
			image_path="fridge.jpg",
			preferences="rapide",
		)

	async def test_similar_recipes_are_listed_after_the_generated_recipe(self) -> None:
		result = {
			"ingredients": [{"name": "tomate", "quantity": 2, "maturity": None}],
			"recipe": {
				"title": "Soupe",
				"ingredients": ["tomate"],
				"steps": ["Cuire."],
				"cooking_time": "20 minutes",
			},
			"similar_recipes": [{
				"title": "Gratin de tomates",
				"coverage": 0.5,
				"cosine_similarity": 0.75,
				"missing_ingredients": [{"name": "fromage"}],
				"steps": ["Enfourner."],
			}],
		}
		with patch(
			"smart_recipe_inventory_manager.ui_gradio.suggest_recipe",
			new=AsyncMock(return_value=result),
		), patch("smart_recipe_inventory_manager.ui_gradio.save_result"):
			_, message = await propose_recipe("fridge.jpg", None)

		self.assertIn("Autres recettes proches", message)
		self.assertIn("### Gratin de tomates", message)
		self.assertIn("50%", message)
		self.assertIn("fromage", message)
		self.assertIn("0.75", message)

	def test_save_result_writes_json_with_decimal_values(self) -> None:
		from decimal import Decimal
		from tempfile import TemporaryDirectory

		with TemporaryDirectory() as directory, patch(
			"smart_recipe_inventory_manager.ui_gradio.settings.output_dir",
			directory,
		):
			path = save_result({"coverage": Decimal("0.667"), "titre": "Purée"})
			saved = json.loads(path.read_text(encoding="utf-8"))
			self.assertEqual(path.parent, Path(directory))

		self.assertEqual(saved, {"coverage": 0.667, "titre": "Purée"})

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
				self.assertIn(expected_message, recipe)


class LevelOneContractTests(unittest.IsolatedAsyncioTestCase):
	async def test_suggest_recipe_uses_database_candidates(self) -> None:
		ingredients = [{"name": "tomate", "quantity": 2, "maturity": None}]
		candidates = [{
			"title": "Soupe de tomates",
			"coverage": 1.0,
			"cosine_similarity": 0.876543210123,
		}]
		llm = StubLLM({
			"title": "Soupe",
			"ingredients": ["tomate"],
			"steps": ["Cuire."],
			"cooking_time": "20 minutes",
		})
		embedding = StubEmbedding([[0.1] * 768])
		with patch(
			"smart_recipe_inventory_manager.service.core.search_recipes",
			return_value=candidates,
		) as search:
			result = await suggest_recipe(
				image_path="unused.jpg",
				vlm=StubDetectionVLM(ingredients),
				llm=llm,
				embedding_client=embedding,
			)

		search.assert_called_once_with(ingredients, [0.1] * 768)
		self.assertEqual(result["recipe"]["title"], "Soupe")
		self.assertIn("Soupe de tomates", llm.prompt)
		self.assertEqual(
			result["metrics"]["recipe_cosine_similarity"],
			0.876543210123,
		)

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
		), self.assertRaises(OllamaResponseError):
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

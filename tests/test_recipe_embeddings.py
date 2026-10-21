import unittest
from collections.abc import Callable
from unittest.mock import AsyncMock, MagicMock, patch

from scripts import index_recipe_embeddings
from smart_recipe_inventory_manager.ollama_client.base import OllamaResponseError
from smart_recipe_inventory_manager.ollama_client.embedding import OllamaEmbedding
from smart_recipe_inventory_manager.storage.recipe_repository import (
	RecipeRepositoryError,
	upsert_recipe_embeddings,
)


class OllamaEmbeddingTests(unittest.IsolatedAsyncioTestCase):
	async def test_embed_validates_and_normalizes_vectors(self) -> None:
		adapter = OllamaEmbedding()
		adapter._post = AsyncMock(return_value={"embeddings": [[1, 0.5]]})

		result = await adapter.embed("tomate")

		self.assertEqual(result, [[1.0, 0.5]])

	async def test_embed_rejects_wrong_vector_count_or_non_finite_values(self) -> None:
		for response in (
			{"embeddings": []},
			{"embeddings": [[float("nan")]]},
		):
			with self.subTest(response=response):
				adapter = OllamaEmbedding()
				adapter._post = AsyncMock(return_value=response)
				with self.assertRaises(OllamaResponseError):
					await adapter.embed("tomate")


class RecipeEmbeddingIndexerTests(unittest.IsolatedAsyncioTestCase):
	async def test_indexer_embeds_recipe_content_and_persists_vectors(self) -> None:
		recipe = {
			"id": 12,
			"title": "Soupe tomate",
			"description": None,
			"ingredients": [{"name": "tomate"}],
			"steps": ["Cuire."],
		}
		vector = [0.1] * 768
		adapter = MagicMock()
		adapter.embed = AsyncMock(return_value=[vector])

		async def run_in_thread(
			function: Callable[..., object],
			*args: object,
		) -> object:
			return function(*args)

		with (
			patch.object(
				index_recipe_embeddings.asyncio,
				"to_thread",
				new=AsyncMock(side_effect=run_in_thread),
			),
			patch.object(
				index_recipe_embeddings,
				"list_recipes_for_embedding",
				return_value=[recipe],
			),
			patch.object(
				index_recipe_embeddings,
				"OllamaEmbedding",
				return_value=adapter,
			),
			patch.object(
				index_recipe_embeddings,
				"upsert_recipe_embeddings",
				return_value=1,
			) as upsert,
		):
			count = await index_recipe_embeddings.index_recipes()

		self.assertEqual(count, 1)
		adapter.embed.assert_awaited_once_with(
			["Soupe tomate\ntomate\nCuire."]
		)
		upsert.assert_called_once_with([
			(12, "Soupe tomate\ntomate\nCuire.", vector),
		])


class RecipeEmbeddingRepositoryTests(unittest.TestCase):
	def test_upsert_sends_pgvector_values(self) -> None:
		connection = MagicMock()
		cursor = MagicMock()
		connection.__enter__.return_value = connection
		connection.cursor.return_value.__enter__.return_value = cursor

		with patch(
			"smart_recipe_inventory_manager.storage.recipe_repository.get_connection",
			return_value=connection,
		):
			count = upsert_recipe_embeddings([
				(12, "Soupe tomate", [0.0] * 768),
			])

		self.assertEqual(count, 1)
		query, parameters = cursor.executemany.call_args.args
		self.assertIn("%s::vector", query)
		self.assertEqual(parameters[0][0:2], (12, "Soupe tomate"))
		self.assertEqual(parameters[0][2], "[" + ",".join(["0"] * 768) + "]")

	def test_upsert_rejects_invalid_embedding_dimensions(self) -> None:
		with self.assertRaises(RecipeRepositoryError):
			upsert_recipe_embeddings([(12, "Soupe tomate", [0.0])])

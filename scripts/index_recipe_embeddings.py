import asyncio

from smart_recipe_inventory_manager.ollama_client.embedding import OllamaEmbedding
from smart_recipe_inventory_manager.storage.recipe_repository import (
	list_recipes_for_embedding,
	recipe_embedding_text,
	upsert_recipe_embeddings,
)

BATCH_SIZE = 32


async def index_recipes() -> int:
	recipes = await asyncio.to_thread(list_recipes_for_embedding)
	if not recipes:
		print("Aucune recette à indexer.")
		return 0

	adapter = OllamaEmbedding()
	records: list[tuple[int, str, list[float]]] = []
	for offset in range(0, len(recipes), BATCH_SIZE):
		batch = recipes[offset : offset + BATCH_SIZE]
		contents = [recipe_embedding_text(recipe) for recipe in batch]
		embeddings = await adapter.embed(contents)
		if len(embeddings) != len(batch):
			raise ValueError(
				"Ollama n'a pas renvoyé un embedding par recette."
			)
		records.extend(
			(recipe["id"], content, embedding)
			for recipe, content, embedding in zip(
				batch,
				contents,
				embeddings,
				strict=True,
			)
		)

	indexed_count = await asyncio.to_thread(upsert_recipe_embeddings, records)
	print(f"{indexed_count} recette(s) indexée(s).")
	return indexed_count


if __name__ == "__main__":
	asyncio.run(index_recipes())

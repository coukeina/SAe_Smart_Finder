import math
from collections.abc import Iterable
from typing import Any

import psycopg
from psycopg.rows import dict_row

from .base import get_connection

EMBEDDING_DIMENSIONS = 768
VECTOR_CANDIDATE_LIMIT = 100


class RecipeRepositoryError(RuntimeError):
	"""Raised when recipe data cannot be retrieved from PostgreSQL."""


def _normalize_name(name: str) -> str:
	return " ".join(name.strip().casefold().split())


def _search_names(ingredients: Iterable[dict[str, Any]]) -> list[str]:
	names: set[str] = set()
	for ingredient in ingredients:
		name = ingredient.get("name")
		if not isinstance(name, str) or not name.strip():
			continue

		normalized = _normalize_name(name)
		names.add(normalized)
		if normalized.endswith(("s", "x")):
			names.add(normalized[:-1])
		else:
			names.update((normalized + "s", normalized + "x"))

	return sorted(names)


def recipe_embedding_text(recipe: dict[str, Any]) -> str:
	parts = [
		str(recipe.get("title") or "").strip(),
		str(recipe.get("description") or "").strip(),
	]
	ingredients = recipe.get("ingredients", [])
	if isinstance(ingredients, list):
		parts.extend(
			str(item.get("name") or "").strip()
			if isinstance(item, dict)
			else str(item).strip()
			for item in ingredients
		)

	steps = recipe.get("steps", [])
	if isinstance(steps, list):
		parts.extend(str(step).strip() for step in steps)
	elif isinstance(steps, str):
		parts.append(steps.strip())

	content = "\n".join(part for part in parts if part)
	if not content:
		raise RecipeRepositoryError(
			"Impossible de créer un embedding pour une recette sans contenu."
		)
	return content


def _serialize_embedding(embedding: list[float]) -> str:
	if len(embedding) != EMBEDDING_DIMENSIONS or any(
		not isinstance(value, (int, float))
		or isinstance(value, bool)
		or not math.isfinite(value)
		for value in embedding
	):
		raise RecipeRepositoryError(
			f"Un embedding doit contenir {EMBEDDING_DIMENSIONS} valeurs finies."
		)
	return "[" + ",".join(format(float(value), ".17g") for value in embedding) + "]"


def list_recipes_for_embedding() -> list[dict[str, Any]]:
	query = """
		SELECT
			r.id,
			r.title,
			r.description,
			r.steps,
			COALESCE(
				JSONB_AGG(
					JSONB_BUILD_OBJECT('name', i.name) ORDER BY i.name
				) FILTER (WHERE i.id IS NOT NULL),
				'[]'::jsonb
			) AS ingredients
		FROM recipes AS r
		LEFT JOIN recipe_ingredients AS ri ON ri.recipe_id = r.id
		LEFT JOIN ingredients AS i ON i.id = ri.ingredient_id
		GROUP BY r.id
		ORDER BY r.id
	"""
	try:
		with get_connection() as connection, connection.cursor(
			row_factory=dict_row
		) as cursor:
			cursor.execute(query)
			return [dict(row) for row in cursor.fetchall()]
	except psycopg.Error as exc:
		raise RecipeRepositoryError(
			"Impossible de charger les recettes pour leur indexation."
		) from exc


def upsert_recipe_embeddings(
	records: list[tuple[int, str, list[float]]],
) -> int:
	if not records:
		return 0

	parameters = [
		(recipe_id, content, _serialize_embedding(embedding))
		for recipe_id, content, embedding in records
	]
	query = """
		INSERT INTO recipe_embeddings (recipe_id, content, embedding)
		VALUES (%s, %s, %s::vector)
		ON CONFLICT (recipe_id) DO UPDATE SET
			content = EXCLUDED.content,
			embedding = EXCLUDED.embedding,
			created_at = NOW()
	"""
	try:
		with get_connection() as connection, connection.cursor() as cursor:
			cursor.executemany(query, parameters)
	except psycopg.Error as exc:
		raise RecipeRepositoryError(
			"Impossible d'enregistrer les embeddings des recettes."
		) from exc
	return len(records)


def search_recipes(
	ingredients: list[dict[str, Any]],
	embedding: list[float],
	limit: int = 5,
) -> list[dict[str, Any]]:
	names = _search_names(ingredients)
	if not names or limit <= 0:
		return []
	serialized_embedding = _serialize_embedding(embedding)

	query = """
		WITH requested_names AS (
			SELECT %s::text[] AS names
		),
		query_embedding AS (
			SELECT %s::vector AS embedding
		),
		nearest_recipes AS (
			SELECT
				re.recipe_id,
				1 - (re.embedding <=> query_embedding.embedding)
					AS cosine_similarity
			FROM recipe_embeddings AS re
			CROSS JOIN query_embedding
			WHERE re.embedding IS NOT NULL
			ORDER BY re.embedding <=> query_embedding.embedding
			LIMIT %s
		)
		SELECT
			r.id,
			r.title,
			r.description,
			r.steps,
			COUNT(DISTINCT ri.ingredient_id) FILTER (
				WHERE i.normalized_name = ANY(requested_names.names)
			) AS matched_ingredient_count,
			COUNT(DISTINCT ri.ingredient_id) AS ingredient_count,
			ROUND(
				COUNT(DISTINCT ri.ingredient_id) FILTER (
					WHERE i.normalized_name = ANY(requested_names.names)
				)::numeric
				/ NULLIF(COUNT(DISTINCT ri.ingredient_id), 0),
				3
			) AS coverage,
			nearest_recipes.cosine_similarity,
			COALESCE(
				JSONB_AGG(
					JSONB_BUILD_OBJECT(
						'name', i.name,
						'quantity', ri.quantity,
						'unit', ri.unit
					) ORDER BY i.name
				) FILTER (
					WHERE i.normalized_name = ANY(requested_names.names)
				),
				'[]'::jsonb
			) AS available_ingredients,
			COALESCE(
				JSONB_AGG(
					JSONB_BUILD_OBJECT(
						'name', i.name,
						'quantity', ri.quantity,
						'unit', ri.unit
					) ORDER BY i.name
				) FILTER (
					WHERE NOT i.normalized_name = ANY(requested_names.names)
				),
				'[]'::jsonb
			) AS missing_ingredients
		FROM recipes AS r
		JOIN nearest_recipes ON nearest_recipes.recipe_id = r.id
		JOIN recipe_ingredients AS ri ON ri.recipe_id = r.id
		JOIN ingredients AS i ON i.id = ri.ingredient_id
		CROSS JOIN requested_names
		GROUP BY r.id, requested_names.names, nearest_recipes.cosine_similarity
		HAVING COUNT(DISTINCT ri.ingredient_id) FILTER (
			WHERE i.normalized_name = ANY(requested_names.names)
		) > 0
		ORDER BY coverage DESC, matched_ingredient_count DESC,
			nearest_recipes.cosine_similarity DESC, ingredient_count ASC, r.title ASC
		LIMIT %s
	"""

	try:
		with get_connection() as connection, connection.cursor(
			row_factory=dict_row
		) as cursor:
			cursor.execute(
				query,
				(names, serialized_embedding, VECTOR_CANDIDATE_LIMIT, limit),
			)
			return [dict(row) for row in cursor.fetchall()]
	except psycopg.Error as exc:
		raise RecipeRepositoryError(
			"Impossible de rechercher les recettes dans PostgreSQL."
		) from exc

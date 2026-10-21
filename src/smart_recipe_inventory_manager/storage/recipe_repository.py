from collections.abc import Iterable
from typing import Any

import psycopg
from psycopg.rows import dict_row

from .base import get_connection


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


def search_recipes(
	ingredients: list[dict[str, Any]],
	limit: int = 5,
) -> list[dict[str, Any]]:
	names = _search_names(ingredients)
	if not names or limit <= 0:
		return []

	query = """
		WITH requested_names AS (
			SELECT %s::text[] AS names
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
		JOIN recipe_ingredients AS ri ON ri.recipe_id = r.id
		JOIN ingredients AS i ON i.id = ri.ingredient_id
		CROSS JOIN requested_names
		GROUP BY r.id, requested_names.names
		HAVING COUNT(DISTINCT ri.ingredient_id) FILTER (
			WHERE i.normalized_name = ANY(requested_names.names)
		) > 0
		ORDER BY coverage DESC, matched_ingredient_count DESC,
			ingredient_count ASC, r.title ASC
		LIMIT %s
	"""

	try:
		with get_connection() as connection, connection.cursor(
			row_factory=dict_row
		) as cursor:
			cursor.execute(query, (names, limit))
			return [dict(row) for row in cursor.fetchall()]
	except psycopg.Error as exc:
		raise RecipeRepositoryError(
			"Impossible de rechercher les recettes dans PostgreSQL."
		) from exc

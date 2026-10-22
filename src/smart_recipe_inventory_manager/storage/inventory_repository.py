from collections.abc import Sequence
from typing import Any

import psycopg
from psycopg.rows import dict_row

from .base import get_connection


class InventoryRepositoryError(RuntimeError):
	"""Raised when inventory data cannot be persisted or retrieved."""


def _normalize_name(name: str) -> str:
	return " ".join(name.strip().casefold().split())


def save_inventory(ingredients: Sequence[dict[str, Any]]) -> int:
	if not ingredients:
		return 0

	upsert_ingredient_query = """
		INSERT INTO ingredients (name, normalized_name)
		VALUES (%s, %s)
		ON CONFLICT (normalized_name) DO UPDATE SET name = EXCLUDED.name
		RETURNING id
	"""
	upsert_inventory_query = """
		INSERT INTO inventory (
			ingredient_id, quantity, unit, maturity, confidence, needs_confirmation
		)
		VALUES (%s, %s, %s, %s, %s, FALSE)
		ON CONFLICT (ingredient_id) DO UPDATE SET
			quantity = EXCLUDED.quantity,
			unit = EXCLUDED.unit,
			maturity = EXCLUDED.maturity,
			confidence = EXCLUDED.confidence,
			needs_confirmation = FALSE,
			created_at = NOW()
	"""

	try:
		with get_connection() as connection, connection.cursor() as cursor:
			for ingredient in ingredients:
				name = ingredient["name"].strip()
				cursor.execute(
					upsert_ingredient_query,
					(name, _normalize_name(name)),
				)
				ingredient_id = cursor.fetchone()[0]
				cursor.execute(
					upsert_inventory_query,
					(
						ingredient_id,
						ingredient.get("quantity"),
						ingredient.get("unit"),
						ingredient.get("maturity"),
						ingredient.get("confidence"),
					),
				)
	except psycopg.Error as exc:
		raise InventoryRepositoryError(
			"Impossible d'enregistrer l'inventaire dans PostgreSQL."
		) from exc

	return len(ingredients)


def list_inventory() -> list[dict[str, Any]]:
	query = """
		SELECT
			i.name,
			inv.quantity,
			inv.unit,
			inv.maturity,
			inv.confidence,
			inv.needs_confirmation,
			inv.created_at
		FROM inventory AS inv
		JOIN ingredients AS i ON i.id = inv.ingredient_id
		ORDER BY i.normalized_name
	"""

	try:
		with get_connection() as connection, connection.cursor(
			row_factory=dict_row
		) as cursor:
			cursor.execute(query)
			return [dict(row) for row in cursor.fetchall()]
	except psycopg.Error as exc:
		raise InventoryRepositoryError(
			"Impossible de lire l'inventaire dans PostgreSQL."
		) from exc

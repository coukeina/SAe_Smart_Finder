from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

import psycopg


def normalize_name(name: str) -> str:
	"""Return a stable lookup key for an ingredient label."""
	return " ".join(name.strip().lower().split())


def ingredient_label(raw_ingredient: str | dict[str, Any]) -> str:
	if isinstance(raw_ingredient, dict):
		return str(raw_ingredient["name"])
	return str(raw_ingredient)


def split_ingredient(raw_ingredient: str | dict[str, Any]) -> tuple[str, float | None, str | None]:
	if isinstance(raw_ingredient, dict):
		name = ingredient_label(raw_ingredient)
		quantity = raw_ingredient.get("quantity")
		unit = raw_ingredient.get("unit")
		return name, quantity, unit

	match = re.match(r"^\s*(\d+(?:[.,]\d+)?)\s*([^a-zA-ZÀ-ÿ]*)\s*(.*)$", raw_ingredient)
	if not match:
		return raw_ingredient.strip(), None, None

	quantity_text, _, name = match.groups()
	quantity = float(quantity_text.replace(",", "."))
	return name.strip() or raw_ingredient.strip(), quantity, None


def database_url() -> str:
	return (
		f"host={os.getenv('DB_HOST', 'localhost')} "
		f"port={os.getenv('DB_PORT', '5432')} "
		f"dbname={os.getenv('DB_NAME', 'app_db')} "
		f"user={os.getenv('DB_USER', 'app_user')} "
		f"password={os.getenv('DB_PASSWORD', 'app_secret')}"
	)


def import_recipes(file_path: str = "data/recipes.json") -> int:
	recipes = json.loads(Path(file_path).read_text(encoding="utf-8"))

	with psycopg.connect(database_url()) as connection:
		with connection.cursor() as cursor:
			for recipe_id, recipe in enumerate(recipes, start=1):
				cursor.execute(
					"""
					INSERT INTO recipes (id, title, description, steps, source)
					VALUES (%s, %s, %s, %s::jsonb, %s)
					ON CONFLICT (id) DO UPDATE SET
						title = EXCLUDED.title,
						description = EXCLUDED.description,
						steps = EXCLUDED.steps,
						source = EXCLUDED.source
					""",
					(
						recipe_id,
						recipe["nom"],
						None,
						json.dumps(recipe.get("etapes_preparation", []), ensure_ascii=False),
						recipe.get("uuid"),
					),
				)

				cursor.execute(
					"DELETE FROM recipe_ingredients WHERE recipe_id = %s",
					(recipe_id,),
				)

				for raw_ingredient in recipe.get("ingredients", []):
					name, quantity, unit = split_ingredient(raw_ingredient)
					normalized_name = normalize_name(name)

					cursor.execute(
						"""
						INSERT INTO ingredients (id, name, normalized_name)
						VALUES (
							(SELECT COALESCE(MAX(id), 0) + 1 FROM ingredients),
							%s,
							%s
						)
						ON CONFLICT (normalized_name) DO UPDATE SET name = EXCLUDED.name
						RETURNING id
						""",
						(name, normalized_name),
					)
					ingredient_id = cursor.fetchone()[0]

					cursor.execute(
						"""
						INSERT INTO recipe_ingredients
							(recipe_id, ingredient_id, quantity, unit)
						VALUES (%s, %s, %s, %s)
						ON CONFLICT (recipe_id, ingredient_id) DO UPDATE SET
							quantity = EXCLUDED.quantity,
							unit = EXCLUDED.unit
						""",
						(recipe_id, ingredient_id, quantity, unit),
					)

	return len(recipes)


if __name__ == "__main__":
	imported_count = import_recipes()
	print(f"{imported_count} recettes importees.")

import math
from typing import Any

from pydantic import ValidationError

from ..storage.inventory_repository import list_inventory, save_inventory
from .models import DetectedIngredient


class InventoryInputError(ValueError):
	"""Raised when the edited ingredient rows cannot be confirmed."""


def _is_blank(value: Any) -> bool:
	return (
		value is None
		or (isinstance(value, str) and not value.strip())
		or (isinstance(value, float) and math.isnan(value))
	)


def _parse_ingredient_rows(
	rows: list[list[Any]] | None,
) -> list[dict[str, Any]]:
	if rows is None:
		raise InventoryInputError("Aucun ingrédient à confirmer.")

	ingredients: list[dict[str, Any]] = []
	seen_names: set[str] = set()
	for index, row in enumerate(rows, start=1):
		if not isinstance(row, (list, tuple)):
			raise InventoryInputError(
				f"La ligne {index} de l'inventaire est invalide."
			)
		if all(_is_blank(value) for value in row):
			continue
		if len(row) < 3:
			raise InventoryInputError(
				f"La ligne {index} doit contenir un nom, une quantité et une maturité."
			)

		quantity = row[1]
		maturity = row[2]
		payload = {
			"name": row[0],
			"quantity": None if _is_blank(quantity) else quantity,
			"maturity": None if _is_blank(maturity) else maturity,
		}
		try:
			ingredient = DetectedIngredient.model_validate(payload)
		except ValidationError as exc:
			raise InventoryInputError(
				f"Les données de la ligne {index} sont invalides."
			) from exc

		normalized_name = " ".join(ingredient.name.casefold().split())
		if normalized_name in seen_names:
			raise InventoryInputError(
				f"L'ingrédient « {ingredient.name} » apparaît plusieurs fois."
			)
		seen_names.add(normalized_name)
		ingredients.append(ingredient.model_dump(mode="json"))

	if not ingredients:
		raise InventoryInputError(
			"Ajoutez au moins un ingrédient avant de confirmer l'inventaire."
		)
	return ingredients


def save_confirmed_inventory(rows: list[list[Any]] | None) -> list[dict[str, Any]]:
	ingredients = _parse_ingredient_rows(rows)
	save_inventory(ingredients)
	return list_inventory()


def get_inventory() -> list[dict[str, Any]]:
	return list_inventory()

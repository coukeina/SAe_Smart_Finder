import unittest
from typing import Any
from unittest.mock import MagicMock, patch

import psycopg

from smart_recipe_inventory_manager.service.inventory import (
	InventoryInputError,
	save_confirmed_inventory,
)
from smart_recipe_inventory_manager.storage.inventory_repository import (
	InventoryRepositoryError,
	list_inventory,
	save_inventory,
)
from smart_recipe_inventory_manager.ui_gradio import (
	build_demo,
	confirm_inventory,
)


class InventoryServiceTests(unittest.TestCase):
	def test_save_requires_at_least_one_valid_ingredient(self) -> None:
		for rows in (None, [], [["", "", ""]]):
			with self.subTest(rows=rows), self.assertRaises(InventoryInputError):
				save_confirmed_inventory(rows)

	def test_save_validates_rows_before_persisting(self) -> None:
		inventory = [{"name": "Tomate", "quantity": 2.0, "needs_confirmation": False}]
		with (
			patch(
				"smart_recipe_inventory_manager.service.inventory.save_inventory"
			) as save,
			patch(
				"smart_recipe_inventory_manager.service.inventory.list_inventory",
				return_value=inventory,
			),
		):
			result = save_confirmed_inventory([[" Tomate ", "2", "mûre"]])

		self.assertEqual(result, inventory)
		save.assert_called_once_with([{
			"name": "Tomate",
			"quantity": 2.0,
			"maturity": "mûre",
		}])

	def test_blank_dataframe_cells_are_saved_as_null(self) -> None:
		with (
			patch(
				"smart_recipe_inventory_manager.service.inventory.save_inventory"
			) as save,
			patch(
				"smart_recipe_inventory_manager.service.inventory.list_inventory",
				return_value=[],
			),
		):
			save_confirmed_inventory([["Tomate", float("nan"), float("nan")]])

		save.assert_called_once_with([{
			"name": "Tomate",
			"quantity": None,
			"maturity": None,
		}])

	def test_save_rejects_negative_quantities_and_duplicate_names(self) -> None:
		with patch(
			"smart_recipe_inventory_manager.service.inventory.save_inventory"
		) as save:
			for rows in (
				[["Tomate", "-1", ""]],
				[["Tomate", 1, ""], [" tomate ", 2, ""]],
			):
				with self.subTest(rows=rows), self.assertRaises(InventoryInputError):
					save_confirmed_inventory(rows)

		save.assert_not_called()


class InventoryRepositoryTests(unittest.TestCase):
	def test_save_upserts_ingredients_and_inventory(self) -> None:
		connection = MagicMock()
		cursor = MagicMock()
		connection.__enter__.return_value = connection
		connection.cursor.return_value.__enter__.return_value = cursor
		cursor.fetchone.side_effect = [(7,), (8,)]

		with patch(
			"smart_recipe_inventory_manager.storage.inventory_repository.get_connection",
			return_value=connection,
		):
			count = save_inventory([
				{"name": "Tomate", "quantity": 2.0, "maturity": "mûre"},
				{"name": "Oignon", "quantity": 1.0, "maturity": None},
			])

		self.assertEqual(count, 2)
		self.assertEqual(cursor.execute.call_count, 4)
		self.assertEqual(
			cursor.execute.call_args_list[0].args[1],
			("Tomate", "tomate"),
		)
		self.assertEqual(
			cursor.execute.call_args_list[1].args[1],
			(7, 2.0, None, "mûre", None),
		)

	def test_list_inventory_returns_records(self) -> None:
		expected: list[dict[str, Any]] = [{
			"name": "Tomate",
			"quantity": 2.0,
			"unit": None,
			"maturity": "mûre",
			"confidence": None,
			"needs_confirmation": False,
		}]
		connection = MagicMock()
		cursor = MagicMock()
		connection.__enter__.return_value = connection
		connection.cursor.return_value.__enter__.return_value = cursor
		cursor.fetchall.return_value = expected

		with patch(
			"smart_recipe_inventory_manager.storage.inventory_repository.get_connection",
			return_value=connection,
		):
			result = list_inventory()

		self.assertEqual(result, expected)
		self.assertIn("ORDER BY i.normalized_name", cursor.execute.call_args.args[0])

	def test_repository_errors_are_explicit(self) -> None:
		with (
			patch(
				"smart_recipe_inventory_manager.storage.inventory_repository.get_connection",
				side_effect=psycopg.OperationalError("database unavailable"),
			),
			self.assertRaises(InventoryRepositoryError),
		):
			save_inventory([{"name": "Tomate"}])


class InventoryUiTests(unittest.TestCase):
	def test_confirm_inventory_returns_status_and_inventory_rows(self) -> None:
		inventory = [{
			"name": "Tomate",
			"quantity": 2.0,
			"unit": None,
			"maturity": "mûre",
			"confidence": None,
			"needs_confirmation": False,
		}]
		with patch(
			"smart_recipe_inventory_manager.ui_gradio.save_confirmed_inventory",
			return_value=inventory,
		):
			rows, status = confirm_inventory([["Tomate", 2, "mûre"]])

		self.assertEqual(rows, [["Tomate", 2.0, None, "mûre", None, True]])
		self.assertIn("1 ingrédient", status)

	def test_demo_builds_with_editable_confirmation_table(self) -> None:
		demo = build_demo()

		self.assertIsNotNone(demo)

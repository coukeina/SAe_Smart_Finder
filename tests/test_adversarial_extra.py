import unittest
from unittest.mock import patch

import psycopg

from smart_recipe_inventory_manager.config import Settings
from smart_recipe_inventory_manager.service.inventory import (
    InventoryInputError,
    save_confirmed_inventory,
)
from smart_recipe_inventory_manager.storage.recipe_repository import (
    RecipeRepositoryError,
    search_recipes,
)


class AdversarialAndConfigTests(unittest.TestCase):
    def test_settings_default_values(self):
        settings = Settings()
        self.assertIsNotNone(settings.ollama_host)
        self.assertIsNotNone(settings.db_name)

    def test_adversarial_empty_or_whitespace_ingredients(self):
        for bad_input in (None, [], [["   ", "", ""]], [["", -5, ""]]):
            with (
                self.subTest(bad_input=bad_input),
                self.assertRaises(InventoryInputError),
            ):
                save_confirmed_inventory(bad_input)

    def test_adversarial_negative_quantity_rejection(self):
        with self.assertRaises(InventoryInputError):
            save_confirmed_inventory([["Pomme", -10.5, "kg"]])

    def test_adversarial_duplicate_ingredients_rejection(self):
        with self.assertRaises(InventoryInputError):
            save_confirmed_inventory([["Lait", 1.0, "l"], [" lait ", 2.0, "l"]])

    def test_repository_connection_error_handling(self):
        with (
            patch(
                "smart_recipe_inventory_manager.storage.recipe_repository.get_connection",
                side_effect=psycopg.OperationalError("Connexion refusée"),
            ),
            self.assertRaises(RecipeRepositoryError),
        ):
            search_recipes([{"name": "Tomate"}], embedding=[0.1] * 768)

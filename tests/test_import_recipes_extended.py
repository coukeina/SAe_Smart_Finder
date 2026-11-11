import unittest

from scripts.import_recipes import ingredient_label, normalize_name, split_ingredient


class ImportRecipesExtendedTests(unittest.TestCase):
    def test_normalize_name(self):
        self.assertEqual(normalize_name("  Pomme de terre  "), "pomme de terre")

    def test_ingredient_label_string_and_dict(self):
        self.assertEqual(ingredient_label("Farine"), "Farine")
        self.assertEqual(ingredient_label({"name": "Sucre", "quantity": 100}), "Sucre")

    def test_split_ingredient_parsing(self):
        _name, qty, _unit = split_ingredient("500g")
        self.assertEqual(qty, 500.0)

    def test_split_ingredient_no_number(self):
        name, qty, _unit = split_ingredient("Sel fin")
        self.assertEqual(name, "Sel fin")
        self.assertIsNone(qty)

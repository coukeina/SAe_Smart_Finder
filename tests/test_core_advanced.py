import unittest

from smart_recipe_inventory_manager.service.core import (
    _is_detected_ingredient,
    _normalize_ingredient_name,
)


class CoreAdvancedTests(unittest.TestCase):
    def test_normalize_ingredient_name_variants(self):
        self.assertEqual(_normalize_ingredient_name("  Tomates  "), "tomates")
        self.assertEqual(_normalize_ingredient_name("Carottes"), "carottes")
        self.assertEqual(_normalize_ingredient_name("  "), "")

    def test_is_detected_ingredient_matching(self):
        detected_names = {"tomate", "oignon"}
        self.assertTrue(_is_detected_ingredient("tomates", detected_names))
        self.assertTrue(_is_detected_ingredient("Tomate", detected_names))
        self.assertFalse(_is_detected_ingredient("safran", detected_names))

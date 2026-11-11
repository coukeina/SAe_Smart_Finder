import unittest

from smart_recipe_inventory_manager.ui_gradio import (
    _clean_number,
    _format_metrics,
    propose_recipes,
    show_ingredients,
)


class UiCallbacksExtendedTests(unittest.IsolatedAsyncioTestCase):
    def test_clean_number_edge_cases(self):
        self.assertIsNone(_clean_number(True))
        self.assertIsNone(_clean_number("123"))
        self.assertIsNone(_clean_number(float("nan")))
        self.assertEqual(_clean_number(42.5), 42.5)

    def test_format_metrics_with_missing_keys(self):
        metrics = {"vision_latency_ms": 150.0}
        formatted = _format_metrics(metrics)
        self.assertIn("Latence VLM", formatted)
        self.assertIn("non disponible", formatted)

    async def test_show_ingredients_no_image(self):
        rows, msg = await show_ingredients(None)
        self.assertEqual(rows, [])
        self.assertIn("Aucune image", msg)

    async def test_propose_recipes_no_ingredients(self):
        msg = await propose_recipes([], "vegan")
        self.assertIn("Affichez d'abord les ingrédients", msg)

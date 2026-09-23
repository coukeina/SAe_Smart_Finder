from annotationlib import *
from ..ollama_client.vlm import OllamaVLM
from typing import Any

def search_recipes(ingredients: list[dict], limit: int = 5) -> list[dict]:
    return []

DETECTION_PROMPT = """
Analyse cette photo de frigo, placard ou aliments sur une table.
Liste uniquement les aliments clairement visibles.
N'invente aucun aliment.
Estime une quantité uniquement si elle est visible.
Indique la maturité seulement lorsqu'elle est visible.

Réponds strictement avec ce JSON :
{
  "ingredients": [
    {
      "name": "string",
      "quantity": "number ou null",
      "maturity": "string ou null"
    }
  ]
}
"""


async def detect_ingredients(image_path: str) -> dict[str, Any]:
    result = await OllamaVLM().detect_ingredients(
        image_path=image_path,
        prompt=DETECTION_PROMPT,
    )

    ingredients = result.get("ingredients")
    if not isinstance(ingredients, list):
        raise ValueError("La réponse VLM doit contenir une liste d'ingrédients.")

    return {"ingrédients": ingredients}
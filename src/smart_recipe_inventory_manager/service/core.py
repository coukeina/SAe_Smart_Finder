<<<<<<< HEAD
from ..ollama_client.vlm import OllamaVLM
=======
>>>>>>> feat/ollama-recipe-generation
from typing import Any
from ..ollama_client.llm import OllamaLLM
from ..ollama_client.vlm import OllamaVLM

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

async def generate_recipe(
    ingredients: list[dict[str, Any]],
    preferences: str = "",
    recipes: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    prompt = f"""
Tu es un assistant spécialisé dans les recettes anti-gaspillage.

Ingrédients disponibles :
{ingredients}

Recettes existantes compatibles :
{recipes or []}

Préférences de l'utilisateur :
{preferences or "Aucune préférence particulière"}

Propose une recette réalisable avec les ingrédients disponibles.
Réponds uniquement avec ce JSON :
{{
  "title": "nom de la recette",
  "ingredients": ["ingrédient 1"],
  "steps": ["étape 1"],
  "cooking_time": "30 minutes"
}}
"""

    return await OllamaLLM().generate_json(
        prompt,
        max_tokens=700,
        temperature=0.4,
    )

async def suggest_recipe(
    image_path: str,
    preferences: str = "",
) -> dict[str, Any]:
    detection = await detect_ingredients(image_path)
    ingredients = detection["ingredients"]

    recipes = search_recipes(ingredients)

    recipe = await generate_recipe(
        ingredients=ingredients,
        preferences=preferences,
        recipes=recipes,
    )

    return {
        "ingredients": ingredients,
        "recipe": recipe,
    }
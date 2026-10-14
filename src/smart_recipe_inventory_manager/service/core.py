from typing import Any

from pydantic import ValidationError

from ..ollama_client.base import OllamaResponseError
from ..ollama_client.llm import OllamaLLM
from ..ollama_client.vlm import OllamaVLM
from .models import GeneratedRecipe, IngredientDetection


def search_recipes(
    ingredients: list[dict[str, Any]],
    limit: int = 5,
) -> list[dict[str, Any]]:
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


async def detect_ingredients(
    image_path: str,
    vlm: OllamaVLM | None = None,
) -> dict[str, Any]:
    adapter = vlm if vlm is not None else OllamaVLM()
    result = await adapter.detect_ingredients(
        image_path=image_path,
        prompt=DETECTION_PROMPT,
        schema=IngredientDetection.model_json_schema(),
    )

    try:
        detection = IngredientDetection.model_validate(result)
    except ValidationError as exc:
        raise OllamaResponseError(
            "ollama vision response does not match the ingredient schema"
        ) from exc

    return detection.model_dump(mode="json")


async def generate_recipe(
    ingredients: list[dict[str, Any]],
    preferences: str = "",
    recipes: list[dict[str, Any]] | None = None,
    llm: OllamaLLM | None = None,
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

    try:
        adapter = llm if llm is not None else OllamaLLM()
        payload = await adapter.generate_json(
            prompt,
            schema=GeneratedRecipe.model_json_schema(),
            max_tokens=700,
            temperature=0.4,
        )
        return GeneratedRecipe.model_validate(payload).model_dump(mode="json")
    except ValidationError as exc:
        raise OllamaResponseError(
            "ollama recipe response does not match the expected schema"
        ) from exc


async def suggest_recipe(
    image_path: str,
    preferences: str = "",
    vlm: OllamaVLM | None = None,
    llm: OllamaLLM | None = None,
) -> dict[str, Any]:
    detection = await detect_ingredients(image_path, vlm=vlm)
    ingredients = detection["ingredients"]

    recipes = search_recipes(ingredients)

    recipe = await generate_recipe(
        ingredients=ingredients,
        preferences=preferences,
        recipes=recipes,
        llm=llm,
    )

    return {
        "ingredients": ingredients,
        "recipe": recipe,
    }
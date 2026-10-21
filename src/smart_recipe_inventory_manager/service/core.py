import re
import unicodedata
from typing import Any

from pydantic import ValidationError

from ..ollama_client.base import OllamaResponseError
from ..ollama_client.llm import OllamaLLM
from ..ollama_client.vlm import OllamaVLM
from ..storage.recipe_repository import search_recipes
from .models import GeneratedRecipe, IngredientDetection


class RecipeInputError(ValueError):
    """Raised when detected ingredients are not usable for recipe generation."""


def _normalize_ingredient_name(name: str) -> str:
    decomposed = unicodedata.normalize("NFKD", name.casefold())
    without_accents = "".join(
        character for character in decomposed
        if not unicodedata.combining(character)
    )
    without_ligatures = without_accents.replace("œ", "oe").replace("æ", "ae")
    return " ".join(re.findall(r"[a-z0-9]+", without_ligatures))


def _is_detected_ingredient(recipe_ingredient: str, detected_names: set[str]) -> bool:
    normalized = _normalize_ingredient_name(recipe_ingredient)
    return normalized in detected_names or any(
        normalized in {name + "s", name + "x"}
        or name in {normalized + "s", normalized + "x"}
        for name in detected_names
    )


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
      "name": "tomates",
      "quantity": 2,
      "maturity": null
    }
  ]
}
quantity doit être un nombre ou null ; maturity doit être une chaîne ou null.
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
    if not ingredients:
        raise RecipeInputError(
            "Aucun ingrédient utilisable n'a été fourni pour générer une recette."
        )

    prompt = f"""
Tu es un assistant spécialisé dans les recettes anti-gaspillage.

Ingrédients disponibles :
{ingredients}

Suggestions du référentiel de recettes (à adapter aux ingrédients disponibles) :
{recipes or []}

Préférences de l'utilisateur :
{preferences or "Aucune préférence particulière"}

Propose une recette réalisable avec les ingrédients disponibles.
N'ajoute aucun ingrédient qui ne figure pas dans la liste détectée.
N'inclus pas d'ingrédients de base (sel, poivre, huile, eau) s'ils ne sont pas détectés.
Réponds uniquement avec ce JSON :
{{
  "title": "nom de la recette",
  "ingredients": ["ingrédient 1"],
  "steps": ["étape 1"],
  "cooking_time": "30 minutes"
}}
"""

    adapter = llm if llm is not None else OllamaLLM()
    payload = await adapter.generate_json(
        prompt,
        schema=GeneratedRecipe.model_json_schema(),
        max_tokens=700,
        temperature=0.4,
    )
    try:
        recipe = GeneratedRecipe.model_validate(payload)
    except ValidationError as exc:
        raise OllamaResponseError(
            "ollama recipe response does not match the expected schema"
        ) from exc

    detected_names = {
        _normalize_ingredient_name(ingredient["name"])
        for ingredient in ingredients
    }
    unknown_ingredients = [
        ingredient
        for ingredient in recipe.ingredients
        if not _is_detected_ingredient(ingredient, detected_names)
    ]
    if unknown_ingredients:
        raise OllamaResponseError(
            "ollama recipe contains ingredients that were not detected"
        )

    return recipe.model_dump(mode="json")


async def suggest_recipe(
    image_path: str,
    preferences: str = "",
    vlm: OllamaVLM | None = None,
    llm: OllamaLLM | None = None,
) -> dict[str, Any]:
    detection = await detect_ingredients(image_path, vlm=vlm)
    ingredients = detection["ingredients"]
    if not ingredients:
        raise RecipeInputError(
            "Aucun ingrédient utilisable n'a été détecté. "
            "Essayez une photo plus nette et mieux éclairée."
        )

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

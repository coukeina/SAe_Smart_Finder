import json
import math
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

import gradio as gr

from .config import settings
from .ollama_client.base import (
    OllamaConnectionError,
    OllamaContextError,
    OllamaError,
    OllamaResponseError,
)
from .service.core import RecipeInputError, analyze_photo, recipes_from_ingredients
from .service.inventory import (
    InventoryInputError,
    get_inventory,
    save_confirmed_inventory,
)
from .storage.inventory_repository import InventoryRepositoryError
from .storage.recipe_repository import RecipeRepositoryError


def save_json(name: str, payload: dict[str, object], stamp: str) -> Path:
    output_dir = Path(settings.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{name}_{stamp}.json"
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def _format_recipe(recipe: dict[str, object]) -> str:
    title = str(recipe.get("title") or "Recette proposée")
    recipe_text = f"## {title}\n"

    cooking_time = recipe.get("cooking_time")
    if cooking_time:
        recipe_text += f"\n**Temps de préparation :** {cooking_time}\n"

    ingredients = recipe.get("ingredients", [])
    if isinstance(ingredients, list) and ingredients:
        recipe_text += "\n### Ingrédients\n" + "\n".join(
            f"- {ingredient}" for ingredient in ingredients
        )

    steps = recipe.get("steps", [])
    if isinstance(steps, list) and steps:
        recipe_text += "\n\n### Préparation\n" + "\n".join(
            f"{index}. {step}" for index, step in enumerate(steps, start=1)
        )

    return recipe_text


def _format_metrics(
    metrics: dict[str, object],
    keys: Sequence[str] | None = None,
) -> str:
    labels = (
        ("vision_latency_ms", "Latence VLM"),
        ("generation_latency_ms", "Latence LLM"),
        ("generated_tokens", "Tokens générés"),
        ("tokens_per_second", "Débit de génération"),
        ("recipe_cosine_similarity", "Score cosine brut"),
    )
    lines = []
    for key, label in labels:
        if keys is not None and key not in keys:
            continue
        value = metrics.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if key == "recipe_cosine_similarity":
                formatted = repr(value)
            elif key == "generated_tokens":
                formatted = str(int(value))
            else:
                formatted = f"{value:.2f}"
            unit = "" if key in {"generated_tokens", "recipe_cosine_similarity"} else " ms"
            if key == "tokens_per_second":
                unit = " tokens/s"
            lines.append(f"- **{label} :** {formatted}{unit}")
        else:
            lines.append(f"- **{label} :** non disponible")
    return "\n".join(lines)


VISION_METRICS = ("vision_latency_ms",)
GENERATION_METRICS = (
    "generation_latency_ms",
    "generated_tokens",
    "tokens_per_second",
    "recipe_cosine_similarity",
)


def _error_message(error: Exception, context_hint: str, retry_hint: str) -> str:
    if isinstance(error, OllamaContextError):
        return context_hint
    if isinstance(error, OllamaConnectionError):
        return (
            "Le service Ollama est inaccessible. "
            "Vérifiez qu'il est démarré, puis réessayez."
        )
    if isinstance(error, OllamaResponseError):
        return f"Le modèle n'a pas renvoyé une réponse exploitable. {retry_hint}"
    if isinstance(error, (RecipeInputError, RecipeRepositoryError)):
        return str(error)
    return f"Une erreur Ollama est survenue : {error}"


def _clean_number(value: object) -> object:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return None if math.isnan(value) else value


def _rows_to_ingredients(rows: list[list[object]] | None) -> list[dict[str, object]]:
    ingredients = []
    for row in rows or []:
        if not isinstance(row, (list, tuple)) or not row:
            continue
        name = row[0]
        if not isinstance(name, str) or not name.strip():
            continue
        maturity = row[2] if len(row) > 2 else None
        ingredients.append({
            "name": name.strip(),
            "quantity": _clean_number(row[1]) if len(row) > 1 else None,
            "maturity": maturity if isinstance(maturity, str) and maturity.strip() else None,
        })
    return ingredients


async def show_ingredients(
    image_path: str | None,
) -> tuple[list[list[object]], str]:
    if not image_path:
        return [], "Aucune image sélectionnée. Ajoutez une photo puis réessayez."

    try:
        analysis = await analyze_photo(image_path)
    except OSError:
        return [], "La photo n'a pas pu être lue. Choisissez un autre fichier."
    except (OllamaError, RecipeInputError) as error:
        return [], _error_message(
            error,
            context_hint=(
                "La photo contient trop d'informations pour être analysée. "
                "Essayez une photo plus rapprochée."
            ),
            retry_hint="Réessayez avec une autre photo.",
        )

    ingredients = analysis["ingredients"]
    ingredient_rows = [
        [item.get("name"), item.get("quantity"), item.get("maturity")]
        for item in ingredients
    ]
    message = (
        f"{len(ingredient_rows)} ingrédient(s) détecté(s) par l'IA. "
        "Vous pouvez maintenant proposer des recettes."
    )
    metrics = analysis.get("metrics")
    if isinstance(metrics, dict):
        message += "\n\n" + _format_metrics(metrics, VISION_METRICS)
    try:
        save_json(
            "ingredients",
            {"ingredients": ingredients},
            f"{datetime.now():%Y%m%d_%H%M%S}",
        )
    except OSError:
        message += "\n\nLe fichier JSON n'a pas pu être enregistré."
    return ingredient_rows, message


async def propose_recipes(
    ingredient_rows: list[list[object]] | None,
    user_preferences: str | None,
) -> str:
    ingredients = _rows_to_ingredients(ingredient_rows)
    if not ingredients:
        return "Affichez d'abord les ingrédients de la photo pour obtenir des recettes."

    try:
        result = await recipes_from_ingredients(
            ingredients,
            preferences=user_preferences or "",
        )
    except (OllamaError, RecipeInputError, RecipeRepositoryError) as error:
        return _error_message(
            error,
            context_hint=(
                "La liste d'ingrédients est trop longue pour être traitée. "
                "Retirez quelques ingrédients puis réessayez."
            ),
            retry_hint="Réessayez.",
        )

    recipes = result.get("recipes")
    if not isinstance(recipes, list) or not recipes:
        return "Les recettes générées ont un format invalide."

    message = "\n\n---\n\n".join(
        _format_recipe(recipe) for recipe in recipes if isinstance(recipe, dict)
    )
    metrics = result.get("metrics")
    if isinstance(metrics, dict):
        message += "\n\n### Métriques\n" + _format_metrics(metrics, GENERATION_METRICS)
    try:
        save_json("recipes", {"recipes": recipes}, f"{datetime.now():%Y%m%d_%H%M%S}")
    except OSError:
        message += "\n\nLe fichier JSON n'a pas pu être enregistré."
    return message


def _inventory_rows(inventory: list[dict[str, object]]) -> list[list[object]]:
    return [
        [
            item.get("name"),
            item.get("quantity"),
            item.get("unit"),
            item.get("maturity"),
            item.get("confidence"),
            not item.get("needs_confirmation", True),
        ]
        for item in inventory
    ]


def confirm_inventory(
    ingredient_rows: list[list[object]] | None,
) -> tuple[list[list[object]], str]:
    try:
        inventory = save_confirmed_inventory(ingredient_rows)
    except InventoryInputError as error:
        return [], str(error)
    except InventoryRepositoryError as error:
        return [], str(error)

    rows = _inventory_rows(inventory)
    return rows, f"Inventaire confirmé : {len(rows)} ingrédient(s) enregistré(s)."


def refresh_inventory() -> tuple[list[list[object]], str]:
    try:
        rows = _inventory_rows(get_inventory())
    except InventoryRepositoryError as error:
        return [], str(error)
    return rows, f"{len(rows)} ingrédient(s) dans l'inventaire."


def build_demo() -> gr.Blocks:
    """Build the recipe suggestion interface."""
    with gr.Blocks(title="Smart Recipe") as demo:
        gr.Markdown(
            "# Smart Recipe\n\n"
            "Déposez une photo de votre frigo ou placard : l'IA détecte les "
            "ingrédients, puis vous propose des recettes."
        )

        with gr.Row():
            image_input = gr.Image(
                label="Photo du frigo / placard",
                type="filepath",
                sources=["upload", "clipboard"],
            )
            preferences_input = gr.Textbox(
                label="Préférences (facultatif)",
                placeholder="Exemple : végétarien, rapide, pour 2 personnes",
            )

        ingredients_button = gr.Button("Afficher les ingrédients")
        ingredients_status = gr.Markdown()
        ingredients_output = gr.Dataframe(
            headers=["Aliment", "Quantité", "Maturité"],
            label="Ingrédients détectés par l'IA",
            type="array",
            interactive=True,
        )
        recipes_button = gr.Button("Proposer des recettes")
        recipe_output = gr.Markdown(
            "Les recettes apparaîtront ici après l'analyse des ingrédients."
        )

        gr.Markdown(
            "Vérifiez et corrigez les ingrédients détectés dans le tableau avant "
            "de les enregistrer dans l'inventaire."
        )
        confirm_button = gr.Button("Confirmer et enregistrer l'inventaire")
        inventory_output = gr.Dataframe(
            headers=[
                "Aliment",
                "Quantité",
                "Unité",
                "Maturité",
                "Confiance",
                "Confirmé",
            ],
            label="Inventaire enregistré",
            type="array",
            interactive=False,
        )
        inventory_status = gr.Markdown()

        ingredients_button.click(
            fn=show_ingredients,
            inputs=[image_input],
            outputs=[ingredients_output, ingredients_status],
        )
        recipes_button.click(
            fn=propose_recipes,
            inputs=[ingredients_output, preferences_input],
            outputs=[recipe_output],
        )
        confirm_button.click(
            fn=confirm_inventory,
            inputs=[ingredients_output],
            outputs=[inventory_output, inventory_status],
        )
        demo.load(
            fn=refresh_inventory,
            outputs=[inventory_output, inventory_status],
        )
    return demo


if __name__ == "__main__":
    build_demo().launch(
        server_name=settings.gradio_host,
        server_port=settings.gradio_port,
        share=False,
    )

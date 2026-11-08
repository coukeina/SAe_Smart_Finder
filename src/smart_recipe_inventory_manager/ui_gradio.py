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

CUSTOM_CSS = """
/* =========================
   SMARTFINDER — GLOBAL
   ========================= */

.gradio-container {
    max-width: 1280px !important;
    margin: 0 auto !important;
    padding: 24px 32px 60px !important;
    font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif !important;
}

/* Header */
.sf-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 0 28px;
}

.sf-logo {
    font-size: 25px;
    font-weight: 800;
    letter-spacing: -1px;
}

.sf-logo span {
    opacity: .55;
}

.sf-badge {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 8px 13px;
    border: 1px solid var(--border-color-primary);
    border-radius: 999px;
    font-size: 13px;
    opacity: .8;
}

/* Hero */
.sf-hero {
    text-align: center;
    padding: 36px 10px 30px;
}

.sf-eyebrow {
    font-size: 13px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    opacity: .55;
    margin-bottom: 14px;
}

.sf-hero h1 {
    font-size: clamp(38px, 6vw, 67px);
    line-height: 1.02;
    letter-spacing: -3px;
    margin: 0 auto 18px;
    max-width: 850px;
    font-weight: 850;
}

.sf-hero p {
    font-size: 18px;
    line-height: 1.6;
    opacity: .65;
    max-width: 650px;
    margin: 0 auto;
}

/* Progress */
.sf-progress {
    max-width: 720px;
    margin: 24px auto 42px;
    display: flex;
    align-items: center;
    justify-content: center;
}

.sf-step {
    display: flex;
    align-items: center;
    gap: 9px;
    font-size: 14px;
    font-weight: 650;
    white-space: nowrap;
}

.sf-step-number {
    width: 30px;
    height: 30px;
    border-radius: 50%;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border: 1px solid var(--border-color-primary);
    font-size: 13px;
}

.sf-step.active .sf-step-number {
    background: var(--primary-500);
    border-color: var(--primary-500);
    color: white;
}

.sf-step-line {
    height: 1px;
    background: var(--border-color-primary);
    flex: 1;
    min-width: 35px;
    margin: 0 15px;
}

/* Main card */
.sf-section-title {
    margin-bottom: 4px !important;
}

.sf-section-title h2 {
    font-size: 23px;
    letter-spacing: -.6px;
    margin-bottom: 5px;
}

.sf-section-title p {
    opacity: .6;
    margin-top: 0;
}

.sf-card {
    border: 1px solid var(--border-color-primary) !important;
    border-radius: 22px !important;
    padding: 24px !important;
    background: var(--background-fill-secondary) !important;
}

/* Image upload */
.sf-image {
    border-radius: 18px !important;
    overflow: hidden !important;
    min-height: 300px !important;
}

/* Buttons */
.sf-primary-btn {
    min-height: 52px !important;
    border-radius: 14px !important;
    font-weight: 750 !important;
    font-size: 15px !important;
}

.sf-secondary-btn {
    min-height: 48px !important;
    border-radius: 14px !important;
    font-weight: 650 !important;
}

/* Status */
.sf-status {
    border-radius: 14px;
    margin-top: 8px;
}

/* Dataframes */
.sf-table {
    border-radius: 16px !important;
    overflow: hidden !important;
}

/* Recipe output */
.sf-recipes {
    border: 1px solid var(--border-color-primary);
    border-radius: 20px;
    padding: 22px !important;
    min-height: 140px;
}

/* Preferences */
.sf-preferences {
    border-radius: 18px !important;
}

/* Divider title */
.sf-divider {
    margin-top: 45px;
    padding-top: 30px;
    border-top: 1px solid var(--border-color-primary);
}

/* Footer */
.sf-footer {
    text-align: center;
    opacity: .45;
    font-size: 12px;
    margin-top: 55px;
}

/* Mobile */
@media (max-width: 700px) {
    .gradio-container {
        padding: 16px 14px 40px !important;
    }

    .sf-hero {
        padding-top: 20px;
    }

    .sf-hero h1 {
        letter-spacing: -2px;
    }

    .sf-progress {
        margin-bottom: 28px;
    }

    .sf-step span:last-child {
        display: none;
    }

    .sf-step-line {
        margin: 0 8px;
    }
}
"""


def build_demo() -> gr.Blocks:
    """Build the SmartFinder user interface."""

    with gr.Blocks(
        title="SmartFinder",
        css=CUSTOM_CSS,
        theme=gr.themes.Base(
            primary_hue="emerald",
            neutral_hue="slate",
            radius_size="lg",
        ),
    ) as demo:

        # =========================
        # HEADER
        # =========================
        gr.HTML(
            """
            <div class="sf-header">
                <div class="sf-logo">
                    Smart<span>Finder</span>
                </div>

                <div class="sf-badge">
                    <span>●</span>
                    Smart food assistant
                </div>
            </div>
            """
        )

        # =========================
        # HERO
        # =========================
        gr.HTML(
            """
            <section class="sf-hero">
                <div class="sf-eyebrow">Anti-gaspillage · Propulsé par l'IA</div>

                <h1>
                    Ton frigo a déjà<br>
                    ton prochain repas.
                </h1>

                <p>
                    Prends une photo de tes aliments.
                    SmartFinder les reconnaît et imagine des recettes
                    adaptées à ce que tu as vraiment chez toi.
                </p>
            </section>

            <div class="sf-progress">
                <div class="sf-step active">
                    <span class="sf-step-number">1</span>
                    <span>Photo</span>
                </div>

                <div class="sf-step-line"></div>

                <div class="sf-step">
                    <span class="sf-step-number">2</span>
                    <span>Ingrédients</span>
                </div>

                <div class="sf-step-line"></div>

                <div class="sf-step">
                    <span class="sf-step-number">3</span>
                    <span>Recettes</span>
                </div>
            </div>
            """
        )

        # =========================
        # STEP 1 — PHOTO
        # =========================
        gr.HTML(
            """
            <div class="sf-section-title">
                <h2>01 — Montre-nous ce que tu as</h2>
                <p>
                    Une photo nette de ton frigo, placard
                    ou directement de tes aliments suffit.
                </p>
            </div>
            """
        )

        with gr.Group(elem_classes=["sf-card"]):

            with gr.Row(equal_height=True):

                image_input = gr.Image(
                    label="Photo de tes aliments",
                    type="filepath",
                    sources=["upload", "clipboard"],
                    height=330,
                    elem_classes=["sf-image"],
                )

                with gr.Column():

                    gr.Markdown(
                        """
### Une bonne photo fait toute la différence

Pour obtenir une détection plus précise :

- garde les aliments **visibles**
- évite une photo trop sombre
- rapproche-toi si ton frigo est très rempli
- tu pourras **corriger les résultats** ensuite

L'IA ne doit utiliser que les aliments réellement détectés.
                        """
                    )

                    ingredients_button = gr.Button(
                        "✨ Analyser ma photo",
                        variant="primary",
                        elem_classes=["sf-primary-btn"],
                    )

        ingredients_status = gr.Markdown(
            elem_classes=["sf-status"]
        )

        # =========================
        # STEP 2 — INGREDIENTS
        # =========================
        gr.HTML(
            """
            <div class="sf-divider sf-section-title">
                <h2>02 — Vérifie tes ingrédients</h2>
                <p>
                    L'IA peut se tromper. Corrige les aliments,
                    quantités ou maturités avant de continuer.
                </p>
            </div>
            """
        )

        ingredients_output = gr.Dataframe(
            headers=["Aliment", "Quantité", "Maturité"],
            datatype=["str", "number", "str"],
            label="Ingrédients détectés",
            type="array",
            interactive=True,
            wrap=True,
            elem_classes=["sf-table"],
        )

        # =========================
        # PREFERENCES
        # =========================
        with gr.Row():

            servings_input = gr.Radio(
                choices=["1", "2", "3", "4+"],
                value="2",
                label="👥 Pour combien de personnes ?",
                elem_classes=["sf-preferences"],
            )

            time_input = gr.Radio(
                choices=[
                    "Moins de 15 min",
                    "Moins de 30 min",
                    "Peu importe",
                ],
                value="Moins de 30 min",
                label="⏱️ Temps disponible",
                elem_classes=["sf-preferences"],
            )

        preferences_input = gr.Textbox(
            label="Une envie particulière ?",
            placeholder=(
                "Ex : végétarien, léger, épicé, repas du soir..."
            ),
            lines=2,
            elem_classes=["sf-preferences"],
        )

        recipes_button = gr.Button(
            "Trouver mes recettes →",
            variant="primary",
            elem_classes=["sf-primary-btn"],
        )

        # =========================
        # STEP 3 — RECIPES
        # =========================
        gr.HTML(
            """
            <div class="sf-divider sf-section-title">
                <h2>03 — Tes recettes</h2>
                <p>
                    Des idées adaptées aux ingrédients
                    que tu viens de valider.
                </p>
            </div>
            """
        )

        recipe_output = gr.Markdown(
            """
### Tes recettes apparaîtront ici ✨

Ajoute une photo, vérifie tes ingrédients puis lance la génération.
            """,
            elem_classes=["sf-recipes"],
        )

        # =========================
        # INVENTORY
        # =========================
        gr.HTML(
            """
            <div class="sf-divider sf-section-title">
                <h2>Mon inventaire</h2>
                <p>
                    Enregistre les ingrédients confirmés pour
                    retrouver ton stock lors de ta prochaine visite.
                </p>
            </div>
            """
        )

        confirm_button = gr.Button(
            "＋ Ajouter ces ingrédients à mon inventaire",
            elem_classes=["sf-secondary-btn"],
        )

        inventory_status = gr.Markdown()

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
            wrap=True,
            elem_classes=["sf-table"],
        )

        gr.HTML(
            """
            <div class="sf-footer">
                SmartFinder · Cuisiner mieux · Gaspiller moins
            </div>
            """
        )

        # =========================
        # EVENTS
        # =========================

        ingredients_button.click(
            fn=show_ingredients,
            inputs=[image_input],
            outputs=[
                ingredients_output,
                ingredients_status,
            ],
        )

        # Pour l'instant on conserve exactement le callback backend
        # existant. Les contrôles portions/temps seront connectés
        # à l'étape suivante.
        recipes_button.click(
            fn=propose_recipes,
            inputs=[
                ingredients_output,
                preferences_input,
            ],
            outputs=[recipe_output],
        )

        confirm_button.click(
            fn=confirm_inventory,
            inputs=[ingredients_output],
            outputs=[
                inventory_output,
                inventory_status,
            ],
        )

        demo.load(
            fn=refresh_inventory,
            outputs=[
                inventory_output,
                inventory_status,
            ],
        )

    return demo


if __name__ == "__main__":
    build_demo().launch(
        server_name=settings.gradio_host,
        server_port=settings.gradio_port,
        share=False,
    )

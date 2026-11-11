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
/* ==========================================
   SMARTFINDER — FOOD TECH UI
   ========================================== */

:root {
    --sf-bg: #070b12;
    --sf-surface: #0d131d;
    --sf-surface-2: #121a26;
    --sf-border: rgba(255,255,255,.09);
    --sf-text: #f5f7f2;
    --sf-muted: #8d96a5;
    --sf-lime: #b8ff3d;
    --sf-lime-soft: rgba(184,255,61,.12);
}


/* ---------- APP ---------- */

html,
body {
    margin: 0 !important;
    padding: 0 !important;
    min-height: 100% !important;
    background: #070b12 !important;
}

body {
    overflow-x: hidden !important;
}

.gradio-container {
    min-height: 100vh !important;

    background:
        radial-gradient(
            circle at 15% 5%,
            rgba(184,255,61,.07),
            transparent 28%
        ),
        radial-gradient(
            circle at 85% 30%,
            rgba(42,122,255,.06),
            transparent 28%
        ),
        #070b12 !important;
}

.gradio-container {
    max-width: none !important;
    width: 100% !important;
    margin: 0 !important;

    padding: 28px max(34px, calc((100vw - 1240px) / 2)) 80px !important;

    color: var(--sf-text) !important;
}


/* ---------- HEADER ---------- */

.sf-header {
    display: flex;
    align-items: center;
    justify-content: space-between;

    padding: 6px 0 28px;

    border-bottom: 1px solid var(--sf-border);
}

.sf-logo {
    color: white;

    font-size: 25px;
    font-weight: 900;

    letter-spacing: -1.4px;
}

.sf-logo span {
    color: var(--sf-lime);
    opacity: 1;
}

.sf-badge {
    padding: 8px 14px;

    border: 1px solid rgba(184,255,61,.25);
    border-radius: 100px;

    background: rgba(184,255,61,.05);

    color: #cfff7b;

    font-size: 11px;
    font-weight: 800;

    letter-spacing: 1px;
    text-transform: uppercase;
}

.sf-badge span {
    color: var(--sf-lime);
}


/* ---------- HERO ---------- */

.sf-hero {
    position: relative;

    padding: 85px 20px 58px;

    text-align: left;

    overflow: hidden;
}

.sf-hero::after {
    content: "✦";

    position: absolute;

    right: 7%;
    top: 38px;

    color: var(--sf-lime);

    font-size: 170px;
    line-height: 1;

    opacity: .09;

    transform: rotate(12deg);

    pointer-events: none;
}

.sf-eyebrow {
    color: var(--sf-lime) !important;

    margin-bottom: 18px;

    font-size: 11px !important;
    font-weight: 900 !important;

    letter-spacing: 2.5px !important;
    text-transform: uppercase;
}

.sf-hero h1 {
    max-width: 900px;

    margin: 0;

    color: #f7f8f4;

    font-size: clamp(50px, 7vw, 86px);
    line-height: .95;

    font-weight: 900;

    letter-spacing: -5px;
}

.sf-hero p {
    max-width: 600px;

    margin: 30px 0 0;

    color: var(--sf-muted);

    font-size: 18px;
    line-height: 1.65;
}


/* ---------- PROGRESS ---------- */

.sf-progress {
    display: flex;
    align-items: center;

    max-width: 700px;

    margin: 0 20px 70px;
}

.sf-step {
    display: flex;
    align-items: center;
    gap: 10px;

    color: #697384;

    font-size: 11px;
    font-weight: 900;

    letter-spacing: 1.2px;
    text-transform: uppercase;
}

.sf-step-number {
    display: flex;
    align-items: center;
    justify-content: center;

    width: 34px;
    height: 34px;

    border: 1px solid #293344;
    border-radius: 50%;

    font-size: 11px;
}

.sf-step.active {
    color: white;
}

.sf-step.active .sf-step-number {
    background: var(--sf-lime);

    border-color: var(--sf-lime);

    color: #071008;

    box-shadow:
        0 0 0 5px rgba(184,255,61,.08),
        0 0 30px rgba(184,255,61,.12);
}

.sf-step-line {
    flex: 1;

    height: 1px;

    margin: 0 18px;

    background: linear-gradient(
        90deg,
        #2c3746,
        #17202c
    );
}


/* ---------- SECTION TITLES ---------- */

.sf-section-title {
    margin: 0 10px 22px !important;
}

.sf-section-title h2 {
    margin: 5px 0 8px !important;

    color: #f7f8f4 !important;

    font-size: 31px !important;
    font-weight: 850 !important;

    letter-spacing: -1.3px !important;
}

.sf-section-title p {
    max-width: 680px;

    margin: 0 !important;

    color: var(--sf-muted) !important;

    font-size: 15px !important;
}

.sf-divider {
    margin-top: 90px !important;
    padding-top: 45px;

    border-top: 1px solid var(--sf-border);
}


/* ---------- CARDS ---------- */

.sf-card {
    position: relative;

    padding: 12px !important;

    border: 1px solid var(--sf-border) !important;
    border-radius: 30px !important;

    background:
        linear-gradient(
            145deg,
            rgba(255,255,255,.035),
            rgba(255,255,255,.012)
        ) !important;

    box-shadow:
        0 30px 80px rgba(0,0,0,.25) !important;

    overflow: hidden;
}

.sf-card::before {
    content: "";

    position: absolute;

    width: 220px;
    height: 220px;

    top: -120px;
    right: -100px;

    border-radius: 50%;

    background: var(--sf-lime);

    opacity: .035;

    filter: blur(20px);

    pointer-events: none;
}


/* ---------- IMAGE DROP ZONE ---------- */

.sf-image {
    min-height: 390px !important;

    border: 1px dashed rgba(184,255,61,.25) !important;
    border-radius: 23px !important;

    background:
        radial-gradient(
            circle at center,
            rgba(184,255,61,.055),
            transparent 50%
        ),
        #0a1019 !important;

    overflow: hidden !important;

    transition:
        border .25s ease,
        transform .25s ease,
        box-shadow .25s ease !important;
}

.sf-image:hover {
    border-color: rgba(184,255,61,.7) !important;

    transform: translateY(-2px);

    box-shadow:
        inset 0 0 40px rgba(184,255,61,.03),
        0 18px 45px rgba(0,0,0,.25);
}


/* ---------- BUTTONS ---------- */

.sf-primary-btn {
    min-height: 58px !important;

    border: 0 !important;
    border-radius: 17px !important;

    background:
        linear-gradient(
            110deg,
            #b8ff3d,
            #8bea32
        ) !important;

    color: #071008 !important;

    font-size: 14px !important;
    font-weight: 900 !important;

    letter-spacing: .2px;

    box-shadow:
        0 10px 30px rgba(184,255,61,.12) !important;

    transition:
        transform .2s ease,
        box-shadow .2s ease,
        filter .2s ease !important;
}

.sf-primary-btn:hover {
    transform: translateY(-3px) !important;

    filter: brightness(1.06);

    box-shadow:
        0 16px 45px rgba(184,255,61,.22) !important;
}

.sf-primary-btn:active {
    transform: scale(.985) !important;
}

.sf-secondary-btn {
    min-height: 52px !important;

    border: 1px solid var(--sf-border) !important;
    border-radius: 16px !important;

    background: #101824 !important;

    color: white !important;

    font-weight: 750 !important;

    transition: all .2s ease !important;
}

.sf-secondary-btn:hover {
    border-color: rgba(184,255,61,.35) !important;

    background: #151f2c !important;
}


/* ---------- TABLE ---------- */

.sf-table {
    border: 1px solid var(--sf-border) !important;
    border-radius: 20px !important;

    background: #0b111b !important;

    overflow: hidden !important;

    box-shadow: none !important;
}

.sf-table table {
    background: transparent !important;
}

.sf-table th {
    background: #101823 !important;

    color: #9ba6b6 !important;

    font-size: 11px !important;
    font-weight: 900 !important;

    letter-spacing: 1px !important;
    text-transform: uppercase !important;
}

.sf-table td {
    background: #0b111b !important;

    border-color: rgba(255,255,255,.055) !important;

    color: #f5f7f2 !important;
}


/* ---------- PREFERENCES ---------- */

.sf-preferences {
    border-radius: 18px !important;
}

.sf-preferences > div {
    border-color: var(--sf-border) !important;
}


/* ---------- RECIPE AREA ---------- */

.sf-recipes {
    position: relative;

    min-height: 220px;

    padding: 30px !important;

    border: 1px solid rgba(184,255,61,.13) !important;
    border-radius: 25px !important;

    background:
        radial-gradient(
            circle at 95% 0%,
            rgba(184,255,61,.08),
            transparent 30%
        ),
        #0c131d !important;

    box-shadow:
        0 30px 80px rgba(0,0,0,.2);
}

.sf-recipes h1,
.sf-recipes h2,
.sf-recipes h3 {
    color: #f7f8f4 !important;
}


/* ---------- STATUS ---------- */

.sf-status {
    margin: 15px 5px 0;

    color: #c5ceda;
}


/* ---------- INVENTORY ---------- */

.sf-inventory-card {
    padding: 26px !important;

    border: 1px solid var(--sf-border) !important;
    border-radius: 25px !important;

    background: #0b111a !important;
}


/* ---------- ANIMATION ---------- */

@keyframes sfReveal {
    from {
        opacity: 0;
        transform: translateY(18px);
    }

    to {
        opacity: 1;
        transform: translateY(0);
    }
}

.sf-card,
.sf-section-title,
.sf-recipes {
    animation: sfReveal .55s ease both;
}


/* ---------- FOOTER ---------- */

.sf-footer {
    margin-top: 70px;

    color: #525c69;

    text-align: center;

    font-size: 11px;

    letter-spacing: 1px;
    text-transform: uppercase;
}


/* ---------- MOBILE ---------- */

@media (max-width: 700px) {

    .gradio-container {
        padding: 18px 15px 55px !important;
    }

    .sf-header {
        padding-bottom: 18px;
    }

    .sf-badge {
        display: none;
    }

    .sf-hero {
        padding:
            55px 5px
            40px;
    }

    .sf-hero h1 {
        font-size: 48px;

        letter-spacing: -3px;
    }

    .sf-hero p {
        font-size: 16px;
    }

    .sf-hero::after {
        font-size: 100px;
    }

    .sf-progress {
        margin:
            0 5px
            45px;
    }

    .sf-step span:last-child {
        display: none;
    }

    .sf-step-line {
        margin: 0 9px;
    }

    .sf-section-title h2 {
        font-size: 26px !important;
    }

    .sf-divider {
        margin-top: 60px !important;
    }
    footer {
    display: none !important;
}
}
"""
def reveal_preferences():
    """Reveal recipe preferences after ingredient validation."""
    return (
        gr.update(visible=True),
        gr.update(visible=True),
    )


def reveal_recipes():
    """Reveal the recipe result section."""
    return gr.update(visible=True)

def build_demo() -> gr.Blocks:
    async def propose_recipes_with_preferences(
        ingredient_rows,
        servings,
        cooking_time,
        preferences,
):
        """Generate recipes using the selected user preferences."""
        combined_preferences = (
            f"Nombre de personnes : {servings}. "
            f"Temps disponible : {cooking_time}. "
            f"Préférences supplémentaires : {preferences or 'aucune'}."
        )

        return await propose_recipes(
            ingredient_rows,
            combined_preferences,
        )
    """Build the SmartFinder user interface."""

    with gr.Blocks(
        title="SmartFinder",
        css=CUSTOM_CSS,
        theme=gr.themes.Base(
        primary_hue="lime",
        neutral_hue="slate",
        radius_size="lg",
        font=[gr.themes.GoogleFont("Inter"),"Arial","sans-serif",
               ],
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

                <div class="sf-eyebrow">
                    ✦ AI-POWERED FOOD ASSISTANT
                </div>

                <h1>
                    COOK WHAT<br>
                    YOU ALREADY HAVE.
                </h1>

                <p>
                    Ton frigo est probablement plus rempli que tu ne le penses.
                    Prends une photo. SmartFinder détecte tes aliments et
                    transforme ce que tu as déjà en idées de repas.
                </p>

            </section>
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

        with gr.Group(elem_classes=["sf-card"]), gr.Row(equal_height=True):

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
                        " Analyser ma photo",
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
    <div style="
        padding: 28px 26px;
        height: 100%;
        display: flex;
        flex-direction: column;
        justify-content: center;
    ">

        <div class="sf-eyebrow">
            BEFORE YOU SCAN
        </div>

        <h2 style="
            font-size: 28px;
            line-height: 1.1;
            letter-spacing: -1px;
            margin: 0 0 25px;
        ">
            Give the AI<br>
            something good to see.
        </h2>

        <div style="
            display:grid;
            gap:14px;
            color:#9aa4b3;
            font-size:14px;
        ">

            <div>
                <b style="color:#b8ff3d;">01</b>
                &nbsp; Garde les aliments visibles
            </div>

            <div>
                <b style="color:#b8ff3d;">02</b>
                &nbsp; Évite les photos trop sombres
            </div>

            <div>
                <b style="color:#b8ff3d;">03</b>
                &nbsp; Cadre au plus près des aliments
            </div>

            <div>
                <b style="color:#b8ff3d;">04</b>
                &nbsp; Vérifie la détection avant de cuisiner
            </div>

        </div>

        <div style="
            margin-top:28px;
            padding:14px 16px;
            border:1px solid rgba(184,255,61,.12);
            border-radius:14px;
            background:rgba(184,255,61,.04);
            color:#b6c0cd;
            font-size:12px;
            line-height:1.5;
        ">
            ✦ SmartFinder ne doit jamais inventer
            un aliment absent de la photo.
        </div>

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

        continue_button = gr.Button(
            "Tout est bon, continuer →",
            variant="primary",
            elem_classes=["sf-primary-btn"],
        )

        # =========================
        # PREFERENCES
        # Cachées au démarrage
        # =========================
        with gr.Column(visible=False) as preferences_section:

            gr.HTML(
                """
                <div class="sf-divider sf-section-title">
                    <div class="sf-eyebrow">MAKE IT YOURS</div>
                    <h2>Comment veux-tu manger aujourd'hui ?</h2>
                    <p>
                        Donne-moi quelques préférences et je m'occupe du reste.
                    </p>
                </div>
                """
            )

            with gr.Row():

                servings_input = gr.Radio(
                    choices=["1", "2", "3", "4+"],
                    value="2",
                    label="👥 Pour combien de personnes ?",
                    elem_classes=["sf-preferences"],
                )

                time_input = gr.Radio(
                    choices=[
                        "⚡ Moins de 15 min",
                        "⏱️ Moins de 30 min",
                        "🍳 Peu importe",
                    ],
                    value="⏱️ Moins de 30 min",
                    label="Temps disponible",
                    elem_classes=["sf-preferences"],
                )

            preferences_input = gr.Textbox(
                label="Une envie particulière ?",
                placeholder="Healthy, végétarien, épicé, comfort food...",
                lines=2,
                elem_classes=["sf-preferences"],
            )

            recipes_button = gr.Button(
                "✦ Trouver mes recettes",
                variant="primary",
                elem_classes=["sf-primary-btn"],
            )

        # =========================
        # STEP 3 — RECIPES
        # Cachées au démarrage
        # =========================
        with gr.Column(visible=False):

            gr.HTML(
                """
                <div class="sf-divider sf-section-title">
                    <div class="sf-eyebrow">SMART MATCHES</div>
                    <h2>03 — Voilà ce qu'on peut cuisiner ✦</h2>
                    <p>
                        Des recettes pensées à partir de ce que
                        tu as réellement chez toi.
                    </p>
                </div>
                """
            )

            recipe_output = gr.Markdown(
                """
### Tes recettes arrivent ici

Choisis tes préférences puis lance la génération.
                """,
                elem_classes=["sf-recipes"],
            )
                # =========================
        # INVENTORY
        # =========================
        gr.HTML(
            """
            <div class="sf-divider sf-section-title">
                <div class="sf-eyebrow">YOUR KITCHEN</div>
                <h2>Garde un œil sur ton stock.</h2>
                <p>
                    Ton inventaire reste disponible sans encombrer
                    ton parcours de génération de recettes.
                </p>
            </div>
            """
        )

        with gr.Accordion(
            " Ouvrir mon inventaire",
            open=False,
        ):
            gr.Markdown(
                """
Les ingrédients que tu confirmes sont sauvegardés ici.
Ajoute les aliments détectés quand tu souhaites les conserver.
                """
            )

            confirm_button = gr.Button(
                "＋ Ajouter les ingrédients détectés",
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
        continue_button.click(
            fn=reveal_preferences,
            outputs=[preferences_section],
        )
        
        # Pour l'instant on conserve exactement le callback backend
        # existant. Les contrôles portions/temps seront connectés
        # à l'étape suivante.
        recipes_button.click(
    fn=propose_recipes_with_preferences,
    inputs=[
        ingredients_output,
        servings_input,
        time_input,
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

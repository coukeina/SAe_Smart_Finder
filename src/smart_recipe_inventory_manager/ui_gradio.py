import gradio as gr

from .config import settings
from .ollama_client.base import (
    OllamaConnectionError,
    OllamaContextError,
    OllamaError,
    OllamaResponseError,
)
from .service.core import RecipeInputError, suggest_recipe


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


async def propose_recipe(
    image_path: str | None,
    user_preferences: str | None,
) -> tuple[list[list[object]], str]:
    if not image_path:
        return [], "Aucune image sélectionnée. Ajoutez une photo puis réessayez."

    try:
        result = await suggest_recipe(
            image_path=image_path,
            preferences=user_preferences or "",
        )
    except OllamaContextError:
        return [], (
            "La photo contient trop d'informations pour être analysée. "
            "Essayez une photo plus rapprochée."
        )
    except OllamaConnectionError:
        return [], (
            "Le service Ollama est inaccessible. "
            "Vérifiez qu'il est démarré, puis réessayez."
        )
    except OllamaResponseError:
        return [], (
            "Le modèle n'a pas renvoyé une réponse exploitable. "
            "Réessayez avec une autre photo."
        )
    except RecipeInputError as error:
        return [], str(error)
    except OllamaError as error:
        return [], f"Une erreur Ollama est survenue : {error}"
    except OSError:
        return [], "La photo n'a pas pu être lue. Choisissez un autre fichier."

    ingredients = result.get("ingredients", [])
    ingredient_rows = [
        [item.get("name"), item.get("quantity"), item.get("maturity")]
        for item in ingredients
        if isinstance(item, dict)
    ]
    recipe = result.get("recipe")
    if not isinstance(recipe, dict):
        return ingredient_rows, "La recette générée a un format invalide."

    return ingredient_rows, _format_recipe(recipe)


def build_demo() -> gr.Blocks:
    """Build the recipe suggestion interface."""
    with gr.Blocks(title="Smart Recipe") as demo:
        gr.Markdown(
            "# Smart Recipe\n\n"
            "Déposez une photo de votre frigo ou placard pour obtenir une recette adaptée."
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

        generate_button = gr.Button("Proposer une recette")
        with gr.Row():
            ingredients_output = gr.Dataframe(
                headers=["Aliment", "Quantité", "Maturité"],
                label="Ingrédients détectés",
            )
            recipe_output = gr.Markdown(
                "La recette apparaîtra ici après l'analyse."
            )

        generate_button.click(
            fn=propose_recipe,
            inputs=[image_input, preferences_input],
            outputs=[ingredients_output, recipe_output],
        )
    return demo


if __name__ == "__main__":
    build_demo().launch(
        server_name=settings.gradio_host,
        server_port=settings.gradio_port,
        share=False,
    )

import gradio as gr

from .config import settings
from .service.core import suggest_recipe

def build_demo() -> gr.Blocks:
    with gr.Blocks(title="Smart Recipe") as demo:
        gr.Markdown(
            "# Smart Recipe\n"
            "Trouvez une recette à partir d'une photo de vos ingrédients."
        )

        image = gr.Image(
            type="filepath",
            label="Photo du réfrigérateur",
        )

        preferences = gr.Textbox(
            label="Préférences",
            placeholder="Exemple : végétarien, rapide, pour 2 personnes",
        )

        generate_button = gr.Button("Proposer une recette")
        ingredients_result = gr.JSON(label="Ingrédients détectés")
        recipe_result = gr.JSON(label="Recette proposée")

        async def propose_recipe(
            image_path: str | None,
            user_preferences: str,
        ) -> tuple[dict, dict]:
            if image_path is None:
                return {"error": "Aucune image sélectionnée."}, {}

            result = await suggest_recipe(
                image_path=image_path,
                preferences=user_preferences,
            )

            return result["ingredients"], result["recipe"]

        generate_button.click(
            propose_recipe,
            inputs=[image, preferences],
            outputs=[ingredients_result, recipe_result],
        )

    return demo


if __name__ == "__main__":
	build_demo().launch(
		server_name=settings.gradio_host,
		server_port=settings.gradio_port,
		share=False,
	)

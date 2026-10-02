import gradio as gr

from .config import settings
from .service.core import detect_ingredients


async def analyze_image(image_path: str | None) -> list[list[object]]:
	"""Run VLM ingredient detection on the uploaded photo and format rows for display."""
	if not image_path:
		return []

	result = await detect_ingredients(image_path)
	ingredients = result.get("ingrédients", [])
	return [
		[item.get("name"), item.get("quantity"), item.get("maturity")]
		for item in ingredients
	]


def build_demo() -> gr.Blocks:
	"""Build the Gradio UI for uploading a fridge/cupboard photo and listing detected ingredients."""
	with gr.Blocks(title="Smart Recipe") as demo:
		gr.Markdown("# Smart Recipe\n\nDéposez une photo de votre frigo ou placard pour détecter les aliments.")

		with gr.Row():
			image_input = gr.Image(
				label="Photo du frigo / placard",
				type="filepath",
				sources=["upload", "clipboard"],
			)
			ingredients_output = gr.Dataframe(
				headers=["Aliment", "Quantité", "Maturité"],
				label="Ingrédients détectés",
			)

		analyze_button = gr.Button("Analyser la photo")
		analyze_button.click(
			fn=analyze_image,
			inputs=image_input,
			outputs=ingredients_output,
		)
		image_input.change(
			fn=analyze_image,
			inputs=image_input,
			outputs=ingredients_output,
		)
	return demo
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

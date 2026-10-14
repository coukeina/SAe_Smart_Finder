import gradio as gr

from .config import settings
from .service.core import RecipeInputError, suggest_recipe
from .ollama_client.base import OllamaError


async def propose_recipe(
	image_path: str | None,
	user_preferences: str | None,
) -> tuple[list[list[object]], dict[str, object]]:
	if not image_path:
		return [], {"error": "Aucune image sélectionnée."}

	try:
		result = await suggest_recipe(
			image_path=image_path,
			preferences=user_preferences or "",
		)
	except OllamaError as error:
		return [], {"error": f"Erreur Ollama : {error}"}
	except RecipeInputError as error:
		return [], {"error": str(error)}
	ingredients = result.get("ingredients", [])
	ingredient_rows = [
		[item.get("name"), item.get("quantity"), item.get("maturity")]
		for item in ingredients
		if isinstance(item, dict)
	]
	recipe = result.get("recipe", {})
	if not isinstance(recipe, dict):
		recipe = {"error": "La recette générée a un format invalide."}

	return ingredient_rows, recipe


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
			recipe_output = gr.JSON(label="Recette proposée")

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

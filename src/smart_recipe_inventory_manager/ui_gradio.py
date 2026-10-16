import json
from datetime import datetime
from pathlib import Path

import gradio as gr

from .config import settings
from .service.core import suggest_recipe
from .ollama_client.base import OllamaError


def save_result(result: dict[str, object]) -> str:
	output_dir = Path(settings.output_dir)
	output_dir.mkdir(parents=True, exist_ok=True)
	path = output_dir / f"recipe_{datetime.now():%Y%m%d_%H%M%S}.json"
	path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
	return str(path)


async def propose_recipe(
	image_path: str | None,
	user_preferences: str | None,
) -> tuple[list[list[object]], str | None, str]:
	if not image_path:
		return [], None, "Aucune image sélectionnée."

	try:
		result = await suggest_recipe(
			image_path=image_path,
			preferences=user_preferences or "",
		)
	except (OllamaError, ValueError) as error:
		return [], None, f"Erreur : {error}"
	ingredients = result.get("ingredients", [])
	ingredient_rows = [
		[item.get("name"), item.get("quantity"), item.get("maturity")]
		for item in ingredients
		if isinstance(item, dict)
	]
	path = save_result(result)

	return ingredient_rows, path, f"Résultat enregistré : {path}"


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
			file_output = gr.File(label="Fichier JSON généré")
		status_output = gr.Markdown()

		generate_button.click(
			fn=propose_recipe,
			inputs=[image_input, preferences_input],
			outputs=[ingredients_output, file_output, status_output],
		)
	return demo


if __name__ == "__main__":
	build_demo().launch(
		server_name=settings.gradio_host,
		server_port=settings.gradio_port,
		share=False,
	)

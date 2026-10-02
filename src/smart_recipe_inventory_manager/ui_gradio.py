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
<<<<<<< HEAD
	"""Build the initial inventory interface."""
	with gr.Blocks(title="Smart Recipe") as demo:
		gr.Markdown("# Smart Recipe\n\nApplication de gestion d'inventaire et de recettes.")
		image = gr.Image(type="filepath", label="Photo du réfrigérateur")
		result = gr.Textbox(label="Résultat", value="Application prête.")
		check_button = gr.Button("Vérifier l'image")

		def check_image(image_path: str | None) -> str:
			if image_path is None:
				return "Aucune image sélectionnée."
			return f"Image reçue : {image_path}"

		check_button.click(check_image, inputs=image, outputs=result)
=======
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
>>>>>>> feat/ui-gradio
	return demo


if __name__ == "__main__":
	build_demo().launch(
		server_name=settings.gradio_host,
		server_port=settings.gradio_port,
		share=False,
	)

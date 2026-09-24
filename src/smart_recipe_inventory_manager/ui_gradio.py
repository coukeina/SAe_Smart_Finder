import gradio as gr

from .config import settings


def build_demo() -> gr.Blocks:
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
	return demo


if __name__ == "__main__":
	build_demo().launch(
		server_name=settings.gradio_host,
		server_port=settings.gradio_port,
		share=False,
	)

import gradio as gr

from .config import settings


def build_demo() -> gr.Blocks:
	"""Build the minimal shell used while feature services are added."""
	with gr.Blocks(title="Smart Recipe") as demo:
		gr.Markdown("# Smart Recipe\n\nLe service est disponible.")
	return demo


if __name__ == "__main__":
	build_demo().launch(
		server_name=settings.gradio_host,
		server_port=settings.gradio_port,
		share=False,
	)

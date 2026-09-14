# ---------- Builder ----------
FROM python:3.12-slim AS builder
WORKDIR /app
COPY pyproject.toml poetry.lock* ./
RUN pip install --upgrade pip && \
    pip install poetry && \
    poetry config virtualenvs.create false && \   
    poetry install --only main
    
# ---------- Runtime ----------
FROM python:3.12-slim
WORKDIR /app
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY . /app
ENV PYTHONUNBUFFERED=1

# Ollama n’est **pas** installé ici ; il tourne dans un service séparé.
EXPOSE 7860
CMD ["python", "-m", "gradio", "src/smart_recipe_and_inventory_manager_anti_gaspillage/ui_gradio.py"]
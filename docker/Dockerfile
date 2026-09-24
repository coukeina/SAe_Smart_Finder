# ---------- Builder ----------
FROM python:3.12-slim AS builder
WORKDIR /app

COPY pyproject.toml ./
COPY src ./src

RUN pip install --upgrade pip && \
    pip wheel --no-cache-dir --wheel-dir /wheels .
    
# ---------- Runtime ----------
FROM python:3.12-slim
WORKDIR /app
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir /wheels/*
COPY . /app
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/src

# Ollama n’est **pas** installé ici ; il tourne dans un service séparé.
EXPOSE 7860
CMD ["python", "-m", "smart_recipe_inventory_manager.ui_gradio"]
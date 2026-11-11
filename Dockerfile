# Production-ready Dockerfile for Smart Recipe & Inventory Manager

## Architecture

This Docker image provides a complete AI-powered food waste reduction application with:

- **Ollama** (local LLM inference)
- **PostgreSQL 16 + pgvector** (recipe database + vector search)
- **Python application** (Gradio + Pydantic + httpx)

All AI models and recipes are handled **100% locally** - no cloud APIs, no external dependencies.

## Technology Stack

- Python 3.12 (minimal slim image)
- Gradio 5 (web interface)
- Ollama (local AI models)
- PostgreSQL 16 + pgvector extension (vector search)
- Pydantic v2 (data validation)

## Build Arguments

```dockerfile
ARG PYTHON_VERSION=3.12-slim
ARG DEBIAN_VERSION=bullseye
```

## Stages

### Stage 1: System dependencies
```dockerfile
FROM ${DEBIAN_VERSION} AS system-deps

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    gnupg \
    git \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Install PostgreSQL client
RUN wget -qO- https://www.postgresql.org/media/keys/ACCC4CF8.asc | gpg --dearmor -o /usr/share/keyrings/postgresql.gpg && \
    echo "deb [arch=amd64 signed-by=/usr/share/keyrings/postgresql.gpg] https://deb.debian.org.debian.org/debian bullseye main" > /etc/apt/sources.list.d/postgresql.list && \
    apt-get update && apt-get install -y --no-install-recommends postgresql-client-16 && \
    rm -rf /var/lib/apt/lists/*

# Clean up temporary files
RUN rm -rf /tmp/* /var/tmp/*
```

### Stage 2: Python dependencies
```dockerfile
FROM python:${PYTHON_VERSION} AS python-deps

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/src

# Install system dependencies for Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better layer caching
WORKDIR /app
COPY pyproject.toml pyproject.toml

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e .
```

### Stage 3: Application
```dockerfile
FROM python:${PYTHON_VERSION} AS app

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/src \
    DJANGO_SETTINGS_MODULE=smart_recipe_inventory_manager.settings \
    DATABASE_URL=postgresql://app_user:app_secret@localhost:5432/app_db

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create app user
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Set working directory
WORKDIR /app

# Copy from Python dependencies stage
COPY --from=python-deps /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages

# Copy application code
COPY src/ src/
COPY scripts/ scripts/
COPY database/ database/
COPY data/ data/

# Create necessary directories
RUN mkdir -p data/outputs vector_store

# Set permissions
RUN chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose ports
EXPOSE 7860 5432

# Health check script
RUN cat > /app/healthcheck.sh << 'EOF'
#!/bin/bash
set -e

# Wait for PostgreSQL to be ready
for i in {1..30}; do
    if PGPASSWORD=app_secret pg_isready -h localhost -p 5432 -U app_user; then
        break
    fi
    sleep 1
done

# Wait for Ollama to be ready
for i in {1..30}; do
    if curl -s http://localhost:11434/api/version > /dev/null 2>&1; then
        break
    fi
    sleep 1
done

# Check if application can start
python -c "from smart_recipe_inventory_manager.config import settings; print('Configuration loaded successfully')"
EOF

RUN chmod +x /app/healthcheck.sh

# Default command (development)
CMD ["python", "-m", "smart_recipe_inventory_manager"]
```

## Development Overrides

For development, use `docker-compose.yml` which includes:

- Ollama service (with models pre-pulled)
- PostgreSQL with pgvector
- Application service

## Production Usage

```bash
# Build the image
./build.sh

# Run with Docker Compose
make deploy

# Or run individual containers
make run-app
make run-postgres
make run-ollama
```

## Build Script

```bash
def build.sh
#!/bin/bash
set -e

docker build --tag smart-recipe-inventory-manager:latest .
```

## Makefile

```makefile
.PHONY: build up down restart app postgres ollama logs clean

build:
	./build.sh

up:
	docker-compose up --build -d
	down:
	docker-compose down

restart: down up

app:
	docker-compose exec app sh

postgres:
	docker-compose exec postgres psql -U app_user -d app_db

ollama:
	docker-compose exec ollama curl -s http://localhost:11434/api/version

logs:
	docker-compose logs -f

clean:
	docker-compose down -v
	docker system prune -f
```

## Environment Variables

- `DATABASE_URL`: Override PostgreSQL connection string
- `OLLAMA_HOST`: Ollama service URL
- `GRADIO_HOST`/`GRADIO_PORT`: Gradio server binding
- `LLM_MODEL`/`VLM_MODEL`/`EMBEDDING_MODEL`: Ollama model names

## Health Check

The container includes a health check script that validates:
1. PostgreSQL is accessible
2. Ollama service is responding
3. Application configuration loads correctly

## Volume Management

- `data/`: Application data and recipe JSON
- `vector_store/`: pgvector embeddings
- `outputs/`: Generated files and exports

All volumes are managed via Docker Compose for persistence.

## Security Notes

- Application runs as non-root user (`appuser`)
- PostgreSQL credentials are environment variables
- Ollama runs without authentication (local access only)
- All AI models are executed locally - no data leaves the container

## Performance Optimizations

- Multi-stage build for smaller final image
- System packages installed only when needed
- Python dependencies cached via pip
- Non-root user for security

## Extension Points

To add new AI models:
1. Pull additional models via Ollama API
2. Update `settings.py` default model names
3. Add tests in `tests/`

To add new features:
1. Follow existing patterns in `src/`
2. Add unit tests in `tests/`
3. Update documentation in `docs/`
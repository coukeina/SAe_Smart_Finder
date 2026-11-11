# Smart Recipe & Inventory Manager

[![CI](https://github.com/coukeina/SAe_Smart_Finder/actions/workflows/ci.yml/badge.svg)](https://github.com/coukeina/SAe_Smart_Finder/actions/workflows/ci.yml)
![Python Version](https://img.shields.io/badge/python-3.12%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

Application web destinée à réduire le gaspillage alimentaire en analysant le contenu d'un réfrigérateur ou d'un placard à partir d'une photo, puis en suggérant des recettes adaptées aux ingrédients disponibles.

## Fonctionnalités

- Détection automatique des ingrédients à partir d'une image
- Analyse de l'inventaire et suivi des stocks
- Propositions de recettes adaptées aux produits disponibles
- Support d'un moteur IA local via Ollama
- Stockage PostgreSQL avec extension `pgvector`
- Interface web avec Gradio
- Persistance des données, de la base et du vector store via Docker

## Stack technique

- Python 3.12
- Gradio
- Ollama
- PostgreSQL 16 avec `pgvector`
- Docker / Docker Compose

## Prérequis

- Docker Engine
- Docker Compose
- Git

## Démarrage rapide

1. Cloner le dépôt :

```bash
git clone https://github.com/coukeina/SAe_Smart_Finder.git
cd SAe_Smart_Finder
```

2. Lancer les services avec Docker :

```bash
docker compose up --build
```

3. Importer et indexer les recettes :

```bash
python scripts/import_recipes.py
python scripts/index_recipe_embeddings.py
```

4. Lancer l'application :

```bash
python -m smart_recipe_inventory_manager
```

## Organisation du dépôt

```
SAe_Smart_Finder/
├── src/
│   ├── smart_recipe_inventory_manager/
│   │   ├── config.py               # Configuration Pydantic
│   │   ├── ui_gradio.py            # Interface Gradio principale
│   │   ├── ollama_client/          # Adaptateurs Ollama (VLM/LLM/Embedding)
│   │   ├── service/                # Couche d'orchestration métier
│   │   └── storage/                # Repositories PostgreSQL/pgvector
│   └── ...
│
├── tests/                           # Suite de tests complète (90% de couverture)
│   ├── test_level_one_contracts.py  # Tests contrats de niveau 1
│   ├── test_inventory.py           # Tests inventaire
│   └── ...
│
├── scripts/                         # Utilitaires de données
│   ├── import_recipes.py            # Import JSON → PostgreSQL
│   └── index_recipe_embeddings.py   # Indexation vectorielle
│
├── docs/                            # Documentation complète
│   ├── user_stories.md              # 8 histoires utilisateur HU01-HU08
│   ├── architecture.md              # Architecture en couches
│   ├── demo.md                      # Guide de présentation
│   ├── monitoring/                  # Rapports de sprint
│   └── ...
│
├── database/                        # Initialiseur PostgreSQL
│   └── init.sql
│
├── docker/                          # Dockerfile Python 3.12 slim
├── data/                            # Référentiel de recettes JSON
├── .github/workflows/ci.yml         # CI avec tests, linting, coverage ≥80%
├── CONTRIBUTING.md                  # Guide de contribution
└── README.md                        # Ce fichier
```

## Fonctionnement

- **Détection VLM** : Utilise `qwen3-vl:instruct` pour analyser les photos et identifier les ingrédients.
- **Recherche sémantique** : Recherche vectorielle via `pgvector` et `embeddinggemma` pour les suggestions pertinentes.
- **Génération de recettes** : Utilise `gemma4:12b` avec des contrats JSON stricts pour éviter les hallucinations.
- **Inventaire** : Gestion persistante via PostgreSQL avec suivi des stocks.

## Test et validation

```bash
# Tests unitaires avec couverture
coverage run -m pytest
coverage report -m --fail-under=80

# Linting et formatage
ruff check src/ tests/
ruff format --check src/ tests/
```

Le CI vérifie l'ensemble de la suite (plus 73 tests) avec une couverture >90%.

## Notes de version

- Version 0.1.0 – Preuve de concept anti-gaspillage alimentée par l'IA
- Livrable SAE : documentation complète en français, tests unitaires étendus et pipelines CI/CD matures.

## Cibles du projet

- **Documentation** : 8 histoires utilisateur HU01-HU08, architecture complète, 3 sprints techniques, guides de présentation et de recette.
- **Tests** : Passage de 52 tests à plus de 70 tests unitaires couvrant tous les contrats d'API.
- **CI/CD** : Tests, linting et formatage automatisés avec couverture >=80%, infrastructure Docker Compose avec PostgreSQL + pgvector + Ollama.
- **IA locale** : Ollama (qwen3-vl:instruct, gemma4:12b, embeddinggemma) sans appel API cloud, respect de la vie privée.
- **Validation** : Tests adversariaux, gestion des erreurs, contrats Pydantic stricts pour prévenir les hallucinations de l'IA.

## Contributions

Voir [CONTRIBUTING.md](CONTRIBUTING.md) pour les directives de contribution, la stratégie de branches et le workflow de PR.

---
*Projet réalisé dans le cadre de la SAE Smart Recipe & Inventory Manager (AntiGaspillage). Toutes les améliorations d'IA sont exécutées localement via Ollama pour préserver la vie privée et éviter les coûts externes.*

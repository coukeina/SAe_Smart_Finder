# Architecture — SmartFinder

## Vue d'ensemble

SmartFinder est une application web anti-gaspillage alimentaire. L'utilisateur prend une photo de son frigo ou de ses aliments, l'IA détecte les ingrédients, recherche des recettes similaires dans une base de données, puis génère des recettes adaptées uniquement aux ingrédients disponibles.

Toute l'IA tourne **en local** via Ollama — aucune API cloud, aucune donnée envoyée à l'extérieur.

---

## Architecture en couches

```
┌─────────────────────────────────────────────────┐
│                 COUCHE UI                        │
│         Gradio (ui_gradio.py)                   │
│   Affichage, callbacks, formatage des résultats  │
└───────────────────┬─────────────────────────────┘
                    │ appelle uniquement
┌───────────────────▼─────────────────────────────┐
│              COUCHE SERVICE                      │
│   service/core.py        service/inventory.py   │
│   Orchestration métier,  Validation et           │
│   validation IA,         gestion de l'inventaire │
│   anti-hallucination                             │
└───────┬───────────────────────────┬─────────────┘
        │                           │
┌───────▼───────────┐   ┌───────────▼─────────────┐
│  COUCHE ADAPTERS  │   │    COUCHE STORAGE        │
│  ollama_client/   │   │    storage/              │
│  - vlm.py (VLM)  │   │    - recipe_repository   │
│  - llm.py (LLM)  │   │    - inventory_repository│
│  - embedding.py  │   │    - base.py (connexion) │
│  - base.py       │   └───────────┬──────────────┘
└───────┬───────────┘               │
        │                           │
┌───────▼───────────┐   ┌───────────▼─────────────┐
│  Ollama (Docker)  │   │  PostgreSQL 16 (Docker)  │
│  - qwen3-vl       │   │  + pgvector extension    │
│  - gemma4:12b     │   │  - recipes               │
│  - embeddinggemma │   │  - ingredients           │
│  port 11434       │   │  - inventory             │
└───────────────────┘   │  - recipe_embeddings     │
                        └──────────────────────────┘
```

**Règle fondamentale :** la couche UI (`ui_gradio.py`) n'importe jamais directement les classes Ollama. Elle passe toujours par la couche service.

---

## Flux principal : photo → recettes

```
1. Utilisateur upload une photo
        │
        ▼
2. OllamaVLM.detect_ingredients()
   - Encode la photo en base64
   - POST /api/chat → qwen3-vl:instruct
   - Prompt contraint : liste uniquement les aliments visibles
   - Réponse JSON validée par Pydantic (IngredientDetection)
   - Retry 1 fois si JSON malformé
        │
        ▼
3. OllamaEmbedding.embed()
   - Concatène les noms des ingrédients détectés
   - POST /api/embed → embeddinggemma
   - Retourne un vecteur de 768 dimensions
        │
        ▼
4. search_recipes() — PostgreSQL + pgvector
   - Recherche les 100 recettes les plus proches (distance cosine)
   - Filtre celles qui ont au moins 1 ingrédient en commun
   - Classe par : taux de couverture DESC, similarité cosine DESC
   - Retourne les 5 meilleures candidates
        │
        ▼
5. OllamaLLM.generate_json()
   - POST /api/generate → gemma4:12b
   - Prompt : ingrédients disponibles + recettes candidates + préférences
   - Réponse JSON validée par Pydantic (GeneratedRecipes)
   - Vérification anti-hallucination : chaque ingrédient de la recette
     doit être présent dans la liste détectée (normalisation accents/pluriels)
   - Retry 1 fois si JSON malformé
        │
        ▼
6. Gradio affiche les recettes + métriques
   (latence VLM, latence LLM, tokens/s, score cosine)
```

---

## Flux inventaire : confirmation et persistance

```
1. Tableau d'ingrédients détectés (modifiable par l'utilisateur)
        │
        ▼
2. save_confirmed_inventory()
   - Validation : noms non vides, quantités ≥ 0, pas de doublons
   - Pour chaque ingrédient :
     * Upsert dans la table ingredients (clé : normalized_name)
     * Upsert dans la table inventory (clé : ingredient_id)
     * Si déjà présent → mise à jour du stock, pas de doublon
        │
        ▼
3. list_inventory()
   - SELECT avec JOIN ingredients + ORDER BY normalized_name
   - Retourné et affiché dans le tableau inventaire Gradio
```

---

## Schéma de base de données

```sql
recipes              -- recettes importées du référentiel JSON
  id, title, description, steps (JSONB), source, created_at

ingredients          -- référentiel normalisé des ingrédients
  id, name, normalized_name (UNIQUE)

recipe_ingredients   -- association recette ↔ ingrédient
  recipe_id, ingredient_id, quantity, unit

inventory            -- stock courant de l'utilisateur
  id, ingredient_id (UNIQUE), quantity, unit, maturity,
  confidence, needs_confirmation, created_at

recipe_embeddings    -- vecteurs pgvector pour la recherche sémantique
  recipe_id (PK), content (TEXT), embedding VECTOR(768),
  INDEX HNSW vector_cosine_ops
```

---

## Choix techniques — pourquoi ces outils

| Outil | Pourquoi ce choix |
|---|---|
| **Ollama** | Exécution 100% locale, pas de clé API, pas de coût par requête, modèles open-source |
| **qwen3-vl:instruct** | Modèle vision-langage (VLM) capable d'analyser des images et de répondre en JSON contraint |
| **gemma4:12b** | LLM léger et rapide pour la génération de texte structuré (JSON), bon rapport qualité/vitesse |
| **embeddinggemma** | Modèle d'embedding compatible avec les dimensions 768 attendues par pgvector |
| **PostgreSQL + pgvector** | Base relationnelle robuste + extension vectorielle pour la recherche sémantique en SQL natif, sans service externe |
| **Gradio** | Framework Python qui génère une UI web complète avec peu de code, adapté aux projets IA académiques |
| **Pydantic v2** | Validation des schémas JSON retournés par les LLMs — protège contre les hallucinations de format |
| **Docker Compose** | Orchestration reproductible des 3 services (pg, ollama, app) avec healthchecks et dépendances |

---

## Gestion des erreurs et résilience

| Situation | Comportement |
|---|---|
| Ollama inaccessible | `OllamaConnectionError` → message lisible dans Gradio |
| JSON malformé du VLM | Retry 1 fois, puis `OllamaResponseError` |
| JSON malformé du LLM | Retry 1 fois, puis `OllamaResponseError` |
| Context window dépassé | `OllamaContextError` → **pas de retry** → message "photo trop chargée" |
| Erreur HTTP 503/429 | Retry jusqu'à 3 fois avec délai exponentiel |
| Ingrédient inventé par le LLM | Recette rejetée côté service, jamais affichée |
| Aucun ingrédient détecté | Arrêt explicite avant d'appeler le LLM |
| PostgreSQL indisponible | `InventoryRepositoryError` → message lisible dans Gradio |

---

## Structure des fichiers

```
SAe_Smart_Finder/
├── src/smart_recipe_inventory_manager/
│   ├── config.py                    # Settings Pydantic (env vars)
│   ├── ui_gradio.py                 # Interface Gradio + callbacks
│   ├── ollama_client/
│   │   ├── base.py                  # Transport HTTP async, retry, métriques
│   │   ├── vlm.py                   # Adaptateur modèle vision (VLM)
│   │   ├── llm.py                   # Adaptateur modèle texte (LLM)
│   │   └── embedding.py             # Adaptateur modèle embedding
│   ├── service/
│   │   ├── core.py                  # Orchestration métier principale
│   │   ├── inventory.py             # Validation et gestion inventaire
│   │   └── models.py                # Schémas Pydantic (IngredientDetection, GeneratedRecipe...)
│   └── storage/
│       ├── base.py                  # Connexion PostgreSQL
│       ├── recipe_repository.py     # Requêtes recettes + pgvector
│       └── inventory_repository.py  # Requêtes inventaire
├── tests/
│   ├── fixtures/level1_scenarios.json
│   ├── test_level_one_contracts.py  # Tests contrats IA + Gradio callbacks
│   ├── test_inventory.py            # Tests inventaire service + repository
│   └── test_recipe_embeddings.py    # Tests indexation pgvector
├── scripts/
│   ├── import_recipes.py            # Import du JSON de recettes dans PostgreSQL
│   └── index_recipe_embeddings.py   # Calcul et stockage des embeddings
├── database/
│   └── init.sql                     # Schéma PostgreSQL (idempotent)
├── docker/
│   └── Dockerfile                   # Image Python 3.12 slim
├── data/
│   └── recipes.json                 # Référentiel de recettes (source)
├── docs/
│   ├── user_stories.md              # User stories du projet
│   ├── architecture.md              # Ce fichier
│   └── monitoring/sprint_00.md      # Suivi des livrables V1/V2/V3
├── docker-compose.yml
├── pyproject.toml
└── README.md
```

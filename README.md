# Smart Recipe & Inventory Manager

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
git clone https://github.com/coukeina/SA--Smart-recipe-and-inventory-manager--Anti-Gaspillage/
cd SA--Smart-recipe-and-inventory-manager--Anti-Gaspillage
```

2. Lancer les services avec Docker :

```bash
docker compose up --build
```

3. Ouvrir l'application dans le navigateur :

```text
http://localhost:7860
```

4. Initialiser la base de données après le premier démarrage :

```bash
docker compose exec -T pg psql -U app_user -d app_db -c "CREATE EXTENSION IF NOT EXISTS vector;"
Get-Content database/init.sql | docker compose exec -T pg psql -U app_user -d app_db
```

5. Pour arrêter les services :

```bash
docker compose down
```

## Services Docker

Le projet utilise une configuration Docker Compose avec trois services :

- `pg` : base PostgreSQL 16 avec `pgvector`, accessible par l'application sur le réseau Docker
- `ollama` : moteur IA local exposé sur le port `11434`
- `app` : application Python/Gradio construite à partir du Dockerfile, exposée sur le port `7860`

Le port PostgreSQL est publié automatiquement par Docker uniquement pour le débogage. Pour connaître le port attribué sur la machine hôte :

```bash
docker compose port pg 5432
```

Le conteneur applicatif attend que PostgreSQL soit sain avant de démarrer et communique avec les deux services via le réseau interne Docker. Les variables utilisées sont :

```env
OLLAMA_HOST=http://ollama:11434
LLM_MODEL=gemma4:12b
VECTOR_DB_PATH=/app/vector_store
DB_HOST=pg
DB_PORT=5432
DB_NAME=app_db
DB_USER=app_user
DB_PASSWORD=app_secret
```

## Conteneur applicatif

Le Dockerfile du projet :

- utilise Python 3.12 slim
- installe les dépendances Poetry du projet
- copie le code dans le conteneur
- expose le port 7860
- lance `ui_gradio.py` au démarrage

## Persistance

Les données sont conservées via des volumes Docker :

- `ollama_data` pour le service Ollama
- `pg_data_smart_recipe_and_inventory_manager_anti_gaspillage` pour PostgreSQL
- `./data` monté dans le conteneur application pour les vecteurs et les logs

Pour supprimer également les volumes et réinitialiser les données locales :

```bash
docker compose down -v
```

## Base de données

Le fichier [`database/init.sql`](database/init.sql) crée le schéma PostgreSQL suivant :

- `recipes` : recettes et étapes de préparation au format JSON
- `ingredients` : ingrédients avec leur nom normalisé
- `recipe_ingredients` : association entre recettes et ingrédients
- `inventory` : ingrédients détectés dans l'inventaire, quantités, maturité et confiance
- `recipe_embeddings` : contenu des recettes et vecteurs de dimension 768

L'extension `vector` doit être activée avant la création de la table `recipe_embeddings`. Le script d'initialisation est idempotent grâce à `CREATE TABLE IF NOT EXISTS` et peut être rejoué sans recréer les tables existantes.

## Notes

- L'API Ollama n'est pas installée dans le conteneur applicatif ; elle est fournie par le service dédié `ollama`.
- PostgreSQL n'est pas installé dans le conteneur applicatif ; il est fourni par le service `pg`.
- La configuration Docker est pensée pour un environnement local de démonstration et de développement.


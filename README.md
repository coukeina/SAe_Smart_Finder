# Smart Recipe & Inventory Manager

Application web destinée à réduire le gaspillage alimentaire en analysant le contenu d'un réfrigérateur ou d'un placard à partir d'une photo, puis en suggérant des recettes adaptées aux ingrédients disponibles.

## Fonctionnalités

- Détection automatique des ingrédients à partir d'une image
- Analyse de l'inventaire et suivi des stocks
- Propositions de recettes adaptées aux produits disponibles
- Support d'un moteur IA local via Ollama
- Interface web avec Gradio
- Persistance des données et des modèles/vector store via Docker

## Stack technique

- Python 3.12
- Gradio
- Ollama
- Docker / Docker Compose

## Prérequis

<<<<<<< HEAD
```
git clone https://github.com/coukeina/SAe_Smart_Finder/
=======
- Docker Engine
- Docker Compose
- Git

## Démarrage rapide

1. Cloner le dépôt :

```bash
git clone https://github.com/coukeina/SA--Smart-recipe-and-inventory-manager--Anti-Gaspillage/
cd SA--Smart-recipe-and-inventory-manager--Anti-Gaspillage
>>>>>>> dev
```

2. Vérifier ou créer le fichier `.env` si nécessaire :

```env
OLLAMA_HOST=http://ollama:11434
LLM_MODEL=gemma4:12b
VECTOR_DB_PATH=/app/data
```

3. Lancer les services avec Docker :

```bash
docker compose up --build
```

4. Ouvrir l'application dans le navigateur :

```text
http://localhost:7860
```

5. Pour arrêter les services :

```bash
docker compose down
```

## Services Docker

Le projet utilise une configuration Docker Compose avec deux services :

- `ollama` : moteur IA local exposé sur le port `11434`
- `app` : application Python/Gradio construite à partir du Dockerfile, exposée sur le port `7860`

Le conteneur applicatif est configuré pour communiquer avec Ollama via le réseau interne Docker, avec la variable d'environnement :

```env
OLLAMA_HOST=http://ollama:11434
```

## Conteneur applicatif

Le Dockerfile du projet :

- utilise Python 3.12 slim
- installe les dépendances du projet
- copie le code dans le conteneur
- expose le port 7860
- lance l'application Gradio au démarrage

## Persistance

Les données sont conservées via un volume Docker pour les éléments liés à Ollama et à l'application :

- `ollama_data` pour le service Ollama
- `./data` monté dans le conteneur application

## Notes

- L'API Ollama n'est pas installée dans le conteneur applicatif ; elle est fournie par le service dédié `ollama`.
- La configuration Docker est pensée pour un environnement local de démonstration et de développement.


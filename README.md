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

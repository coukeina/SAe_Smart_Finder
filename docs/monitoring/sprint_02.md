# Sprint 02 — Base de Données, RAG et Inventaire (Semaines 4 à 7)

## Objectifs du Sprint
- Intégration de PostgreSQL 16 avec l'extension `pgvector` pour la recherche sémantique de recettes.
- Implémentation du script d'importation des recettes (`scripts/import_recipes.py`) et du calcul des embeddings vectoriels 768d via `embeddinggemma` (`scripts/index_recipe_embeddings.py`).
- Développement du module d'inventaire persistant (`service/inventory.py` et `storage/inventory_repository.py`) permettant de sauvegarder les ingrédients confirmés.

## Backlog & User Stories (HU05, HU06, HU07)
- **HU05** : Enregistrer les ingrédients détectés dans l'inventaire persistant.
- **HU06** : Consulter son inventaire actuel depuis la base de données.
- **HU07** : Trouver des recettes similaires grâce à la recherche sémantique vectorielle (`pgvector`).

## Définition of Ready (DoR)
- Schéma relationnel et tables `recipes`, `ingredients`, `recipe_ingredients`, `inventory`, `recipe_embeddings` définis dans `database/init.sql`.
- Index HNSW configuré pour la similarité cosine.

## Définition of Done (DoD)
- Repositories testés unitairement (mocking des connexions psycopg).
- Validation de l'intégrité des données et rejet des quantités négatives / doublons.
- Intégration dans la CI.

## Tableau de Suivi et Traçabilité

| ID | User Story | Statut | Preuve de test / Fichier associé |
|---|---|---|---|
| HU05 | Enregistrer l'inventaire | ✅ Terminé | `tests/test_inventory.py` |
| HU06 | Consulter l'inventaire | ✅ Terminé | `tests/test_inventory.py` |
| HU07 | Recherche sémantique RAG | ✅ Terminé | `tests/test_recipe_embeddings.py` |

## Rétrospective du Sprint
- **Points positifs :** La recherche vectorielle `pgvector` offre une excellente pertinence dans les suggestions de recettes par rapport aux ingrédients détectés.
- **Axes d'amélioration :** Gestion des connexions en cas de coupure de la base de données à consolider.

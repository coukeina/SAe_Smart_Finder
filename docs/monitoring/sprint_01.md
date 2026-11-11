# Sprint 01 — Socle Technique et Pipeline V1 (Semaines 1 à 3)

## Objectifs du Sprint
- Initialisation du dépôt Git et structuration modulaire (UI, services, adaptateurs, stockage).
- Mise en place de l'environnement de conteneurisation Docker Compose (PostgreSQL 16 + pgvector et Ollama).
- Implémentation du parcours nominal V1 : prise de photo, détection VLM (`qwen3-vl:instruct`), validation par schémas Pydantic et génération de recettes LLM (`gemma4:12b`) avec barrière anti-hallucination.

## Backlog & User Stories (HU01, HU02, HU03)
- **HU01** : Analyser une photo pour détecter les ingrédients (VLM).
- **HU02** : Corriger les ingrédients détectés avant de générer des recettes.
- **HU03** : Obtenir des suggestions de recettes anti-gaspillage sans hallucination.

## Définition of Ready (DoR)
- User stories formalisées au format *Étant donné / Quand / Alors*.
- Contrats d'API et schémas Pydantic validés.
- Environnement Docker fonctionnel en local.

## Définition of Done (DoD)
- Code testé par la suite unitaire (tests mockés de niveau 1).
- Validation du linter (`ruff check`) et du formatage.
- Code fusionné sur la branche d'intégration `dev`.

## Tableau de Suivi et Traçabilité

| ID | User Story | Statut | Preuve de test / Fichier associé |
|---|---|---|---|
| HU01 | Analyser une photo (VLM) | ✅ Terminé | `tests/test_level_one_contracts.py` |
| HU02 | Corriger les ingrédients | ✅ Terminé | `src/smart_recipe_inventory_manager/ui_gradio.py` |
| HU03 | Recettes anti-gaspillage | ✅ Terminé | `tests/test_level_one_contracts.py` |

## Rétrospective du Sprint
- **Points positifs :** Excellente mise en place de la architecture en couches et des schémas de validation Pydantic évitant les plantages sur les JSON mal formés de l'IA.
- **Axes d'amélioration :** Nécessité d'optimiser les temps de réponse Ollama et de formaliser un cache local pour les tests.

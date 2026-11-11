# Sprint 03 — Refonte UI/UX, Robustesse et Documentation (Semaines 8 à 10)

## Objectifs du Sprint
- Refonte complète de l'interface Gradio (`ui_gradio.py`) : design moderne, thèmes, gestion des portions et du temps de préparation.
- Renforcement de la couverture de tests (passage à 57+ tests unitaires robustes et tests adversariaux).
- Finalisation de la documentation technique et de la CI/CD (GitHub Actions, Ruff, Coverage 80%+).

## Backlog & User Stories (HU04, HU08)
- **HU04** : Personnaliser les recettes selon ses préférences (portions, temps, texte libre).
- **HU08** : Consulter les performances de l'analyse (latences VLM/LLM, tokens/s, score cosine).

## Définition of Ready (DoR)
- Maquettes et structure des composants Gradio validées.
- Exigences du tuteur et du jury recensées (documentation, user stories en français).

## Définition of Done (DoD)
- Suite de tests 100% au vert.
- Couverture de code supérieure à 80% (mesurée par `coverage.py`).
- Dossier `docs/` complet (architecture, user stories, guides, scénarios de test).

## Tableau de Suivi et Traçabilité

| ID | User Story | Statut | Preuve de test / Fichier associé |
|---|---|---|---|
| HU04 | Personnaliser les recettes | ✅ Terminé | `tests/test_level_one_contracts.py` |
| HU08 | Consulter les performances | ✅ Terminé | `tests/test_level_one_contracts.py` |

## Rétrospective du Sprint
- **Points positifs :** L'interface est devenue particulièrement soignée et professionnelle (thème sombre/clair, design épuré), et la couverture de test atteint 90%.
- **Axes d'amélioration :** Projet prêt pour la livraison finale et la soutenance.

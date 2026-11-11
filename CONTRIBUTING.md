# CONTRIBUTING — Guide de contribution

## Stratégie de branches

Notre dépôt suit un workflow strict de type Git Flow simplifié :

| Branche | Rôle |
|---|---|
| `main` | Version stable, validée et livrable (tags de version). On ne commit **jamais** directement dessus. |
| `dev` | Branche d'intégration principale. Toutes les branches de travail fusionnent ici en premier. |
| `feat/<nom>` | Nouvelle fonctionnalité (ex. `feat/vector-recipe-search`) |
| `fix/<nom>` | Correction de bug (ex. `fix/json-output-timeout`) |
| `docs/<nom>` | Documentation et suivi de projet (ex. `docs/user-stories`) |
| `chore/<nom>` | Maintenance, nettoyage, CI/CD et pre-commit (ex. `chore/ci-coverage`) |

**Workflow :**
```
feat/xxx ou docs/xxx  →  dev  →  main (via Pull Request validée)
```

## Convention de commits

Format obligatoire : `type(scope): description courte en français`

| Type | Quand l'utiliser |
|---|---|
| `feat` | Nouvelle fonctionnalité |
| `fix` | Correction de bug |
| `docs` | Documentation uniquement |
| `test` | Ajout ou modification de tests unitaires |
| `chore` | Maintenance, dépendances, configuration CI |
| `refactor` | Refactoring du code sans modification fonctionnelle |

**Exemples corrects :**
```
feat(ui): connecter les préférences portions et temps au LLM
fix(ui): afficher la section recettes après génération
docs(user-stories): ajouter les user stories du projet
test(adversarial): ajouter des tests robustes de non-régression
chore(ci): configurer le seuil de couverture à 80%
```

## Validation et Qualité du Code

### Validation locale requise avant PR

Exécuter manuellement **toutes** les commandes suivantes avant de soumettre une Pull Request (valider directement sur la branche `feat/expand-tests`) :

1. **Démarrage de l'environnement Docker**
   ```bash
   docker compose up --build -d
   ```

2. **Importation et indexation des recettes** (une fois par environnement)
   ```bash
   python scripts/import_recipes.py
   python scripts/index_recipe_embeddings.py
   ```

3. **Validation du linter et formatage**
   ```bash
   ruff check src/ tests/
   ruff format --check src/ tests/
   ```

4. **Suite complète de tests unitaires avec couverture**
   ```bash
   coverage run -m pytest
   coverage report -m --fail-under=80
   ```

5. **Vérification manuelle rapide de l'application** (optionnel)
   ```bash
   python -m smart_recipe_inventory_manager
   ```
   (Ouvrir l'application dans un navigateur : http://localhost:7860 et exécuter un scénario de base rapide)

### Processus de Pull Request

1. **Créer une branche explicite à partir de `dev`**
   ```bash
   git checkout dev
   git checkout -b feat/<nom-travaillable>
   ```

2. **Respecter les conventions de commit**
   ```
   feat(ui): connecter les préférences portions et temps au LLM
   fix(ui): afficher la section recettes après génération
   docs(user-stories): ajouter les user stories du projet
   test(adversarial): ajouter des tests robustes de non-régression
   chore(ci): configurer le seuil de couverture à 80%
   ```

3. **Valider localement** les changements avec tous les tests, linter et formatage avant la création de PR.

4. **Remplir intégralement le modèle de Pull Request** (objectif, US liées, validation des tests et de la couverture, scénarios de test réels).

5. **Soumettre la PR** vers `dev`.

6. **Révision et fusion** (fusion avec `dev` si toutes les validations passent).

## Exigences spécifiques à ce projet

### Documentation complète en français
- Toutes les **8 histoires utilisateur** HU01-HU08 sont rédigées en français dans `docs/user_stories.md`
- **Architecture** documentée avec diagrammes et schéma de base de données
- **3 sprints techniques** (Sprint 01 à 03) couvrant tous les livrables V1/V2/V3
- **Guide de présentation** (`docs/demo.md`) avec déroulé utilisateur étape par étape
- **Protocole de recette** (`docs/recette.md`) listant tous les scénarios de test fonctionnel

### Validation requise

1. **Exécution locale :**
   ```bash
   # Docker compose
   docker compose up --build
   
   # Importer et indexer les recettes (exécuter une fois)
   python scripts/import_recipes.py
   python scripts/index_recipe_embeddings.py
   
   # Tests unitaires
   pytest
   ```

2. **Suite de tests minimum** :
   - Toutes les histoires utilisateur HU01-HU08 doivent avoir au moins une preuve de test associée
   - Tests unitaires pour les contrats de couche (UI → Service → Adaptateurs)
   - Tests adversariaux couvrant tous les points de terminaison Ollama
   - Tests d'intégration pour l'inventaire et la recherche vectorielle

3. **Qualité de code**
   - 100% de tests passant
   - Coverage >= 80% (mesurée par `coverage.py`)
   - Linter et formatage Ruff applicables

### Contraintes spécifiques au projet

- **IA locale uniquement** : Utiliser Ollama (`qwen3-vl:instruct`, `gemma4:12b`, `embeddinggemma`) sans aucun appel API cloud
- **IA sans coûts** : Pas de clés API, pas de frais externes par requête
- **Validation anti-hallucination** : Contrats JSON Pydantic stricts pour tous les adaptateurs VLM et LLM
- **Authentification Git** : Tous les commits doivent être sous profil `ahmedxfikri` (pas d'attribution Claude/Copilot)
- **Contraintes linguistiques** : Toutes les chaînes d'interface utilisateur et toutes les documentation doivent être en français

## Validation de livraison finale

Lors de la préparation de la livraison, vérifier les points suivants :

1. **CI verte** sur la branche `dev` avec tous les tests passant
2. **Tests localisés** avec éxécution manuelle réussie
3. **Documentation** complète et prête à être présentée au jury
4. **Code bien structuré** avec une couverture de test minimale >= 80%
5. **Toutes les user stories** HU01-HU08 sont implémentées et testées
6. **Guides de présentation** (`docs/demo.md` et `docs/recette.md`) finalisés avec les scénarios de test actualisés

Après la livraison, fusionner `feat/expand-tests` dans `dev`, puis fusionner `dev` dans `main` via PR validée avec toutes les preuves de test actualisées.
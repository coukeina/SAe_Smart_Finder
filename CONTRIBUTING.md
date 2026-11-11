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

Avant de soumettre une Pull Request, assurez-vous que les commandes suivantes passent avec succès en local :

```powershell
# 1. Vérification du linter
ruff check src/ tests/

# 2. Vérification du formatage
ruff format --check src/ tests/

# 3. Lancement des tests unitaires et de couverture
coverage run -m pytest
coverage report -m --fail-under=80
```

## Processus de Pull Request

1. Créer une branche explicite à partir de `dev`.
2. Respecter les conventions de commit.
3. Remplir intégralement le modèle de Pull Request (objectif, US liées, validation des tests et de la couverture).
4. Soumettre la PR vers `dev`.

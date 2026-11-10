# CONTRIBUTING — Guide de contribution

## Branches

| Branche | Rôle |
|---|---|
| `main` | Version stable, déployable. On ne commit **jamais** directement dessus. |
| `dev` | Branche d'intégration. Les features mergent ici après review. |
| `feat/<nom>` | Nouvelle fonctionnalité (ex. `feat/preferences-ui`) |
| `fix/<nom>` | Correction de bug (ex. `fix/recipes-section-hidden`) |
| `docs/<nom>` | Documentation uniquement (ex. `docs/user-stories`) |
| `chore/<nom>` | Maintenance, nettoyage, CI (ex. `chore/remove-venv`) |

**Workflow :**
```
feat/xxx  →  dev  →  main (via PR pour chaque étape)
```

## Convention de commits

Format : `type(scope): description courte en français`

| Type | Quand l'utiliser |
|---|---|
| `feat` | Nouvelle fonctionnalité |
| `fix` | Correction de bug |
| `docs` | Documentation uniquement |
| `test` | Ajout ou modification de tests |
| `chore` | Maintenance, dépendances, CI |
| `refactor` | Refactoring sans changement de comportement |

**Exemples corrects :**
```
feat(ui): connecter les préférences portions et temps au LLM
fix(ui): afficher la section recettes après génération
docs(user-stories): ajouter les 8 user stories du projet
chore(git): supprimer .venv du suivi Git
```

## Pull Requests

- Toujours depuis une branche `feat/`, `fix/`, `docs/` ou `chore/` vers `dev`
- Remplir le template de PR (titre, description, tests effectués)
- Au moins 1 reviewer avant de merger

## Tests

```powershell
# Depuis SAe_Smart_Finder/
python -m unittest discover -s tests -v
python -m ruff check src tests
```

Les tests ne nécessitent ni Ollama ni PostgreSQL.

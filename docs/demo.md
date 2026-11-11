# Protocole de Démonstration — SmartFinder

Ce guide détaille les étapes pas à pas pour réaliser une démonstration fluide et réussie de l'application SmartFinder devant le jury ou le tuteur.

---

## 1. Préparation de l'environnement (Avant la démo)
1. S'assurer que Docker Desktop est lancé.
2. Démarrer les conteneurs :
   ```bash
   docker compose up --build -d
   ```
3. Vérifier que les recettes sont bien importées et indexées :
   ```bash
   python scripts/import_recipes.py
   python scripts/index_recipe_embeddings.py
   ```

## 2. Lancement de l'application
1. Ouvrir le navigateur à l'adresse : **`http://localhost:7860`**
2. Vérifier l'affichage de l'interface moderne (en-tête *SmartFinder*, badge d'état, slogan, sections numérotées).

## 3. Déroulé du parcours utilisateur (Live Demo)
1. **Étape 01 — Photo :** Glisser-déposer une photo de test (ex: frigo ou fruits).
2. **Analyse VLM :** Cliquer sur « Afficher les ingrédients ». Montrer le tableau interactif rempli par l'IA et les métriques de latence.
3. **Correction :** Modifier rapidement un ingrédient dans le tableau pour montrer la flexibilité de l'interface (HU02).
4. **Préférences & Recettes :** Choisir le nombre de portions et le temps, puis cliquer sur « Proposer des recettes ». Montrer les cartes de recettes générées et la barrière anti-hallucination.
5. **Inventaire :** Cliquer sur « Confirmer et enregistrer l'inventaire » pour valider la persistance en base de données PostgreSQL.

## 4. Preuve de robustesse (Tests & CI)
1. Ouvrir le terminal et lancer la suite de tests unitaires pour prouver que tout est validé :
   ```bash
   pytest
   ```
2. Montrer le badge de la CI (GitHub Actions) vert sur le dépôt GitHub.

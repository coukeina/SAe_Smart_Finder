# Histoires utilisateur — SmartFinder (Sujet 10 : Gestionnaire de recettes et d'inventaire anti-gaspillage)

> Format : **En tant que** [rôle], **je veux** [action] **afin de** [bénéfice]
> Critères d'acceptation au format **Étant donné / Quand / Alors**

---

## HU01 — Analyser une photo pour détecter les ingrédients

**En tant qu'** utilisateur,
**je veux** prendre ou importer une photo de mon frigo ou de mes aliments,
**afin de** connaître automatiquement les ingrédients disponibles sans avoir à les saisir manuellement.

**Critères d'acceptation :**

- **Étant donné** une photo contenant des aliments visibles
- **Quand** je clique sur « Analyser ma photo »
- **Alors** le système affiche la liste des ingrédients détectés avec leur nom, quantité estimée et maturité si visible

- **Étant donné** une photo sans aliment identifiable
- **Quand** je clique sur « Analyser ma photo »
- **Alors** le système affiche un message clair : aucun ingrédient détecté, invitation à réessayer avec une meilleure photo

- **Étant donné** aucune photo sélectionnée
- **Quand** je clique sur « Analyser ma photo »
- **Alors** le système affiche un message d'erreur sans lancer l'analyse

**Implémentation :** `ui_gradio.show_ingredients` → `service/core.analyze_photo` → `ollama_client/vlm.py`

---

## HU02 — Corriger les ingrédients détectés avant de générer des recettes

**En tant qu'** utilisateur,
**je veux** modifier, ajouter ou supprimer des ingrédients dans le tableau de détection,
**afin de** corriger les erreurs de l'analyse avant de lancer la génération de recettes.

**Critères d'acceptation :**

- **Étant donné** une liste d'ingrédients affichée après analyse
- **Quand** je modifie un nom, une quantité ou une maturité dans le tableau
- **Alors** les modifications sont prises en compte pour la suite du parcours

- **Étant donné** un ingrédient incorrect détecté (ex. : « carton » au lieu de « lait »)
- **Quand** je corrige la ligne directement dans le tableau
- **Alors** la génération de recettes utilise la version corrigée

**Implémentation :** tableau interactif dans `ui_gradio.build_demo`

---

## HU03 — Obtenir des suggestions de recettes anti-gaspillage

**En tant qu'** utilisateur,
**je veux** obtenir des recettes réalisables uniquement avec les ingrédients que j'ai,
**afin d'** éviter le gaspillage alimentaire et de ne pas avoir à acheter des ingrédients supplémentaires.

**Critères d'acceptation :**

- **Étant donné** une liste d'ingrédients validée
- **Quand** je clique sur « Proposer des recettes »
- **Alors** le système propose des recettes contenant uniquement les ingrédients détectés, sans en inventer
- **Et** chaque recette affiche : titre, liste d'ingrédients, étapes de préparation, temps de cuisson

- **Étant donné** une liste d'ingrédients validée
- **Quand** le modèle de langage propose une recette avec un ingrédient absent de la liste
- **Alors** cette recette est rejetée automatiquement et non affichée à l'utilisateur

- **Étant donné** que le service d'intelligence artificielle est indisponible
- **Quand** je demande des recettes
- **Alors** un message lisible s'affiche : « Le service est inaccessible, veuillez réessayer »

**Implémentation :** `ui_gradio.propose_recipes` → `service/core.recipes_from_ingredients` → `ollama_client/llm.py`

---

## HU04 — Personnaliser les recettes selon ses préférences

**En tant qu'** utilisateur,
**je veux** indiquer le nombre de personnes, le temps disponible et mes préférences alimentaires,
**afin d'** obtenir des recettes adaptées à ma situation du moment.

**Critères d'acceptation :**

- **Étant donné** des préférences saisies (ex. : « 2 personnes », « moins de 30 min », « végétarien »)
- **Quand** je clique sur « Proposer des recettes »
- **Alors** ces préférences sont transmises au modèle de langage
- **Et** les recettes générées tiennent compte du temps et du nombre de personnes

- **Étant donné** aucune préférence saisie
- **Quand** je clique sur « Proposer des recettes »
- **Alors** le système génère des recettes sans contrainte particulière

**Implémentation :** champs nombre de personnes, temps disponible et texte libre → `ui_gradio.propose_recipes` → paramètre `preferences` de `recipes_from_ingredients`

---

## HU05 — Enregistrer les ingrédients détectés dans mon inventaire

**En tant qu'** utilisateur,
**je veux** sauvegarder les ingrédients confirmés dans un inventaire persistant,
**afin de** garder une trace de mon stock et de l'utiliser pour les prochaines analyses.

**Critères d'acceptation :**

- **Étant donné** une liste d'ingrédients affichée après analyse
- **Quand** je clique sur « Confirmer et enregistrer l'inventaire »
- **Alors** les ingrédients sont enregistrés dans la base de données
- **Et** un message de confirmation indique le nombre d'ingrédients enregistrés

- **Étant donné** un ingrédient déjà présent dans l'inventaire
- **Quand** je le confirme à nouveau
- **Alors** l'entrée existante est mise à jour sans créer de doublon

- **Étant donné** une quantité négative saisie dans le tableau
- **Quand** je tente de confirmer l'inventaire
- **Alors** une erreur de validation s'affiche et aucune donnée n'est enregistrée

**Implémentation :** `ui_gradio.confirm_inventory` → `service/inventory.save_confirmed_inventory` → `storage/inventory_repository.py`

---

## HU06 — Consulter son inventaire actuel

**En tant qu'** utilisateur,
**je veux** voir la liste de tous les ingrédients enregistrés dans mon stock,
**afin de** savoir ce que j'ai chez moi sans avoir à rouvrir le frigo.

**Critères d'acceptation :**

- **Étant donné** des ingrédients précédemment enregistrés
- **Quand** j'ouvre l'application
- **Alors** l'inventaire est automatiquement chargé depuis la base de données
- **Et** chaque ligne affiche : nom, quantité, unité, maturité, niveau de confiance, statut de confirmation

- **Étant donné** que la base de données est indisponible
- **Quand** l'application tente de charger l'inventaire
- **Alors** un message d'erreur explicite s'affiche dans l'interface

**Implémentation :** `ui_gradio.refresh_inventory` → `service/inventory.get_inventory` → `storage/inventory_repository.py`

---

## HU07 — Trouver des recettes similaires grâce à la recherche par similarité

**En tant qu'** utilisateur,
**je veux** que l'application s'appuie sur un référentiel de recettes existantes,
**afin d'** obtenir des suggestions plus pertinentes, pas seulement générées aléatoirement.

**Critères d'acceptation :**

- **Étant donné** des recettes indexées dans la base de données
- **Quand** je demande des recettes à partir d'ingrédients détectés
- **Alors** le système recherche les 5 recettes les plus proches par similarité
- **Et** ces recettes sont classées par taux de couverture des ingrédients disponibles
- **Et** le score de similarité du meilleur résultat est affiché dans l'interface

- **Étant donné** que la base de recettes est vide ou indisponible
- **Quand** je demande des recettes
- **Alors** le modèle de langage génère quand même des recettes sans référentiel

**Implémentation :** `service/core.recipes_from_ingredients` → `ollama_client/embedding.py` → `storage/recipe_repository.search_recipes`

---

## HU08 — Consulter les performances de l'analyse

**En tant qu'** utilisateur,
**je veux** voir les indicateurs de performance après chaque analyse,
**afin de** comprendre le comportement du système et détecter d'éventuels problèmes.

**Critères d'acceptation :**

- **Étant donné** une analyse photo réussie
- **Quand** les résultats sont affichés
- **Alors** la durée de l'analyse visuelle est visible en millisecondes

- **Étant donné** une génération de recettes réussie
- **Quand** les recettes sont affichées
- **Alors** sont affichés : durée de génération, nombre de tokens générés, débit en tokens par seconde, score de similarité

**Implémentation :** `ui_gradio._format_metrics` alimenté par les métriques de requête depuis `ollama_client/base.py`

---

## Tableau récapitulatif

| Identifiant | Histoire utilisateur                             | Statut           | Priorité |
|-------------|--------------------------------------------------|------------------|----------|
| HU01        | Analyser une photo                               | ✅ Implémentée   | Haute    |
| HU02        | Corriger les ingrédients détectés                | ✅ Implémentée   | Haute    |
| HU03        | Obtenir des recettes anti-gaspillage             | ✅ Implémentée   | Haute    |
| HU04        | Personnaliser les recettes                       | ✅ Implémentée   | Moyenne  |
| HU05        | Enregistrer l'inventaire                         | ✅ Implémentée   | Moyenne  |
| HU06        | Consulter l'inventaire                           | ✅ Implémentée   | Moyenne  |
| HU07        | Recherche par similarité dans le référentiel     | ✅ Implémentée   | Haute    |
| HU08        | Consulter les performances de l'analyse          | ✅ Implémentée   | Faible   |

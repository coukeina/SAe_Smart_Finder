# User Stories — SmartFinder (Sujet 10 : Smart Recipe & Inventory Manager)

> Format : **En tant que** [rôle], **je veux** [action] **afin de** [bénéfice]  
> Critères d'acceptation au format **Given / When / Then**

---

## US01 — Analyser une photo pour détecter les ingrédients

**En tant qu'** utilisateur,  
**je veux** prendre ou importer une photo de mon frigo ou de mes aliments,  
**afin de** connaître automatiquement les ingrédients disponibles sans les saisir manuellement.

**Critères d'acceptation :**

- **Given** une photo contenant des aliments visibles
- **When** je clique sur « Analyser ma photo »
- **Then** le système affiche la liste des ingrédients détectés (nom, quantité estimée, maturité si visible)
- **And** la latence de l'analyse VLM est affichée

- **Given** une photo sans aliment identifiable
- **When** je clique sur « Analyser ma photo »
- **Then** le système affiche un message explicite : aucun ingrédient détecté, invitation à réessayer avec une meilleure photo

- **Given** aucune photo sélectionnée
- **When** je clique sur « Analyser ma photo »
- **Then** le système affiche un message d'erreur sans appeler le modèle IA

**Implémentation :** `ui_gradio.show_ingredients` → `service/core.analyze_photo` → `ollama_client/vlm.OllamaVLM.detect_ingredients`

---

## US02 — Corriger les ingrédients détectés avant de générer des recettes

**En tant qu'** utilisateur,  
**je veux** modifier, ajouter ou supprimer des ingrédients dans le tableau de détection,  
**afin de** corriger les erreurs du modèle IA avant de lancer la génération de recettes.

**Critères d'acceptation :**

- **Given** une liste d'ingrédients affichée après analyse
- **When** je modifie un nom, une quantité ou une maturité dans le tableau
- **Then** les modifications sont prises en compte pour la suite du parcours

- **Given** un ingrédient incorrect détecté (ex. : « carton » au lieu de « lait »)
- **When** je corrige la ligne directement dans le tableau
- **Then** la génération de recettes utilise la version corrigée

**Implémentation :** `gr.Dataframe` interactif dans `ui_gradio.build_demo` (paramètre `interactive=True`)

---

## US03 — Obtenir des suggestions de recettes anti-gaspillage

**En tant qu'** utilisateur,  
**je veux** obtenir des recettes réalisables uniquement avec les ingrédients que j'ai,  
**afin d'** éviter le gaspillage alimentaire et de ne pas avoir à acheter des ingrédients supplémentaires.

**Critères d'acceptation :**

- **Given** une liste d'ingrédients validée
- **When** je clique sur « Trouver mes recettes »
- **Then** le système propose des recettes contenant uniquement les ingrédients détectés (aucun ingrédient inventé)
- **And** chaque recette affiche : titre, liste d'ingrédients, étapes de préparation, temps de cuisson

- **Given** une liste d'ingrédients validée
- **When** le LLM propose une recette avec un ingrédient absent de la liste
- **Then** cette recette est rejetée automatiquement et non affichée

- **Given** le service Ollama est indisponible
- **When** je demande des recettes
- **Then** un message lisible s'affiche : « Le service Ollama est inaccessible »

**Implémentation :** `ui_gradio.propose_recipes` → `service/core.recipes_from_ingredients` → `ollama_client/llm.OllamaLLM.generate_json`

---

## US04 — Personnaliser les recettes selon ses préférences

**En tant qu'** utilisateur,  
**je veux** indiquer le nombre de personnes, le temps disponible et mes préférences alimentaires,  
**afin d'** obtenir des recettes adaptées à ma situation du moment.

**Critères d'acceptation :**

- **Given** des préférences saisies (ex. : « 2 personnes », « moins de 30 min », « végétarien »)
- **When** je clique sur « Trouver mes recettes »
- **Then** ces préférences sont transmises au LLM dans le prompt
- **And** les recettes générées tiennent compte du temps et du nombre de personnes

- **Given** aucune préférence saisie
- **When** je clique sur « Trouver mes recettes »
- **Then** le système génère des recettes sans contrainte particulière

**Implémentation :** `servings_input`, `time_input`, `preferences_input` → `ui_gradio.propose_recipes` → paramètre `preferences` de `recipes_from_ingredients`

---

## US05 — Enregistrer les ingrédients détectés dans mon inventaire

**En tant qu'** utilisateur,  
**je veux** sauvegarder les ingrédients confirmés dans un inventaire persistant,  
**afin de** garder une trace de mon stock et l'utiliser pour les prochaines analyses.

**Critères d'acceptation :**

- **Given** une liste d'ingrédients affichée après analyse
- **When** je clique sur « Ajouter les ingrédients détectés »
- **Then** les ingrédients sont enregistrés dans la base de données PostgreSQL
- **And** un message de confirmation indique le nombre d'ingrédients enregistrés

- **Given** un ingrédient déjà présent dans l'inventaire (même nom normalisé)
- **When** je le confirme à nouveau
- **Then** l'entrée existante est mise à jour (quantité, maturité) sans créer de doublon

- **Given** une quantité négative saisie dans le tableau
- **When** je tente de confirmer l'inventaire
- **Then** une erreur de validation s'affiche et aucune donnée n'est enregistrée

**Implémentation :** `ui_gradio.confirm_inventory` → `service/inventory.save_confirmed_inventory` → `storage/inventory_repository.save_inventory`

---

## US06 — Consulter son inventaire actuel

**En tant qu'** utilisateur,  
**je veux** voir la liste de tous les ingrédients enregistrés dans mon stock,  
**afin de** savoir ce que j'ai chez moi sans rouvrir le frigo.

**Critères d'acceptation :**

- **Given** des ingrédients précédemment enregistrés
- **When** j'ouvre l'application
- **Then** l'inventaire est automatiquement chargé depuis la base de données
- **And** chaque ligne affiche : nom, quantité, unité, maturité, niveau de confiance, statut confirmé

- **Given** la base de données PostgreSQL est indisponible
- **When** l'application tente de charger l'inventaire
- **Then** un message d'erreur explicite s'affiche dans l'interface

**Implémentation :** `demo.load` → `ui_gradio.refresh_inventory` → `service/inventory.get_inventory` → `storage/inventory_repository.list_inventory`

---

## US07 — Trouver des recettes similaires grâce à la recherche sémantique

**En tant qu'** utilisateur,  
**je veux** que l'application s'appuie sur un référentiel de recettes existantes,  
**afin d'** obtenir des suggestions plus pertinentes et cohérentes, pas seulement générées à l'improviste.

**Critères d'acceptation :**

- **Given** des recettes indexées dans PostgreSQL avec pgvector
- **When** je demande des recettes à partir d'ingrédients détectés
- **Then** le système recherche les 5 recettes les plus proches par similarité cosine
- **And** ces recettes sont classées par taux de couverture des ingrédients disponibles
- **And** le score cosine du meilleur résultat est affiché dans l'interface

- **Given** la base pgvector est vide ou indisponible
- **When** je demande des recettes
- **Then** le LLM génère quand même des recettes (dégradation gracieuse)

**Implémentation :** `service/core.recipes_from_ingredients` → `ollama_client/embedding.OllamaEmbedding.embed` → `storage/recipe_repository.search_recipes`

---

## US08 — Comprendre les performances du modèle IA

**En tant qu'** utilisateur avancé,  
**je veux** voir les métriques d'inférence après chaque analyse,  
**afin de** comprendre le comportement du système et diagnostiquer d'éventuels problèmes de performance.

**Critères d'acceptation :**

- **Given** une analyse photo réussie
- **When** les résultats sont affichés
- **Then** la latence du modèle VLM est visible (en ms)

- **Given** une génération de recettes réussie
- **When** les recettes sont affichées
- **Then** sont affichés : latence LLM (ms), tokens générés, débit (tokens/s), score cosine

**Implémentation :** `ui_gradio._format_metrics` alimenté par `OllamaRequestMetrics` depuis `ollama_client/base.py`

---

## Tableau récapitulatif

| ID   | User Story                              | Statut      | Priorité |
|------|-----------------------------------------|-------------|----------|
| US01 | Analyser une photo                      | ✅ Implémenté | Haute    |
| US02 | Corriger les ingrédients                | ✅ Implémenté | Haute    |
| US03 | Obtenir des recettes anti-gaspillage    | ✅ Implémenté | Haute    |
| US04 | Personnaliser les recettes              | ✅ Corrigé   | Moyenne  |
| US05 | Enregistrer l'inventaire                | ✅ Implémenté | Moyenne  |
| US06 | Consulter l'inventaire                  | ✅ Implémenté | Moyenne  |
| US07 | Recherche sémantique pgvector           | ✅ Implémenté | Haute    |
| US08 | Métriques d'inférence                   | ✅ Implémenté | Faible   |

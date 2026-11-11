# Protocole de Recette — SmartFinder

Ce document liste les scénarios de test fonctionnel et de robustesse à valider pour s'assurer du bon fonctionnement de l'application SmartFinder dans le cadre de la SAE.

---

## Scénario 1 : Photo claire avec aliments identifiables
- **Description :** L'utilisateur importe une photo nette de son réfrigérateur ou de ses aliments.
- **Étapes :**
  1. Cliquer sur le bouton « Afficher les ingrédients ».
  2. Vérifier que le tableau se remplit avec les aliments détectés, leurs quantités et leur maturité.
  3. Sélectionner les préférences (ex: 2 personnes, moins de 30 min) et cliquer sur « Proposer des recettes ».
- **Résultat attendu :**
  - Résultat obtenu : [À remplir lors de la démo réelle]
  - Captures d'écran : [Insérer la capture ici]

---

## Scénario 2 : Photo floue ou sombre
- **Description :** L'utilisateur importe une image inexploitable.
- **Étapes :**
  1. Télécharger une photo sombre ou floue.
  2. Cliquer sur « Afficher les ingrédients ».
- **Résultat attendu :**
  - Le système affiche un message d'avertissement invitant à réessayer avec une photo plus nette.
  - Résultat obtenu : [À remplir lors de la démo réelle]
  - Captures d'écran : [Insérer la capture ici]

---

## Scénario 3 : Absence totale d'aliments sur la photo
- **Description :** L'utilisateur importe une photo sans rapport (ex: un paysage).
- **Étapes :**
  1. Importer l'image et lancer l'analyse.
- **Résultat attendu :**
  - Aucun ingrédient détecté, message clair invitant à recommencer.
  - Résultat obtenu : [À remplir lors de la démo réelle]

---

## Scénario 4 : Correction manuelle des ingrédients détectés
- **Description :** L'utilisateur modifie un ingrédient mal reconnu dans le tableau interactif avant de générer les recettes.
- **Étapes :**
  1. Analyser une photo.
  2. Cliquer sur une cellule du tableau et corriger le nom ou la quantité.
  3. Lancer la proposition de recettes.
- **Résultat attendu :**
  - La génération prend en compte les modifications apportées par l'utilisateur.
  - Résultat obtenu : [À remplir lors de la démo réelle]

---

## Scénario 5 : Panne ou indisponibilité du service Ollama
- **Description :** Le service local Ollama est arrêté ou inaccessible.
- **Étapes :**
  1. Couper le service Ollama (ou stopper le conteneur).
  2. Tenter de lancer une analyse ou une génération.
- **Résultat attendu :**
  - Un message d'erreur explicite s'affiche dans l'interface (`Le service Ollama est inaccessible...`).
  - Résultat obtenu : [À remplir lors de la démo réelle]

---

## Scénario 6 : Base de données vide ou indisponible
- **Description :** La base PostgreSQL ne répond pas lors d'une demande d'inventaire ou de recherche.
- **Étapes :**
  1. Simuler l'indisponibilité de la base.
  2. Charger l'application ou l'inventaire.
- **Résultat attendu :**
  - Capture de l'erreur gérée proprement par le repository et affichée dans l'interface.
  - Résultat obtenu : [À remplir lors de la démo réelle]

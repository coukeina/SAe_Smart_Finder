# Suivi de livraison SAE — Smart Recipe

Le découpage ci-dessous sert au suivi des livrables V1/V2/V3 ; il ne remplace
pas une nomenclature de versions imposée par le sujet.

## V1 — Parcours photo vers recette

**Objectif :** relier l'image à une recette générée et vérifiable.

- [x] Détection VLM et réponses validées par schémas métier.
- [x] Arrêt explicite en l'absence d'ingrédient détecté.
- [x] Génération LLM structurée, avec refus d'ingrédients absents de la détection.
- [x] Retries bornés et erreurs Ollama compréhensibles dans Gradio.
- [x] Tests du parcours nominal, des réponses mal formées et des pannes.

## V2 — Référentiel, recherche sémantique et inventaire

**Objectif :** enrichir le parcours avec les données persistantes du projet.

- [x] Recherche PostgreSQL de recettes et classement tenant compte des
  ingrédients disponibles.
- [x] Commande reproductible d'indexation des recettes avec `embeddinggemma`,
  recherche pgvector et score cosine brut.
- [x] Affichage des latences VLM/LLM, tokens générés, débit et score cosine.
- [x] Inventaire éditable, confirmé par l'utilisateur et persisté dans
  PostgreSQL.
- [x] Tests unitaires des repositories, de l'indexation, des métriques et des
  callbacks Gradio.
- [x] Préférences utilisateur (nombre de personnes, temps, texte libre)
  transmises au LLM via l'interface.
- [ ] Vérifier le parcours complet sur une base PostgreSQL alimentée et un
  serveur Ollama avec les trois modèles requis.

## V3 — Validation de livraison et documentation

**Objectif :** permettre à un autre membre du groupe de lancer et vérifier le
projet sans hypothèses cachées.

- [x] README avec installation Docker, import et réindexation des recettes,
  modèles nécessaires et commandes de tests.
- [x] Workflow GitHub Actions avec lint et tests unitaires.
- [x] Validation locale : 46 tests, Ruff, compilation Python et configuration
  Docker Compose réussis.
- [x] CI verte sur la branche `feat/vector-recipe-search` (`b75d44a`).
- [x] User stories rédigées et liées à l'implémentation (`docs/user_stories.md`).
- [x] Documentation d'architecture avec flux et choix techniques
  (`docs/architecture.md`).
- [x] CONTRIBUTING.md et template de PR ajoutés.
- [x] `.venv` retiré du suivi Git.
- [ ] Construire et lancer l'image Docker avec PostgreSQL et Ollama sur le
  matériel IUT.
- [ ] Faire une démonstration sur des photos réelles et consigner les limites
  de détection et de qualité des recettes dans `docs/demo.md`.

## Critères de clôture

La livraison est clôturée lorsque les cases restantes de V2/V3 sont validées,
que la CI est verte et qu'un essai réel du parcours photo → ingrédients →
recettes est documenté avec captures d'écran. Les tests mockés vérifient les
contrats applicatifs, mais ne mesurent ni la qualité des modèles ni les
performances sur le matériel IUT.

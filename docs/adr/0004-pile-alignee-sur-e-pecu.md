# ADR 0004 — Pile technique alignée sur e-PECU

**Décision.** Adopter la pile de la plateforme e-PECU : PostgreSQL, Docker Compose, Celery et Redis pour les tâches de fond, stockage objet S3/MinIO pour les pièces, DRF avec schéma OpenAPI, pytest et ruff. Wagtail est conservé pour le site public, Flutter pour le mobile.

**Pourquoi.** La direction exploitera deux plateformes ; une seule pile à administrer, à sauvegarder et à surveiller réduit le coût d'exploitation et permet de réutiliser les procédures déjà écrites pour e-PECU.

**Configuration.** `config/settings/` est découpé en `base`, `dev`, `recette`, `prod` et `test`. En développement hors conteneur, `dev` retombe sur SQLite et exécute les tâches Celery en direct, pour démarrer sans dépendance.

**Sécurité.** Argon2 pour les mots de passe, `django-axes` pour le verrouillage après échecs répétés, cookies et HSTS en production.

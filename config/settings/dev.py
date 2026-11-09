"""Developpement : base locale, courriels captures, pas de cache distant obligatoire."""
from .base import *  # noqa: F403
from .base import BASE_DIR, env, env_bool, env_liste

DEBUG = True
# En developpement, l'hote varie : boucle locale, nom du conteneur, ou adresse
# de la machine virtuelle WSL vue depuis Windows. On ne filtre donc pas.
ALLOWED_HOSTS = env_liste("DJANGO_ALLOWED_HOSTS") or ["*"]

# Hors conteneur, on retombe sur SQLite pour demarrer sans dependance.
if not env("POSTGRES_HOST"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

STORAGES["staticfiles"] = {  # noqa: F405
    "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
}

if not env("REDIS_URL"):
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
    CELERY_TASK_ALWAYS_EAGER = True

AXES_ENABLED = env_bool("AXES_ENABLED", False)

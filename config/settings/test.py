"""Tests : rapide, deterministe, sans dependance externe."""
from .base import *  # noqa: F403
from .base import BASE_DIR

DEBUG = False
ALLOWED_HOSTS = ["*"]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db-test.sqlite3",
        "TEST": {"NAME": ":memory:"},
    }
}

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
CELERY_TASK_ALWAYS_EAGER = True
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
AXES_ENABLED = False
WAGTAILADMIN_BASE_URL = "http://testserver"

LOGGING = {"version": 1, "disable_existing_loggers": True, "root": {"handlers": []}}

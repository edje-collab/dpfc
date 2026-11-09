"""Recette : identique a la production, sans redirection HTTPS imposee."""
from .base import env_bool
from .prod import *  # noqa: F403

SECURE_SSL_REDIRECT = env_bool("DJANGO_SSL_REDIRECT", False)
SECURE_HSTS_SECONDS = 0

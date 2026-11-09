"""Production : HTTPS impose, cookies surs, stockage objet et cache distants."""
from .base import *  # noqa: F403
from .base import env_bool, env_liste

DEBUG = False
ALLOWED_HOSTS = env_liste("DJANGO_ALLOWED_HOSTS")

SECURE_SSL_REDIRECT = env_bool("DJANGO_SSL_REDIRECT", True)
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
AXES_ENABLED = True

from django.apps import AppConfig
from django.db.models.signals import post_migrate


def _installer_circuits(sender, **kwargs):
    """Les circuits modeles sont des donnees de reference : toujours presents."""
    from .modeles import installer_circuits_modeles

    installer_circuits_modeles()


class CircuitsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.circuits"
    verbose_name = "circuits de validation"

    def ready(self):
        post_migrate.connect(_installer_circuits, sender=self)

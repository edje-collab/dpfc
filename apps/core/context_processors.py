from .models import ConfigurationSite, Structure


def configuration_site(request):
    """Rend la configuration editoriale et les antennes disponibles partout."""
    return {
        "config_site": ConfigurationSite.actuelle(),
        "menu_antennes": Structure.objects.filter(
            type=Structure.Type.ANTENNE, active=True
        ).select_related("region")[:20],
    }

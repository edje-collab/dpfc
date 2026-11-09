from .models import ConfigurationSite, Perimetre, Structure


def configuration_site(request):
    """Rend la configuration editoriale et les antennes disponibles partout."""
    return {
        "config_site": ConfigurationSite.actuelle(request),
        "menu_antennes": Structure.objects.filter(
            type=Structure.Type.ANTENNE, active=True
        ).select_related("region")[:20],
    }


def perimetre_courant(request):
    """
    Perimetre de gestion de l'agent connecte.

    Les ecrans de l'intranet s'en servent pour annoncer le champ d'action :
    direction centrale, antenne regionale ou CNRPN.
    """
    agent = getattr(request, "user", None)
    if agent is None or not agent.is_authenticated:
        return {"perimetre_courant": None, "perimetres": Perimetre.objects.none()}
    perimetre = agent.perimetre
    visibles = (
        Perimetre.objects.actifs()
        if (agent.est_rh or agent.est_direction or agent.peut_administrer)
        else Perimetre.objects.filter(pk=perimetre.pk) if perimetre else Perimetre.objects.none()
    )
    return {"perimetre_courant": perimetre, "perimetres": visibles}

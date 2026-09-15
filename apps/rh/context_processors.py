def compteurs_intranet(request):
    agent = getattr(request, "user", None)
    if agent is None or not agent.is_authenticated:
        return {}
    from .services import demandes_a_traiter

    return {
        "nb_notifications": agent.notifications.filter(lue=False).count(),
        "nb_a_valider": demandes_a_traiter(agent).count(),
    }

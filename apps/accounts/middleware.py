from datetime import timedelta

from django.utils import timezone


class DerniereActiviteMiddleware:
    """Met a jour la derniere activite de l'agent, au plus une fois par quart d'heure."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        agent = getattr(request, "user", None)
        if agent is not None and agent.is_authenticated:
            recent = agent.derniere_activite and (
                timezone.now() - agent.derniere_activite < timedelta(minutes=15)
            )
            if not recent:
                agent.marquer_activite()
        return self.get_response(request)

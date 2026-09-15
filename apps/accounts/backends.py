from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.db.models import Q


class MatriculeOuEmailBackend(ModelBackend):
    """Permet la connexion avec le matricule ou le courriel professionnel."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        Agent = get_user_model()
        identifiant = (username or kwargs.get("matricule") or "").strip()
        if not identifiant or password is None:
            return None
        try:
            agent = Agent.objects.get(
                Q(matricule__iexact=identifiant) | Q(email__iexact=identifiant)
            )
        except Agent.DoesNotExist:
            Agent().set_password(password)  # temporisation contre l'enumeration
            return None
        except Agent.MultipleObjectsReturned:
            agent = Agent.objects.filter(matricule__iexact=identifiant).first()
            if agent is None:
                return None
        if agent.check_password(password) and self.user_can_authenticate(agent):
            return agent
        return None

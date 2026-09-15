from django.contrib.auth.models import BaseUserManager


class AgentManager(BaseUserManager):
    """Gestionnaire de comptes : l'identifiant de connexion est le matricule."""

    use_in_migrations = True

    def _creer(self, matricule, email, password, **extra):
        if not matricule:
            raise ValueError("Le matricule est obligatoire.")
        email = self.normalize_email(email) if email else ""
        agent = self.model(matricule=matricule.strip().upper(), email=email, **extra)
        agent.set_password(password)
        agent.save(using=self._db)
        return agent

    def create_user(self, matricule, email=None, password=None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._creer(matricule, email, password, **extra)

    def create_superuser(self, matricule, email=None, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        extra.setdefault("role", "ADMIN")
        if not extra.get("is_staff") or not extra.get("is_superuser"):
            raise ValueError("Un superutilisateur doit avoir is_staff et is_superuser a True.")
        return self._creer(matricule, email, password, **extra)

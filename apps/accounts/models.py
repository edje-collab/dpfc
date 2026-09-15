from django.contrib.auth.models import AbstractUser
from django.db import models
from django.urls import reverse
from django.utils import timezone

from apps.core.models import Structure

from .managers import AgentManager


class Agent(AbstractUser):
    """
    Compte d'un agent de la DPFC.

    Un agent est affecte soit a la direction centrale (nationale),
    soit a une antenne regionale de la pedagogie et de la formation continue.
    """

    class Role(models.TextChoices):
        AGENT = "AGENT", "Agent"
        CHEF_SERVICE = "CHEF_SERVICE", "Chef de service"
        SOUS_DIRECTEUR = "SOUS_DIRECTEUR", "Sous-directeur"
        SECRETARIAT = "SECRETARIAT", "Secretariat d'antenne"
        CHEF_ANTENNE = "CHEF_ANTENNE", "Chef d'antenne (APFC)"
        DIRECTEUR_REGIONAL = "DIRECTEUR_REGIONAL", "Directeur regional (DRENAET)"
        RH = "RH", "Gestionnaire du personnel"
        DIRECTEUR = "DIRECTEUR", "Directeur"
        ADMIN = "ADMIN", "Administrateur du portail"

    class Civilite(models.TextChoices):
        M = "M", "Monsieur"
        MME = "MME", "Madame"

    class Situation(models.TextChoices):
        EN_POSTE = "EN_POSTE", "En poste"
        EN_CONGE = "EN_CONGE", "En conge"
        EN_MISSION = "EN_MISSION", "En mission"
        ABSENT = "ABSENT", "Absent"
        DETACHE = "DETACHE", "Detache"
        RETRAITE = "RETRAITE", "Admis a la retraite"

    username = None
    matricule = models.CharField("matricule", max_length=20, unique=True)
    civilite = models.CharField("civilite", max_length=3, choices=Civilite.choices, default=Civilite.M)
    first_name = models.CharField("prenoms", max_length=150)
    last_name = models.CharField("nom", max_length=150)
    email = models.EmailField("courriel professionnel", blank=True)
    telephone = models.CharField("telephone", max_length=40, blank=True)
    photo = models.ImageField("photo", upload_to="agents/", blank=True)

    structure = models.ForeignKey(
        Structure,
        verbose_name="structure d'affectation",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="agents",
    )
    fonction = models.CharField("fonction", max_length=150, blank=True)
    grade = models.CharField("grade", max_length=100, blank=True)
    role = models.CharField("role dans le portail", max_length=20, choices=Role.choices, default=Role.AGENT)
    superieur = models.ForeignKey(
        "self",
        verbose_name="superieur hierarchique",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="subordonnes",
    )
    situation = models.CharField(
        "situation administrative", max_length=15, choices=Situation.choices, default=Situation.EN_POSTE
    )
    date_prise_service = models.DateField("date de prise de service", null=True, blank=True)
    date_naissance = models.DateField("date de naissance", null=True, blank=True)
    lieu_service = models.CharField("lieu de service", max_length=150, blank=True)
    doit_changer_mot_de_passe = models.BooleanField("doit changer son mot de passe", default=False)
    derniere_activite = models.DateTimeField("derniere activite", null=True, blank=True)

    USERNAME_FIELD = "matricule"
    REQUIRED_FIELDS = ["last_name", "first_name"]

    objects = AgentManager()

    class Meta:
        verbose_name = "agent"
        verbose_name_plural = "agents"
        ordering = ["last_name", "first_name"]
        indexes = [models.Index(fields=["matricule"]), models.Index(fields=["role"])]

    def __str__(self):
        return f"{self.nom_complet} ({self.matricule})"

    def save(self, *args, **kwargs):
        self.matricule = self.matricule.strip().upper()
        self.last_name = self.last_name.strip().upper()
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("accounts:agent_detail", args=[self.pk])

    # --- Identite ---------------------------------------------------------
    @property
    def nom_complet(self):
        return f"{self.last_name} {self.first_name}".strip()

    def get_full_name(self):
        return self.nom_complet

    def get_short_name(self):
        return self.first_name or self.matricule

    @property
    def initiales(self):
        p = (self.first_name[:1] or "").upper()
        n = (self.last_name[:1] or "").upper()
        return f"{n}{p}" or "?"

    @property
    def titre_civilite(self):
        return "M." if self.civilite == self.Civilite.M else "Mme"

    # --- Affectation ------------------------------------------------------
    @property
    def affectation(self):
        """CENTRALE ou REGION."""
        if self.structure_id:
            return self.structure.rattachement
        return Structure.Rattachement.CENTRALE

    @property
    def est_en_region(self):
        return self.affectation == Structure.Rattachement.REGION

    @property
    def libelle_affectation(self):
        if not self.structure_id:
            return "Non affecte"
        if self.est_en_region:
            return f"{self.structure.nom} - {self.structure.region}"
        return self.structure.nom

    # --- Droits metier ----------------------------------------------------
    @property
    def est_valideur(self):
        return self.role in {
            self.Role.CHEF_SERVICE,
            self.Role.SOUS_DIRECTEUR,
            self.Role.CHEF_ANTENNE,
            self.Role.DIRECTEUR_REGIONAL,
            self.Role.DIRECTEUR,
        }

    @property
    def est_rh(self):
        return self.role == self.Role.RH or self.is_superuser

    @property
    def est_direction(self):
        return self.role == self.Role.DIRECTEUR or self.is_superuser

    @property
    def peut_administrer(self):
        return self.role == self.Role.ADMIN or self.is_superuser

    @property
    def est_secretariat(self):
        return self.role == self.Role.SECRETARIAT

    @property
    def perimetre_drenaet(self):
        return self.structure.perimetre_drenaet if self.structure_id else None

    def agents_de_mon_antenne(self):
        """Agents de la meme antenne : perimetre de depot du secretariat."""
        if not self.structure_id:
            return Agent.objects.none()
        racine = self.structure
        if racine.type == Structure.Type.BUREAU and racine.parent_id:
            racine = racine.parent
        return Agent.objects.filter(
            models.Q(structure=racine) | models.Q(structure__parent=racine), is_active=True
        ).distinct()

    def equipe(self):
        """Agents dont l'agent courant est le superieur direct."""
        return Agent.objects.filter(superieur=self, is_active=True)

    def perimetre_agents(self):
        """Agents visibles par cet agent selon son role."""
        base = Agent.objects.filter(is_active=True)
        if self.est_rh or self.est_direction or self.peut_administrer:
            return base
        if self.role == self.Role.DIRECTEUR_REGIONAL and self.structure_id:
            perimetre = self.perimetre_drenaet
            if perimetre is not None:
                return base.filter(
                    models.Q(structure__drenaet=perimetre) | models.Q(structure=perimetre)
                ).distinct()
        if self.role in {self.Role.CHEF_ANTENNE, self.Role.SECRETARIAT} and self.structure_id:
            return base.filter(structure__region_id=self.structure.region_id)
        if self.est_valideur and self.structure_id:
            return base.filter(
                models.Q(structure=self.structure) | models.Q(superieur=self)
            ).distinct()
        return base.filter(pk=self.pk)

    def marquer_activite(self):
        Agent.objects.filter(pk=self.pk).update(derniere_activite=timezone.now())


class Notification(models.Model):
    """Notification interne affichee dans l'intranet et l'application mobile."""

    class Niveau(models.TextChoices):
        INFO = "INFO", "Information"
        SUCCES = "SUCCES", "Succes"
        ALERTE = "ALERTE", "Alerte"

    destinataire = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name="notifications")
    titre = models.CharField("titre", max_length=200)
    message = models.TextField("message", blank=True)
    lien = models.CharField("lien", max_length=300, blank=True)
    niveau = models.CharField(max_length=10, choices=Niveau.choices, default=Niveau.INFO)
    lue = models.BooleanField("lue", default=False)
    creee_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "notification"
        verbose_name_plural = "notifications"
        ordering = ["-creee_le"]

    def __str__(self):
        return f"{self.destinataire_id} - {self.titre}"

    @classmethod
    def envoyer(cls, destinataire, titre, message="", lien="", niveau=Niveau.INFO):
        if destinataire is None:
            return None
        return cls.objects.create(
            destinataire=destinataire, titre=titre, message=message, lien=lien, niveau=niveau
        )

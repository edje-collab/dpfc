"""
Ateliers, sessions et emargement par QR code.

La direction et ses antennes tiennent de nombreux ateliers, seminaires et
sessions de formation. L'emargement conditionne l'etat de paiement des
participants et la delivrance des attestations : il doit donc etre fiable,
tracable, et fonctionner la ou le reseau ne passe pas.

Trois choix structurent ce module :

  - le QR code ne porte aucune donnee personnelle (voir `qr.py`) ;
  - l'emargement est idempotent : son identifiant vient de l'appareil, de
    sorte qu'un envoi repete apres une coupure ne cree pas de doublon ;
  - un doublon n'est jamais perdu, il est journalise.
"""
import secrets
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils import timezone

from apps.core.models import Horodate, Perimetre, Structure

from .qr import jeton as construire_jeton


def identifiant_court():
    """Identifiant court, lisible et sans ambiguite dans un QR code."""
    return secrets.token_hex(4).upper()


def nouvelle_cle():
    return secrets.token_hex(32)


class AtelierQuerySet(models.QuerySet):
    def visibles_par(self, agent):
        if agent.est_rh or agent.est_direction or agent.peut_administrer:
            return self
        perimetre = agent.perimetre
        return self.filter(perimetre=perimetre) if perimetre else self.none()

    def a_venir(self, reference=None):
        reference = reference or timezone.localdate()
        return self.filter(date_debut__gte=reference).exclude(statut=Atelier.Statut.ANNULE)


class Atelier(Horodate):
    """Rencontre organisee par un perimetre : atelier, formation, seminaire."""

    class Type(models.TextChoices):
        ATELIER = "ATELIER", "Atelier de production"
        FORMATION = "FORMATION", "Formation"
        SEMINAIRE = "SEMINAIRE", "Seminaire"
        REUNION = "REUNION", "Reunion"
        JOURNEE = "JOURNEE", "Journee pedagogique"

    class Statut(models.TextChoices):
        PLANIFIE = "PLANIFIE", "Planifie"
        EN_COURS = "EN_COURS", "En cours"
        CLOS = "CLOS", "Clos"
        ANNULE = "ANNULE", "Annule"

    perimetre = models.ForeignKey(
        Perimetre, verbose_name="perimetre", on_delete=models.PROTECT, related_name="ateliers"
    )
    intitule = models.CharField("intitule", max_length=255)
    type = models.CharField("type", max_length=12, choices=Type.choices, default=Type.ATELIER)
    activite = models.ForeignKey(
        "activites.Activite", verbose_name="activite du plan d'action",
        on_delete=models.SET_NULL, null=True, blank=True, related_name="ateliers",
        help_text="Rattache l'atelier au plan d'action : son execution y sera reportee.",
    )
    lieu = models.CharField("lieu", max_length=200)
    structure_hote = models.ForeignKey(
        Structure, verbose_name="structure d'accueil", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="ateliers",
    )
    date_debut = models.DateField("date de debut")
    date_fin = models.DateField("date de fin")
    ordre_du_jour = models.TextField("ordre du jour", blank=True)
    public_cible = models.CharField("public cible", max_length=200, blank=True)
    budget = models.DecimalField("budget (FCFA)", max_digits=14, decimal_places=0, default=0)
    organisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="organisateur", on_delete=models.PROTECT,
        null=True, blank=True, related_name="ateliers_organises",
    )
    controleurs = models.ManyToManyField(
        settings.AUTH_USER_MODEL, verbose_name="controleurs d'emargement", blank=True,
        related_name="ateliers_controles",
        help_text="Agents habilites a scanner les QR codes et a emarger manuellement.",
    )
    statut = models.CharField("statut", max_length=10, choices=Statut.choices, default=Statut.PLANIFIE)
    motif_annulation = models.TextField("motif de l'annulation", blank=True)

    # Elements techniques du dispositif d'emargement.
    id_court = models.CharField(max_length=8, unique=True, default=identifiant_court, editable=False)
    cle = models.CharField(
        max_length=64, default=nouvelle_cle, editable=False,
        help_text="Cle de signature des jetons de presence, propre a l'atelier.",
    )

    objects = AtelierQuerySet.as_manager()

    class Meta:
        verbose_name = "atelier"
        verbose_name_plural = "ateliers"
        ordering = ["-date_debut"]
        indexes = [models.Index(fields=["perimetre", "-date_debut"]), models.Index(fields=["statut"])]

    def __str__(self):
        return self.intitule

    def clean(self):
        if self.date_debut and self.date_fin and self.date_fin < self.date_debut:
            raise ValidationError({"date_fin": "La fin precede le debut."})

    def get_absolute_url(self):
        return reverse("ateliers:detail", args=[self.pk])

    # --- Etat -------------------------------------------------------------
    @property
    def est_clos(self):
        return self.statut in {self.Statut.CLOS, self.Statut.ANNULE}

    @property
    def accepte_emargement(self):
        """On n'emarge pas un atelier clos ou annule."""
        return self.statut in {self.Statut.PLANIFIE, self.Statut.EN_COURS}

    @property
    def nb_jours(self):
        return (self.date_fin - self.date_debut).days + 1

    @property
    def couleur_statut(self):
        return {
            self.Statut.PLANIFIE: "neutre",
            self.Statut.EN_COURS: "attente",
            self.Statut.CLOS: "ok",
            self.Statut.ANNULE: "neutre",
        }[self.statut]

    # --- Consolidation ----------------------------------------------------
    @property
    def nb_participants(self):
        return self.participants.exclude(statut=Participant.Statut.REVOQUE).count()

    @property
    def nb_emarges(self):
        """Participants ayant emarge au moins une session."""
        return (
            self.participants.filter(emargements__isnull=False).distinct().count()
        )

    @property
    def taux_presence(self):
        attendus = self.nb_participants
        return round(100 * self.nb_emarges / attendus) if attendus else 0

    def peut_etre_controle_par(self, agent):
        """Qui peut emarger : organisateur, controleurs designes, direction."""
        if agent.est_direction or agent.peut_administrer:
            return True
        if self.organisateur_id == agent.pk:
            return True
        if self.controleurs.filter(pk=agent.pk).exists():
            return True
        return agent.dirige_son_perimetre and agent.perimetre == self.perimetre

    def peut_etre_organise_par(self, agent):
        """Qui cree et modifie l'atelier."""
        if agent.est_direction or agent.peut_administrer:
            return True
        if self.organisateur_id == agent.pk:
            return True
        return agent.dirige_son_perimetre and agent.perimetre == self.perimetre


class Session(models.Model):
    """
    Demi-journee ou journee d'emargement.

    L'emargement se fait par session et non par atelier : c'est la seule facon
    de constater une presence partielle, qui conditionne l'etat de paiement.
    """

    class Creneau(models.TextChoices):
        JOURNEE = "JOURNEE", "Journee"
        MATIN = "MATIN", "Matinee"
        APRES_MIDI = "APRES_MIDI", "Apres-midi"

    atelier = models.ForeignKey(Atelier, on_delete=models.CASCADE, related_name="sessions")
    date = models.DateField("date")
    creneau = models.CharField("creneau", max_length=10, choices=Creneau.choices, default=Creneau.JOURNEE)
    libelle = models.CharField("libelle", max_length=150, blank=True)

    class Meta:
        verbose_name = "session"
        verbose_name_plural = "sessions"
        # MATIN avant APRES_MIDI dans l'ordre alphabetique inverse du creneau.
        ordering = ["date", "-creneau"]
        constraints = [
            models.UniqueConstraint(
                fields=["atelier", "date", "creneau"], name="une_session_par_creneau_et_date"
            )
        ]

    def __str__(self):
        return self.libelle or f"{self.date:%d/%m/%Y} - {self.get_creneau_display()}"

    @property
    def nb_emarges(self):
        return self.emargements.count()

    @property
    def poids_journee(self):
        """Part de journee que represente la session, pour le barème."""
        return 1.0 if self.creneau == self.Creneau.JOURNEE else 0.5


class Participant(Horodate):
    """
    Personne conviee a l'atelier.

    Elle peut etre un agent du portail ou une personne exterieure — enseignant,
    inspecteur, partenaire — auquel cas son identite est saisie a la main.
    """

    class Statut(models.TextChoices):
        INSCRIT = "INSCRIT", "Inscrit"
        PROVISOIRE = "PROVISOIRE", "Inscrit sur place, a valider"
        REVOQUE = "REVOQUE", "Revoque"

    atelier = models.ForeignKey(Atelier, on_delete=models.CASCADE, related_name="participants")
    id_court = models.CharField(max_length=8, default=identifiant_court, editable=False)
    agent = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="agent du portail", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="participations",
        help_text="A renseigner lorsque le participant est un agent de la direction.",
    )
    nom = models.CharField("nom", max_length=100)
    prenoms = models.CharField("prenoms", max_length=150, blank=True)
    fonction = models.CharField("fonction", max_length=150, blank=True)
    structure_origine = models.CharField("structure d'origine", max_length=200, blank=True)
    telephone = models.CharField("telephone", max_length=40, blank=True)
    email = models.EmailField("courriel", blank=True)
    categorie = models.ForeignKey(
        "Bareme", verbose_name="categorie de barème", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="participants",
    )
    provenance = models.CharField(
        "provenance", max_length=150, blank=True,
        help_text="Localite d'ou vient le participant, pour les frais de transport.",
    )
    statut = models.CharField("statut", max_length=10, choices=Statut.choices, default=Statut.INSCRIT)
    convoque_le = models.DateTimeField("convoque le", null=True, blank=True)
    inscrit_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )

    class Meta:
        verbose_name = "participant"
        verbose_name_plural = "participants"
        ordering = ["nom", "prenoms"]
        constraints = [
            models.UniqueConstraint(
                fields=["atelier", "id_court"], name="un_identifiant_court_par_atelier"
            )
        ]

    def __str__(self):
        return self.nom_complet

    def save(self, *args, **kwargs):
        if self.agent_id and not self.nom:
            self.nom = self.agent.last_name
            self.prenoms = self.agent.first_name
            self.fonction = self.fonction or self.agent.fonction
            self.structure_origine = self.structure_origine or str(self.agent.structure or "")
        self.nom = self.nom.strip().upper()
        super().save(*args, **kwargs)

    @property
    def nom_complet(self):
        return f"{self.nom} {self.prenoms}".strip()

    @property
    def jeton(self):
        """Jeton a encoder dans le QR code. Aucune donnee personnelle."""
        return construire_jeton(self.atelier, self)

    @property
    def est_actif(self):
        return self.statut != self.Statut.REVOQUE

    @property
    def nb_sessions_emargees(self):
        return self.emargements.count()

    @property
    def a_emarge(self):
        return self.emargements.exists()

    @property
    def jours_de_presence(self):
        """Nombre de journees constatees, les demi-journees comptant pour moitie."""
        total = sum(
            e.session.poids_journee for e in self.emargements.select_related("session")
        )
        return round(total, 1)


class Bareme(Horodate):
    """Categorie de participant et montant journalier associe."""

    code = models.CharField("code", max_length=20, unique=True)
    libelle = models.CharField("libelle", max_length=150)
    montant_journalier = models.DecimalField(
        "montant journalier (FCFA)", max_digits=10, decimal_places=0, default=0
    )
    actif = models.BooleanField("actif", default=True)

    class Meta:
        verbose_name = "barème de participation"
        verbose_name_plural = "barèmes de participation"
        ordering = ["-montant_journalier", "code"]

    def __str__(self):
        return f"{self.libelle} ({self.montant_journalier:.0f} FCFA/jour)"


class Emargement(models.Model):
    """
    Presence constatee d'un participant a une session.

    L'identifiant primaire vient de l'appareil qui a scanne : renvoyer deux
    fois le meme emargement apres une coupure reseau ne cree pas de doublon.
    """

    class Mode(models.TextChoices):
        SCAN = "SCAN", "Scan du QR code"
        MANUEL = "MANUEL", "Saisie manuelle"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    participant = models.ForeignKey(Participant, on_delete=models.CASCADE, related_name="emargements")
    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name="emargements")
    horodatage = models.DateTimeField(
        "horodatage", help_text="Instant du scan, tel que l'appareil l'a releve."
    )
    mode = models.CharField("mode", max_length=8, choices=Mode.choices, default=Mode.SCAN)
    appareil = models.CharField("appareil", max_length=80, blank=True)
    motif = models.CharField(
        "motif", max_length=200, blank=True,
        help_text="Exige pour un emargement manuel : pourquoi le QR n'a pas pu etre scanne.",
    )
    saisi_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="emargements_saisis"
    )
    recu_le = models.DateTimeField("recu par le serveur le", auto_now_add=True)

    class Meta:
        verbose_name = "emargement"
        verbose_name_plural = "emargements"
        ordering = ["horodatage"]
        constraints = [
            models.UniqueConstraint(
                fields=["participant", "session"], name="un_emargement_par_participant_et_session"
            )
        ]

    def __str__(self):
        return f"{self.participant} - {self.session}"


class DoublonEmargement(models.Model):
    """
    Emargement refuse parce que le participant avait deja emarge la session.

    Rien n'est perdu : le doublon est conserve, ce qui permet de reconstituer
    ce qui s'est passe sur le terrain en cas de contestation.
    """

    id = models.UUIDField(primary_key=True, editable=False)
    participant = models.ForeignKey(Participant, on_delete=models.CASCADE, related_name="doublons")
    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name="doublons")
    horodatage = models.DateTimeField("horodatage")
    appareil = models.CharField("appareil", max_length=80, blank=True)
    saisi_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    recu_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "doublon d'emargement"
        verbose_name_plural = "doublons d'emargement"
        ordering = ["-recu_le"]

    def __str__(self):
        return f"Doublon : {self.participant_id} - {self.session_id} ({self.horodatage:%d/%m/%Y %H:%M})"


class CompteRendu(Horodate):
    """Compte rendu de l'atelier et decisions prises."""

    atelier = models.OneToOneField(Atelier, on_delete=models.CASCADE, related_name="compte_rendu")
    contenu = models.TextField("compte rendu")
    decisions = models.TextField("decisions", blank=True)
    recommandations = models.TextField("recommandations", blank=True)
    fichier = models.FileField("rapport detaille", upload_to="ateliers/comptes-rendus/%Y/", blank=True)
    redige_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )

    class Meta:
        verbose_name = "compte rendu d'atelier"
        verbose_name_plural = "comptes rendus d'atelier"

    def __str__(self):
        return f"Compte rendu - {self.atelier.intitule}"

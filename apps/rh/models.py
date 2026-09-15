from datetime import date, timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils import timezone

from apps.core.models import Horodate, Region, Structure


class JourFerie(models.Model):
    """Jour ferie legal, exclu du decompte des jours ouvrables."""

    date = models.DateField("date", unique=True)
    libelle = models.CharField("libelle", max_length=150)

    class Meta:
        verbose_name = "jour ferie"
        verbose_name_plural = "jours feries"
        ordering = ["date"]

    def __str__(self):
        return f"{self.date:%d/%m/%Y} - {self.libelle}"


def jours_ouvrables(debut: date, fin: date) -> int:
    """Nombre de jours ouvrables entre deux dates incluses (hors samedi, dimanche et jours feries)."""
    if not debut or not fin or fin < debut:
        return 0
    feries = set(
        JourFerie.objects.filter(date__range=(debut, fin)).values_list("date", flat=True)
    )
    total, jour = 0, debut
    while jour <= fin:
        if jour.weekday() < 5 and jour not in feries:
            total += 1
        jour += timedelta(days=1)
    return total


class TypeDemande(models.TextChoices):
    CONGE_ANNUEL = "CONGE_ANNUEL", "Conge annuel"
    CONGE_EXCEPTIONNEL = "CONGE_EXCEPTIONNEL", "Conge exceptionnel"
    PERMISSION = "PERMISSION", "Permission d'absence"
    ORDRE_MISSION = "ORDRE_MISSION", "Ordre de mission"
    ABSENCE = "ABSENCE", "Declaration d'absence"
    FORMATION = "FORMATION", "Demande de formation"


# Regles par type d'acte : visa du service du personnel, signature du directeur,
# decompte sur le solde de conge annuel, piece justificative exigee.
REGLES_TYPE = {
    TypeDemande.CONGE_ANNUEL: {
        "visa_rh": True, "signature_directeur": True, "decompte_solde": True, "justificatif": False,
        "document": "Decision de conge",
    },
    TypeDemande.CONGE_EXCEPTIONNEL: {
        "visa_rh": True, "signature_directeur": True, "decompte_solde": False, "justificatif": True,
        "document": "Decision de conge exceptionnel",
    },
    TypeDemande.PERMISSION: {
        "visa_rh": True, "signature_directeur": False, "decompte_solde": False, "justificatif": False,
        "document": "Autorisation d'absence",
    },
    TypeDemande.ORDRE_MISSION: {
        "visa_rh": True, "signature_directeur": True, "decompte_solde": False, "justificatif": False,
        "document": "Ordre de mission",
    },
    TypeDemande.ABSENCE: {
        "visa_rh": True, "signature_directeur": False, "decompte_solde": False, "justificatif": True,
        "document": "Declaration d'absence",
    },
    TypeDemande.FORMATION: {
        "visa_rh": True, "signature_directeur": True, "decompte_solde": False, "justificatif": False,
        "document": "Autorisation de formation",
    },
}


class SoldeConge(models.Model):
    """Droits a conge annuel d'un agent pour une annee de reference."""

    agent = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="soldes"
    )
    annee = models.PositiveSmallIntegerField("annee de reference")
    droit_jours = models.PositiveSmallIntegerField(
        "droit annuel (jours)", default=settings.RH["DROIT_CONGE_ANNUEL_JOURS"]
    )
    jours_reportes = models.PositiveSmallIntegerField("jours reportes", default=0)
    jours_consommes = models.PositiveSmallIntegerField("jours consommes", default=0)

    class Meta:
        verbose_name = "solde de conge"
        verbose_name_plural = "soldes de conge"
        unique_together = ("agent", "annee")
        ordering = ["-annee"]

    def __str__(self):
        return f"{self.agent} - {self.annee} : {self.jours_restants} j restants"

    @property
    def total_droits(self):
        return self.droit_jours + self.jours_reportes

    @property
    def jours_restants(self):
        return self.total_droits - self.jours_consommes

    @property
    def taux_consommation(self):
        return round(100 * self.jours_consommes / self.total_droits) if self.total_droits else 0

    @classmethod
    def pour(cls, agent, annee=None):
        annee = annee or timezone.localdate().year
        solde, _ = cls.objects.get_or_create(agent=agent, annee=annee)
        return solde


class Demande(Horodate):
    """
    Acte administratif consigne par un agent :
    conge, permission, ordre de mission, absence, formation.
    """

    class Statut(models.TextChoices):
        BROUILLON = "BROUILLON", "Brouillon"
        SOUMISE = "SOUMISE", "Soumise"
        EN_COURS = "EN_COURS", "Validation en cours"
        APPROUVEE = "APPROUVEE", "Approuvee"
        REJETEE = "REJETEE", "Rejetee"
        ANNULEE = "ANNULEE", "Annulee"

    numero = models.CharField(
        "numero", max_length=40, unique=True, blank=True, null=True, default=None
    )
    agent = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="demandes", verbose_name="agent"
    )
    structure = models.ForeignKey(
        Structure, on_delete=models.PROTECT, null=True, blank=True, related_name="demandes"
    )
    type = models.CharField("type d'acte", max_length=25, choices=TypeDemande.choices)
    motif = models.TextField("motif / objet", help_text="Expliquez brievement la demande.")
    date_debut = models.DateField("du")
    date_fin = models.DateField("au")
    heure_debut = models.TimeField("heure de debut", null=True, blank=True)
    heure_fin = models.TimeField("heure de fin", null=True, blank=True)
    nb_jours = models.PositiveSmallIntegerField("nombre de jours ouvrables", default=0)

    # Interim pendant l'absence
    interimaire = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="interims",
        verbose_name="agent assurant l'interim",
    )

    # Specifique ordre de mission
    destination = models.CharField("destination", max_length=200, blank=True)
    region_mission = models.ForeignKey(
        Region, on_delete=models.SET_NULL, null=True, blank=True, related_name="missions",
        verbose_name="region de la mission",
    )
    moyen_transport = models.CharField("moyen de transport", max_length=120, blank=True)
    structures_visitees = models.CharField("structures a visiter", max_length=250, blank=True)
    accompagnants = models.CharField("accompagnants", max_length=250, blank=True)
    hors_perimetre_drenaet = models.BooleanField(
        "mission hors du perimetre de la DRENAET",
        default=False,
        help_text="Cochez si le deplacement sort du perimetre de la direction regionale : "
                  "l'ordre de mission est alors etabli par le DRENAET, sur presentation des "
                  "termes de reference et de la lettre d'invitation ou d'information.",
    )
    termes_de_reference = models.FileField(
        "termes de reference (TDR)", upload_to="demandes/tdr/%Y/", blank=True
    )
    lettre_invitation = models.FileField(
        "lettre d'invitation ou d'information", upload_to="demandes/invitations/%Y/", blank=True
    )

    # Lieu de jouissance du conge
    lieu_jouissance = models.CharField("lieu de jouissance", max_length=150, blank=True)
    contact_pendant_absence = models.CharField("contact pendant l'absence", max_length=60, blank=True)

    justificatif = models.FileField("piece justificative", upload_to="demandes/%Y/", blank=True)
    depose_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="depose au secretariat par",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="depots_effectues",
        help_text="Renseigne lorsque le depot est effectue par le secretariat de l'antenne.",
    )
    statut = models.CharField("statut", max_length=12, choices=Statut.choices, default=Statut.BROUILLON)
    soumise_le = models.DateTimeField("soumise le", null=True, blank=True)
    cloturee_le = models.DateTimeField("decision finale le", null=True, blank=True)
    motif_rejet = models.TextField("motif du rejet", blank=True)
    solde_impacte = models.BooleanField("solde deja decompte", default=False)

    class Meta:
        verbose_name = "demande"
        verbose_name_plural = "demandes"
        ordering = ["-cree_le"]
        indexes = [
            models.Index(fields=["statut", "-cree_le"]),
            models.Index(fields=["agent", "-cree_le"]),
        ]

    def __str__(self):
        return f"{self.numero or 'Brouillon'} - {self.get_type_display()} - {self.agent}"

    # --- Regles -----------------------------------------------------------
    @property
    def regles(self):
        return REGLES_TYPE.get(self.type, REGLES_TYPE[TypeDemande.PERMISSION])

    @property
    def est_mission_hors_perimetre(self):
        return self.type == TypeDemande.ORDRE_MISSION and self.hors_perimetre_drenaet

    @property
    def autorite_signataire(self):
        """Autorite competente pour etablir l'acte."""
        if self.est_mission_hors_perimetre:
            return "DRENAET"
        if self.agent_id and self.agent.est_en_region:
            return "Chef d'antenne (APFC)"
        return "Directeur de la pedagogie et de la formation continue"

    @property
    def est_modifiable(self):
        return self.statut == self.Statut.BROUILLON

    @property
    def est_annulable(self):
        return self.statut in {self.Statut.BROUILLON, self.Statut.SOUMISE, self.Statut.EN_COURS}

    @property
    def est_en_circuit(self):
        return self.statut in {self.Statut.SOUMISE, self.Statut.EN_COURS}

    @property
    def libelle_document(self):
        return self.regles["document"]

    @property
    def couleur_statut(self):
        return {
            self.Statut.BROUILLON: "neutre",
            self.Statut.SOUMISE: "attente",
            self.Statut.EN_COURS: "attente",
            self.Statut.APPROUVEE: "ok",
            self.Statut.REJETEE: "ko",
            self.Statut.ANNULEE: "neutre",
        }[self.statut]

    def clean(self):
        if self.date_debut and self.date_fin and self.date_fin < self.date_debut:
            raise ValidationError({"date_fin": "La date de fin precede la date de debut."})
        if self.type == TypeDemande.ORDRE_MISSION and not self.destination:
            raise ValidationError({"destination": "Indiquez la destination de la mission."})
        if self.est_mission_hors_perimetre and self.statut != self.Statut.BROUILLON:
            manquants = {}
            if not self.termes_de_reference:
                manquants["termes_de_reference"] = (
                    "Les termes de reference sont exiges pour une mission hors perimetre DRENAET."
                )
            if not self.lettre_invitation:
                manquants["lettre_invitation"] = (
                    "Joignez la lettre d'invitation ou d'information de la structure d'accueil."
                )
            if manquants:
                raise ValidationError(manquants)
        if self.type == TypeDemande.PERMISSION and self.date_debut and self.date_fin:
            plafond = settings.RH["PERMISSION_MAX_JOURS"]
            if jours_ouvrables(self.date_debut, self.date_fin) > plafond:
                raise ValidationError(
                    f"Une permission ne peut exceder {plafond} jours ouvrables. "
                    "Au-dela, deposez une demande de conge."
                )
        if self.regles.get("justificatif") and not self.justificatif and self.statut != self.Statut.BROUILLON:
            raise ValidationError({"justificatif": "Une piece justificative est exigee pour ce type d'acte."})

    def save(self, *args, **kwargs):
        if not self.numero:
            self.numero = None  # plusieurs brouillons peuvent coexister sans numero
        if self.date_debut and self.date_fin:
            self.nb_jours = jours_ouvrables(self.date_debut, self.date_fin)
        if not self.structure_id and self.agent_id:
            self.structure = self.agent.structure
        super().save(*args, **kwargs)

    def attribuer_numero(self):
        if self.numero:
            return self.numero
        prefixes = {
            TypeDemande.CONGE_ANNUEL: "CG",
            TypeDemande.CONGE_EXCEPTIONNEL: "CE",
            TypeDemande.PERMISSION: "PA",
            TypeDemande.ORDRE_MISSION: "OM",
            TypeDemande.ABSENCE: "AB",
            TypeDemande.FORMATION: "FO",
        }
        annee = timezone.localdate().year
        prefixe = prefixes.get(self.type, "DM")
        existants = set(
            Demande.objects.filter(numero__startswith=f"{prefixe}-", numero__contains=f"/{annee}/")
            .values_list("numero", flat=True)
        )
        rang = len(existants) + 1
        while f"{prefixe}-{rang:04d}/{annee}/DPFC" in existants:
            rang += 1
        self.numero = f"{prefixe}-{rang:04d}/{annee}/DPFC"
        return self.numero

    def get_absolute_url(self):
        return reverse("rh:demande_detail", args=[self.pk])

    def condense(self):
        """Chaine canonique servant d'empreinte pour la signature electronique."""
        elements = [
            self.numero or "",
            self.type,
            self.agent.matricule if self.agent_id else "",
            self.agent.nom_complet if self.agent_id else "",
            self.agent.structure.sigle if self.agent_id and self.agent.structure_id else "",
            self.date_debut.isoformat() if self.date_debut else "",
            self.date_fin.isoformat() if self.date_fin else "",
            str(self.nb_jours),
            self.destination or "",
            "HORS_PERIMETRE" if self.est_mission_hors_perimetre else "PERIMETRE",
            (self.motif or "").strip(),
        ]
        return "|".join(elements)

    # --- Circuit ----------------------------------------------------------
    def etape_courante(self):
        return self.validations.filter(decision=Validation.Decision.ATTENTE).order_by("ordre").first()

    def valideur_attendu(self):
        etape = self.etape_courante()
        return etape.valideur if etape else None

    def progression(self):
        total = self.validations.count()
        if not total:
            return 0
        faites = self.validations.exclude(decision=Validation.Decision.ATTENTE).count()
        return round(100 * faites / total)


class Validation(models.Model):
    """Etape du circuit de validation d'une demande."""

    class Decision(models.TextChoices):
        ATTENTE = "ATTENTE", "En attente"
        FAVORABLE = "FAVORABLE", "Avis favorable"
        DEFAVORABLE = "DEFAVORABLE", "Avis defavorable"
        IGNOREE = "IGNOREE", "Etape sans objet"

    demande = models.ForeignKey(Demande, on_delete=models.CASCADE, related_name="validations")
    ordre = models.PositiveSmallIntegerField("ordre")
    libelle = models.CharField("intitule de l'etape", max_length=120)
    valideur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="validations_a_traiter"
    )
    decision = models.CharField(max_length=12, choices=Decision.choices, default=Decision.ATTENTE)
    commentaire = models.TextField("observation", blank=True)
    decide_le = models.DateTimeField("decide le", null=True, blank=True)

    class Meta:
        verbose_name = "etape de validation"
        verbose_name_plural = "etapes de validation"
        ordering = ["demande", "ordre"]
        unique_together = ("demande", "ordre")

    def __str__(self):
        return f"{self.demande_id} - {self.ordre}. {self.libelle}"


class RapportMission(Horodate):
    """Rapport depose par l'agent au retour d'une mission."""

    demande = models.OneToOneField(
        Demande, on_delete=models.CASCADE, related_name="rapport", limit_choices_to={"type": TypeDemande.ORDRE_MISSION}
    )
    resume = models.TextField("resume de la mission")
    resultats = models.TextField("resultats obtenus", blank=True)
    difficultes = models.TextField("difficultes rencontrees", blank=True)
    recommandations = models.TextField("recommandations", blank=True)
    fichier = models.FileField("rapport detaille", upload_to="rapports/%Y/", blank=True)
    depose_le = models.DateTimeField("depose le", auto_now_add=True)

    class Meta:
        verbose_name = "rapport de mission"
        verbose_name_plural = "rapports de mission"
        ordering = ["-depose_le"]

    def __str__(self):
        return f"Rapport {self.demande.numero}"

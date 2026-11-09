"""
Courrier et gestion electronique des documents.

Chaque perimetre tient son propre registre du courrier — arrivee et depart —
avec sa numerotation annuelle, comme il tient sa serie d'actes administratifs.
Un courrier arrive est impute a un agent, assorti d'instructions et d'un delai ;
il est traite lorsque toutes ses imputations le sont.

Les documents sont verses a la bibliotheque de la direction, versionnes et
indexes pour la recherche plein texte. Une piece peut etre soumise au parapheur,
qui reutilise le moteur de circuits de l'application `circuits`.
"""
import hashlib

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils import timezone

from apps.core.models import Horodate, Perimetre, Structure


# ---------------------------------------------------------------------------
# Courrier
# ---------------------------------------------------------------------------
class CourrierQuerySet(models.QuerySet):
    def visibles_par(self, agent):
        """
        Courriers accessibles a l'agent.

        Le service du personnel, la direction et l'administration voient tous
        les perimetres ; les autres ne voient que le leur. Un courrier
        confidentiel n'est visible que de son enregistreur, de ses imputataires
        et du responsable du perimetre.
        """
        base = self
        if not (agent.est_rh or agent.est_direction or agent.peut_administrer):
            perimetre = agent.perimetre
            base = base.filter(perimetre=perimetre) if perimetre else base.none()
            responsable = perimetre.responsable if perimetre else None
            if responsable is None or responsable.pk != agent.pk:
                base = base.exclude(
                    models.Q(confidentiel=True)
                    & ~models.Q(enregistre_par=agent)
                    & ~models.Q(imputations__destinataire=agent)
                )
        return base.distinct()

    def en_retard(self, reference=None):
        """Courriers dont au moins une imputation a depasse son delai."""
        reference = reference or timezone.localdate()
        return self.filter(
            imputations__delai__lt=reference, imputations__traite_le__isnull=True
        ).distinct()


class Courrier(Horodate):
    """Piece de correspondance enregistree au registre d'un perimetre."""

    class Sens(models.TextChoices):
        ARRIVEE = "ARRIVEE", "Courrier arrive"
        DEPART = "DEPART", "Courrier depart"

    class Statut(models.TextChoices):
        ENREGISTRE = "ENREGISTRE", "Enregistre"
        IMPUTE = "IMPUTE", "Impute"
        TRAITE = "TRAITE", "Traite"
        CLASSE = "CLASSE", "Classe sans suite"

    class Nature(models.TextChoices):
        LETTRE = "LETTRE", "Lettre"
        NOTE = "NOTE", "Note de service"
        CIRCULAIRE = "CIRCULAIRE", "Circulaire"
        RAPPORT = "RAPPORT", "Rapport"
        INVITATION = "INVITATION", "Invitation"
        DEMANDE = "DEMANDE", "Demande"
        AUTRE = "AUTRE", "Autre"

    perimetre = models.ForeignKey(
        Perimetre, verbose_name="perimetre", on_delete=models.PROTECT, related_name="courriers"
    )
    numero = models.CharField("numero d'ordre", max_length=40, unique=True, blank=True)
    sens = models.CharField("sens", max_length=8, choices=Sens.choices)
    nature = models.CharField("nature", max_length=12, choices=Nature.choices, default=Nature.LETTRE)
    correspondant = models.CharField(
        "expediteur ou destinataire", max_length=200,
        help_text="Structure ou personne a l'origine du courrier, ou a qui il est adresse.",
    )
    structure_correspondante = models.ForeignKey(
        Structure, verbose_name="structure correspondante", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="courriers",
        help_text="A renseigner lorsque le correspondant est une structure du ministere.",
    )
    objet = models.CharField("objet", max_length=255)
    reference_expediteur = models.CharField(
        "reference de l'expediteur", max_length=80, blank=True,
        help_text="Numero porte par le courrier d'origine, le cas echeant.",
    )
    date_courrier = models.DateField("date du courrier", default=timezone.localdate)
    date_enregistrement = models.DateField("date d'enregistrement", default=timezone.localdate)
    resume = models.TextField("resume", blank=True)
    confidentiel = models.BooleanField(
        "confidentiel", default=False,
        help_text="Limite l'acces a l'enregistreur, aux imputataires et au responsable du perimetre.",
    )
    statut = models.CharField("statut", max_length=12, choices=Statut.choices, default=Statut.ENREGISTRE)
    courrier_lie = models.ForeignKey(
        "self", verbose_name="courrier auquel celui-ci repond", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="reponses",
    )
    activite = models.ForeignKey(
        "activites.Activite", verbose_name="activite liee", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="courriers",
    )
    enregistre_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="enregistre par", on_delete=models.SET_NULL,
        null=True, related_name="courriers_enregistres",
    )
    classe_le = models.DateTimeField("classe le", null=True, blank=True)
    motif_classement = models.TextField("motif du classement", blank=True)

    objects = CourrierQuerySet.as_manager()

    class Meta:
        verbose_name = "courrier"
        verbose_name_plural = "courriers"
        ordering = ["-date_enregistrement", "-id"]
        indexes = [
            models.Index(fields=["perimetre", "sens", "-date_enregistrement"]),
            models.Index(fields=["statut"]),
        ]

    def __str__(self):
        return f"{self.numero} - {self.objet}"

    def clean(self):
        if self.date_courrier and self.date_enregistrement:
            if self.date_enregistrement < self.date_courrier:
                raise ValidationError(
                    {"date_enregistrement": "Un courrier ne peut etre enregistre avant sa date."}
                )
        if self.courrier_lie_id and self.courrier_lie_id == self.pk:
            raise ValidationError({"courrier_lie": "Un courrier ne peut repondre a lui-meme."})

    def save(self, *args, **kwargs):
        if not self.numero:
            self.numero = self.attribuer_numero()
        super().save(*args, **kwargs)

    def attribuer_numero(self):
        """
        Numero d'ordre du registre : ARR-0001/2026/APFC-GBK.

        Chaque perimetre tient une serie par sens et par annee, comme pour les
        actes administratifs.
        """
        prefixe = "ARR" if self.sens == self.Sens.ARRIVEE else "DEP"
        annee = (self.date_enregistrement or timezone.localdate()).year
        code = self.perimetre.code if self.perimetre_id else "DPFC"
        existants = set(
            Courrier.objects.filter(
                perimetre_id=self.perimetre_id, sens=self.sens, numero__contains=f"/{annee}/"
            ).values_list("numero", flat=True)
        )
        rang = len(existants) + 1
        while f"{prefixe}-{rang:04d}/{annee}/{code}" in existants:
            rang += 1
        return f"{prefixe}-{rang:04d}/{annee}/{code}"

    def get_absolute_url(self):
        return reverse("courrier:detail", args=[self.pk])

    # --- Etat -------------------------------------------------------------
    @property
    def est_arrive(self):
        return self.sens == self.Sens.ARRIVEE

    @property
    def est_clos(self):
        return self.statut in {self.Statut.TRAITE, self.Statut.CLASSE}

    @property
    def imputations_en_cours(self):
        return self.imputations.filter(traite_le__isnull=True)

    @property
    def est_en_retard(self):
        if self.est_clos:
            return False
        return self.imputations_en_cours.filter(delai__lt=timezone.localdate()).exists()

    @property
    def jours_de_retard(self):
        plus_ancienne = (
            self.imputations_en_cours.filter(delai__lt=timezone.localdate())
            .order_by("delai")
            .first()
        )
        if plus_ancienne is None:
            return 0
        return (timezone.localdate() - plus_ancienne.delai).days

    @property
    def couleur_statut(self):
        if self.est_en_retard:
            return "ko"
        return {
            self.Statut.ENREGISTRE: "neutre",
            self.Statut.IMPUTE: "attente",
            self.Statut.TRAITE: "ok",
            self.Statut.CLASSE: "neutre",
        }[self.statut]

    def peut_etre_vu_par(self, agent):
        """Controle unitaire, miroir du filtrage de `visibles_par`."""
        if agent.est_rh or agent.est_direction or agent.peut_administrer:
            return True
        if self.perimetre_id != getattr(agent.perimetre, "pk", None):
            return False
        if not self.confidentiel:
            return True
        if self.enregistre_par_id == agent.pk:
            return True
        if self.imputations.filter(destinataire=agent).exists():
            return True
        responsable = self.perimetre.responsable
        return responsable is not None and responsable.pk == agent.pk


class Imputation(Horodate):
    """Affectation d'un courrier arrive a un agent, pour traitement."""

    courrier = models.ForeignKey(Courrier, on_delete=models.CASCADE, related_name="imputations")
    destinataire = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="impute a", on_delete=models.PROTECT,
        related_name="imputations_recues",
    )
    structure = models.ForeignKey(
        Structure, verbose_name="structure", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="imputations",
    )
    instructions = models.TextField("instructions", help_text="Suite a donner au courrier.")
    delai = models.DateField("delai de traitement")
    pour_information = models.BooleanField(
        "pour information", default=False,
        help_text="L'imputation n'appelle pas de suite : elle est close des sa lecture.",
    )
    compte_rendu = models.TextField("suite donnee", blank=True)
    traite_le = models.DateTimeField("traite le", null=True, blank=True)
    impute_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="impute par", on_delete=models.SET_NULL,
        null=True, related_name="imputations_faites",
    )

    class Meta:
        verbose_name = "imputation"
        verbose_name_plural = "imputations"
        ordering = ["delai", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["courrier", "destinataire"], name="une_imputation_par_agent_et_courrier"
            )
        ]

    def __str__(self):
        return f"{self.courrier.numero} -> {self.destinataire}"

    @property
    def est_traitee(self):
        return self.traite_le is not None

    @property
    def est_en_retard(self):
        return not self.est_traitee and self.delai < timezone.localdate()

    @property
    def jours_restants(self):
        return (self.delai - timezone.localdate()).days


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------
class TypeDocument(models.TextChoices):
    PROGRAMME = "PROGRAMME", "Programme educatif"
    GUIDE = "GUIDE", "Guide d'execution"
    RAPPORT = "RAPPORT", "Rapport"
    COMPTE_RENDU = "COMPTE_RENDU", "Compte rendu"
    TDR = "TDR", "Termes de reference"
    NOTE = "NOTE", "Note"
    ACTE = "ACTE", "Acte administratif"
    COURRIER = "COURRIER", "Courrier"
    SUPPORT = "SUPPORT", "Support de formation"
    AUTRE = "AUTRE", "Autre"


class DocumentQuerySet(models.QuerySet):
    def visibles_par(self, agent):
        if agent.est_rh or agent.est_direction or agent.peut_administrer:
            return self
        perimetre = agent.perimetre
        if perimetre is None:
            return self.none()
        # Un document partage est visible de tous ; sinon il reste au perimetre.
        return self.filter(
            models.Q(partage=True) | models.Q(perimetre=perimetre)
        ).exclude(
            models.Q(acces=Document.Acces.RESTREINT) & ~models.Q(deposant=agent)
            & ~models.Q(agents_autorises=agent)
        ).distinct()


class Document(Horodate):
    """Piece versee a la bibliotheque de la direction, versionnee et indexee."""

    class Acces(models.TextChoices):
        INTERNE = "INTERNE", "Tous les agents du perimetre"
        RESTREINT = "RESTREINT", "Acces restreint"

    perimetre = models.ForeignKey(
        Perimetre, verbose_name="perimetre", on_delete=models.PROTECT, related_name="documents"
    )
    titre = models.CharField("titre", max_length=255)
    type_document = models.CharField(
        "type", max_length=15, choices=TypeDocument.choices, default=TypeDocument.AUTRE
    )
    annee = models.PositiveSmallIntegerField("annee", default=timezone.localdate().year)
    description = models.TextField("description", blank=True)
    courrier = models.ForeignKey(
        Courrier, verbose_name="courrier d'origine", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="documents",
    )
    activite = models.ForeignKey(
        "activites.Activite", verbose_name="activite liee", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="documents",
    )
    acces = models.CharField("acces", max_length=10, choices=Acces.choices, default=Acces.INTERNE)
    partage = models.BooleanField(
        "partage avec tous les perimetres", default=False,
        help_text="Rend le document consultable par les antennes et le CNRPN.",
    )
    agents_autorises = models.ManyToManyField(
        settings.AUTH_USER_MODEL, verbose_name="agents autorises", blank=True, related_name="documents_autorises"
    )
    deposant = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="depose par", on_delete=models.SET_NULL,
        null=True, related_name="documents_deposes",
    )
    texte_extrait = models.TextField("texte extrait", blank=True, editable=False)
    indexe_le = models.DateTimeField("indexe le", null=True, blank=True, editable=False)

    objects = DocumentQuerySet.as_manager()

    class Meta:
        verbose_name = "document"
        verbose_name_plural = "documents"
        ordering = ["-annee", "titre"]
        indexes = [models.Index(fields=["perimetre", "type_document", "-annee"])]

    def __str__(self):
        return self.titre

    def get_absolute_url(self):
        return reverse("courrier:document_detail", args=[self.pk])

    @property
    def version_courante(self):
        return self.versions.order_by("-numero").first()

    @property
    def nb_versions(self):
        return self.versions.count()

    def peut_etre_vu_par(self, agent):
        if agent.est_rh or agent.est_direction or agent.peut_administrer:
            return True
        meme_perimetre = self.perimetre_id == getattr(agent.perimetre, "pk", None)
        if not (self.partage or meme_perimetre):
            return False
        if self.acces == self.Acces.INTERNE:
            return True
        if self.deposant_id == agent.pk:
            return True
        return self.agents_autorises.filter(pk=agent.pk).exists()


class VersionDocument(models.Model):
    """Une version du fichier. Les versions anterieures sont conservees."""

    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="versions")
    numero = models.PositiveSmallIntegerField("version", default=1)
    fichier = models.FileField("fichier", upload_to="documents/%Y/", max_length=255)
    commentaire = models.CharField("commentaire de version", max_length=200, blank=True)
    empreinte = models.CharField("empreinte SHA-256", max_length=64, blank=True, editable=False)
    taille = models.PositiveIntegerField("taille (octets)", default=0, editable=False)
    deposee_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="versions_deposees"
    )
    deposee_le = models.DateTimeField("deposee le", auto_now_add=True)

    class Meta:
        verbose_name = "version de document"
        verbose_name_plural = "versions de document"
        ordering = ["-numero"]
        constraints = [
            models.UniqueConstraint(fields=["document", "numero"], name="une_version_par_numero")
        ]

    def __str__(self):
        return f"{self.document.titre} v{self.numero}"

    def save(self, *args, **kwargs):
        if not self.numero_est_fixe():
            dernier = (
                VersionDocument.objects.filter(document=self.document)
                .aggregate(m=models.Max("numero"))["m"] or 0
            )
            self.numero = dernier + 1
        if self.fichier and not self.empreinte:
            self.empreinte, self.taille = self._empreinte_et_taille()
        super().save(*args, **kwargs)

    def numero_est_fixe(self):
        return bool(self.pk) or self.numero > 1

    def _empreinte_et_taille(self):
        condensat = hashlib.sha256()
        taille = 0
        self.fichier.open("rb")
        try:
            for bloc in self.fichier.chunks():
                condensat.update(bloc)
                taille += len(bloc)
        finally:
            self.fichier.seek(0)
        return condensat.hexdigest(), taille

    @property
    def taille_lisible(self):
        octets = float(self.taille)
        for unite in ("o", "Ko", "Mo", "Go"):
            if octets < 1024 or unite == "Go":
                return f"{octets:.0f} {unite}" if unite == "o" else f"{octets:.1f} {unite}"
            octets /= 1024
        return f"{octets:.1f} Go"


# ---------------------------------------------------------------------------
# Parapheur
# ---------------------------------------------------------------------------
# Regles du parapheur, dans la forme attendue par le moteur de circuits.
# Le visa remonte au responsable du perimetre, pas au directeur national :
# une note d'antenne n'a pas a traverser la direction centrale.
REGLES_PARAPHEUR = {
    "visa_rh": False,
    "signature_directeur": False,
    "decompte_solde": False,
    "justificatif": False,
    "document": "Piece au parapheur",
}

TYPE_ACTE_PARAPHEUR = "PARAPHEUR"


class PieceParapheur(Horodate):
    """
    Piece soumise aux visas internes avant signature.

    Elle expose la meme interface qu'une demande administrative (`agent`,
    `type`, `regles`, `est_mission_hors_perimetre`), ce qui lui permet de
    reutiliser le moteur de circuits sans que celui-ci connaisse le courrier.
    """

    class Statut(models.TextChoices):
        BROUILLON = "BROUILLON", "Brouillon"
        EN_CIRCUIT = "EN_CIRCUIT", "Au parapheur"
        VISEE = "VISEE", "Visee"
        REJETEE = "REJETEE", "Rejetee"

    perimetre = models.ForeignKey(
        Perimetre, verbose_name="perimetre", on_delete=models.PROTECT, related_name="pieces_parapheur"
    )
    objet = models.CharField("objet", max_length=255)
    document = models.ForeignKey(
        Document, verbose_name="document", on_delete=models.PROTECT, related_name="parapheurs"
    )
    courrier = models.ForeignKey(
        Courrier, verbose_name="courrier associe", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="parapheurs",
    )
    demandeur = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="demandeur", on_delete=models.PROTECT,
        related_name="pieces_soumises",
    )
    note = models.TextField("note de presentation", blank=True)
    statut = models.CharField("statut", max_length=12, choices=Statut.choices, default=Statut.BROUILLON)
    soumise_le = models.DateTimeField("soumise le", null=True, blank=True)
    close_le = models.DateTimeField("close le", null=True, blank=True)
    motif_rejet = models.TextField("motif du rejet", blank=True)

    class Meta:
        verbose_name = "piece au parapheur"
        verbose_name_plural = "parapheur"
        ordering = ["-cree_le"]

    def __str__(self):
        return self.objet

    def get_absolute_url(self):
        return reverse("courrier:parapheur_detail", args=[self.pk])

    # --- Interface attendue par le moteur de circuits ---------------------
    @property
    def agent(self):
        return self.demandeur

    @property
    def type(self):
        return TYPE_ACTE_PARAPHEUR

    @property
    def regles(self):
        return REGLES_PARAPHEUR

    @property
    def est_mission_hors_perimetre(self):
        return False

    # --- Etat -------------------------------------------------------------
    @property
    def est_modifiable(self):
        return self.statut == self.Statut.BROUILLON

    @property
    def couleur_statut(self):
        return {
            self.Statut.BROUILLON: "neutre",
            self.Statut.EN_CIRCUIT: "attente",
            self.Statut.VISEE: "ok",
            self.Statut.REJETEE: "ko",
        }[self.statut]

    def etape_courante(self):
        return self.visas.filter(decision=Visa.Decision.ATTENTE).order_by("ordre").first()

    def progression(self):
        total = self.visas.count()
        if not total:
            return 0
        faits = self.visas.exclude(decision=Visa.Decision.ATTENTE).count()
        return round(100 * faits / total)


class Visa(models.Model):
    """Etape du parapheur, calquee sur les validations des actes."""

    class Decision(models.TextChoices):
        ATTENTE = "ATTENTE", "En attente"
        VISE = "VISE", "Vise"
        REFUSE = "REFUSE", "Refuse"
        IGNORE = "IGNORE", "Etape sans objet"

    piece = models.ForeignKey(PieceParapheur, on_delete=models.CASCADE, related_name="visas")
    ordre = models.PositiveSmallIntegerField("ordre")
    libelle = models.CharField("intitule de l'etape", max_length=150)
    viseur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="visas_a_donner"
    )
    decision = models.CharField(max_length=10, choices=Decision.choices, default=Decision.ATTENTE)
    observation = models.TextField("observation", blank=True)
    decide_le = models.DateTimeField("decide le", null=True, blank=True)

    class Meta:
        verbose_name = "visa"
        verbose_name_plural = "visas"
        ordering = ["piece", "ordre"]
        constraints = [
            models.UniqueConstraint(fields=["piece", "ordre"], name="un_visa_par_ordre_et_piece")
        ]

    def __str__(self):
        return f"{self.piece_id} - {self.ordre}. {self.libelle}"


class ModeleDocument(Horodate):
    """Modele de courrier ou de note, rendu a l'en-tete de la direction."""

    code = models.SlugField("code", unique=True)
    titre = models.CharField("titre", max_length=200)
    nature = models.CharField(
        "nature", max_length=12, choices=Courrier.Nature.choices, default=Courrier.Nature.LETTRE
    )
    corps = models.TextField(
        "corps",
        help_text="Variables disponibles : {{ objet }}, {{ correspondant }}, {{ date }}, "
                  "{{ perimetre }}, {{ signataire }}.",
    )
    actif = models.BooleanField("actif", default=True)

    class Meta:
        verbose_name = "modele de document"
        verbose_name_plural = "modeles de documents"
        ordering = ["titre"]

    def __str__(self):
        return self.titre

    def rendre(self, **variables):
        """Substitution simple, sans moteur de gabarit : le corps est du texte."""
        rendu = self.corps
        for cle, valeur in variables.items():
            rendu = rendu.replace(f"{{{{ {cle} }}}}", str(valeur or ""))
        return rendu

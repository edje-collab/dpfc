"""
Plan d'action annuel et suivi des activites.

Chaque perimetre de gestion — la direction centrale, chaque antenne regionale,
le CNRPN — etablit son plan d'action annuel, le fait valider, puis rend compte
de son execution. L'activite est le pivot : elle porte une periode prevue, un
budget, un responsable, et un avancement alimente par les comptes rendus
successifs.

Le taux d'execution se lit a trois niveaux : l'activite, l'axe strategique et
le plan. Il est calcule, jamais saisi globalement.
"""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils import timezone

from apps.core.models import Horodate, Perimetre, Structure


class Axe(Horodate):
    """
    Axe strategique de la direction.

    Referentiel commun a tous les perimetres : les antennes declinent les memes
    axes que la direction centrale, ce qui permet la consolidation nationale.
    """

    code = models.CharField("code", max_length=20, unique=True)
    libelle = models.CharField("libelle", max_length=250)
    description = models.TextField("description", blank=True)
    ordre = models.PositiveSmallIntegerField("ordre", default=10)
    actif = models.BooleanField("actif", default=True)

    class Meta:
        verbose_name = "axe strategique"
        verbose_name_plural = "axes strategiques"
        ordering = ["ordre", "code"]

    def __str__(self):
        return f"{self.code} - {self.libelle}"


class PlanActionQuerySet(models.QuerySet):
    def visibles_par(self, agent):
        """Un agent voit le plan de son perimetre ; la direction voit tout."""
        if agent.est_rh or agent.est_direction or agent.peut_administrer:
            return self
        perimetre = agent.perimetre
        return self.filter(perimetre=perimetre) if perimetre else self.none()


class PlanAction(Horodate):
    """Plan d'action annuel d'un perimetre."""

    class Statut(models.TextChoices):
        BROUILLON = "BROUILLON", "En preparation"
        SOUMIS = "SOUMIS", "Soumis a validation"
        VALIDE = "VALIDE", "Valide"
        CLOS = "CLOS", "Clos"

    perimetre = models.ForeignKey(
        Perimetre, verbose_name="perimetre", on_delete=models.PROTECT, related_name="plans"
    )
    annee = models.PositiveSmallIntegerField("annee")
    libelle = models.CharField("libelle", max_length=250, blank=True)
    contexte = models.TextField("contexte et orientations", blank=True)
    statut = models.CharField("statut", max_length=10, choices=Statut.choices, default=Statut.BROUILLON)
    soumis_le = models.DateTimeField("soumis le", null=True, blank=True)
    valide_le = models.DateTimeField("valide le", null=True, blank=True)
    valide_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="valide par", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="plans_valides",
    )
    clos_le = models.DateTimeField("clos le", null=True, blank=True)
    motif_rejet = models.TextField("motif du renvoi", blank=True)

    objects = PlanActionQuerySet.as_manager()

    class Meta:
        verbose_name = "plan d'action"
        verbose_name_plural = "plans d'action"
        ordering = ["-annee", "perimetre"]
        constraints = [
            models.UniqueConstraint(fields=["perimetre", "annee"], name="un_plan_par_perimetre_et_annee")
        ]

    def __str__(self):
        return f"Plan d'action {self.annee} - {self.perimetre.code}"

    def save(self, *args, **kwargs):
        if not self.libelle:
            self.libelle = f"Plan d'action {self.annee} de {self.perimetre.nom}"
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("activites:plan_detail", args=[self.pk])

    # --- Etats -----------------------------------------------------------
    @property
    def est_modifiable(self):
        """On n'ajoute ni ne retire d'activite dans un plan valide ou clos."""
        return self.statut in {self.Statut.BROUILLON, self.Statut.SOUMIS}

    @property
    def est_en_execution(self):
        return self.statut == self.Statut.VALIDE

    @property
    def couleur_statut(self):
        return {
            self.Statut.BROUILLON: "neutre",
            self.Statut.SOUMIS: "attente",
            self.Statut.VALIDE: "ok",
            self.Statut.CLOS: "neutre",
        }[self.statut]

    # --- Consolidation ----------------------------------------------------
    @property
    def nb_activites(self):
        return self.activites.count()

    @property
    def budget_prevu(self):
        return self.activites.aggregate(t=models.Sum("budget_prevu"))["t"] or 0

    @property
    def budget_execute(self):
        return self.activites.aggregate(t=models.Sum("budget_execute"))["t"] or 0

    @property
    def taux_execution_budgetaire(self):
        prevu = self.budget_prevu
        return round(100 * self.budget_execute / prevu) if prevu else 0

    @property
    def taux_execution(self):
        """
        Taux d'execution physique : moyenne des avancements des activites,
        les activites annulees etant exclues du calcul.
        """
        retenues = self.activites.exclude(statut=Activite.Statut.ANNULEE)
        moyenne = retenues.aggregate(m=models.Avg("avancement"))["m"]
        return round(moyenne) if moyenne is not None else 0

    def repartition_par_statut(self):
        return {
            ligne["statut"]: ligne["n"]
            for ligne in self.activites.values("statut").annotate(n=models.Count("id"))
        }

    def synthese_par_axe(self):
        """Avancement et budget par axe strategique, pour le tableau de bord."""
        lignes = (
            self.activites.exclude(statut=Activite.Statut.ANNULEE)
            .values("axe__code", "axe__libelle")
            .annotate(
                nb=models.Count("id"),
                avancement=models.Avg("avancement"),
                prevu=models.Sum("budget_prevu"),
                execute=models.Sum("budget_execute"),
            )
            .order_by("axe__code")
        )
        return [
            {
                "code": ligne["axe__code"] or "-",
                "libelle": ligne["axe__libelle"] or "Hors axe",
                "nb": ligne["nb"],
                "avancement": round(ligne["avancement"] or 0),
                "prevu": ligne["prevu"] or 0,
                "execute": ligne["execute"] or 0,
            }
            for ligne in lignes
        ]

    @classmethod
    def pour(cls, perimetre, annee=None):
        annee = annee or timezone.localdate().year
        plan, _ = cls.objects.get_or_create(perimetre=perimetre, annee=annee)
        return plan


class ActiviteQuerySet(models.QuerySet):
    def visibles_par(self, agent):
        if agent.est_rh or agent.est_direction or agent.peut_administrer:
            return self
        perimetre = agent.perimetre
        return self.filter(plan__perimetre=perimetre) if perimetre else self.none()

    def en_retard(self, reference=None):
        """Activites dont l'echeance est depassee sans etre achevees."""
        reference = reference or timezone.localdate()
        return self.filter(
            date_fin_prevue__lt=reference,
            statut__in=[Activite.Statut.PLANIFIEE, Activite.Statut.EN_COURS],
        )

    def de_l_annee(self, annee=None):
        return self.filter(plan__annee=annee or timezone.localdate().year)


class Activite(Horodate):
    """Activite inscrite au plan d'action d'un perimetre."""

    class Type(models.TextChoices):
        FORMATION = "FORMATION", "Formation / renforcement de capacites"
        ATELIER = "ATELIER", "Atelier de production"
        ELABORATION = "ELABORATION", "Elaboration de programmes ou de guides"
        SUIVI = "SUIVI", "Suivi pedagogique et encadrement"
        EVALUATION = "EVALUATION", "Evaluation des acquis"
        PRODUCTION = "PRODUCTION", "Production de ressources"
        REUNION = "REUNION", "Reunion et concertation"
        AUTRE = "AUTRE", "Autre"

    class Statut(models.TextChoices):
        PLANIFIEE = "PLANIFIEE", "Planifiee"
        EN_COURS = "EN_COURS", "En cours"
        REALISEE = "REALISEE", "Realisee"
        REPORTEE = "REPORTEE", "Reportee"
        ANNULEE = "ANNULEE", "Annulee"

    plan = models.ForeignKey(PlanAction, on_delete=models.CASCADE, related_name="activites")
    axe = models.ForeignKey(
        Axe, verbose_name="axe strategique", on_delete=models.PROTECT,
        null=True, blank=True, related_name="activites",
    )
    code = models.CharField("code", max_length=30, blank=True)
    intitule = models.CharField("intitule", max_length=250)
    type = models.CharField("type", max_length=15, choices=Type.choices, default=Type.FORMATION)
    description = models.TextField("description", blank=True)
    structure = models.ForeignKey(
        Structure, verbose_name="structure chargee de l'execution", on_delete=models.PROTECT,
        null=True, blank=True, related_name="activites",
    )
    responsable = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="responsable", on_delete=models.PROTECT,
        null=True, blank=True, related_name="activites_pilotees",
    )
    date_debut_prevue = models.DateField("debut prevu")
    date_fin_prevue = models.DateField("fin prevue")
    date_debut_reelle = models.DateField("debut reel", null=True, blank=True)
    date_fin_reelle = models.DateField("fin reelle", null=True, blank=True)
    lieu = models.CharField("lieu", max_length=200, blank=True)
    public_cible = models.CharField("public cible", max_length=200, blank=True)
    effectif_prevu = models.PositiveIntegerField("beneficiaires prevus", default=0)
    effectif_realise = models.PositiveIntegerField("beneficiaires touches", default=0)
    budget_prevu = models.DecimalField(
        "budget prevu (FCFA)", max_digits=14, decimal_places=0, default=0
    )
    budget_execute = models.DecimalField(
        "budget execute (FCFA)", max_digits=14, decimal_places=0, default=0
    )
    source_financement = models.CharField("source de financement", max_length=150, blank=True)
    statut = models.CharField("statut", max_length=12, choices=Statut.choices, default=Statut.PLANIFIEE)
    avancement = models.PositiveSmallIntegerField("avancement (%)", default=0)
    motif_report = models.TextField("motif du report ou de l'annulation", blank=True)

    objects = ActiviteQuerySet.as_manager()

    class Meta:
        verbose_name = "activite"
        verbose_name_plural = "activites"
        ordering = ["date_debut_prevue", "code"]
        indexes = [
            models.Index(fields=["statut", "date_fin_prevue"]),
            models.Index(fields=["plan", "axe"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(avancement__lte=100), name="avancement_au_plus_cent"
            )
        ]

    def __str__(self):
        return f"{self.code or '—'} {self.intitule}"

    def clean(self):
        if self.date_debut_prevue and self.date_fin_prevue and self.date_fin_prevue < self.date_debut_prevue:
            raise ValidationError({"date_fin_prevue": "La fin prevue precede le debut prevu."})
        if self.date_debut_reelle and self.date_fin_reelle and self.date_fin_reelle < self.date_debut_reelle:
            raise ValidationError({"date_fin_reelle": "La fin reelle precede le debut reel."})
        if self.plan_id and self.date_debut_prevue and self.date_debut_prevue.year != self.plan.annee:
            raise ValidationError(
                {"date_debut_prevue": f"L'activite doit demarrer dans l'annee du plan ({self.plan.annee})."}
            )

    def save(self, *args, **kwargs):
        if not self.code and self.plan_id:
            self.code = self._code_suivant()
        super().save(*args, **kwargs)

    def _code_suivant(self):
        """Code sequentiel dans le plan : A-001, A-002..."""
        existants = set(
            Activite.objects.filter(plan=self.plan).exclude(pk=self.pk).values_list("code", flat=True)
        )
        rang = len(existants) + 1
        while f"A-{rang:03d}" in existants:
            rang += 1
        return f"A-{rang:03d}"

    def get_absolute_url(self):
        return reverse("activites:activite_detail", args=[self.pk])

    # --- Etat -------------------------------------------------------------
    @property
    def est_achevee(self):
        return self.statut == self.Statut.REALISEE

    @property
    def est_close(self):
        return self.statut in {self.Statut.REALISEE, self.Statut.ANNULEE}

    @property
    def est_en_retard(self):
        if self.est_close or self.statut == self.Statut.REPORTEE:
            return False
        return self.date_fin_prevue < timezone.localdate()

    @property
    def jours_de_retard(self):
        if not self.est_en_retard:
            return 0
        return (timezone.localdate() - self.date_fin_prevue).days

    @property
    def taux_execution_budgetaire(self):
        return round(100 * self.budget_execute / self.budget_prevu) if self.budget_prevu else 0

    @property
    def taux_couverture_beneficiaires(self):
        return round(100 * self.effectif_realise / self.effectif_prevu) if self.effectif_prevu else 0

    @property
    def couleur_statut(self):
        if self.est_en_retard:
            return "ko"
        return {
            self.Statut.PLANIFIEE: "neutre",
            self.Statut.EN_COURS: "attente",
            self.Statut.REALISEE: "ok",
            self.Statut.REPORTEE: "attente",
            self.Statut.ANNULEE: "neutre",
        }[self.statut]

    @property
    def perimetre(self):
        return self.plan.perimetre


class Avancement(models.Model):
    """
    Compte rendu d'etape sur une activite.

    L'avancement de l'activite reflete toujours le dernier compte rendu : la
    valeur n'est pas saisie directement sur l'activite.
    """

    activite = models.ForeignKey(Activite, on_delete=models.CASCADE, related_name="avancements")
    date = models.DateField("date du point", default=timezone.localdate)
    taux = models.PositiveSmallIntegerField("avancement declare (%)")
    realisations = models.TextField("realisations de la periode")
    difficultes = models.TextField("difficultes rencontrees", blank=True)
    effectif_touche = models.PositiveIntegerField("beneficiaires touches sur la periode", default=0)
    montant_engage = models.DecimalField(
        "montant engage sur la periode (FCFA)", max_digits=14, decimal_places=0, default=0
    )
    piece_jointe = models.FileField("piece jointe", upload_to="activites/avancements/%Y/", blank=True)
    auteur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="avancements_saisis"
    )
    saisi_le = models.DateTimeField("saisi le", auto_now_add=True)

    class Meta:
        verbose_name = "point d'avancement"
        verbose_name_plural = "points d'avancement"
        ordering = ["-date", "-saisi_le"]

    def __str__(self):
        return f"{self.activite.code} - {self.date:%d/%m/%Y} : {self.taux} %"

    def clean(self):
        if self.taux is not None and self.taux > 100:
            raise ValidationError({"taux": "L'avancement ne peut depasser 100 %."})


class Indicateur(Horodate):
    """Indicateur de resultat rattache a une activite."""

    activite = models.ForeignKey(Activite, on_delete=models.CASCADE, related_name="indicateurs")
    libelle = models.CharField("libelle", max_length=250)
    unite = models.CharField("unite", max_length=50, blank=True, help_text="Ex. enseignants, guides, seances.")
    valeur_cible = models.DecimalField("valeur cible", max_digits=12, decimal_places=2)
    valeur_realisee = models.DecimalField(
        "valeur realisee", max_digits=12, decimal_places=2, default=0
    )
    commentaire = models.TextField("commentaire", blank=True)

    class Meta:
        verbose_name = "indicateur"
        verbose_name_plural = "indicateurs"
        ordering = ["activite", "libelle"]

    def __str__(self):
        return f"{self.libelle} ({self.valeur_realisee}/{self.valeur_cible} {self.unite})".strip()

    @property
    def taux_atteinte(self):
        if not self.valeur_cible:
            return 0
        return min(100, round(100 * float(self.valeur_realisee) / float(self.valeur_cible)))

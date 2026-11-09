"""
Circuits de validation parametrables.

Chaque perimetre de gestion autonome definit, pour chaque type d'acte, la suite
des etapes a franchir. Une etape ne nomme pas un agent mais une *fonction*
(`Designation`) : le valideur reel est resolu au moment de la soumission, ce qui
evite de reprendre les circuits a chaque mouvement de personnel.

Si un perimetre ne definit pas de circuit pour un type d'acte, le circuit
modele de son type de perimetre s'applique (`perimetre` a vide).
"""
from django.db import models

from apps.core.models import Horodate, Perimetre


class Designation(models.TextChoices):
    """Comment designer le valideur d'une etape, au moment de la soumission."""

    SUPERIEUR = "SUPERIEUR", "Superieur hierarchique de l'agent"
    RESPONSABLE_STRUCTURE = "RESPONSABLE_STRUCTURE", "Responsable de la structure de l'agent"
    RESPONSABLE_SOUS_DIRECTION = "RESPONSABLE_SOUS_DIRECTION", "Sous-directeur de rattachement"
    RESPONSABLE_PERIMETRE = "RESPONSABLE_PERIMETRE", "Responsable du perimetre (chef d'antenne, chef de centre, directeur)"
    DIRECTEUR_REGIONAL = "DIRECTEUR_REGIONAL", "Directeur regional (DRENA) du ressort"
    ROLE = "ROLE", "Premier agent portant un role donne"


class Condition(models.TextChoices):
    """
    Condition d'application d'une etape, evaluee sur la demande.

    Une etape porte zero, une ou plusieurs conditions ; elle s'applique
    lorsqu'elles sont toutes remplies.
    """

    SI_VISA_RH = "SI_VISA_RH", "Si le type d'acte exige le visa du service du personnel"
    SI_SIGNATURE_DIRECTEUR = "SI_SIGNATURE_DIRECTEUR", "Si le type d'acte exige la signature du directeur"
    SI_SANS_SIGNATURE_DIRECTEUR = (
        "SI_SANS_SIGNATURE_DIRECTEUR",
        "Si le type d'acte n'exige pas la signature du directeur",
    )
    SI_HORS_PERIMETRE = "SI_HORS_PERIMETRE", "Si la mission sort du ressort de la DRENA"
    SI_DANS_PERIMETRE = "SI_DANS_PERIMETRE", "Si la mission reste dans le ressort de la DRENA"
    SI_AGENT_EST_RESPONSABLE = "SI_AGENT_EST_RESPONSABLE", "Si l'agent dirige lui-meme le perimetre"
    SI_AGENT_NEST_PAS_RESPONSABLE = "SI_AGENT_NEST_PAS_RESPONSABLE", "Si l'agent ne dirige pas le perimetre"


class CircuitQuerySet(models.QuerySet):
    def actifs(self):
        return self.filter(actif=True)

    def pour(self, perimetre, type_acte):
        """Circuit du perimetre s'il existe, sinon le modele de son type."""
        propre = self.actifs().filter(perimetre=perimetre, type_acte=type_acte).first()
        if propre is not None:
            return propre
        type_perimetre = perimetre.type if perimetre is not None else Perimetre.Type.CENTRALE
        return (
            self.actifs()
            .filter(perimetre__isnull=True, type_perimetre=type_perimetre, type_acte=type_acte)
            .first()
        )


class Circuit(Horodate):
    """Suite d'etapes applicable a un type d'acte dans un perimetre."""

    perimetre = models.ForeignKey(
        Perimetre,
        verbose_name="perimetre",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="circuits",
        help_text="Laisser vide pour definir le circuit modele d'un type de perimetre.",
    )
    type_perimetre = models.CharField(
        "type de perimetre",
        max_length=10,
        choices=Perimetre.Type.choices,
        help_text="Type auquel s'applique le circuit modele.",
    )
    type_acte = models.CharField(
        "type d'acte",
        max_length=25,
        help_text="Code du type de demande (CONGE_ANNUEL, ORDRE_MISSION...).",
    )
    libelle = models.CharField("libelle", max_length=150, blank=True)
    actif = models.BooleanField("actif", default=True)

    objects = CircuitQuerySet.as_manager()

    class Meta:
        verbose_name = "circuit de validation"
        verbose_name_plural = "circuits de validation"
        ordering = ["type_perimetre", "type_acte"]
        constraints = [
            models.UniqueConstraint(
                fields=["perimetre", "type_acte"],
                condition=models.Q(perimetre__isnull=False),
                name="un_circuit_par_acte_et_perimetre",
            ),
            models.UniqueConstraint(
                fields=["type_perimetre", "type_acte"],
                condition=models.Q(perimetre__isnull=True),
                name="un_circuit_modele_par_acte_et_type",
            ),
        ]

    def __str__(self):
        cible = self.perimetre.code if self.perimetre_id else f"modele {self.get_type_perimetre_display()}"
        return f"{self.type_acte} - {cible}"

    def save(self, *args, **kwargs):
        if self.perimetre_id and not self.type_perimetre:
            self.type_perimetre = self.perimetre.type
        super().save(*args, **kwargs)

    @property
    def est_modele(self):
        return self.perimetre_id is None


class Etape(models.Model):
    """Une etape du circuit : qui valide, sous quelle condition."""

    circuit = models.ForeignKey(Circuit, on_delete=models.CASCADE, related_name="etapes")
    ordre = models.PositiveSmallIntegerField("ordre")
    libelle = models.CharField("intitule de l'etape", max_length=150)
    designation = models.CharField(
        "valideur", max_length=30, choices=Designation.choices, default=Designation.SUPERIEUR
    )
    role = models.CharField(
        "role recherche",
        max_length=25,
        blank=True,
        help_text="Uniquement pour la designation « premier agent portant un role donne ».",
    )
    conditions = models.JSONField(
        "conditions",
        default=list,
        blank=True,
        help_text="Codes des conditions a remplir simultanement. Vide : l'etape s'applique toujours.",
    )
    facultative = models.BooleanField(
        "etape facultative",
        default=True,
        help_text="Si aucun agent ne correspond, l'etape est ignoree au lieu de bloquer la soumission.",
    )

    class Meta:
        verbose_name = "etape de circuit"
        verbose_name_plural = "etapes de circuit"
        ordering = ["circuit", "ordre"]
        unique_together = ("circuit", "ordre")

    def __str__(self):
        return f"{self.ordre}. {self.libelle}"

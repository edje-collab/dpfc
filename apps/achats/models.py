"""
Achats et gestion des stocks.

Chaque perimetre exprime ses besoins, les fait valider, commande, receptionne
puis range au magasin. Deux principes gouvernent ce module :

  - le stock n'est pas un compteur libre : il derive du journal des mouvements,
    de sorte que toute quantite s'explique par une entree, une sortie ou un
    inventaire ;
  - le circuit de validation d'un besoin depend du montant : une fourniture de
    bureau ne remonte pas au directeur, un marche si. Le seuil est parametre
    dans les circuits, non code ici.
"""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils import timezone

from apps.core.models import Horodate, Perimetre, Structure

# Type d'acte sous lequel les circuits des expressions de besoin sont ranges.
TYPE_ACTE_BESOIN = "BESOIN"

# Regles du besoin, dans la forme attendue par le moteur de circuits.
REGLES_BESOIN = {
    "visa_rh": False,
    "signature_directeur": False,
    "decompte_solde": False,
    "justificatif": False,
    "document": "Expression de besoin",
}


class Fournisseur(Horodate):
    """Prestataire ou fournisseur consulte par la direction."""

    nom = models.CharField("raison sociale", max_length=200)
    contact = models.CharField("personne a contacter", max_length=150, blank=True)
    telephone = models.CharField("telephone", max_length=40, blank=True)
    email = models.EmailField("courriel", blank=True)
    ncc = models.CharField(
        "compte contribuable", max_length=30, blank=True,
        help_text="Numero de compte contribuable, exige pour toute commande.",
    )
    domaine = models.CharField("domaine d'activite", max_length=150, blank=True)
    adresse = models.CharField("adresse", max_length=255, blank=True)
    actif = models.BooleanField("actif", default=True)

    class Meta:
        verbose_name = "fournisseur"
        verbose_name_plural = "fournisseurs"
        ordering = ["nom"]

    def __str__(self):
        return self.nom


class Article(Horodate):
    """
    Article tenu au magasin.

    Le champ `stock` est une vue cachee du journal des mouvements : il est
    recalcule a chaque mouvement et ne se saisit jamais a la main.
    """

    perimetre = models.ForeignKey(
        Perimetre, verbose_name="perimetre", on_delete=models.PROTECT, related_name="articles",
        help_text="Chaque perimetre tient son propre magasin.",
    )
    code = models.CharField("code", max_length=30)
    designation = models.CharField("designation", max_length=200)
    unite = models.CharField("unite", max_length=20, default="piece")
    seuil_alerte = models.PositiveIntegerField(
        "seuil d'alerte", default=0,
        help_text="En dessous ou a ce niveau, l'article est signale a reapprovisionner.",
    )
    stock = models.IntegerField("stock", default=0, editable=False)
    actif = models.BooleanField("actif", default=True)

    class Meta:
        verbose_name = "article"
        verbose_name_plural = "articles"
        ordering = ["designation"]
        constraints = [
            models.UniqueConstraint(fields=["perimetre", "code"], name="un_code_article_par_perimetre")
        ]

    def __str__(self):
        return f"{self.code} - {self.designation}"

    def get_absolute_url(self):
        return reverse("achats:article_detail", args=[self.pk])

    @property
    def sous_seuil(self):
        return self.stock <= self.seuil_alerte

    @property
    def stock_reel(self):
        """Stock recalcule depuis le journal, pour verifier la vue cachee."""
        total = 0
        for mouvement in self.mouvements.order_by("date", "id"):
            total = mouvement.appliquer(total)
        return total


class ExpressionBesoinQuerySet(models.QuerySet):
    def visibles_par(self, agent):
        if agent.est_rh or agent.est_direction or agent.peut_administrer:
            return self
        perimetre = agent.perimetre
        return self.filter(perimetre=perimetre) if perimetre else self.none()


class ExpressionBesoin(Horodate):
    """
    Demande d'achat formulee par un agent.

    Elle expose l'interface attendue par le moteur de circuits — `agent`,
    `type`, `regles`, `montant_circuit` — ce qui lui permet de reutiliser les
    circuits parametrables sans que ceux-ci connaissent les achats.
    """

    class Statut(models.TextChoices):
        BROUILLON = "BROUILLON", "Brouillon"
        EN_CIRCUIT = "EN_CIRCUIT", "En validation"
        VALIDE = "VALIDE", "Valide"
        REJETE = "REJETE", "Rejete"
        COMMANDE = "COMMANDE", "Commande"
        SOLDE = "SOLDE", "Solde"

    perimetre = models.ForeignKey(
        Perimetre, verbose_name="perimetre", on_delete=models.PROTECT, related_name="besoins"
    )
    numero = models.CharField("numero", max_length=40, unique=True, blank=True)
    objet = models.CharField("objet", max_length=255)
    justification = models.TextField("justification", blank=True)
    activite = models.ForeignKey(
        "activites.Activite", verbose_name="activite du plan d'action",
        on_delete=models.SET_NULL, null=True, blank=True, related_name="besoins",
        help_text="Rattache la depense au plan d'action : son execution budgetaire y sera reportee.",
    )
    structure = models.ForeignKey(
        Structure, verbose_name="structure beneficiaire", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="besoins",
    )
    demandeur = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="demandeur", on_delete=models.PROTECT,
        related_name="besoins",
    )
    date_souhaitee = models.DateField("date de mise a disposition souhaitee", null=True, blank=True)
    statut = models.CharField("statut", max_length=12, choices=Statut.choices, default=Statut.BROUILLON)
    soumis_le = models.DateTimeField("soumis le", null=True, blank=True)
    clos_le = models.DateTimeField("clos le", null=True, blank=True)
    motif_rejet = models.TextField("motif du rejet", blank=True)

    objects = ExpressionBesoinQuerySet.as_manager()

    class Meta:
        verbose_name = "expression de besoin"
        verbose_name_plural = "expressions de besoin"
        ordering = ["-cree_le"]
        indexes = [models.Index(fields=["perimetre", "statut"])]

    def __str__(self):
        return f"{self.numero or 'Brouillon'} - {self.objet}"

    def save(self, *args, **kwargs):
        if not self.numero and self.perimetre_id:
            self.numero = self.attribuer_numero()
        super().save(*args, **kwargs)

    def attribuer_numero(self):
        """Serie annuelle propre au perimetre : EB-0001/2026/APFC-GBK."""
        annee = timezone.localdate().year
        code = self.perimetre.code
        existants = set(
            ExpressionBesoin.objects.filter(
                perimetre_id=self.perimetre_id, numero__contains=f"/{annee}/"
            ).values_list("numero", flat=True)
        )
        rang = len(existants) + 1
        while f"EB-{rang:04d}/{annee}/{code}" in existants:
            rang += 1
        return f"EB-{rang:04d}/{annee}/{code}"

    def get_absolute_url(self):
        return reverse("achats:besoin_detail", args=[self.pk])

    # --- Interface attendue par le moteur de circuits ---------------------
    @property
    def agent(self):
        return self.demandeur

    @property
    def type(self):
        return TYPE_ACTE_BESOIN

    @property
    def regles(self):
        return REGLES_BESOIN

    @property
    def est_mission_hors_perimetre(self):
        return False

    @property
    def montant_circuit(self):
        """Montant servant a choisir les etapes : c'est l'estime du besoin."""
        return self.montant_estime

    # --- Montants ---------------------------------------------------------
    @property
    def montant_estime(self):
        total = self.lignes.aggregate(
            t=models.Sum(models.F("quantite") * models.F("prix_unitaire"))
        )["t"]
        return total or 0

    @property
    def offre_retenue(self):
        return self.offres.filter(retenue=True).first()

    # --- Etat -------------------------------------------------------------
    @property
    def est_modifiable(self):
        return self.statut == self.Statut.BROUILLON

    @property
    def est_validee(self):
        return self.statut in {self.Statut.VALIDE, self.Statut.COMMANDE, self.Statut.SOLDE}

    @property
    def couleur_statut(self):
        return {
            self.Statut.BROUILLON: "neutre",
            self.Statut.EN_CIRCUIT: "attente",
            self.Statut.VALIDE: "ok",
            self.Statut.REJETE: "ko",
            self.Statut.COMMANDE: "attente",
            self.Statut.SOLDE: "ok",
        }[self.statut]

    def etape_courante(self):
        return self.validations.filter(decision=ValidationBesoin.Decision.ATTENTE).order_by("ordre").first()

    def progression(self):
        total = self.validations.count()
        if not total:
            return 0
        faites = self.validations.exclude(decision=ValidationBesoin.Decision.ATTENTE).count()
        return round(100 * faites / total)


class LigneBesoin(models.Model):
    """Article demande, en quantite et en prix estime."""

    besoin = models.ForeignKey(ExpressionBesoin, on_delete=models.CASCADE, related_name="lignes")
    article = models.ForeignKey(
        Article, verbose_name="article du magasin", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="lignes_besoin",
        help_text="A renseigner si l'article est deja tenu au magasin.",
    )
    designation = models.CharField("designation", max_length=200)
    quantite = models.PositiveIntegerField("quantite")
    unite = models.CharField("unite", max_length=20, default="piece")
    prix_unitaire = models.DecimalField(
        "prix unitaire estime (FCFA)", max_digits=12, decimal_places=0, default=0
    )

    class Meta:
        verbose_name = "ligne de besoin"
        verbose_name_plural = "lignes de besoin"
        ordering = ["id"]

    def __str__(self):
        return f"{self.quantite} {self.unite} - {self.designation}"

    def save(self, *args, **kwargs):
        if self.article_id and not self.designation:
            self.designation = self.article.designation
            self.unite = self.article.unite
        super().save(*args, **kwargs)

    @property
    def montant(self):
        return self.quantite * self.prix_unitaire


class ValidationBesoin(models.Model):
    """Etape du circuit de validation d'un besoin."""

    class Decision(models.TextChoices):
        ATTENTE = "ATTENTE", "En attente"
        FAVORABLE = "FAVORABLE", "Avis favorable"
        DEFAVORABLE = "DEFAVORABLE", "Avis defavorable"
        IGNOREE = "IGNOREE", "Etape sans objet"

    besoin = models.ForeignKey(ExpressionBesoin, on_delete=models.CASCADE, related_name="validations")
    ordre = models.PositiveSmallIntegerField("ordre")
    libelle = models.CharField("intitule de l'etape", max_length=150)
    valideur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="besoins_a_valider"
    )
    decision = models.CharField(max_length=12, choices=Decision.choices, default=Decision.ATTENTE)
    commentaire = models.TextField("observation", blank=True)
    decide_le = models.DateTimeField("decide le", null=True, blank=True)

    class Meta:
        verbose_name = "validation de besoin"
        verbose_name_plural = "validations de besoin"
        ordering = ["besoin", "ordre"]
        constraints = [
            models.UniqueConstraint(fields=["besoin", "ordre"], name="une_validation_par_ordre_et_besoin")
        ]

    def __str__(self):
        return f"{self.besoin_id} - {self.ordre}. {self.libelle}"


class Offre(Horodate):
    """Cotation recue d'un fournisseur en reponse a un besoin."""

    besoin = models.ForeignKey(ExpressionBesoin, on_delete=models.CASCADE, related_name="offres")
    fournisseur = models.ForeignKey(
        Fournisseur, verbose_name="fournisseur", on_delete=models.PROTECT, related_name="offres"
    )
    montant = models.DecimalField("montant de l'offre (FCFA)", max_digits=14, decimal_places=0)
    delai_jours = models.PositiveSmallIntegerField("delai de livraison (jours)", null=True, blank=True)
    fichier = models.FileField("offre recue", upload_to="achats/offres/%Y/", blank=True)
    observations = models.CharField("observations", max_length=255, blank=True)
    retenue = models.BooleanField("retenue", default=False)

    class Meta:
        verbose_name = "offre"
        verbose_name_plural = "offres"
        ordering = ["montant"]
        constraints = [
            models.UniqueConstraint(
                fields=["besoin", "fournisseur"], name="une_offre_par_fournisseur_et_besoin"
            )
        ]

    def __str__(self):
        return f"{self.fournisseur} - {self.montant:.0f} FCFA"


class BonCommande(Horodate):
    """Commande passee au fournisseur retenu."""

    class Statut(models.TextChoices):
        EMIS = "EMIS", "Emis"
        RECEPTIONNE = "RECEPTIONNE", "Receptionne"
        PAYE = "PAYE", "Paye"
        ANNULE = "ANNULE", "Annule"

    numero = models.CharField("numero", max_length=40, unique=True, blank=True)
    besoin = models.OneToOneField(
        ExpressionBesoin, verbose_name="besoin", on_delete=models.PROTECT, related_name="bon_commande"
    )
    fournisseur = models.ForeignKey(
        Fournisseur, verbose_name="fournisseur", on_delete=models.PROTECT, related_name="commandes"
    )
    montant = models.DecimalField("montant (FCFA)", max_digits=14, decimal_places=0)
    date_emission = models.DateField("date d'emission", default=timezone.localdate)
    statut = models.CharField("statut", max_length=12, choices=Statut.choices, default=Statut.EMIS)
    emis_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    # Reception
    date_reception = models.DateField("date de reception", null=True, blank=True)
    observations_reception = models.CharField("observations a la reception", max_length=255, blank=True)
    receptionne_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    # Facture
    facture_numero = models.CharField("numero de facture", max_length=40, blank=True)
    facture_montant = models.DecimalField(
        "montant facture (FCFA)", max_digits=14, decimal_places=0, null=True, blank=True
    )
    facture_fichier = models.FileField("facture", upload_to="achats/factures/%Y/", blank=True)
    paye_le = models.DateField("paye le", null=True, blank=True)
    motif_annulation = models.TextField("motif de l'annulation", blank=True)

    class Meta:
        verbose_name = "bon de commande"
        verbose_name_plural = "bons de commande"
        ordering = ["-date_emission", "-id"]

    def __str__(self):
        return self.numero

    def save(self, *args, **kwargs):
        if not self.numero and self.besoin_id:
            self.numero = self.attribuer_numero()
        super().save(*args, **kwargs)

    def attribuer_numero(self):
        annee = timezone.localdate().year
        code = self.besoin.perimetre.code
        existants = set(
            BonCommande.objects.filter(
                besoin__perimetre=self.besoin.perimetre_id, numero__contains=f"/{annee}/"
            ).values_list("numero", flat=True)
        )
        rang = len(existants) + 1
        while f"BC-{rang:04d}/{annee}/{code}" in existants:
            rang += 1
        return f"BC-{rang:04d}/{annee}/{code}"

    def get_absolute_url(self):
        return self.besoin.get_absolute_url()

    def clean(self):
        if self.facture_montant is not None and self.montant:
            ecart = abs(self.facture_montant - self.montant)
            if ecart > self.montant * 0.1:
                raise ValidationError(
                    {"facture_montant": "La facture s'ecarte de plus de 10 % du bon de commande. "
                                        "Justifiez l'ecart dans les observations."}
                )

    @property
    def est_receptionne(self):
        return self.statut in {self.Statut.RECEPTIONNE, self.Statut.PAYE}

    @property
    def couleur_statut(self):
        return {
            self.Statut.EMIS: "attente",
            self.Statut.RECEPTIONNE: "ok",
            self.Statut.PAYE: "ok",
            self.Statut.ANNULE: "neutre",
        }[self.statut]


class MouvementStock(Horodate):
    """
    Ecriture du journal du magasin.

    C'est l'unique facon de faire varier un stock : l'entree ajoute, la sortie
    retranche, l'inventaire fixe la quantite comptee. Rien ne se corrige en
    modifiant un compteur.
    """

    class Type(models.TextChoices):
        ENTREE = "ENTREE", "Entree"
        SORTIE = "SORTIE", "Sortie"
        INVENTAIRE = "INVENTAIRE", "Inventaire"

    article = models.ForeignKey(
        Article, verbose_name="article", on_delete=models.PROTECT, related_name="mouvements"
    )
    type = models.CharField("type", max_length=10, choices=Type.choices)
    quantite = models.PositiveIntegerField(
        "quantite", help_text="Pour un inventaire : la quantite effectivement comptee."
    )
    date = models.DateField("date", default=timezone.localdate)
    motif = models.CharField("motif", max_length=200, blank=True)
    beneficiaire = models.CharField("beneficiaire", max_length=150, blank=True)
    bon_commande = models.ForeignKey(
        BonCommande, verbose_name="bon de commande", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="mouvements",
    )
    saisi_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    stock_apres = models.IntegerField("stock apres le mouvement", default=0, editable=False)

    class Meta:
        verbose_name = "mouvement de stock"
        verbose_name_plural = "mouvements de stock"
        ordering = ["-date", "-id"]
        indexes = [models.Index(fields=["article", "-date"])]

    def __str__(self):
        return f"{self.get_type_display()} de {self.quantite} - {self.article}"

    def appliquer(self, stock_avant):
        """Stock resultant de ce mouvement, applique a un stock donne."""
        if self.type == self.Type.ENTREE:
            return stock_avant + self.quantite
        if self.type == self.Type.SORTIE:
            return stock_avant - self.quantite
        return self.quantite  # inventaire : la quantite comptee fait foi

    @property
    def variation(self):
        """Effet du mouvement sur le stock, signe."""
        if self.type == self.Type.ENTREE:
            return self.quantite
        if self.type == self.Type.SORTIE:
            return -self.quantite
        return 0


class Equipement(Horodate):
    """Bien durable inscrit a l'inventaire et affecte a un agent."""

    class Etat(models.TextChoices):
        BON = "BON", "Bon etat"
        PASSABLE = "PASSABLE", "Etat passable"
        PANNE = "PANNE", "En panne"
        REFORME = "REFORME", "Reforme"

    perimetre = models.ForeignKey(
        Perimetre, verbose_name="perimetre", on_delete=models.PROTECT, related_name="equipements"
    )
    code_inventaire = models.CharField("code d'inventaire", max_length=40, unique=True)
    designation = models.CharField("designation", max_length=200)
    marque = models.CharField("marque et modele", max_length=150, blank=True)
    numero_serie = models.CharField("numero de serie", max_length=80, blank=True)
    structure = models.ForeignKey(
        Structure, verbose_name="structure", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="equipements",
    )
    affecte_a = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="affecte a", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="equipements",
    )
    date_acquisition = models.DateField("acquis le", null=True, blank=True)
    valeur = models.DecimalField(
        "valeur d'acquisition (FCFA)", max_digits=12, decimal_places=0, default=0
    )
    bon_commande = models.ForeignKey(
        BonCommande, verbose_name="bon de commande", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="equipements",
    )
    etat = models.CharField("etat", max_length=10, choices=Etat.choices, default=Etat.BON)
    observations = models.TextField("observations", blank=True)

    class Meta:
        verbose_name = "equipement"
        verbose_name_plural = "equipements"
        ordering = ["code_inventaire"]

    def __str__(self):
        return f"{self.code_inventaire} - {self.designation}"

    @property
    def couleur_etat(self):
        return {
            self.Etat.BON: "ok",
            self.Etat.PASSABLE: "attente",
            self.Etat.PANNE: "ko",
            self.Etat.REFORME: "neutre",
        }[self.etat]

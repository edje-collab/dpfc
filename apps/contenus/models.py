from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify

from apps.core.models import Horodate, Structure


def _slug_unique(instance, base, champ="slug"):
    base = slugify(base)[:190] or "element"
    modele = instance.__class__
    slug, i = base, 2
    while modele.objects.filter(**{champ: slug}).exclude(pk=instance.pk).exists():
        slug = f"{base}-{i}"
        i += 1
    return slug


class Categorie(Horodate):
    nom = models.CharField("nom", max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    couleur = models.CharField("couleur (hexadecimal)", max_length=7, default="#1a9e8f")

    class Meta:
        verbose_name = "categorie d'actualite"
        verbose_name_plural = "categories d'actualites"
        ordering = ["nom"]

    def __str__(self):
        return self.nom

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = _slug_unique(self, self.nom)
        super().save(*args, **kwargs)


class ActualiteQuerySet(models.QuerySet):
    def publiees(self):
        return self.filter(publiee=True, date_publication__lte=timezone.now())


class Actualite(Horodate):
    titre = models.CharField("titre", max_length=250)
    slug = models.SlugField(max_length=270, unique=True, blank=True)
    chapeau = models.CharField("chapeau", max_length=300, help_text="Resume affiche sur la page d'accueil.")
    contenu = models.TextField("contenu")
    image = models.ImageField("image", upload_to="actualites/%Y/%m/", blank=True)
    categorie = models.ForeignKey(
        Categorie, on_delete=models.SET_NULL, null=True, blank=True, related_name="actualites"
    )
    structure = models.ForeignKey(
        Structure,
        verbose_name="structure emettrice",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="actualites",
    )
    auteur = models.ForeignKey(
        "accounts.Agent", on_delete=models.SET_NULL, null=True, blank=True, related_name="actualites"
    )
    date_publication = models.DateTimeField("date de publication", default=timezone.now)
    publiee = models.BooleanField("publiee", default=False)
    a_la_une = models.BooleanField("a la une", default=False)
    vues = models.PositiveIntegerField("nombre de lectures", default=0)

    objects = ActualiteQuerySet.as_manager()

    class Meta:
        verbose_name = "actualite"
        verbose_name_plural = "actualites"
        ordering = ["-date_publication"]
        indexes = [models.Index(fields=["-date_publication", "publiee"])]

    def __str__(self):
        return self.titre

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = _slug_unique(self, self.titre)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("contenus:actualite_detail", args=[self.slug])


class Ressource(Horodate):
    """Programme scolaire, guide pedagogique, fiche de travaux pratiques, module de formation."""

    class Type(models.TextChoices):
        PROGRAMME = "PROGRAMME", "Programme scolaire"
        GUIDE = "GUIDE", "Guide pedagogique"
        FICHE_TP = "FICHE_TP", "Fiche de travaux pratiques"
        MODULE = "MODULE", "Module de formation"
        TEXTE = "TEXTE", "Texte officiel"

    class Niveau(models.TextChoices):
        PRESCOLAIRE = "PRESCOLAIRE", "Prescolaire"
        PRIMAIRE = "PRIMAIRE", "Primaire"
        SECONDAIRE_1 = "SECONDAIRE_1", "Secondaire 1er cycle"
        SECONDAIRE_2 = "SECONDAIRE_2", "Secondaire 2nd cycle"
        TECHNIQUE = "TECHNIQUE", "Enseignement technique"
        TOUS = "TOUS", "Tous niveaux"

    titre = models.CharField("titre", max_length=250)
    slug = models.SlugField(max_length=270, unique=True, blank=True)
    type = models.CharField("type de ressource", max_length=15, choices=Type.choices)
    niveau = models.CharField("niveau", max_length=15, choices=Niveau.choices, default=Niveau.TOUS)
    discipline = models.CharField("discipline", max_length=120, blank=True)
    classe = models.CharField("classe", max_length=60, blank=True, help_text="Ex. CP1, CM2, 6e, Tle D")
    description = models.TextField("description", blank=True)
    fichier = models.FileField("fichier", upload_to="ressources/%Y/", blank=True)
    lien_externe = models.URLField("lien externe", blank=True)
    annee = models.PositiveSmallIntegerField("annee de parution", null=True, blank=True)
    telechargements = models.PositiveIntegerField("telechargements", default=0)
    publiee = models.BooleanField("publiee", default=True)

    class Meta:
        verbose_name = "ressource pedagogique"
        verbose_name_plural = "ressources pedagogiques"
        ordering = ["type", "titre"]

    def __str__(self):
        return self.titre

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = _slug_unique(self, self.titre)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("contenus:ressource_detail", args=[self.slug])

    @property
    def url_fichier(self):
        if self.fichier:
            return self.fichier.url
        return self.lien_externe


class Projet(Horodate):
    """Projet ou programme strategique porte par la DPFC (SIGE, PNAPAS, FOAD, CNRPN...)."""

    class Etat(models.TextChoices):
        PREPARATION = "PREPARATION", "En preparation"
        EN_COURS = "EN_COURS", "En cours"
        ACHEVE = "ACHEVE", "Acheve"

    nom = models.CharField("nom du projet", max_length=200)
    sigle = models.CharField("sigle", max_length=30)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    accroche = models.CharField("accroche", max_length=250, blank=True)
    description = models.TextField("description", blank=True)
    objectifs = models.TextField("objectifs", blank=True)
    partenaires = models.CharField("partenaires", max_length=250, blank=True)
    couleur = models.CharField("couleur de la vignette", max_length=7, default="#1a9e8f")
    icone = models.CharField(
        "icone", max_length=20, default="reseau",
        help_text="Cle d'icone : livre, reseau, ecran, graphique, sigle",
    )
    image = models.ImageField("image", upload_to="projets/", blank=True)
    etat = models.CharField("etat", max_length=15, choices=Etat.choices, default=Etat.EN_COURS)
    ordre = models.PositiveSmallIntegerField("ordre d'affichage", default=10)
    publie = models.BooleanField("publie", default=True)

    class Meta:
        verbose_name = "projet strategique"
        verbose_name_plural = "projets strategiques"
        ordering = ["ordre", "sigle"]

    def __str__(self):
        return self.sigle

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = _slug_unique(self, self.sigle)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("contenus:projet_detail", args=[self.slug])


class Evenement(Horodate):
    class Type(models.TextChoices):
        FORMATION = "FORMATION", "Formation"
        ATELIER = "ATELIER", "Atelier"
        SEMINAIRE = "SEMINAIRE", "Seminaire"
        REUNION = "REUNION", "Reunion"
        AUTRE = "AUTRE", "Autre"

    titre = models.CharField("titre", max_length=250)
    slug = models.SlugField(max_length=270, unique=True, blank=True)
    type = models.CharField("type", max_length=15, choices=Type.choices, default=Type.FORMATION)
    description = models.TextField("description", blank=True)
    date_debut = models.DateField("date de debut")
    date_fin = models.DateField("date de fin", null=True, blank=True)
    heure_debut = models.TimeField("heure de debut", null=True, blank=True)
    lieu = models.CharField("lieu", max_length=200, default="Abidjan")
    structure = models.ForeignKey(
        Structure, on_delete=models.SET_NULL, null=True, blank=True, related_name="evenements",
        verbose_name="structure organisatrice",
    )
    public_cible = models.CharField("public cible", max_length=200, blank=True)
    inscription_requise = models.BooleanField("inscription requise", default=False)
    publie = models.BooleanField("publie", default=True)

    class Meta:
        verbose_name = "evenement"
        verbose_name_plural = "evenements et formations"
        ordering = ["date_debut"]

    def __str__(self):
        return f"{self.titre} ({self.date_debut:%d/%m/%Y})"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = _slug_unique(self, f"{self.titre}-{self.date_debut}")
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("contenus:evenement_detail", args=[self.slug])

    @property
    def est_passe(self):
        return (self.date_fin or self.date_debut) < timezone.localdate()


class PageStatique(Horodate):
    """Page editoriale : presentation, missions, organisation, FOAD..."""

    titre = models.CharField("titre", max_length=200)
    slug = models.SlugField(max_length=220, unique=True)
    chapeau = models.CharField("chapeau", max_length=300, blank=True)
    contenu = models.TextField("contenu", help_text="HTML simple autorise.")
    image = models.ImageField("image d'en-tete", upload_to="pages/", blank=True)
    dans_le_menu = models.BooleanField("afficher dans le menu", default=False)
    ordre = models.PositiveSmallIntegerField("ordre", default=10)
    publiee = models.BooleanField("publiee", default=True)

    class Meta:
        verbose_name = "page editoriale"
        verbose_name_plural = "pages editoriales"
        ordering = ["ordre", "titre"]

    def __str__(self):
        return self.titre

    def get_absolute_url(self):
        return reverse("contenus:page", args=[self.slug])


class MessageContact(models.Model):
    class Etat(models.TextChoices):
        NOUVEAU = "NOUVEAU", "Nouveau"
        EN_COURS = "EN_COURS", "En cours de traitement"
        TRAITE = "TRAITE", "Traite"

    nom = models.CharField("nom et prenoms", max_length=150)
    email = models.EmailField("courriel")
    telephone = models.CharField("telephone", max_length=40, blank=True)
    sujet = models.CharField("sujet", max_length=200)
    message = models.TextField("message")
    structure_destinataire = models.ForeignKey(
        Structure, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="messages", verbose_name="service ou antenne destinataire",
    )
    etat = models.CharField(max_length=10, choices=Etat.choices, default=Etat.NOUVEAU)
    recu_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "message de contact"
        verbose_name_plural = "messages de contact"
        ordering = ["-recu_le"]

    def __str__(self):
        return f"{self.sujet} - {self.nom}"

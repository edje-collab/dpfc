from django.db import models
from django.utils.text import slugify
from wagtail.admin.panels import FieldPanel, MultiFieldPanel
from wagtail.contrib.settings.models import BaseGenericSetting, register_setting


class Horodate(models.Model):
    """Classe de base : tracabilite de creation et de modification."""

    cree_le = models.DateTimeField("cree le", auto_now_add=True)
    modifie_le = models.DateTimeField("modifie le", auto_now=True)

    class Meta:
        abstract = True


class Region(Horodate):
    """Region administrative / district abritant une antenne de la DPFC."""

    nom = models.CharField("nom de la region", max_length=120, unique=True)
    code = models.CharField("code", max_length=10, unique=True)
    chef_lieu = models.CharField("chef-lieu", max_length=120, blank=True)
    dren = models.CharField(
        "DRENA de rattachement",
        max_length=150,
        blank=True,
        help_text="Direction Regionale de l'Education Nationale et de l'Alphabetisation.",
    )

    class Meta:
        verbose_name = "region"
        verbose_name_plural = "regions"
        ordering = ["nom"]

    def __str__(self):
        return self.nom


class Structure(Horodate):
    """
    Unite d'organisation du portail.

    Deux familles :
      - la direction centrale (DPFC) et ses sous-directions / services ;
      - les antennes regionales de la pedagogie et de la formation continue.
    """

    class Type(models.TextChoices):
        DIRECTION = "DIRECTION", "Direction centrale"
        SOUS_DIRECTION = "SOUS_DIRECTION", "Sous-direction"
        SERVICE = "SERVICE", "Service"
        DRENAET = "DRENAET", "Direction regionale (DRENAET)"
        ANTENNE = "ANTENNE", "Antenne de la pedagogie et de la formation continue"
        BUREAU = "BUREAU", "Bureau d'antenne"

    class Rattachement(models.TextChoices):
        CENTRALE = "CENTRALE", "Direction centrale (nationale)"
        REGION = "REGION", "Region"

    nom = models.CharField("libelle", max_length=200)
    sigle = models.CharField("sigle", max_length=30, blank=True)
    slug = models.SlugField("identifiant d'URL", max_length=220, unique=True, blank=True)
    type = models.CharField("type", max_length=20, choices=Type.choices)
    rattachement = models.CharField(
        "rattachement", max_length=10, choices=Rattachement.choices, default=Rattachement.CENTRALE
    )
    parent = models.ForeignKey(
        "self",
        verbose_name="structure de rattachement",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="enfants",
    )
    region = models.ForeignKey(
        Region,
        verbose_name="region",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="structures",
        help_text="Obligatoire pour une antenne ou un bureau d'antenne.",
    )
    drenaet = models.ForeignKey(
        "self",
        verbose_name="DRENAET de rattachement",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="antennes_du_perimetre",
        limit_choices_to={"type": "DRENAET"},
        help_text="Direction regionale dans le perimetre de laquelle l'antenne exerce.",
    )
    responsable = models.ForeignKey(
        "accounts.Agent",
        verbose_name="responsable",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="structures_dirigees",
    )
    adresse = models.CharField("adresse", max_length=255, blank=True)
    telephone = models.CharField("telephone", max_length=40, blank=True)
    email = models.EmailField("courriel", blank=True)
    presentation = models.TextField("presentation", blank=True)
    photo = models.ImageField("photo", upload_to="structures/", blank=True)
    active = models.BooleanField("active", default=True)

    class Meta:
        verbose_name = "structure"
        verbose_name_plural = "structures"
        ordering = ["rattachement", "type", "nom"]

    def __str__(self):
        return f"{self.sigle or self.nom}"

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(f"{self.sigle or ''} {self.nom}")[:200] or "structure"
            slug, i = base, 2
            while Structure.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{i}"
                i += 1
            self.slug = slug
        if self.type in (self.Type.ANTENNE, self.Type.BUREAU, self.Type.DRENAET):
            self.rattachement = self.Rattachement.REGION
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        from apps.site_public.models import url_antenne

        return url_antenne(self)

    @property
    def est_antenne(self):
        return self.type in (self.Type.ANTENNE, self.Type.BUREAU)

    @property
    def perimetre_drenaet(self):
        """DRENAET dont depend la structure (l'antenne elle-meme si c'en est une)."""
        if self.type == self.Type.DRENAET:
            return self
        if self.drenaet_id:
            return self.drenaet
        noeud, garde = self.parent, 0
        while noeud is not None and garde < 6:
            if noeud.type == self.Type.DRENAET:
                return noeud
            if noeud.drenaet_id:
                return noeud.drenaet
            noeud = noeud.parent
            garde += 1
        return None

    @property
    def chaine(self):
        """Chaine hierarchique ascendante, de la structure vers la direction."""
        noeud, chemin = self, []
        while noeud is not None and len(chemin) < 10:
            chemin.append(noeud)
            noeud = noeud.parent
        return chemin

    @property
    def libelle_complet(self):
        if self.region_id and self.est_antenne:
            return f"{self.nom} ({self.region})"
        return self.nom


@register_setting(icon="cog")
class ConfigurationSite(BaseGenericSetting, Horodate):
    """Parametres editoriaux du site public (instance unique, editee dans Wagtail)."""

    nom_site = models.CharField(
        "nom du site", max_length=200, default="Direction de la Pedagogie et de la Formation Continue"
    )
    sigle = models.CharField("sigle", max_length=20, default="DPFC")
    ministere = models.CharField(
        "ministere",
        max_length=250,
        default="Ministere de l'Education Nationale, de l'Alphabetisation et de l'Enseignement Technique",
    )
    logo = models.ForeignKey(
        "wagtailimages.Image",
        verbose_name="logo",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    adresse = models.CharField("adresse", max_length=255, default="Cocody II Plateaux, Abidjan")
    telephone = models.CharField("telephone", max_length=40, default="+225 27 22 41 00 00")
    email = models.EmailField("courriel", default="contact@dpfc.education.ci")
    facebook = models.URLField("Facebook", blank=True)
    youtube = models.URLField("YouTube", blank=True)
    lien_foad = models.URLField("plateforme FOAD", blank=True, default="https://ecole-ci.org")
    pied_de_page = models.TextField(
        "texte du pied de page",
        blank=True,
        default="La DPFC concoit les programmes educatifs, les guides d'execution et pilote la formation continue des enseignants.",
    )
    afficher_espace_agent = models.BooleanField(
        "afficher le bouton « Espace agent »",
        default=True,
        help_text="Decochez pour masquer l'acces a l'espace agent (menu et pied de page) sur le site public. "
        "La page de connexion reste accessible par son adresse directe.",
    )

    panels = [
        MultiFieldPanel([FieldPanel("nom_site"), FieldPanel("sigle"), FieldPanel("ministere"), FieldPanel("logo")],
                        heading="Identite"),
        MultiFieldPanel([FieldPanel("adresse"), FieldPanel("telephone"), FieldPanel("email"),
                         FieldPanel("facebook"), FieldPanel("youtube"), FieldPanel("lien_foad")],
                        heading="Coordonnees"),
        FieldPanel("pied_de_page"),
        MultiFieldPanel([FieldPanel("afficher_espace_agent")], heading="Espace agent"),
    ]

    class Meta:
        verbose_name = "configuration du site"
        verbose_name_plural = "configuration du site"

    def __str__(self):
        return self.nom_site

    @classmethod
    def actuelle(cls, request=None):
        return cls.load(request_or_site=request)


class JournalAction(models.Model):
    """Journal d'audit des actions sensibles (validations, publications)."""

    agent = models.ForeignKey(
        "accounts.Agent", on_delete=models.SET_NULL, null=True, related_name="journal"
    )
    action = models.CharField("action", max_length=150)
    objet = models.CharField("objet", max_length=200, blank=True)
    details = models.TextField("details", blank=True)
    adresse_ip = models.GenericIPAddressField("adresse IP", null=True, blank=True)
    horodatage = models.DateTimeField("horodatage", auto_now_add=True)

    class Meta:
        verbose_name = "entree de journal"
        verbose_name_plural = "journal d'audit"
        ordering = ["-horodatage"]

    def __str__(self):
        return f"{self.horodatage:%d/%m/%Y %H:%M} - {self.action}"

    @classmethod
    def tracer(cls, agent, action, objet="", details="", requete=None):
        ip = None
        if requete is not None:
            ip = requete.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip() or requete.META.get(
                "REMOTE_ADDR"
            )
        return cls.objects.create(
            agent=agent if getattr(agent, "is_authenticated", False) else None,
            action=action,
            objet=str(objet)[:200],
            details=details,
            adresse_ip=ip or None,
        )

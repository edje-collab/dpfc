"""
Organisation de la Direction de la Pedagogie et de la Formation Continue.

Reference : decret n° 2026-509 du 05 aout 2026 portant organisation du Ministere
de l'Education Nationale, de l'Alphabetisation et de l'Enseignement Technique.

  - article 27 : la Direction Generale de la Pedagogie, des Curricula et du Suivi
    des Programmes comprend trois directions centrales, dont la DPFC ;
  - article 28 : la DPFC comprend trois sous-directions ;
  - article 41 : les services exterieurs sont les DRENA, les DDENA et les DRETPI.

Deux structures s'ajoutent par arrete d'organisation (article 1) et disposent
d'une gestion autonome :
  - les antennes de la pedagogie et de la formation continue (APFC) en region,
    dirigees par un chef d'antenne ;
  - le Centre National de Ressources Pedagogiques Numeriques (CNRPN), service
    rattache a la direction, dirige par un chef de centre.

Le `Perimetre` modelise cette autonomie : c'est l'unite dans laquelle les actes
sont instruits, numerotes et pilotes.
"""
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


class PerimetreQuerySet(models.QuerySet):
    def actifs(self):
        return self.filter(actif=True)

    def deconcentres(self):
        """Perimetres implantes hors de la direction centrale."""
        return self.actifs().exclude(type=Perimetre.Type.CENTRALE)


class Perimetre(Horodate):
    """
    Unite de gestion autonome.

    Les trois familles de perimetres sont autonomes : la direction centrale,
    dirigee par un directeur central, chaque antenne regionale, dirigee par un
    chef d'antenne, et le CNRPN, dirige par un chef de centre. Chacune instruit
    ses propres actes, tient sa propre numerotation et dispose de ses propres
    tableaux de bord. Un agent appartient a un seul perimetre, deduit de sa
    structure d'affectation.

    Ce qui les distingue n'est pas l'autonomie mais l'implantation : la
    direction centrale est au niveau national, les autres sont deconcentrees
    ou rattachees.
    """

    class Type(models.TextChoices):
        CENTRALE = "CENTRALE", "Direction centrale"
        ANTENNE = "ANTENNE", "Antenne regionale (APFC)"
        CENTRE = "CENTRE", "Service rattache (CNRPN)"

    code = models.CharField(
        "code",
        max_length=20,
        unique=True,
        help_text="Sert de suffixe aux numeros d'actes du perimetre. Ex. DPFC, APFC-GBK, CNRPN.",
    )
    nom = models.CharField("libelle", max_length=200)
    type = models.CharField("type", max_length=10, choices=Type.choices)
    region = models.ForeignKey(
        Region,
        verbose_name="region",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="perimetres",
        help_text="Obligatoire pour une antenne regionale.",
    )
    actif = models.BooleanField("actif", default=True)

    objects = PerimetreQuerySet.as_manager()

    class Meta:
        verbose_name = "perimetre de gestion"
        verbose_name_plural = "perimetres de gestion"
        ordering = ["type", "nom"]

    def __str__(self):
        return self.code

    @property
    def est_autonome(self):
        """Tout perimetre est autonome : son responsable y instruit les actes."""
        return True

    @property
    def est_deconcentre(self):
        """Vrai hors direction centrale : antenne regionale ou centre rattache."""
        return self.type in {self.Type.ANTENNE, self.Type.CENTRE}

    @property
    def structure_racine(self):
        return self.structures.filter(perimetre_racine=True).first()

    @property
    def responsable(self):
        """Chef d'antenne, chef de centre ou directeur, selon le type."""
        racine = self.structure_racine
        return racine.responsable if racine is not None and racine.responsable_id else None

    @property
    def libelle_responsable(self):
        """Qualite du responsable, telle qu'elle figure sur les actes."""
        return {
            self.Type.CENTRALE: "Directeur de la pedagogie et de la formation continue",
            self.Type.ANTENNE: "Chef d'antenne (APFC)",
            self.Type.CENTRE: "Chef de centre (CNRPN)",
        }[self.type]

    def agents(self):
        from apps.accounts.models import Agent

        return Agent.objects.filter(structure__perimetre=self, is_active=True)

    @classmethod
    def centrale(cls):
        return cls.objects.filter(type=cls.Type.CENTRALE).first()


class Structure(Horodate):
    """
    Unite d'organisation : du niveau ministeriel jusqu'au bureau d'antenne.

    Les types reprennent la nomenclature du decret n° 2026-509, completee par
    les structures creees par arrete (antennes et centre national).
    """

    class Type(models.TextChoices):
        DIRECTION_GENERALE = "DIRECTION_GENERALE", "Direction generale"
        DIRECTION = "DIRECTION", "Direction centrale"
        SOUS_DIRECTION = "SOUS_DIRECTION", "Sous-direction"
        SERVICE = "SERVICE", "Service"
        CENTRE = "CENTRE", "Centre national (CNRPN)"
        ANTENNE = "ANTENNE", "Antenne de la pedagogie et de la formation continue"
        BUREAU = "BUREAU", "Bureau d'antenne"
        DRENA = "DRENA", "Direction regionale (DRENA)"
        DDENA = "DDENA", "Direction departementale (DDENA)"
        DRETPI = "DRETPI", "Direction regionale de l'enseignement technique (DRETPI)"

    # Types relevant des services exterieurs du ministere (article 41).
    TYPES_SERVICES_EXTERIEURS = {Type.DRENA, Type.DDENA, Type.DRETPI}
    # Types implantes en region.
    TYPES_REGIONAUX = {Type.ANTENNE, Type.BUREAU, Type.DRENA, Type.DDENA, Type.DRETPI}

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
    perimetre = models.ForeignKey(
        Perimetre,
        verbose_name="perimetre de gestion",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="structures",
        help_text="Unite de gestion autonome dont releve la structure.",
    )
    perimetre_racine = models.BooleanField(
        "structure de tete du perimetre",
        default=False,
        help_text="Une seule structure par perimetre : celle que dirige le responsable.",
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
        help_text="Obligatoire pour une antenne, un bureau ou un service exterieur.",
    )
    drena = models.ForeignKey(
        "self",
        verbose_name="DRENA de rattachement",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="antennes_du_perimetre",
        limit_choices_to={"type": "DRENA"},
        help_text="Direction regionale dans le ressort de laquelle l'antenne exerce.",
    )
    responsable = models.ForeignKey(
        "accounts.Agent",
        verbose_name="responsable",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="structures_dirigees",
    )
    ordre = models.PositiveSmallIntegerField("ordre d'affichage", default=10)
    adresse = models.CharField("adresse", max_length=255, blank=True)
    telephone = models.CharField("telephone", max_length=40, blank=True)
    email = models.EmailField("courriel", blank=True)
    presentation = models.TextField("presentation", blank=True)
    photo = models.ImageField("photo", upload_to="structures/", blank=True)
    active = models.BooleanField("active", default=True)

    class Meta:
        verbose_name = "structure"
        verbose_name_plural = "structures"
        ordering = ["rattachement", "ordre", "type", "nom"]
        constraints = [
            models.UniqueConstraint(
                fields=["perimetre"],
                condition=models.Q(perimetre_racine=True),
                name="une_seule_structure_de_tete_par_perimetre",
            )
        ]

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
        if self.type in self.TYPES_REGIONAUX:
            self.rattachement = self.Rattachement.REGION
        if self.perimetre_id is None and self.parent_id:
            self.perimetre_id = self.parent.perimetre_id
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        from apps.site_public.models import url_antenne

        return url_antenne(self)

    @property
    def est_antenne(self):
        return self.type in (self.Type.ANTENNE, self.Type.BUREAU)

    @property
    def est_service_exterieur(self):
        return self.type in self.TYPES_SERVICES_EXTERIEURS

    @property
    def perimetre_drena(self):
        """DRENA dont depend la structure (elle-meme si c'en est une)."""
        if self.type == self.Type.DRENA:
            return self
        if self.drena_id:
            return self.drena
        noeud, garde = self.parent, 0
        while noeud is not None and garde < 6:
            if noeud.type == self.Type.DRENA:
                return noeud
            if noeud.drena_id:
                return noeud.drena
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
    direction_generale = models.CharField(
        "direction generale de rattachement",
        max_length=250,
        default="Direction Generale de la Pedagogie, des Curricula et du Suivi des Programmes",
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
        MultiFieldPanel(
            [FieldPanel("nom_site"), FieldPanel("sigle"), FieldPanel("ministere"),
             FieldPanel("direction_generale"), FieldPanel("logo")],
            heading="Identite",
        ),
        MultiFieldPanel(
            [FieldPanel("adresse"), FieldPanel("telephone"), FieldPanel("email"),
             FieldPanel("facebook"), FieldPanel("youtube"), FieldPanel("lien_foad")],
            heading="Coordonnees",
        ),
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
    perimetre = models.ForeignKey(
        Perimetre, on_delete=models.SET_NULL, null=True, blank=True, related_name="journal"
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
        indexes = [models.Index(fields=["-horodatage", "perimetre"])]

    def __str__(self):
        return f"{self.horodatage:%d/%m/%Y %H:%M} - {self.action}"

    @classmethod
    def tracer(cls, agent, action, objet="", details="", requete=None):
        ip = None
        if requete is not None:
            ip = requete.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip() or requete.META.get(
                "REMOTE_ADDR"
            )
        authentifie = getattr(agent, "is_authenticated", False)
        return cls.objects.create(
            agent=agent if authentifie else None,
            perimetre=getattr(agent, "perimetre", None) if authentifie else None,
            action=action,
            objet=str(objet)[:200],
            details=details,
            adresse_ip=ip or None,
        )

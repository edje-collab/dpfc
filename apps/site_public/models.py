"""
Site public de la DPFC, gere par Wagtail.

Arborescence :
    PageAccueil (racine du site)
    ├── PageEditoriale   (presentation, pages libres)
    ├── IndexActualites  → PageActualite
    ├── IndexRessources  (catalogue des ressources, snippets)
    ├── PageFOAD
    ├── IndexProjets     → PageProjet
    ├── IndexEvenements  → PageEvenement
    ├── IndexAntennes    (structures regionales, modele core.Structure)
    └── PageContact

Les ressources pedagogiques, les categories et les messages de contact
sont des « snippets » Wagtail (contenus structures hors arborescence).
"""
from django.contrib import messages
from django.core.paginator import Paginator
from django.db import models
from django.db.models import Count, F, Q
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.utils.text import slugify
from wagtail.admin.panels import FieldPanel, FieldRowPanel, MultiFieldPanel
from wagtail.contrib.routable_page.models import RoutablePageMixin, path
from wagtail.fields import RichTextField, StreamField
from wagtail.models import Page
from wagtail.search import index

from apps.core.models import Horodate, Region, Structure

from .blocks import BLOCS_EDITORIAUX, FONCTIONS_TEXTE


def _slug_unique(instance, base, champ="slug"):
    base = slugify(base)[:190] or "element"
    modele = instance.__class__
    slug, i = base, 2
    while modele.objects.filter(**{champ: slug}).exclude(pk=instance.pk).exists():
        slug = f"{base}-{i}"
        i += 1
    return slug


def page_cle(modele):
    """Premiere page publiee d'un type donne (index des ressources, des antennes...)."""
    return modele.objects.live().first()


def url_index(modele, suffixe=""):
    page = page_cle(modele)
    if page is None or page.url is None:
        return "/"
    return f"{page.url}{suffixe}"


# ---------------------------------------------------------------------------
# Snippets
# ---------------------------------------------------------------------------
class Categorie(Horodate):
    nom = models.CharField("nom", max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    couleur = models.CharField("couleur (hexadecimal)", max_length=7, default="#1a9e8f")

    panels = [FieldPanel("nom"), FieldPanel("couleur")]

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


class Ressource(index.Indexed, Horodate):
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
    document = models.ForeignKey(
        "wagtaildocs.Document",
        verbose_name="fichier",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    lien_externe = models.URLField("lien externe", blank=True)
    annee = models.PositiveSmallIntegerField("annee de parution", null=True, blank=True)
    telechargements = models.PositiveIntegerField("telechargements", default=0)
    publiee = models.BooleanField("publiee", default=True)

    panels = [
        FieldPanel("titre"),
        FieldRowPanel([FieldPanel("type"), FieldPanel("niveau")]),
        FieldRowPanel([FieldPanel("discipline"), FieldPanel("classe"), FieldPanel("annee")]),
        FieldPanel("description"),
        MultiFieldPanel([FieldPanel("document"), FieldPanel("lien_externe")], heading="Fichier"),
        FieldPanel("publiee"),
    ]

    search_fields = [
        index.SearchField("titre", boost=2),
        index.AutocompleteField("titre"),
        index.SearchField("description"),
        index.SearchField("discipline"),
        index.FilterField("publiee"),
        index.FilterField("type"),
        index.FilterField("niveau"),
    ]

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
        return url_index(IndexRessources, f"{self.slug}/")

    @property
    def url_telechargement(self):
        return url_index(IndexRessources, f"{self.slug}/telecharger/")

    @property
    def url_fichier(self):
        if self.document_id:
            return self.document.url
        return self.lien_externe


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
        Structure,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="messages",
        verbose_name="service ou antenne destinataire",
    )
    etat = models.CharField(max_length=10, choices=Etat.choices, default=Etat.NOUVEAU)
    recu_le = models.DateTimeField(auto_now_add=True)

    panels = [
        MultiFieldPanel(
            [FieldPanel("nom"), FieldPanel("email"), FieldPanel("telephone")], heading="Expediteur"
        ),
        FieldPanel("structure_destinataire"),
        FieldPanel("sujet"),
        FieldPanel("message"),
        FieldPanel("etat"),
    ]

    class Meta:
        verbose_name = "message de contact"
        verbose_name_plural = "messages de contact"
        ordering = ["-recu_le"]

    def __str__(self):
        return f"{self.sujet} - {self.nom}"


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------
class PageAccueil(Page):
    """Racine du site public : banniere, acces rapides, actualites, agenda, projets."""

    template = "public/accueil.html"
    max_count = 1
    parent_page_types = ["wagtailcore.Page"]
    subpage_types = [
        "site_public.PageEditoriale",
        "site_public.IndexActualites",
        "site_public.IndexRessources",
        "site_public.PageFOAD",
        "site_public.IndexProjets",
        "site_public.IndexEvenements",
        "site_public.IndexAntennes",
        "site_public.PageContact",
    ]

    slogan = models.CharField(
        "slogan de la banniere", max_length=200, default="Oeuvrons pour une ecole ivoirienne de qualite"
    )
    sous_titre = models.CharField(
        "sous-titre de la banniere",
        max_length=300,
        blank=True,
        default="Programmes, guides et formations au service des enseignants de Cote d'Ivoire.",
    )
    image_banniere = models.ForeignKey(
        "wagtailimages.Image",
        verbose_name="image de la banniere",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    content_panels = Page.content_panels + [
        MultiFieldPanel(
            [FieldPanel("slogan"), FieldPanel("sous_titre"), FieldPanel("image_banniere")],
            heading="Banniere",
        ),
    ]

    class Meta:
        verbose_name = "page d'accueil"

    def get_context(self, request, *args, **kwargs):
        contexte = super().get_context(request, *args, **kwargs)
        aujourdhui = timezone.localdate()
        publiees = PageActualite.publiees().select_related("categorie")
        une = publiees.filter(a_la_une=True).first() or publiees.first()
        contexte.update(
            {
                "une": une,
                "actualites": publiees.exclude(pk=une.pk)[:3] if une else [],
                "familles_ressources": [
                    {
                        "code": Ressource.Type.PROGRAMME,
                        "libelle": "Programmes scolaires",
                        "texte": "Les programmes educatifs en vigueur, du prescolaire au secondaire.",
                        "icone": "livre",
                        "ton": "menthe",
                    },
                    {
                        "code": Ressource.Type.GUIDE,
                        "libelle": "Guides pedagogiques",
                        "texte": "Guides d'execution des programmes et supports d'accompagnement.",
                        "icone": "liste",
                        "ton": "vert",
                    },
                    {
                        "code": Ressource.Type.FICHE_TP,
                        "libelle": "Fiches de travaux pratiques",
                        "texte": "Fiches de seances et protocoles pour les activites pratiques.",
                        "icone": "ecran",
                        "ton": "azur",
                    },
                ],
                "projets": PageProjet.publies()[:4],
                "evenements": PageEvenement.a_venir()[:4],
                "nb_ressources": Ressource.objects.filter(publiee=True).count(),
                "nb_antennes": Structure.objects.filter(type=Structure.Type.ANTENNE, active=True).count(),
                "nb_formations": PageEvenement.objects.live()
                .filter(type=PageEvenement.Type.FORMATION, date_debut__year=aujourdhui.year)
                .count(),
            }
        )
        return contexte


class PageEditoriale(Page):
    """Page libre : presentation, missions, organisation, mentions..."""

    template = "public/page.html"
    parent_page_types = ["site_public.PageAccueil", "site_public.PageEditoriale"]
    subpage_types = ["site_public.PageEditoriale"]

    chapeau = models.CharField("chapeau", max_length=300, blank=True)
    image = models.ForeignKey(
        "wagtailimages.Image",
        verbose_name="image d'en-tete",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    corps = StreamField(BLOCS_EDITORIAUX, verbose_name="contenu", blank=True)
    afficher_organisation = models.BooleanField(
        "afficher l'organisation de la direction centrale",
        default=False,
        help_text="Ajoute le tableau des sous-directions et services sous le contenu.",
    )

    content_panels = Page.content_panels + [
        FieldPanel("chapeau"),
        FieldPanel("image"),
        FieldPanel("corps"),
        FieldPanel("afficher_organisation"),
    ]
    search_fields = Page.search_fields + [index.SearchField("chapeau"), index.SearchField("corps")]

    class Meta:
        verbose_name = "page editoriale"

    def get_context(self, request, *args, **kwargs):
        contexte = super().get_context(request, *args, **kwargs)
        if self.afficher_organisation:
            contexte["structures"] = Structure.objects.filter(
                rattachement=Structure.Rattachement.CENTRALE, active=True
            ).select_related("responsable")
            contexte["nb_antennes"] = Structure.objects.filter(
                type=Structure.Type.ANTENNE, active=True
            ).count()
        return contexte


class IndexActualites(Page):
    template = "public/actualites.html"
    max_count = 1
    parent_page_types = ["site_public.PageAccueil"]
    subpage_types = ["site_public.PageActualite"]

    introduction = models.CharField("introduction", max_length=300, blank=True)

    content_panels = Page.content_panels + [FieldPanel("introduction")]

    class Meta:
        verbose_name = "liste des actualites"

    def get_context(self, request, *args, **kwargs):
        contexte = super().get_context(request, *args, **kwargs)
        liste = PageActualite.publiees().select_related("categorie", "structure")
        categorie = request.GET.get("categorie", "")
        q = request.GET.get("q", "").strip()
        if categorie:
            liste = liste.filter(categorie__slug=categorie)
        if q:
            liste = liste.filter(Q(title__icontains=q) | Q(chapeau__icontains=q) | Q(corps__icontains=q))
        contexte.update(
            {
                "page_obj": Paginator(liste, 9).get_page(request.GET.get("page")),
                "categories": Categorie.objects.annotate(
                    n=Count("actualites", filter=Q(actualites__live=True))
                ).filter(n__gt=0),
                "categorie_active": categorie,
                "q": q,
            }
        )
        return contexte


class PageActualite(Page):
    template = "public/actualite_detail.html"
    parent_page_types = ["site_public.IndexActualites"]
    subpage_types = []

    chapeau = models.CharField("chapeau", max_length=300, help_text="Resume affiche dans les listes.")
    image = models.ForeignKey(
        "wagtailimages.Image",
        verbose_name="image",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    corps = StreamField(BLOCS_EDITORIAUX, verbose_name="contenu", blank=True)
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
    a_la_une = models.BooleanField("a la une", default=False)
    vues = models.PositiveIntegerField("nombre de lectures", default=0, editable=False)

    content_panels = Page.content_panels + [
        FieldPanel("chapeau"),
        FieldPanel("image"),
        FieldPanel("corps"),
    ]
    promote_panels = Page.promote_panels + [
        MultiFieldPanel(
            [
                FieldPanel("categorie"),
                FieldPanel("structure"),
                FieldPanel("date_publication"),
                FieldPanel("a_la_une"),
            ],
            heading="Classement",
        ),
    ]
    search_fields = Page.search_fields + [
        index.SearchField("chapeau"),
        index.SearchField("corps"),
        index.FilterField("date_publication"),
    ]

    class Meta:
        verbose_name = "actualite"
        verbose_name_plural = "actualites"

    @classmethod
    def publiees(cls):
        return cls.objects.live().filter(date_publication__lte=timezone.now()).order_by("-date_publication")

    def serve(self, request, *args, **kwargs):
        PageActualite.objects.filter(pk=self.pk).update(vues=F("vues") + 1)
        return super().serve(request, *args, **kwargs)

    def get_context(self, request, *args, **kwargs):
        contexte = super().get_context(request, *args, **kwargs)
        contexte["article"] = self
        contexte["similaires"] = (
            PageActualite.publiees().filter(categorie=self.categorie).exclude(pk=self.pk)[:3]
            if self.categorie_id
            else []
        )
        return contexte


class IndexRessources(RoutablePageMixin, Page):
    """Catalogue des ressources pedagogiques (liste filtrable, fiche, telechargement)."""

    template = "public/ressources.html"
    max_count = 1
    parent_page_types = ["site_public.PageAccueil"]
    subpage_types = []

    introduction = models.TextField(
        "introduction",
        blank=True,
        default="Programmes educatifs, guides d'execution, fiches de travaux pratiques et modules de "
        "formation, du prescolaire a l'enseignement technique.",
    )

    content_panels = Page.content_panels + [FieldPanel("introduction")]

    class Meta:
        verbose_name = "catalogue des ressources"

    @path("")
    def liste(self, request):
        liste = Ressource.objects.filter(publiee=True)
        type_r = request.GET.get("type", "")
        niveau = request.GET.get("niveau", "")
        q = request.GET.get("q", "").strip()
        if type_r:
            liste = liste.filter(type=type_r)
        if niveau:
            liste = liste.filter(niveau=niveau)
        if q:
            liste = liste.filter(
                Q(titre__icontains=q) | Q(description__icontains=q) | Q(discipline__icontains=q)
            )
        return self.render(
            request,
            context_overrides={
                "page_obj": Paginator(liste, 12).get_page(request.GET.get("page")),
                "types": Ressource.Type.choices,
                "niveaux": Ressource.Niveau.choices,
                "type_actif": type_r,
                "niveau_actif": niveau,
                "q": q,
                "total": liste.count(),
            },
        )

    @path("<slug:slug>/", name="detail")
    def detail(self, request, slug):
        ressource = get_object_or_404(Ressource, slug=slug, publiee=True)
        return self.render(
            request, template="public/ressource_detail.html", context_overrides={"ressource": ressource}
        )

    @path("<slug:slug>/telecharger/", name="telecharger")
    def telecharger(self, request, slug):
        ressource = get_object_or_404(Ressource, slug=slug, publiee=True)
        Ressource.objects.filter(pk=ressource.pk).update(telechargements=F("telechargements") + 1)
        cible = ressource.url_fichier
        if not cible:
            messages.error(request, "Le fichier de cette ressource n'est pas encore disponible.")
            return redirect(ressource.get_absolute_url())
        return redirect(cible)


class PageFOAD(Page):
    """Formation ouverte et a distance : presentation, modules et sessions."""

    template = "public/foad.html"
    max_count = 1
    parent_page_types = ["site_public.PageAccueil"]
    subpage_types = []

    corps = StreamField(BLOCS_EDITORIAUX, verbose_name="contenu", blank=True)
    lien_plateforme = models.URLField("plateforme FOAD", blank=True, default="https://ecole-ci.org")

    content_panels = Page.content_panels + [FieldPanel("corps"), FieldPanel("lien_plateforme")]
    search_fields = Page.search_fields + [index.SearchField("corps")]

    class Meta:
        verbose_name = "page FOAD"

    def get_context(self, request, *args, **kwargs):
        contexte = super().get_context(request, *args, **kwargs)
        contexte["modules"] = Ressource.objects.filter(publiee=True, type=Ressource.Type.MODULE)[:12]
        contexte["formations"] = PageEvenement.a_venir().filter(type=PageEvenement.Type.FORMATION)[:6]
        return contexte


class IndexProjets(Page):
    template = "public/projets.html"
    max_count = 1
    parent_page_types = ["site_public.PageAccueil"]
    subpage_types = ["site_public.PageProjet"]

    introduction = models.CharField(
        "introduction",
        max_length=300,
        blank=True,
        default="Les programmes structurants pilotes par la direction, en lien avec les partenaires "
        "techniques et financiers du systeme educatif.",
    )

    content_panels = Page.content_panels + [FieldPanel("introduction")]

    class Meta:
        verbose_name = "liste des projets"

    def get_context(self, request, *args, **kwargs):
        contexte = super().get_context(request, *args, **kwargs)
        contexte["projets"] = PageProjet.publies()
        return contexte


class PageProjet(Page):
    """Projet ou programme strategique porte par la DPFC (SIGE, PNAPAS, FOAD, CNRPN...)."""

    template = "public/projet_detail.html"
    parent_page_types = ["site_public.IndexProjets"]
    subpage_types = []

    class Etat(models.TextChoices):
        PREPARATION = "PREPARATION", "En preparation"
        EN_COURS = "EN_COURS", "En cours"
        ACHEVE = "ACHEVE", "Acheve"

    ICONES = [
        ("sigle", "Sigle du projet"),
        ("livre", "Livre"),
        ("reseau", "Reseau"),
        ("ecran", "Ecran"),
        ("graphique", "Graphique"),
    ]

    sigle = models.CharField("sigle", max_length=30)
    accroche = models.CharField("accroche", max_length=250, blank=True)
    corps = StreamField(BLOCS_EDITORIAUX, verbose_name="description", blank=True)
    objectifs = RichTextField("objectifs", blank=True, features=FONCTIONS_TEXTE)
    partenaires = models.CharField("partenaires", max_length=250, blank=True)
    couleur = models.CharField("couleur de la vignette", max_length=7, default="#1a9e8f")
    icone = models.CharField("icone", max_length=20, choices=ICONES, default="reseau")
    image = models.ForeignKey(
        "wagtailimages.Image",
        verbose_name="image",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    etat = models.CharField("etat", max_length=15, choices=Etat.choices, default=Etat.EN_COURS)
    ordre = models.PositiveSmallIntegerField("ordre d'affichage", default=10)

    content_panels = Page.content_panels + [
        FieldRowPanel([FieldPanel("sigle"), FieldPanel("etat")]),
        FieldPanel("accroche"),
        FieldPanel("image"),
        FieldPanel("corps"),
        FieldPanel("objectifs"),
        FieldPanel("partenaires"),
        MultiFieldPanel(
            [FieldRowPanel([FieldPanel("couleur"), FieldPanel("icone")]), FieldPanel("ordre")],
            heading="Vignette",
        ),
    ]
    search_fields = Page.search_fields + [
        index.SearchField("sigle", boost=2),
        index.SearchField("accroche"),
        index.SearchField("corps"),
    ]

    class Meta:
        verbose_name = "projet strategique"
        verbose_name_plural = "projets strategiques"

    @property
    def nom(self):
        return self.title

    @classmethod
    def publies(cls):
        return cls.objects.live().order_by("ordre", "sigle")

    def get_context(self, request, *args, **kwargs):
        contexte = super().get_context(request, *args, **kwargs)
        contexte["projet"] = self
        contexte["autres"] = PageProjet.publies().exclude(pk=self.pk)[:3]
        return contexte


class IndexEvenements(Page):
    template = "public/evenements.html"
    max_count = 1
    parent_page_types = ["site_public.PageAccueil"]
    subpage_types = ["site_public.PageEvenement"]

    class Meta:
        verbose_name = "agenda"

    def get_context(self, request, *args, **kwargs):
        contexte = super().get_context(request, *args, **kwargs)
        aujourdhui = timezone.localdate()
        contexte["a_venir"] = PageEvenement.a_venir()
        contexte["passes"] = (
            PageEvenement.objects.live().filter(date_debut__lt=aujourdhui).order_by("-date_debut")[:10]
        )
        return contexte


class PageEvenement(Page):
    template = "public/evenement_detail.html"
    parent_page_types = ["site_public.IndexEvenements"]
    subpage_types = []

    class Type(models.TextChoices):
        FORMATION = "FORMATION", "Formation"
        ATELIER = "ATELIER", "Atelier"
        SEMINAIRE = "SEMINAIRE", "Seminaire"
        REUNION = "REUNION", "Reunion"
        AUTRE = "AUTRE", "Autre"

    type = models.CharField("type", max_length=15, choices=Type.choices, default=Type.FORMATION)
    corps = StreamField(BLOCS_EDITORIAUX, verbose_name="description", blank=True)
    date_debut = models.DateField("date de debut")
    date_fin = models.DateField("date de fin", null=True, blank=True)
    heure_debut = models.TimeField("heure de debut", null=True, blank=True)
    lieu = models.CharField("lieu", max_length=200, default="Abidjan")
    structure = models.ForeignKey(
        Structure,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="evenements",
        verbose_name="structure organisatrice",
    )
    public_cible = models.CharField("public cible", max_length=200, blank=True)
    inscription_requise = models.BooleanField("inscription requise", default=False)

    content_panels = Page.content_panels + [
        FieldRowPanel([FieldPanel("type"), FieldPanel("lieu")]),
        FieldRowPanel([FieldPanel("date_debut"), FieldPanel("date_fin"), FieldPanel("heure_debut")]),
        FieldPanel("structure"),
        FieldPanel("public_cible"),
        FieldPanel("inscription_requise"),
        FieldPanel("corps"),
    ]
    search_fields = Page.search_fields + [
        index.SearchField("corps"),
        index.SearchField("lieu"),
        index.FilterField("date_debut"),
    ]

    class Meta:
        verbose_name = "evenement"
        verbose_name_plural = "evenements et formations"

    @classmethod
    def a_venir(cls):
        return cls.objects.live().filter(date_debut__gte=timezone.localdate()).order_by("date_debut")

    @property
    def est_passe(self):
        return (self.date_fin or self.date_debut) < timezone.localdate()

    def get_context(self, request, *args, **kwargs):
        contexte = super().get_context(request, *args, **kwargs)
        contexte["evenement"] = self
        return contexte


class IndexAntennes(RoutablePageMixin, Page):
    """Antennes regionales (modele core.Structure) : liste filtrable et fiche."""

    template = "public/antennes.html"
    max_count = 1
    parent_page_types = ["site_public.PageAccueil"]
    subpage_types = []

    introduction = models.TextField(
        "introduction",
        blank=True,
        default="Relais de la direction centrale dans les regions, les antennes accompagnent les "
        "enseignants au plus pres des ecoles : encadrement pedagogique, formation continue et "
        "remontee des besoins du terrain.",
    )

    content_panels = Page.content_panels + [FieldPanel("introduction")]

    class Meta:
        verbose_name = "liste des antennes"

    @path("")
    def liste(self, request):
        liste = (
            Structure.objects.filter(type=Structure.Type.ANTENNE, active=True)
            .select_related("region", "responsable")
            .annotate(nb_agents=Count("agents"))
        )
        region = request.GET.get("region", "")
        if region:
            liste = liste.filter(region__code=region)
        return self.render(
            request,
            context_overrides={
                "antennes": liste,
                "regions": Region.objects.all(),
                "region_active": region,
            },
        )

    @path("<slug:slug>/", name="detail")
    def detail(self, request, slug):
        antenne = get_object_or_404(
            Structure.objects.select_related("region", "responsable"), slug=slug, active=True
        )
        return self.render(
            request,
            template="public/antenne_detail.html",
            context_overrides={
                "antenne": antenne,
                "actualites": PageActualite.publiees().filter(structure=antenne)[:4],
                "evenements": PageEvenement.a_venir().filter(structure=antenne)[:4],
            },
        )


def url_antenne(structure):
    return url_index(IndexAntennes, f"{structure.slug}/")


class PageContact(Page):
    template = "public/contact.html"
    max_count = 1
    parent_page_types = ["site_public.PageAccueil"]
    subpage_types = []

    introduction = models.TextField(
        "introduction",
        blank=True,
        default="Une question sur un programme, un guide ou une formation ? Adressez votre message au "
        "service concerne ou a l'antenne de votre region.",
    )
    message_confirmation = models.CharField(
        "message apres envoi",
        max_length=250,
        default="Message envoye. La DPFC vous repondra a l'adresse indiquee.",
    )

    content_panels = Page.content_panels + [FieldPanel("introduction"), FieldPanel("message_confirmation")]

    class Meta:
        verbose_name = "page de contact"

    def serve(self, request, *args, **kwargs):
        from .forms import ContactForm

        form = ContactForm(request.POST or None)
        if request.method == "POST" and form.is_valid():
            form.save()
            messages.success(request, self.message_confirmation)
            return redirect(self.url)
        self._form = form
        return super().serve(request, *args, **kwargs)

    def get_context(self, request, *args, **kwargs):
        from .forms import ContactForm

        contexte = super().get_context(request, *args, **kwargs)
        contexte["form"] = getattr(self, "_form", None) or ContactForm()
        return contexte

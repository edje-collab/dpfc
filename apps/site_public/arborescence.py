"""
Construction de l'arborescence Wagtail du site public.

Utilise par les commandes d'initialisation (`initialiser_dpfc`, `initialiser_donnees`)
et par les tests. Chaque fonction est idempotente : elle retrouve la page existante
ou la cree, sans jamais ecraser un contenu deja saisi.
"""
import json

from django.utils.text import slugify
from wagtail.models import Page, Site

from . import models


def _publier(page):
    page.save_revision().publish()
    return page


def _enfant(parent, modele, slug, **champs):
    """Retrouve l'enfant `slug` de `parent` (type `modele`) ou le cree publie."""
    existant = modele.objects.child_of(parent).filter(slug=slug).first()
    if existant:
        return existant
    page = modele(slug=slug, **champs)
    parent.add_child(instance=page)
    return _publier(page)


def paragraphes(*textes):
    """Construit un StreamField « corps » a partir de paragraphes HTML."""
    return json.dumps([{"type": "paragraphe", "value": texte} for texte in textes])


def assurer_site(nom_site="Portail DPFC", hote="localhost", port=80):
    """
    Cree la page d'accueil, la rattache au site Wagtail par defaut et retourne
    toutes les pages de premier niveau, indexees par cle.
    """
    racine = Page.get_first_root_node()
    accueil = models.PageAccueil.objects.first()
    if accueil is None:
        accueil = models.PageAccueil(title="Accueil", slug="accueil", show_in_menus=True)
        racine.add_child(instance=accueil)
        _publier(accueil)

    # Page « Welcome » installee par Wagtail : inutile ici.
    Page.objects.filter(depth=2, slug="home").exclude(pk=accueil.pk).delete()

    site = Site.objects.filter(is_default_site=True).first()
    if site is None:
        site = Site(is_default_site=True)
    site.hostname, site.port, site.site_name, site.root_page = hote, port, nom_site, accueil
    site.save()

    pages = {
        "accueil": accueil,
        "presentation": _enfant(
            accueil,
            models.PageEditoriale,
            "presentation",
            title="Presentation",
            show_in_menus=True,
            chapeau="Missions, organisation et implantation territoriale.",
            afficher_organisation=True,
            corps=paragraphes(
                "<h3>Missions</h3><p>La direction elabore les programmes educatifs et les guides "
                "d'execution, encadre les pratiques de classe, organise la formation continue des "
                "enseignants et pilote le numerique educatif.</p>",
                "<h3>Organisation</h3><p>Elle comprend des sous-directions et services au niveau "
                "central, et des antennes de la pedagogie et de la formation continue en region.</p>",
            ),
        ),
        "actualites": _enfant(
            accueil, models.IndexActualites, "actualites", title="Actualites", show_in_menus=False
        ),
        "ressources": _enfant(
            accueil, models.IndexRessources, "ressources", title="Ressources", show_in_menus=True
        ),
        "foad": _enfant(
            accueil,
            models.PageFOAD,
            "foad",
            title="FOAD",
            show_in_menus=True,
            seo_title="Formation ouverte et a distance",
            corps=paragraphes(
                "<p><b>La formation continue des enseignants se poursuit en ligne, entre deux "
                "regroupements presentiels.</b></p>",
                "<p>Les modules sont accessibles depuis la plateforme nationale et utilisables sur "
                "ordinateur comme sur telephone, y compris dans les antennes regionales disposant "
                "d'une connexion limitee.</p>",
            ),
        ),
        "projets": _enfant(accueil, models.IndexProjets, "projets", title="Projets", show_in_menus=True),
        "evenements": _enfant(
            accueil, models.IndexEvenements, "evenements", title="Agenda", show_in_menus=False
        ),
        "antennes": _enfant(accueil, models.IndexAntennes, "antennes", title="Antennes", show_in_menus=True),
        "contact": _enfant(accueil, models.PageContact, "contact", title="Contact", show_in_menus=True),
    }
    return pages


def ajouter_actualite(index, titre, chapeau, texte, **champs):
    slug = slugify(titre)[:200]
    if models.PageActualite.objects.child_of(index).filter(slug=slug).exists():
        return None
    page = models.PageActualite(title=titre, slug=slug, chapeau=chapeau, corps=paragraphes(texte), **champs)
    index.add_child(instance=page)
    return _publier(page)


def ajouter_projet(index, sigle, nom, accroche, description, **champs):
    slug = slugify(sigle)
    if models.PageProjet.objects.child_of(index).filter(slug=slug).exists():
        return None
    page = models.PageProjet(
        title=nom, slug=slug, sigle=sigle, accroche=accroche, corps=paragraphes(description), **champs
    )
    index.add_child(instance=page)
    return _publier(page)


def ajouter_evenement(index, titre, date_debut, description="", **champs):
    slug = slugify(f"{titre}-{date_debut}")[:200]
    if models.PageEvenement.objects.child_of(index).filter(slug=slug).exists():
        return None
    page = models.PageEvenement(
        title=titre,
        slug=slug,
        date_debut=date_debut,
        corps=paragraphes(f"<p>{description}</p>") if description else "[]",
        **champs,
    )
    index.add_child(instance=page)
    return _publier(page)


def ajouter_ressource(titre, **champs):
    ressource, _ = models.Ressource.objects.get_or_create(titre=titre, defaults=champs)
    return ressource


def ajouter_categorie(nom, couleur="#1a9e8f"):
    categorie, _ = models.Categorie.objects.get_or_create(nom=nom, defaults={"couleur": couleur})
    return categorie

"""Navigation du site public deduite de l'arborescence Wagtail."""
from django.contrib.contenttypes.models import ContentType
from wagtail.models import Page

from . import models

# Cle de contexte -> type de page (une seule instance publiee de chaque)
PAGES_CLES = {
    "actualites": models.IndexActualites,
    "ressources": models.IndexRessources,
    "foad": models.PageFOAD,
    "projets": models.IndexProjets,
    "evenements": models.IndexEvenements,
    "antennes": models.IndexAntennes,
    "contact": models.PageContact,
}


def navigation_publique(request):
    accueil = models.PageAccueil.objects.live().first()
    if accueil is None:
        return {"accueil": None, "menu": [], "pages_cles": {}}

    enfants = list(Page.objects.child_of(accueil).live().order_by("path"))
    types = ContentType.objects.get_for_models(*PAGES_CLES.values())
    ct_vers_cle = {ct.pk: cle for cle, modele in PAGES_CLES.items() for m, ct in types.items() if m is modele}

    pages_cles, menu = {}, []
    chemin = request.path
    for page in enfants:
        cle = ct_vers_cle.get(page.content_type_id)
        if cle and cle not in pages_cles:
            pages_cles[cle] = page
        if page.show_in_menus:
            menu.append({"page": page, "actif": page.url and chemin.startswith(page.url)})

    return {
        "accueil": accueil,
        "menu": menu,
        "pages_cles": pages_cles,
        "rubrique_accueil": chemin == (accueil.url or "/"),
    }

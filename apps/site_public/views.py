"""Vues Django du site public qui ne sont pas des pages Wagtail : recherche, erreurs."""
from django.shortcuts import render
from wagtail.models import Page
from wagtail.search.backends import get_search_backend

from .models import PageActualite, PageEvenement, PageProjet, Ressource


def recherche(request):
    q = request.GET.get("q", "").strip()
    resultats = {"actualites": [], "ressources": [], "projets": [], "evenements": [], "pages": []}
    if q:
        for page in Page.objects.live().search(q)[:40]:
            specifique = page.specific
            if isinstance(specifique, PageActualite):
                resultats["actualites"].append(specifique)
            elif isinstance(specifique, PageProjet):
                resultats["projets"].append(specifique)
            elif isinstance(specifique, PageEvenement):
                resultats["evenements"].append(specifique)
            elif page.depth > 1:
                resultats["pages"].append(specifique)
        moteur = get_search_backend()
        resultats["ressources"] = list(moteur.search(q, Ressource.objects.filter(publiee=True))[:10])
    total = sum(len(v) for v in resultats.values())
    return render(request, "public/recherche.html", {"q": q, "resultats": resultats, "total": total})


def page_404(request, exception=None):
    return render(request, "public/404.html", status=404)


def page_500(request):
    return render(request, "public/500.html", status=500)

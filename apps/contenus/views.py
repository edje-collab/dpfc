from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, F, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.core.models import Region, Structure

from .forms import ContactForm
from .models import Actualite, Categorie, Evenement, PageStatique, Projet, Ressource


def accueil(request):
    aujourdhui = timezone.localdate()
    contexte = {
        "actualites": Actualite.objects.publiees().select_related("categorie")[:3],
        "une": Actualite.objects.publiees().filter(a_la_une=True).first(),
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
        "projets": Projet.objects.filter(publie=True)[:4],
        "evenements": Evenement.objects.filter(publie=True, date_debut__gte=aujourdhui)[:4],
        "nb_ressources": Ressource.objects.filter(publiee=True).count(),
        "nb_antennes": Structure.objects.filter(type=Structure.Type.ANTENNE, active=True).count(),
        "nb_formations": Evenement.objects.filter(
            publie=True, type=Evenement.Type.FORMATION, date_debut__year=aujourdhui.year
        ).count(),
    }
    return render(request, "public/accueil.html", contexte)


def actualites(request):
    liste = Actualite.objects.publiees().select_related("categorie", "structure")
    categorie = request.GET.get("categorie", "")
    q = request.GET.get("q", "").strip()
    if categorie:
        liste = liste.filter(categorie__slug=categorie)
    if q:
        liste = liste.filter(Q(titre__icontains=q) | Q(chapeau__icontains=q) | Q(contenu__icontains=q))
    pages = Paginator(liste, 9).get_page(request.GET.get("page"))
    return render(
        request,
        "public/actualites.html",
        {
            "page_obj": pages,
            "categories": Categorie.objects.annotate(n=Count("actualites")).filter(n__gt=0),
            "categorie_active": categorie,
            "q": q,
        },
    )


def actualite_detail(request, slug):
    article = get_object_or_404(
        Actualite.objects.publiees().select_related("categorie", "structure", "auteur"), slug=slug
    )
    Actualite.objects.filter(pk=article.pk).update(vues=F("vues") + 1)
    similaires = (
        Actualite.objects.publiees().filter(categorie=article.categorie).exclude(pk=article.pk)[:3]
    )
    return render(request, "public/actualite_detail.html", {"article": article, "similaires": similaires})


def ressources(request):
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
    pages = Paginator(liste, 12).get_page(request.GET.get("page"))
    return render(
        request,
        "public/ressources.html",
        {
            "page_obj": pages,
            "types": Ressource.Type.choices,
            "niveaux": Ressource.Niveau.choices,
            "type_actif": type_r,
            "niveau_actif": niveau,
            "q": q,
            "total": liste.count(),
        },
    )


def ressource_detail(request, slug):
    ressource = get_object_or_404(Ressource, slug=slug, publiee=True)
    return render(request, "public/ressource_detail.html", {"ressource": ressource})


def ressource_telecharger(request, slug):
    ressource = get_object_or_404(Ressource, slug=slug, publiee=True)
    Ressource.objects.filter(pk=ressource.pk).update(telechargements=F("telechargements") + 1)
    cible = ressource.url_fichier
    if not cible:
        messages.error(request, "Le fichier de cette ressource n'est pas encore disponible.")
        return redirect(ressource.get_absolute_url())
    return redirect(cible)


def projets(request):
    return render(
        request, "public/projets.html", {"projets": Projet.objects.filter(publie=True)}
    )


def projet_detail(request, slug):
    projet = get_object_or_404(Projet, slug=slug, publie=True)
    return render(
        request,
        "public/projet_detail.html",
        {"projet": projet, "autres": Projet.objects.filter(publie=True).exclude(pk=projet.pk)[:3]},
    )


def evenements(request):
    aujourdhui = timezone.localdate()
    a_venir = Evenement.objects.filter(publie=True, date_debut__gte=aujourdhui)
    passes = Evenement.objects.filter(publie=True, date_debut__lt=aujourdhui).order_by("-date_debut")[:10]
    return render(
        request, "public/evenements.html", {"a_venir": a_venir, "passes": passes}
    )


def evenement_detail(request, slug):
    evenement = get_object_or_404(Evenement, slug=slug, publie=True)
    return render(request, "public/evenement_detail.html", {"evenement": evenement})


def foad(request):
    """Page dediee a la formation ouverte et a distance."""
    page = PageStatique.objects.filter(slug="foad", publiee=True).first()
    modules = Ressource.objects.filter(publiee=True, type=Ressource.Type.MODULE)[:12]
    formations = Evenement.objects.filter(
        publie=True, type=Evenement.Type.FORMATION, date_debut__gte=timezone.localdate()
    )[:6]
    return render(
        request, "public/foad.html", {"page": page, "modules": modules, "formations": formations}
    )


def antennes(request):
    liste = (
        Structure.objects.filter(type=Structure.Type.ANTENNE, active=True)
        .select_related("region", "responsable")
        .annotate(nb_agents=Count("agents"))
    )
    region = request.GET.get("region", "")
    if region:
        liste = liste.filter(region__code=region)
    return render(
        request,
        "public/antennes.html",
        {"antennes": liste, "regions": Region.objects.all(), "region_active": region},
    )


def antenne_detail(request, slug):
    antenne = get_object_or_404(
        Structure.objects.select_related("region", "responsable"), slug=slug, active=True
    )
    return render(
        request,
        "public/antenne_detail.html",
        {
            "antenne": antenne,
            "actualites": Actualite.objects.publiees().filter(structure=antenne)[:4],
            "evenements": Evenement.objects.filter(
                publie=True, structure=antenne, date_debut__gte=timezone.localdate()
            )[:4],
        },
    )


def page(request, slug):
    page_ = get_object_or_404(PageStatique, slug=slug, publiee=True)
    return render(request, "public/page.html", {"page": page_})


def presentation(request):
    page_ = PageStatique.objects.filter(slug="presentation", publiee=True).first()
    return render(
        request,
        "public/presentation.html",
        {
            "page": page_,
            "structures": Structure.objects.filter(
                rattachement=Structure.Rattachement.CENTRALE, active=True
            ).select_related("responsable"),
            "nb_antennes": Structure.objects.filter(type=Structure.Type.ANTENNE, active=True).count(),
        },
    )


def contact(request):
    form = ContactForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(
            request, "Message envoye. La DPFC vous repondra a l'adresse indiquee."
        )
        return redirect("contenus:contact")
    return render(request, "public/contact.html", {"form": form})


def recherche(request):
    q = request.GET.get("q", "").strip()
    resultats = {"actualites": [], "ressources": [], "projets": [], "evenements": []}
    if q:
        resultats["actualites"] = Actualite.objects.publiees().filter(
            Q(titre__icontains=q) | Q(contenu__icontains=q)
        )[:10]
        resultats["ressources"] = Ressource.objects.filter(publiee=True).filter(
            Q(titre__icontains=q) | Q(description__icontains=q)
        )[:10]
        resultats["projets"] = Projet.objects.filter(publie=True).filter(
            Q(nom__icontains=q) | Q(sigle__icontains=q) | Q(description__icontains=q)
        )[:10]
        resultats["evenements"] = Evenement.objects.filter(publie=True).filter(
            Q(titre__icontains=q) | Q(description__icontains=q)
        )[:10]
    total = sum(len(v) for v in resultats.values())
    return render(request, "public/recherche.html", {"q": q, "resultats": resultats, "total": total})


def page_404(request, exception=None):
    return render(request, "public/404.html", status=404)


def page_500(request):
    return render(request, "public/500.html", status=500)

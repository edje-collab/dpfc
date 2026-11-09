"""Ecrans des achats : besoins, consultation, commandes, magasin, equipements."""
import csv

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from apps.core.models import JournalAction

from .forms import (
    ArticleForm,
    BesoinForm,
    DecisionBesoinForm,
    EquipementForm,
    FactureForm,
    FiltreBesoinsForm,
    LigneBesoinForm,
    MotifForm,
    MouvementForm,
    OffreForm,
    ReceptionForm,
)
from .models import (
    Article,
    BonCommande,
    Equipement,
    ExpressionBesoin,
    LigneBesoin,
    Offre,
    ValidationBesoin,
)
from .services import (
    ErreurAchat,
    annuler_commande,
    decider_besoin,
    emettre_commande,
    enregistrer_mouvement,
    receptionner,
    retenir_offre,
    solder,
    soumettre_besoin,
    tableau_achats,
)


# --- Droits ------------------------------------------------------------------
def _peut_gerer_le_magasin(agent):
    """Le secretariat, le responsable du perimetre et la direction tiennent le magasin."""
    return (
        agent.est_secretariat
        or agent.dirige_son_perimetre
        or agent.est_direction
        or agent.peut_administrer
    )


def _besoin_visible(agent, pk):
    besoin = get_object_or_404(
        ExpressionBesoin.objects.select_related("perimetre", "demandeur", "activite"), pk=pk
    )
    if not ExpressionBesoin.objects.visibles_par(agent).filter(pk=pk).exists():
        raise Http404("Besoin introuvable dans votre perimetre.")
    return besoin


def _article_visible(agent, pk):
    article = get_object_or_404(Article.objects.select_related("perimetre"), pk=pk)
    if not (agent.est_rh or agent.est_direction or agent.peut_administrer):
        if article.perimetre_id != getattr(agent.perimetre, "pk", None):
            raise Http404("Article introuvable dans votre magasin.")
    return article


# --- Tableau de bord ---------------------------------------------------------
@login_required
def tableau(request):
    contexte = tableau_achats(request.user)
    contexte["peut_gerer"] = _peut_gerer_le_magasin(request.user)
    return render(request, "intranet/achats_tableau.html", contexte)


# --- Expressions de besoin ---------------------------------------------------
@login_required
def besoins(request):
    form = FiltreBesoinsForm(request.GET or None, agent=request.user)
    liste = ExpressionBesoin.objects.visibles_par(request.user).select_related(
        "perimetre", "demandeur"
    )
    if form.is_valid():
        if q := form.cleaned_data.get("q"):
            liste = liste.filter(Q(numero__icontains=q) | Q(objet__icontains=q))
        if statut := form.cleaned_data.get("statut"):
            liste = liste.filter(statut=statut)
        if perimetre := form.cleaned_data.get("perimetre"):
            liste = liste.filter(perimetre__code=perimetre)

    return render(
        request,
        "intranet/achats_besoins.html",
        {
            "form": form,
            "page_obj": Paginator(liste, 25).get_page(request.GET.get("page")),
            "total": liste.count(),
        },
    )


@login_required
def besoin_creer(request):
    perimetre = request.user.perimetre
    if perimetre is None:
        messages.error(request, "Votre compte n'est rattache a aucun perimetre.")
        return redirect("achats:besoins")

    form = BesoinForm(request.POST or None, perimetre=perimetre)
    if request.method == "POST" and form.is_valid():
        besoin = form.save(commit=False)
        besoin.perimetre = perimetre
        besoin.demandeur = request.user
        besoin.save()
        messages.success(request, f"Besoin {besoin.numero} cree. Ajoutez-y les articles.")
        return redirect(besoin.get_absolute_url())
    return render(request, "intranet/achats_besoin_form.html", {"form": form, "perimetre": perimetre})


@login_required
def besoin_detail(request, pk):
    besoin = _besoin_visible(request.user, pk)
    etape = besoin.etape_courante()
    commande = getattr(besoin, "bon_commande", None)
    return render(
        request,
        "intranet/achats_besoin_detail.html",
        {
            "besoin": besoin,
            "lignes": besoin.lignes.select_related("article"),
            "offres": besoin.offres.select_related("fournisseur"),
            "validations": besoin.validations.select_related("valideur"),
            "commande": commande,
            "mon_etape": etape if etape is not None and etape.valideur_id == request.user.pk else None,
            "form_ligne": LigneBesoinForm(besoin=besoin),
            "form_offre": OffreForm(besoin=besoin),
            "form_decision": DecisionBesoinForm(),
            "form_reception": ReceptionForm(),
            "form_facture": FactureForm(),
            "est_demandeur": besoin.demandeur_id == request.user.pk,
            "peut_gerer": _peut_gerer_le_magasin(request.user),
        },
    )


@login_required
def ligne_ajouter(request, pk):
    besoin = _besoin_visible(request.user, pk)
    if request.method != "POST":
        return redirect(besoin.get_absolute_url())
    if not besoin.est_modifiable or besoin.demandeur_id != request.user.pk:
        messages.error(request, "Ce besoin n'est plus modifiable.")
        return redirect(besoin.get_absolute_url())

    form = LigneBesoinForm(request.POST, besoin=besoin)
    if form.is_valid():
        form.save()
        messages.success(request, "Article ajoute au besoin.")
    else:
        messages.error(request, "Completez la designation et la quantite.")
    return redirect(besoin.get_absolute_url())


@login_required
def ligne_supprimer(request, pk):
    ligne = get_object_or_404(LigneBesoin.objects.select_related("besoin"), pk=pk)
    besoin = _besoin_visible(request.user, ligne.besoin_id)
    if request.method == "POST" and besoin.est_modifiable and besoin.demandeur_id == request.user.pk:
        ligne.delete()
        messages.success(request, "Article retire du besoin.")
    return redirect(besoin.get_absolute_url())


@login_required
def besoin_soumettre(request, pk):
    besoin = _besoin_visible(request.user, pk)
    if request.method != "POST":
        return redirect(besoin.get_absolute_url())
    if besoin.demandeur_id != request.user.pk:
        messages.error(request, "Seul le demandeur transmet son besoin.")
        return redirect(besoin.get_absolute_url())
    try:
        soumettre_besoin(besoin, requete=request)
        messages.success(request, "Besoin transmis pour validation.")
    except ErreurAchat as erreur:
        messages.error(request, str(erreur))
    return redirect(besoin.get_absolute_url())


@login_required
def besoin_decider(request, pk, decision):
    validation = get_object_or_404(
        ValidationBesoin.objects.select_related("besoin"), pk=pk, valideur=request.user,
        decision=ValidationBesoin.Decision.ATTENTE,
    )
    if request.method != "POST":
        return redirect(validation.besoin.get_absolute_url())

    form = DecisionBesoinForm(request.POST)
    form.is_valid()
    commentaire = form.cleaned_data.get("commentaire", "")
    favorable = decision == "valider"
    if not favorable and not commentaire.strip():
        messages.error(request, "Indiquez le motif de l'avis defavorable.")
        return redirect(validation.besoin.get_absolute_url())
    try:
        decider_besoin(validation, favorable, commentaire, requete=request)
        messages.success(request, "Avis enregistre." if favorable else "Besoin rejete.")
    except ErreurAchat as erreur:
        messages.error(request, str(erreur))
    return redirect(validation.besoin.get_absolute_url())


@login_required
def offre_ajouter(request, pk):
    besoin = _besoin_visible(request.user, pk)
    if request.method != "POST":
        return redirect(besoin.get_absolute_url())
    if not _peut_gerer_le_magasin(request.user):
        messages.error(request, "La consultation des fournisseurs releve du secretariat.")
        return redirect(besoin.get_absolute_url())

    form = OffreForm(request.POST, request.FILES, besoin=besoin)
    if form.is_valid():
        form.save()
        messages.success(request, "Offre enregistree.")
    else:
        messages.error(request, "Choisissez un fournisseur et indiquez le montant.")
    return redirect(besoin.get_absolute_url())


@login_required
def offre_retenir(request, pk):
    offre = get_object_or_404(Offre.objects.select_related("besoin"), pk=pk)
    besoin = _besoin_visible(request.user, offre.besoin_id)
    if request.method != "POST":
        return redirect(besoin.get_absolute_url())
    if not _peut_gerer_le_magasin(request.user):
        messages.error(request, "Le choix de l'offre releve du secretariat ou de la direction.")
        return redirect(besoin.get_absolute_url())
    try:
        retenir_offre(offre, request.user, requete=request)
        messages.success(request, f"Offre de {offre.fournisseur} retenue.")
    except ErreurAchat as erreur:
        messages.error(request, str(erreur))
    return redirect(besoin.get_absolute_url())


@login_required
def besoin_commander(request, pk):
    besoin = _besoin_visible(request.user, pk)
    if request.method != "POST":
        return redirect(besoin.get_absolute_url())
    if not _peut_gerer_le_magasin(request.user):
        messages.error(request, "L'emission du bon de commande releve du secretariat.")
        return redirect(besoin.get_absolute_url())
    try:
        commande = emettre_commande(besoin, request.user, requete=request)
        messages.success(request, f"Bon de commande {commande.numero} emis.")
    except ErreurAchat as erreur:
        messages.error(request, str(erreur))
    return redirect(besoin.get_absolute_url())


# --- Commandes ---------------------------------------------------------------
@login_required
def commandes(request):
    liste = BonCommande.objects.filter(
        besoin__in=ExpressionBesoin.objects.visibles_par(request.user)
    ).select_related("besoin__perimetre", "fournisseur")
    if statut := request.GET.get("statut"):
        liste = liste.filter(statut=statut)
    return render(
        request,
        "intranet/achats_commandes.html",
        {
            "page_obj": Paginator(liste, 25).get_page(request.GET.get("page")),
            "total": liste.count(),
            "statuts": BonCommande.Statut.choices,
            "statut_actif": statut or "",
        },
    )


@login_required
def commande_receptionner(request, pk):
    commande = get_object_or_404(BonCommande.objects.select_related("besoin"), pk=pk)
    besoin = _besoin_visible(request.user, commande.besoin_id)
    if request.method != "POST":
        return redirect(besoin.get_absolute_url())
    if not _peut_gerer_le_magasin(request.user):
        messages.error(request, "La reception releve du secretariat ou du magasin.")
        return redirect(besoin.get_absolute_url())

    form = ReceptionForm(request.POST)
    form.is_valid()
    # Quantites effectivement livrees, ligne par ligne.
    lignes = {}
    for ligne in besoin.lignes.filter(article__isnull=False):
        valeur = request.POST.get(f"ligne-{ligne.pk}")
        if valeur not in (None, ""):
            try:
                lignes[ligne.pk] = max(0, int(valeur))
            except ValueError:
                lignes[ligne.pk] = ligne.quantite
    try:
        _, entrees = receptionner(
            commande, request.user, lignes=lignes or None,
            observations=form.cleaned_data.get("observations", ""), requete=request,
        )
        messages.success(
            request,
            f"Reception enregistree. {len(entrees)} article(s) entre(s) au magasin."
            if entrees else "Reception enregistree.",
        )
    except ErreurAchat as erreur:
        messages.error(request, str(erreur))
    return redirect(besoin.get_absolute_url())


@login_required
def commande_facture(request, pk):
    commande = get_object_or_404(BonCommande.objects.select_related("besoin"), pk=pk)
    besoin = _besoin_visible(request.user, commande.besoin_id)
    if request.method != "POST":
        return redirect(besoin.get_absolute_url())
    if not _peut_gerer_le_magasin(request.user):
        messages.error(request, "L'enregistrement de la facture releve du secretariat.")
        return redirect(besoin.get_absolute_url())

    form = FactureForm(request.POST, request.FILES)
    if not form.is_valid():
        messages.error(request, "Indiquez le numero et le montant de la facture.")
        return redirect(besoin.get_absolute_url())
    try:
        _, rapporte = solder(
            commande, request.user, form.cleaned_data["numero"],
            form.cleaned_data["montant"], fichier=form.cleaned_data.get("fichier"),
            requete=request,
        )
        messages.success(
            request,
            "Facture enregistree, besoin solde."
            + (" La depense a ete reportee sur le plan d'action." if rapporte else ""),
        )
    except ErreurAchat as erreur:
        messages.error(request, str(erreur))
    return redirect(besoin.get_absolute_url())


@login_required
def commande_annuler(request, pk):
    commande = get_object_or_404(BonCommande.objects.select_related("besoin"), pk=pk)
    besoin = _besoin_visible(request.user, commande.besoin_id)
    if request.method != "POST":
        return redirect(besoin.get_absolute_url())
    if not _peut_gerer_le_magasin(request.user):
        messages.error(request, "L'annulation releve du secretariat ou de la direction.")
        return redirect(besoin.get_absolute_url())

    form = MotifForm(request.POST)
    form.is_valid()
    try:
        annuler_commande(commande, request.user, form.cleaned_data.get("motif", ""), requete=request)
        messages.warning(request, "Bon de commande annule.")
    except ErreurAchat as erreur:
        messages.error(request, str(erreur))
    return redirect(besoin.get_absolute_url())


# --- Magasin -----------------------------------------------------------------
@login_required
def magasin(request):
    liste = Article.objects.filter(actif=True).select_related("perimetre")
    if not (request.user.est_rh or request.user.est_direction or request.user.peut_administrer):
        perimetre = request.user.perimetre
        liste = liste.filter(perimetre=perimetre) if perimetre else liste.none()
    if q := request.GET.get("q"):
        liste = liste.filter(Q(code__icontains=q) | Q(designation__icontains=q))
    if request.GET.get("alerte"):
        liste = [a for a in liste if a.sous_seuil]

    return render(
        request,
        "intranet/achats_magasin.html",
        {
            "articles": liste,
            "q": q or "",
            "alerte": bool(request.GET.get("alerte")),
            "peut_gerer": _peut_gerer_le_magasin(request.user),
        },
    )


@login_required
def article_creer(request):
    perimetre = request.user.perimetre
    if perimetre is None or not _peut_gerer_le_magasin(request.user):
        messages.error(request, "La tenue du magasin releve du secretariat.")
        return redirect("achats:magasin")

    form = ArticleForm(request.POST or None, perimetre=perimetre)
    if request.method == "POST" and form.is_valid():
        article = form.save(commit=False)
        article.perimetre = perimetre
        article.save()
        messages.success(request, "Article inscrit au magasin.")
        return redirect(article.get_absolute_url())
    return render(request, "intranet/achats_article_form.html", {"form": form, "perimetre": perimetre})


@login_required
def article_detail(request, pk):
    article = _article_visible(request.user, pk)
    return render(
        request,
        "intranet/achats_article_detail.html",
        {
            "article": article,
            "mouvements": article.mouvements.select_related("saisi_par", "bon_commande")[:50],
            "form": MouvementForm(),
            "peut_gerer": _peut_gerer_le_magasin(request.user),
            "ecart": article.stock_reel - article.stock,
        },
    )


@login_required
def mouvement_creer(request, pk):
    article = _article_visible(request.user, pk)
    if request.method != "POST":
        return redirect(article.get_absolute_url())
    if not _peut_gerer_le_magasin(request.user):
        messages.error(request, "La tenue du magasin releve du secretariat.")
        return redirect(article.get_absolute_url())

    form = MouvementForm(request.POST)
    if not form.is_valid():
        for erreurs in form.errors.values():
            messages.error(request, erreurs[0])
        return redirect(article.get_absolute_url())
    try:
        mouvement = enregistrer_mouvement(
            article, form.cleaned_data["type"], form.cleaned_data["quantite"], request.user,
            motif=form.cleaned_data.get("motif", ""),
            beneficiaire=form.cleaned_data.get("beneficiaire", ""),
            date=form.cleaned_data.get("date"),
        )
        messages.success(
            request, f"Mouvement enregistre. Stock : {mouvement.stock_apres} {article.unite}(s)."
        )
    except ErreurAchat as erreur:
        messages.error(request, str(erreur))
    return redirect(article.get_absolute_url())


@login_required
def magasin_csv(request):
    """Etat du magasin au format CSV."""
    liste = Article.objects.filter(actif=True).select_related("perimetre")
    if not (request.user.est_rh or request.user.est_direction or request.user.peut_administrer):
        perimetre = request.user.perimetre
        liste = liste.filter(perimetre=perimetre) if perimetre else liste.none()

    reponse = HttpResponse(content_type="text/csv; charset=utf-8")
    reponse["Content-Disposition"] = 'attachment; filename="etat-magasin.csv"'
    reponse.write("﻿")
    ecrivain = csv.writer(reponse, delimiter=";")
    ecrivain.writerow(["Perimetre", "Code", "Designation", "Unite", "Stock",
                       "Seuil d'alerte", "A reapprovisionner"])
    for article in liste.order_by("perimetre__code", "designation"):
        ecrivain.writerow([
            article.perimetre.code, article.code, article.designation, article.unite,
            article.stock, article.seuil_alerte, "oui" if article.sous_seuil else "",
        ])
    JournalAction.tracer(request.user, "Export de l'etat du magasin", requete=request)
    return reponse


# --- Equipements -------------------------------------------------------------
@login_required
def equipements(request):
    liste = Equipement.objects.select_related("perimetre", "affecte_a", "structure")
    if not (request.user.est_rh or request.user.est_direction or request.user.peut_administrer):
        perimetre = request.user.perimetre
        liste = liste.filter(perimetre=perimetre) if perimetre else liste.none()
    if q := request.GET.get("q"):
        liste = liste.filter(
            Q(code_inventaire__icontains=q) | Q(designation__icontains=q) | Q(marque__icontains=q)
        )
    if etat := request.GET.get("etat"):
        liste = liste.filter(etat=etat)

    return render(
        request,
        "intranet/achats_equipements.html",
        {
            "page_obj": Paginator(liste, 30).get_page(request.GET.get("page")),
            "total": liste.count(),
            "q": q or "",
            "etats": Equipement.Etat.choices,
            "etat_actif": etat or "",
            "peut_gerer": _peut_gerer_le_magasin(request.user),
        },
    )


@login_required
def equipement_creer(request):
    perimetre = request.user.perimetre
    if perimetre is None or not _peut_gerer_le_magasin(request.user):
        messages.error(request, "L'inventaire releve du secretariat.")
        return redirect("achats:equipements")

    form = EquipementForm(request.POST or None, perimetre=perimetre)
    if request.method == "POST" and form.is_valid():
        equipement = form.save(commit=False)
        equipement.perimetre = perimetre
        equipement.save()
        messages.success(request, "Equipement inscrit a l'inventaire.")
        return redirect("achats:equipements")
    return render(
        request, "intranet/achats_equipement_form.html", {"form": form, "perimetre": perimetre}
    )

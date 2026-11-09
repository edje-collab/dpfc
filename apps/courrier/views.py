"""Ecrans du courrier, de la bibliotheque documentaire et du parapheur."""
import csv

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.core.models import JournalAction

from .forms import (
    ClassementForm,
    CompteRenduForm,
    CourrierForm,
    DocumentForm,
    FiltreCourrierForm,
    FiltreDocumentForm,
    ImputationForm,
    PieceParapheurForm,
    VersionForm,
    VisaForm,
)
from .models import Courrier, Document, Imputation, ModeleDocument, PieceParapheur, Visa
from .services import (
    ErreurCourrier,
    classer,
    deposer_version,
    imputer,
    pieces_a_viser,
    rechercher_documents,
    soumettre_au_parapheur,
    tableau_courrier,
    traiter_imputation,
    viser,
)


# --- Droits ------------------------------------------------------------------
def _peut_enregistrer(agent):
    """Le secretariat, le responsable du perimetre et la direction enregistrent."""
    return (
        agent.est_secretariat
        or agent.dirige_son_perimetre
        or agent.est_direction
        or agent.peut_administrer
    )


def _peut_imputer(agent, courrier):
    """
    L'imputation releve du responsable du perimetre ou de la direction.

    On verifie la designation effective (`dirige_son_perimetre`) et non le seul
    role porte : un agent portant le role de chef sans diriger l'antenne
    n'impute pas le courrier de celle-ci.
    """
    if agent.est_direction or agent.peut_administrer:
        return True
    return agent.dirige_son_perimetre and agent.perimetre == courrier.perimetre


def _courrier_visible(agent, pk):
    courrier = get_object_or_404(
        Courrier.objects.select_related("perimetre", "enregistre_par", "courrier_lie"), pk=pk
    )
    if not courrier.peut_etre_vu_par(agent):
        raise Http404("Courrier introuvable dans votre perimetre.")
    return courrier


def _document_visible(agent, pk):
    document = get_object_or_404(
        Document.objects.select_related("perimetre", "deposant", "courrier"), pk=pk
    )
    if not document.peut_etre_vu_par(agent):
        raise Http404("Document introuvable dans votre perimetre.")
    return document


# --- Tableau de bord ---------------------------------------------------------
@login_required
def tableau(request):
    contexte = tableau_courrier(request.user)
    contexte.update(
        {
            "a_viser": pieces_a_viser(request.user),
            "peut_enregistrer": _peut_enregistrer(request.user),
        }
    )
    return render(request, "intranet/courrier_tableau.html", contexte)


# --- Registre du courrier ----------------------------------------------------
@login_required
def registre(request):
    form = FiltreCourrierForm(request.GET or None, agent=request.user)
    liste = Courrier.objects.visibles_par(request.user).select_related(
        "perimetre", "enregistre_par"
    )
    if form.is_valid():
        if q := form.cleaned_data.get("q"):
            liste = liste.filter(
                Q(numero__icontains=q) | Q(objet__icontains=q)
                | Q(correspondant__icontains=q) | Q(reference_expediteur__icontains=q)
            )
        if sens := form.cleaned_data.get("sens"):
            liste = liste.filter(sens=sens)
        if statut := form.cleaned_data.get("statut"):
            liste = liste.filter(statut=statut)
        if annee := form.cleaned_data.get("annee"):
            liste = liste.filter(date_enregistrement__year=annee)
        if perimetre := form.cleaned_data.get("perimetre"):
            liste = liste.filter(perimetre__code=perimetre)
        if form.cleaned_data.get("retard"):
            liste = liste.en_retard()

    return render(
        request,
        "intranet/courrier_registre.html",
        {
            "form": form,
            "page_obj": Paginator(liste, 25).get_page(request.GET.get("page")),
            "total": liste.count(),
            "peut_enregistrer": _peut_enregistrer(request.user),
        },
    )


@login_required
def courrier_creer(request):
    agent = request.user
    perimetre = agent.perimetre
    if perimetre is None or not _peut_enregistrer(agent):
        messages.error(request, "Vous n'etes pas habilite a enregistrer du courrier.")
        return redirect("courrier:registre")

    form = CourrierForm(request.POST or None, perimetre=perimetre)
    if request.method == "POST" and form.is_valid():
        courrier = form.save(commit=False)
        courrier.perimetre = perimetre
        courrier.enregistre_par = agent
        courrier.save()
        JournalAction.tracer(agent, "Enregistrement d'un courrier", courrier.numero, requete=request)
        messages.success(request, f"Courrier enregistre sous le numero {courrier.numero}.")
        return redirect(courrier.get_absolute_url())
    return render(request, "intranet/courrier_form.html", {"form": form, "perimetre": perimetre})


@login_required
def courrier_detail(request, pk):
    courrier = _courrier_visible(request.user, pk)
    mon_imputation = courrier.imputations.filter(
        destinataire=request.user, traite_le__isnull=True
    ).first()
    return render(
        request,
        "intranet/courrier_detail.html",
        {
            "courrier": courrier,
            "imputations": courrier.imputations.select_related("destinataire", "impute_par"),
            "documents": courrier.documents.all(),
            "reponses": courrier.reponses.all(),
            "mon_imputation": mon_imputation,
            "form_compte_rendu": CompteRenduForm(instance=mon_imputation) if mon_imputation else None,
            "form_classement": ClassementForm(),
            "peut_imputer": _peut_imputer(request.user, courrier) and courrier.est_arrive
            and not courrier.est_clos,
        },
    )


@login_required
def courrier_imputer(request, pk):
    courrier = _courrier_visible(request.user, pk)
    if not _peut_imputer(request.user, courrier):
        messages.error(request, "L'imputation releve du responsable du perimetre.")
        return redirect(courrier.get_absolute_url())

    form = ImputationForm(request.POST or None, courrier=courrier)
    if request.method == "POST" and form.is_valid():
        affectations = [
            {
                "destinataire": destinataire,
                "instructions": form.cleaned_data["instructions"],
                "delai": form.cleaned_data["delai"],
                "pour_information": form.cleaned_data["pour_information"],
            }
            for destinataire in form.cleaned_data["destinataires"]
        ]
        try:
            creees = imputer(courrier, request.user, affectations, requete=request)
            messages.success(request, f"Courrier impute a {len(creees)} agent(s).")
            return redirect(courrier.get_absolute_url())
        except ErreurCourrier as erreur:
            messages.error(request, str(erreur))
    return render(
        request, "intranet/courrier_imputation.html", {"form": form, "courrier": courrier}
    )


@login_required
def imputation_traiter(request, pk):
    imputation = get_object_or_404(
        Imputation.objects.select_related("courrier"), pk=pk, destinataire=request.user
    )
    if request.method != "POST":
        return redirect(imputation.courrier.get_absolute_url())

    form = CompteRenduForm(request.POST, instance=imputation)
    if form.is_valid():
        try:
            traiter_imputation(
                imputation, request.user, form.cleaned_data["compte_rendu"], requete=request
            )
            messages.success(request, "Suite donnee enregistree.")
        except ErreurCourrier as erreur:
            messages.error(request, str(erreur))
    else:
        messages.error(request, "Indiquez la suite donnee au courrier.")
    return redirect(imputation.courrier.get_absolute_url())


@login_required
def courrier_classer(request, pk):
    courrier = _courrier_visible(request.user, pk)
    if request.method != "POST":
        return redirect(courrier.get_absolute_url())
    if not _peut_imputer(request.user, courrier):
        messages.error(request, "Le classement releve du responsable du perimetre.")
        return redirect(courrier.get_absolute_url())

    form = ClassementForm(request.POST)
    form.is_valid()
    try:
        classer(courrier, request.user, form.cleaned_data.get("motif", ""), requete=request)
        messages.warning(request, "Courrier classe sans suite.")
    except ErreurCourrier as erreur:
        messages.error(request, str(erreur))
    return redirect(courrier.get_absolute_url())


@login_required
def export_registre(request):
    """Registre du courrier au format CSV, dans le perimetre visible."""
    liste = Courrier.objects.visibles_par(request.user).select_related("perimetre")
    if annee := request.GET.get("annee"):
        liste = liste.filter(date_enregistrement__year=annee)

    reponse = HttpResponse(content_type="text/csv; charset=utf-8")
    reponse["Content-Disposition"] = 'attachment; filename="registre-courrier.csv"'
    reponse.write("﻿")
    ecrivain = csv.writer(reponse, delimiter=";")
    ecrivain.writerow([
        "Numero", "Sens", "Perimetre", "Date du courrier", "Date d'enregistrement",
        "Correspondant", "Objet", "Reference expediteur", "Statut", "Imputations",
    ])
    for c in liste.order_by("date_enregistrement"):
        ecrivain.writerow([
            c.numero, c.get_sens_display(), c.perimetre.code, c.date_courrier,
            c.date_enregistrement, c.correspondant, c.objet, c.reference_expediteur,
            c.get_statut_display(), c.imputations.count(),
        ])
    JournalAction.tracer(request.user, "Export du registre du courrier", requete=request)
    return reponse


# --- Bibliotheque documentaire -----------------------------------------------
@login_required
def documents(request):
    form = FiltreDocumentForm(request.GET or None, agent=request.user)
    filtres, requete = {}, ""
    if form.is_valid():
        requete = form.cleaned_data.get("q", "")
        filtres = {
            "type_document": form.cleaned_data.get("type_document"),
            "annee": form.cleaned_data.get("annee"),
            "perimetre": form.cleaned_data.get("perimetre"),
        }
    resultats = rechercher_documents(request.user, requete, **filtres)
    return render(
        request,
        "intranet/documents.html",
        {
            "form": form,
            "page_obj": Paginator(resultats, 20).get_page(request.GET.get("page")),
            "requete": requete,
            "total": resultats.count(),
        },
    )


@login_required
def document_creer(request):
    perimetre = request.user.perimetre
    if perimetre is None:
        messages.error(request, "Votre compte n'est rattache a aucun perimetre.")
        return redirect("courrier:documents")

    form = DocumentForm(request.POST or None, request.FILES or None, perimetre=perimetre)
    if request.method == "POST" and form.is_valid():
        document = form.save(commit=False)
        document.perimetre = perimetre
        document.deposant = request.user
        document.save()
        form.save_m2m()
        deposer_version(
            document, form.cleaned_data["fichier"], request.user,
            form.cleaned_data.get("commentaire_version", "") or "Version initiale",
        )
        JournalAction.tracer(request.user, "Depot d'un document", document.titre, requete=request)
        messages.success(request, "Document verse a la bibliotheque.")
        return redirect(document.get_absolute_url())
    return render(request, "intranet/document_form.html", {"form": form, "perimetre": perimetre})


@login_required
def document_detail(request, pk):
    document = _document_visible(request.user, pk)
    return render(
        request,
        "intranet/document_detail.html",
        {
            "document": document,
            "versions": document.versions.select_related("deposee_par"),
            "form_version": VersionForm(),
            "peut_deposer": document.deposant_id == request.user.pk
            or request.user.est_direction or request.user.peut_administrer
            or (request.user.dirige_son_perimetre
                and request.user.perimetre == document.perimetre),
        },
    )


@login_required
def document_version(request, pk):
    document = _document_visible(request.user, pk)
    if request.method != "POST":
        return redirect(document.get_absolute_url())

    form = VersionForm(request.POST, request.FILES)
    if form.is_valid():
        version = deposer_version(
            document, form.cleaned_data["fichier"], request.user,
            form.cleaned_data.get("commentaire", ""),
        )
        JournalAction.tracer(
            request.user, "Nouvelle version d'un document",
            f"{document.titre} v{version.numero}", requete=request,
        )
        messages.success(request, f"Version {version.numero} deposee.")
    else:
        messages.error(request, "Choisissez un fichier.")
    return redirect(document.get_absolute_url())


# --- Parapheur ---------------------------------------------------------------
@login_required
def parapheur(request):
    mes_pieces = PieceParapheur.objects.filter(demandeur=request.user).select_related("document")
    return render(
        request,
        "intranet/parapheur.html",
        {"a_viser": pieces_a_viser(request.user), "mes_pieces": mes_pieces},
    )


@login_required
def parapheur_creer(request):
    perimetre = request.user.perimetre
    if perimetre is None:
        messages.error(request, "Votre compte n'est rattache a aucun perimetre.")
        return redirect("courrier:parapheur")

    form = PieceParapheurForm(request.POST or None, perimetre=perimetre, agent=request.user)
    if request.method == "POST" and form.is_valid():
        piece = form.save(commit=False)
        piece.perimetre = perimetre
        piece.demandeur = request.user
        piece.save()
        messages.success(request, "Piece creee. Transmettez-la lorsqu'elle est prete.")
        return redirect(piece.get_absolute_url())
    return render(request, "intranet/parapheur_form.html", {"form": form, "perimetre": perimetre})


@login_required
def parapheur_detail(request, pk):
    piece = get_object_or_404(
        PieceParapheur.objects.select_related("document", "demandeur", "perimetre"), pk=pk
    )
    etape = piece.etape_courante()
    return render(
        request,
        "intranet/parapheur_detail.html",
        {
            "piece": piece,
            "visas": piece.visas.select_related("viseur"),
            "mon_etape": etape if etape is not None and etape.viseur_id == request.user.pk else None,
            "form_visa": VisaForm(),
            "peut_soumettre": piece.demandeur_id == request.user.pk and piece.est_modifiable,
        },
    )


@login_required
def parapheur_soumettre(request, pk):
    piece = get_object_or_404(PieceParapheur, pk=pk, demandeur=request.user)
    if request.method != "POST":
        return redirect(piece.get_absolute_url())
    try:
        soumettre_au_parapheur(piece, requete=request)
        messages.success(request, "Piece transmise au premier viseur.")
    except ErreurCourrier as erreur:
        messages.error(request, str(erreur))
    return redirect(piece.get_absolute_url())


@login_required
def parapheur_viser(request, pk, decision):
    visa = get_object_or_404(
        Visa.objects.select_related("piece"), pk=pk, viseur=request.user,
        decision=Visa.Decision.ATTENTE,
    )
    if request.method != "POST":
        return redirect(visa.piece.get_absolute_url())

    form = VisaForm(request.POST)
    form.is_valid()
    observation = form.cleaned_data.get("observation", "")
    favorable = decision == "viser"
    if not favorable and not observation.strip():
        messages.error(request, "Indiquez le motif du refus.")
        return redirect(visa.piece.get_absolute_url())
    try:
        viser(visa, favorable, observation, requete=request)
        messages.success(request, "Visa donne." if favorable else "Piece refusee.")
    except ErreurCourrier as erreur:
        messages.error(request, str(erreur))
    return redirect(visa.piece.get_absolute_url())


@login_required
def modeles(request):
    """Modeles de courrier, rendus a l'en-tete de la direction."""
    liste = ModeleDocument.objects.filter(actif=True)
    choisi = liste.filter(code=request.GET.get("modele")).first()
    rendu = ""
    if choisi is not None:
        rendu = choisi.rendre(
            objet="",
            correspondant="",
            date=timezone.localdate().strftime("%d/%m/%Y"),
            perimetre=request.user.perimetre.nom if request.user.perimetre else "",
            signataire=request.user.nom_complet,
        )
    return render(
        request, "intranet/modeles.html", {"modeles": liste, "choisi": choisi, "rendu": rendu}
    )

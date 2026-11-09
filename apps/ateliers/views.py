"""Ecrans des ateliers : organisation, QR codes, emargement, paiement, attestations."""
import csv
import io

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.core.models import JournalAction

from .forms import (
    AtelierForm,
    CompteRenduForm,
    EmargementManuelForm,
    FiltreAteliersForm,
    ImportParticipantsForm,
    MotifForm,
    ParticipantForm,
    ScanForm,
    SessionForm,
)
from .models import Atelier, Emargement, Participant, Session
from .services import (
    ErreurAtelier,
    annuler,
    annuler_emargement,
    clore,
    donnees_attestation,
    enregistrer_emargement,
    etat_de_paiement,
    feuille_de_presence,
    generer_sessions,
    ouvrir,
    participant_du_jeton,
    tableau_ateliers,
)


# --- Acces -------------------------------------------------------------------
def _atelier_visible(agent, pk):
    atelier = get_object_or_404(
        Atelier.objects.select_related("perimetre", "organisateur", "activite"), pk=pk
    )
    if not Atelier.objects.visibles_par(agent).filter(pk=pk).exists():
        raise Http404("Atelier introuvable dans votre perimetre.")
    return atelier


def _exiger_controle(agent, atelier):
    if not atelier.peut_etre_controle_par(agent):
        raise Http404("Vous n'etes pas habilite a emarger cet atelier.")


# --- Tableau de bord ---------------------------------------------------------
@login_required
def tableau(request):
    contexte = tableau_ateliers(request.user)
    contexte["peut_organiser"] = request.user.perimetre is not None
    return render(request, "intranet/ateliers_tableau.html", contexte)


@login_required
def liste(request):
    form = FiltreAteliersForm(request.GET or None, agent=request.user)
    ateliers = Atelier.objects.visibles_par(request.user).select_related(
        "perimetre", "organisateur"
    )
    if form.is_valid():
        if q := form.cleaned_data.get("q"):
            ateliers = ateliers.filter(Q(intitule__icontains=q) | Q(lieu__icontains=q))
        if statut := form.cleaned_data.get("statut"):
            ateliers = ateliers.filter(statut=statut)
        if type_ := form.cleaned_data.get("type"):
            ateliers = ateliers.filter(type=type_)
        if perimetre := form.cleaned_data.get("perimetre"):
            ateliers = ateliers.filter(perimetre__code=perimetre)

    return render(
        request,
        "intranet/ateliers.html",
        {
            "form": form,
            "page_obj": Paginator(ateliers, 25).get_page(request.GET.get("page")),
            "total": ateliers.count(),
        },
    )


# --- Organisation ------------------------------------------------------------
@login_required
def creer(request):
    perimetre = request.user.perimetre
    if perimetre is None:
        messages.error(request, "Votre compte n'est rattache a aucun perimetre.")
        return redirect("ateliers:liste")

    form = AtelierForm(request.POST or None, perimetre=perimetre)
    if request.method == "POST" and form.is_valid():
        atelier = form.save(commit=False)
        atelier.perimetre = perimetre
        atelier.organisateur = atelier.organisateur or request.user
        atelier.save()
        form.save_m2m()
        sessions = generer_sessions(
            atelier, creneaux_par_jour=int(form.cleaned_data["creneaux_par_jour"])
        )
        JournalAction.tracer(request.user, "Creation d'un atelier", atelier.intitule, requete=request)
        messages.success(request, f"Atelier cree avec {len(sessions)} session(s).")
        return redirect(atelier.get_absolute_url())
    return render(request, "intranet/atelier_form.html", {"form": form, "perimetre": perimetre})


@login_required
def detail(request, pk):
    atelier = _atelier_visible(request.user, pk)
    return render(
        request,
        "intranet/atelier_detail.html",
        {
            "atelier": atelier,
            "sessions": atelier.sessions.all(),
            "participants": atelier.participants.select_related("categorie", "agent"),
            "feuille": feuille_de_presence(atelier),
            "peut_organiser": atelier.peut_etre_organise_par(request.user),
            "peut_controler": atelier.peut_etre_controle_par(request.user),
            "form_motif": MotifForm(),
            "compte_rendu": getattr(atelier, "compte_rendu", None),
        },
    )


@login_required
def modifier(request, pk):
    atelier = _atelier_visible(request.user, pk)
    if not atelier.peut_etre_organise_par(request.user):
        messages.error(request, "Vous n'etes pas habilite a modifier cet atelier.")
        return redirect(atelier.get_absolute_url())

    form = AtelierForm(request.POST or None, instance=atelier, perimetre=atelier.perimetre)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Atelier mis a jour.")
        return redirect(atelier.get_absolute_url())
    return render(
        request, "intranet/atelier_form.html",
        {"form": form, "perimetre": atelier.perimetre, "atelier": atelier},
    )


@login_required
def cycle(request, pk, operation):
    """Ouverture, cloture ou annulation de l'atelier."""
    atelier = _atelier_visible(request.user, pk)
    if request.method != "POST":
        return redirect(atelier.get_absolute_url())
    if not atelier.peut_etre_organise_par(request.user):
        messages.error(request, "Vous n'etes pas habilite a prendre cette decision.")
        return redirect(atelier.get_absolute_url())

    form = MotifForm(request.POST)
    form.is_valid()
    try:
        if operation == "ouvrir":
            ouvrir(atelier, request.user, requete=request)
            messages.success(request, "Atelier ouvert : l'emargement est possible.")
        elif operation == "clore":
            _, rapporte = clore(atelier, request.user, requete=request)
            messages.success(
                request,
                "Atelier clos."
                + (" Les presences ont ete reportees sur le plan d'action." if rapporte else ""),
            )
        elif operation == "annuler":
            annuler(atelier, request.user, form.cleaned_data.get("motif", ""), requete=request)
            messages.warning(request, "Atelier annule.")
        else:
            raise ErreurAtelier("Operation inconnue.")
    except ErreurAtelier as erreur:
        messages.error(request, str(erreur))
    return redirect(atelier.get_absolute_url())


# --- Participants ------------------------------------------------------------
@login_required
def participant_creer(request, pk):
    atelier = _atelier_visible(request.user, pk)
    if not atelier.peut_etre_organise_par(request.user):
        messages.error(request, "Vous n'etes pas habilite a inscrire des participants.")
        return redirect(atelier.get_absolute_url())

    form = ParticipantForm(request.POST or None, atelier=atelier)
    import_form = ImportParticipantsForm(perimetre=atelier.perimetre)
    if request.method == "POST" and form.is_valid():
        participant = form.save(commit=False)
        participant.atelier = atelier
        participant.inscrit_par = request.user
        participant.save()
        messages.success(request, f"{participant.nom_complet} inscrit(e).")
        return redirect("ateliers:participants", pk=atelier.pk)
    return render(
        request,
        "intranet/atelier_participants.html",
        {
            "atelier": atelier, "form": form, "import_form": import_form,
            "participants": atelier.participants.select_related("categorie", "agent"),
            "peut_organiser": atelier.peut_etre_organise_par(request.user),
        },
    )


@login_required
def participants_importer(request, pk):
    """Inscrit d'un coup tous les agents d'une structure."""
    atelier = _atelier_visible(request.user, pk)
    if request.method != "POST" or not atelier.peut_etre_organise_par(request.user):
        return redirect("ateliers:participants", pk=atelier.pk)

    form = ImportParticipantsForm(request.POST, perimetre=atelier.perimetre)
    if not form.is_valid():
        messages.error(request, "Choisissez une structure.")
        return redirect("ateliers:participants", pk=atelier.pk)

    structure = form.cleaned_data["structure"]
    categorie = form.cleaned_data.get("categorie")
    deja = set(atelier.participants.values_list("agent_id", flat=True))
    crees = 0
    for agent in structure.agents.filter(is_active=True).exclude(pk__in=deja):
        Participant.objects.create(
            atelier=atelier, agent=agent, nom="", categorie=categorie,
            inscrit_par=request.user,
        )
        crees += 1
    messages.success(request, f"{crees} agent(s) inscrit(s).")
    return redirect("ateliers:participants", pk=atelier.pk)


@login_required
def participant_revoquer(request, pk):
    participant = get_object_or_404(Participant.objects.select_related("atelier"), pk=pk)
    atelier = _atelier_visible(request.user, participant.atelier_id)
    if request.method != "POST" or not atelier.peut_etre_organise_par(request.user):
        return redirect("ateliers:participants", pk=atelier.pk)
    participant.statut = Participant.Statut.REVOQUE
    participant.save(update_fields=["statut"])
    messages.warning(request, f"{participant.nom_complet} revoque(e).")
    return redirect("ateliers:participants", pk=atelier.pk)


@login_required
def badges(request, pk):
    """Planche de badges a imprimer : un QR code par participant."""
    atelier = _atelier_visible(request.user, pk)
    return render(
        request,
        "intranet/atelier_badges.html",
        {
            "atelier": atelier,
            "participants": atelier.participants.exclude(statut=Participant.Statut.REVOQUE),
        },
    )


@login_required
def qr_participant(request, pk):
    """Image SVG du QR code d'un participant."""
    import qrcode
    import qrcode.image.svg

    participant = get_object_or_404(Participant.objects.select_related("atelier"), pk=pk)
    _atelier_visible(request.user, participant.atelier_id)

    image = qrcode.make(
        participant.jeton, image_factory=qrcode.image.svg.SvgPathImage, box_size=10, border=2
    )
    tampon = io.BytesIO()
    image.save(tampon)
    return HttpResponse(tampon.getvalue(), content_type="image/svg+xml")


# --- Emargement --------------------------------------------------------------
@login_required
def emargement(request, pk, session_pk=None):
    """Ecran de scan : un jeton saisi, une presence constatee."""
    atelier = _atelier_visible(request.user, pk)
    _exiger_controle(request.user, atelier)

    sessions = list(atelier.sessions.all())
    if not sessions:
        messages.error(request, "Definissez au moins une session avant d'emarger.")
        return redirect(atelier.get_absolute_url())

    session = (
        get_object_or_404(Session, pk=session_pk, atelier=atelier)
        if session_pk
        else _session_du_jour(sessions)
    )

    form = ScanForm(request.POST or None)
    form_manuel = EmargementManuelForm(session=session)
    if request.method == "POST" and form.is_valid():
        participant = participant_du_jeton(atelier, form.cleaned_data["jeton"])
        if participant is None:
            messages.error(request, "Jeton invalide : ce code ne correspond a aucun participant.")
        else:
            try:
                _, cree = enregistrer_emargement(
                    session, participant, request.user, appareil=_appareil(request)
                )
                if cree:
                    messages.success(request, f"{participant.nom_complet} : presence enregistree.")
                else:
                    messages.warning(request, f"{participant.nom_complet} avait deja emarge.")
            except ErreurAtelier as erreur:
                messages.error(request, str(erreur))
        return redirect("ateliers:emargement_session", pk=atelier.pk, session_pk=session.pk)

    return render(
        request,
        "intranet/atelier_emargement.html",
        {
            "atelier": atelier, "session": session, "sessions": sessions,
            "form": form, "form_manuel": form_manuel,
            "emargements": session.emargements.select_related("participant", "saisi_par"),
            "attendus": atelier.nb_participants,
        },
    )


def _session_du_jour(sessions):
    """Session correspondant a aujourd'hui, ou la premiere a venir."""
    aujourdhui = timezone.localdate()
    for session in sessions:
        if session.date == aujourdhui:
            return session
    for session in sessions:
        if session.date >= aujourdhui:
            return session
    return sessions[-1]


def _appareil(request):
    return (request.META.get("HTTP_USER_AGENT") or "")[:80]


@login_required
def emargement_manuel(request, pk, session_pk):
    atelier = _atelier_visible(request.user, pk)
    _exiger_controle(request.user, atelier)
    session = get_object_or_404(Session, pk=session_pk, atelier=atelier)

    if request.method != "POST":
        return redirect("ateliers:emargement_session", pk=atelier.pk, session_pk=session.pk)

    form = EmargementManuelForm(request.POST, session=session)
    if form.is_valid():
        try:
            enregistrer_emargement(
                session, form.cleaned_data["participant"], request.user,
                mode=Emargement.Mode.MANUEL, motif=form.cleaned_data["motif"],
                appareil=_appareil(request),
            )
            messages.success(request, "Presence enregistree manuellement.")
        except ErreurAtelier as erreur:
            messages.error(request, str(erreur))
    else:
        messages.error(request, "Choisissez un participant et indiquez le motif.")
    return redirect("ateliers:emargement_session", pk=atelier.pk, session_pk=session.pk)


@login_required
def emargement_annuler(request, pk):
    emarg = get_object_or_404(
        Emargement.objects.select_related("session__atelier", "participant"), pk=pk
    )
    atelier = _atelier_visible(request.user, emarg.session.atelier_id)
    _exiger_controle(request.user, atelier)
    session_pk = emarg.session_id
    if request.method != "POST":
        return redirect("ateliers:emargement_session", pk=atelier.pk, session_pk=session_pk)

    form = MotifForm(request.POST)
    form.is_valid()
    try:
        annuler_emargement(emarg, request.user, form.cleaned_data.get("motif", ""))
        messages.warning(request, "Emargement annule.")
    except ErreurAtelier as erreur:
        messages.error(request, str(erreur))
    return redirect("ateliers:emargement_session", pk=atelier.pk, session_pk=session_pk)


# --- Sorties -----------------------------------------------------------------
@login_required
def paiement(request, pk):
    atelier = _atelier_visible(request.user, pk)
    return render(
        request,
        "intranet/atelier_paiement.html",
        {"atelier": atelier, "etat": etat_de_paiement(atelier)},
    )


@login_required
def paiement_csv(request, pk):
    atelier = _atelier_visible(request.user, pk)
    etat = etat_de_paiement(atelier)

    reponse = HttpResponse(content_type="text/csv; charset=utf-8")
    reponse["Content-Disposition"] = (
        f'attachment; filename="etat-paiement-{atelier.id_court}.csv"'
    )
    reponse.write("﻿")
    ecrivain = csv.writer(reponse, delimiter=";")
    ecrivain.writerow(["Nom", "Prenoms", "Fonction", "Structure", "Categorie",
                       "Jours constates", "Montant journalier", "Montant du"])
    for ligne in etat["lignes"]:
        p = ligne["participant"]
        ecrivain.writerow([p.nom, p.prenoms, p.fonction, p.structure_origine,
                           ligne["categorie"], ligne["jours"],
                           ligne["montant_journalier"], ligne["montant"]])
    ecrivain.writerow([])
    ecrivain.writerow(["", "", "", "", "TOTAL", "", "", etat["total"]])
    JournalAction.tracer(
        request.user, "Export de l'etat de paiement", atelier.intitule, requete=request
    )
    return reponse


@login_required
def presence_csv(request, pk):
    atelier = _atelier_visible(request.user, pk)
    feuille = feuille_de_presence(atelier)

    reponse = HttpResponse(content_type="text/csv; charset=utf-8")
    reponse["Content-Disposition"] = f'attachment; filename="presence-{atelier.id_court}.csv"'
    reponse.write("﻿")
    ecrivain = csv.writer(reponse, delimiter=";")
    ecrivain.writerow(
        ["Nom", "Prenoms", "Structure"] + [str(s) for s in feuille["sessions"]] + ["Total"]
    )
    for ligne in feuille["lignes"]:
        p = ligne["participant"]
        ecrivain.writerow(
            [p.nom, p.prenoms, p.structure_origine]
            + ["X" if presence else "" for presence in ligne["presences"]]
            + [ligne["nb_presences"]]
        )
    return reponse


@login_required
def attestation(request, pk):
    participant = get_object_or_404(Participant.objects.select_related("atelier"), pk=pk)
    atelier = _atelier_visible(request.user, participant.atelier_id)
    donnees = donnees_attestation(participant)
    if donnees is None:
        messages.error(
            request,
            f"{participant.nom_complet} n'a pas emarge assez de sessions pour recevoir "
            "une attestation.",
        )
        return redirect(atelier.get_absolute_url())
    return render(request, "intranet/atelier_attestation.html", donnees)


@login_required
def compte_rendu(request, pk):
    atelier = _atelier_visible(request.user, pk)
    if not atelier.peut_etre_organise_par(request.user):
        messages.error(request, "Vous n'etes pas habilite a rediger le compte rendu.")
        return redirect(atelier.get_absolute_url())

    instance = getattr(atelier, "compte_rendu", None)
    form = CompteRenduForm(request.POST or None, request.FILES or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        rendu = form.save(commit=False)
        rendu.atelier = atelier
        rendu.redige_par = request.user
        rendu.save()
        messages.success(request, "Compte rendu enregistre.")
        return redirect(atelier.get_absolute_url())
    return render(
        request, "intranet/atelier_compte_rendu.html", {"form": form, "atelier": atelier}
    )


@login_required
def session_creer(request, pk):
    atelier = _atelier_visible(request.user, pk)
    if not atelier.peut_etre_organise_par(request.user):
        messages.error(request, "Vous n'etes pas habilite a modifier les sessions.")
        return redirect(atelier.get_absolute_url())

    form = SessionForm(request.POST or None, atelier=atelier)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Session ajoutee.")
        return redirect(atelier.get_absolute_url())
    return render(request, "intranet/atelier_session_form.html", {"form": form, "atelier": atelier})

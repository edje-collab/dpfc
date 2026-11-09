import csv
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.core.models import JournalAction, Structure
from apps.signature.services import ErreurSignature, signer_demande

from .forms import (
    AIDE_PAR_TYPE,
    DecisionForm,
    DemandeForm,
    FiltreRegistreForm,
    RapportMissionForm,
    SoldeForm,
)
from .models import Demande, JourFerie, SoldeConge, TypeDemande, Validation
from .services import annuler, decider, demandes_a_traiter, soumettre

Agent = get_user_model()


# --- Tableau de bord ---------------------------------------------------------
@login_required
def tableau_bord(request):
    agent = request.user
    aujourdhui = timezone.localdate()
    mes_demandes = Demande.objects.filter(agent=agent)
    solde = SoldeConge.pour(agent)
    a_valider = demandes_a_traiter(agent)

    equipe_absente = (
        Demande.objects.filter(
            statut=Demande.Statut.APPROUVEE,
            date_fin__gte=aujourdhui,
            date_debut__lte=aujourdhui + timedelta(days=30),
        )
        .exclude(agent=agent)
        .select_related("agent", "agent__structure")
    )
    if agent.est_rh or agent.est_direction:
        pass
    elif agent.structure_id:
        equipe_absente = equipe_absente.filter(agent__structure=agent.structure)
    else:
        equipe_absente = equipe_absente.none()

    contexte = {
        "solde": solde,
        "mes_demandes_recentes": mes_demandes.select_related("agent")[:5],
        "nb_en_cours": mes_demandes.filter(
            statut__in=[Demande.Statut.SOUMISE, Demande.Statut.EN_COURS]
        ).count(),
        "nb_approuvees": mes_demandes.filter(statut=Demande.Statut.APPROUVEE).count(),
        "nb_brouillons": mes_demandes.filter(statut=Demande.Statut.BROUILLON).count(),
        "a_valider": a_valider[:6],
        "nb_a_valider_total": a_valider.count(),
        "equipe_absente": equipe_absente[:8],
        "types": TypeDemande.choices,
        "aides": AIDE_PAR_TYPE,
        "missions_sans_rapport": mes_demandes.filter(
            type=TypeDemande.ORDRE_MISSION,
            statut=Demande.Statut.APPROUVEE,
            date_fin__lt=aujourdhui,
            rapport__isnull=True,
        )[:5],
    }
    return render(request, "intranet/tableau_bord.html", contexte)


# --- Demandes de l'agent -----------------------------------------------------
@login_required
def mes_demandes(request):
    liste = Demande.objects.filter(agent=request.user).select_related("agent")
    statut = request.GET.get("statut", "")
    type_acte = request.GET.get("type", "")
    if statut:
        liste = liste.filter(statut=statut)
    if type_acte:
        liste = liste.filter(type=type_acte)
    pages = Paginator(liste, 20).get_page(request.GET.get("page"))
    return render(
        request,
        "intranet/mes_demandes.html",
        {
            "page_obj": pages,
            "statuts": Demande.Statut.choices,
            "types": TypeDemande.choices,
            "statut_actif": statut,
            "type_actif": type_acte,
        },
    )


@login_required
def demande_creer(request, type_acte):
    type_acte = type_acte.upper()
    if type_acte not in TypeDemande.values:
        messages.error(request, "Type d'acte inconnu.")
        return redirect("rh:mes_demandes")
    pour_autrui = request.GET.get("pour") == "agent" and _peut_deposer_pour_autrui(request.user)
    form = DemandeForm(
        request.POST or None,
        request.FILES or None,
        type_acte=type_acte,
        agent=request.user,
        depot_pour_autrui=pour_autrui,
    )
    if request.method == "POST" and form.is_valid():
        demande = form.save()
        if request.POST.get("action") == "soumettre":
            return _soumettre_et_rediriger(request, demande)
        messages.success(request, "Brouillon enregistre. Vous pouvez le completer puis le soumettre.")
        return redirect("rh:demande_detail", pk=demande.pk)
    return render(
        request,
        "intranet/demande_form.html",
        {
            "form": form,
            "type_acte": type_acte,
            "libelle_type": TypeDemande(type_acte).label,
            "aide": AIDE_PAR_TYPE.get(type_acte, ""),
            "solde": SoldeConge.pour(request.user),
            "pour_autrui": pour_autrui,
            "peut_deposer_pour_autrui": _peut_deposer_pour_autrui(request.user),
        },
    )


def _peut_deposer_pour_autrui(agent):
    """Le secretariat d'antenne (et le chef d'antenne) depose pour les agents de l'antenne."""
    return agent.role in {agent.Role.SECRETARIAT, agent.Role.CHEF_ANTENNE} and agent.structure_id


@login_required
def demande_modifier(request, pk):
    demande = get_object_or_404(Demande, pk=pk)
    if demande.agent_id != request.user.pk and demande.depose_par_id != request.user.pk:
        messages.error(request, "Vous ne pouvez modifier que vos demandes ou vos depots.")
        return redirect("rh:demande_detail", pk=pk)
    if not demande.est_modifiable:
        messages.error(request, "Cette demande est engagee dans le circuit : elle n'est plus modifiable.")
        return redirect("rh:demande_detail", pk=pk)
    form = DemandeForm(
        request.POST or None,
        request.FILES or None,
        instance=demande,
        type_acte=demande.type,
        agent=request.user,
    )
    if request.method == "POST" and form.is_valid():
        demande = form.save()
        if request.POST.get("action") == "soumettre":
            return _soumettre_et_rediriger(request, demande)
        messages.success(request, "Modifications enregistrees.")
        return redirect("rh:demande_detail", pk=demande.pk)
    return render(
        request,
        "intranet/demande_form.html",
        {
            "form": form,
            "demande": demande,
            "type_acte": demande.type,
            "libelle_type": demande.get_type_display(),
            "aide": AIDE_PAR_TYPE.get(demande.type, ""),
            "solde": SoldeConge.pour(request.user),
        },
    )


def _soumettre_et_rediriger(request, demande):
    try:
        demande.full_clean(exclude=["numero", "structure", "nb_jours"])
        soumettre(demande, requete=request)
    except ValidationError as err:
        for champ, erreurs in err.message_dict.items():
            messages.error(request, f"{champ} : {' '.join(erreurs)}")
        return redirect("rh:demande_modifier", pk=demande.pk)
    except ValueError as err:
        messages.error(request, str(err))
        return redirect("rh:demande_detail", pk=demande.pk)
    messages.success(
        request, f"Demande {demande.numero} transmise. Vous serez notifie a chaque etape."
    )
    return redirect("rh:demande_detail", pk=demande.pk)


@login_required
def demande_detail(request, pk):
    demande = get_object_or_404(
        Demande.objects.select_related("agent", "agent__structure", "interimaire", "structure"), pk=pk
    )
    agent = request.user
    est_valideur = demande.validations.filter(valideur=agent).exists()
    if not (
        demande.agent_id == agent.pk
        or demande.depose_par_id == agent.pk
        or est_valideur
        or agent.est_rh
        or agent.est_direction
        or agent.peut_administrer
        or demande.interimaire_id == agent.pk
    ):
        messages.error(request, "Vous n'avez pas acces a cette demande.")
        return redirect("rh:tableau_bord")

    etape = demande.etape_courante()
    peut_decider = etape is not None and etape.valideur_id == agent.pk
    derniere = etape is not None and not demande.validations.filter(ordre__gt=etape.ordre).exists()
    return render(
        request,
        "intranet/demande_detail.html",
        {
            "demande": demande,
            "validations": demande.validations.select_related("valideur", "signature").all(),
            "peut_decider": peut_decider,
            "form_decision": DecisionForm(signature_requise=derniere) if peut_decider else None,
            "etape": etape,
            "etape_de_signature": derniere,
            "rapport": getattr(demande, "rapport", None),
            "signatures": demande.signatures.select_related("signataire").all(),
        },
    )


@login_required
def demande_soumettre(request, pk):
    demande = get_object_or_404(Demande, pk=pk)
    if demande.agent_id != request.user.pk and demande.depose_par_id != request.user.pk:
        return redirect("rh:demande_detail", pk=pk)
    if request.method != "POST" or not demande.est_modifiable:
        return redirect("rh:demande_detail", pk=pk)
    return _soumettre_et_rediriger(request, demande)


@login_required
def demande_annuler(request, pk):
    demande = get_object_or_404(Demande, pk=pk)
    autorise = demande.agent_id == request.user.pk or request.user.est_rh or request.user.est_direction
    if request.method != "POST" or not autorise or not demande.est_annulable:
        return redirect("rh:demande_detail", pk=pk)
    annuler(demande, request.user, requete=request)
    messages.success(request, f"Demande {demande.numero or ''} annulee.")
    return redirect("rh:demande_detail", pk=pk)


@login_required
def demande_decider(request, pk):
    demande = get_object_or_404(Demande, pk=pk)
    etape = demande.etape_courante()
    if etape is None or etape.valideur_id != request.user.pk or request.method != "POST":
        messages.error(request, "Cette demande n'attend pas votre decision.")
        return redirect("rh:demande_detail", pk=pk)
    derniere = not demande.validations.filter(ordre__gt=etape.ordre).exists()
    form = DecisionForm(request.POST, signature_requise=derniere and _peut_signer(request.user))
    if not form.is_valid():
        for erreurs in form.errors.values():
            for e in erreurs:
                messages.error(request, e)
        return redirect("rh:demande_detail", pk=pk)

    favorable = form.cleaned_data["decision"] == "FAVORABLE"
    code = form.cleaned_data.get("code_signature")
    decider(etape, favorable, form.cleaned_data["commentaire"], requete=request)
    demande.refresh_from_db()

    if favorable and code:
        try:
            signature = signer_demande(
                demande, request.user, code, qualite=etape.libelle, validation=etape, requete=request
            )
        except ErreurSignature as err:
            messages.warning(
                request,
                f"Avis enregistre, mais la signature electronique n'a pas pu etre apposee : {err}",
            )
        else:
            messages.success(
                request,
                f"Acte signe electroniquement. Code de verification : {signature.code_verification}.",
            )
            return redirect("rh:demande_detail", pk=pk)
    elif favorable and derniere and not _peut_signer(request.user):
        messages.info(
            request,
            "Acte approuve. Creez votre cle dans « Ma signature electronique » pour signer "
            "numeriquement vos prochains actes.",
        )
    messages.success(
        request, "Avis favorable enregistre." if favorable else "Demande rejetee."
    )
    return redirect("rh:a_valider")


def _peut_signer(agent):
    cle = getattr(agent, "cle_signature", None)
    return bool(cle and cle.est_valide)


@login_required
def a_valider(request):
    liste = demandes_a_traiter(request.user)
    return render(
        request,
        "intranet/a_valider.html",
        {"demandes": liste, "total": liste.count()},
    )


# --- Rapport de mission ------------------------------------------------------
@login_required
def rapport_mission(request, pk):
    demande = get_object_or_404(Demande, pk=pk, agent=request.user, type=TypeDemande.ORDRE_MISSION)
    if demande.statut != Demande.Statut.APPROUVEE:
        messages.error(request, "Le rapport se depose apres approbation de l'ordre de mission.")
        return redirect("rh:demande_detail", pk=pk)
    instance = getattr(demande, "rapport", None)
    form = RapportMissionForm(request.POST or None, request.FILES or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        rapport = form.save(commit=False)
        rapport.demande = demande
        rapport.save()
        Agent.objects.filter(pk=request.user.pk, situation=Agent.Situation.EN_MISSION).update(
            situation=Agent.Situation.EN_POSTE
        )
        messages.success(request, "Rapport de mission depose.")
        return redirect("rh:demande_detail", pk=pk)
    return render(request, "intranet/rapport_form.html", {"form": form, "demande": demande})


# --- Planning et registre ----------------------------------------------------
@login_required
def planning(request):
    """Absences approuvees sur une periode, par structure."""
    debut = timezone.localdate().replace(day=1)
    try:
        mois = int(request.GET.get("mois", debut.month))
        annee = int(request.GET.get("annee", debut.year))
        debut = debut.replace(year=annee, month=mois)
    except (ValueError, TypeError):
        pass
    fin = (debut + timedelta(days=32)).replace(day=1) - timedelta(days=1)

    absences = (
        Demande.objects.filter(
            statut=Demande.Statut.APPROUVEE, date_debut__lte=fin, date_fin__gte=debut
        )
        .select_related("agent", "agent__structure", "agent__structure__region")
        .order_by("date_debut")
    )
    perimetre = request.user.perimetre_agents()
    absences = absences.filter(agent__in=perimetre)

    structure = request.GET.get("structure", "")
    if structure:
        absences = absences.filter(agent__structure__slug=structure)

    jours = [debut + timedelta(days=i) for i in range((fin - debut).days + 1)]
    lignes = []
    for demande in absences:
        lignes.append(
            {
                "demande": demande,
                "cases": [
                    {
                        "jour": j,
                        "occupee": demande.date_debut <= j <= demande.date_fin,
                        "weekend": j.weekday() >= 5,
                    }
                    for j in jours
                ],
            }
        )
    return render(
        request,
        "intranet/planning.html",
        {
            "lignes": lignes,
            "jours": jours,
            "debut": debut,
            "fin": fin,
            "structures": Structure.objects.filter(active=True),
            "structure_active": structure,
            "mois_precedent": (debut - timedelta(days=1)).replace(day=1),
            "mois_suivant": fin + timedelta(days=1),
        },
    )


def _acces_registre(agent):
    return agent.est_rh or agent.est_direction or agent.peut_administrer or agent.est_valideur


@login_required
def registre(request):
    if not _acces_registre(request.user):
        messages.error(request, "Le registre est reserve aux responsables et au service du personnel.")
        return redirect("rh:tableau_bord")
    form = FiltreRegistreForm(request.GET or None)
    liste = Demande.objects.select_related("agent", "agent__structure", "structure").exclude(
        statut=Demande.Statut.BROUILLON
    )
    if not (request.user.est_rh or request.user.est_direction or request.user.peut_administrer):
        liste = liste.filter(agent__in=request.user.perimetre_agents())
    if form.is_valid():
        d = form.cleaned_data
        if d.get("q"):
            liste = liste.filter(
                Q(numero__icontains=d["q"])
                | Q(agent__last_name__icontains=d["q"])
                | Q(agent__first_name__icontains=d["q"])
                | Q(agent__matricule__icontains=d["q"])
                | Q(motif__icontains=d["q"])
            )
        if d.get("type"):
            liste = liste.filter(type=d["type"])
        if d.get("statut"):
            liste = liste.filter(statut=d["statut"])
        if d.get("rattachement"):
            liste = liste.filter(agent__structure__rattachement=d["rattachement"])
        if d.get("du"):
            liste = liste.filter(date_fin__gte=d["du"])
        if d.get("au"):
            liste = liste.filter(date_debut__lte=d["au"])

    if request.GET.get("export") == "csv":
        return _export_csv(liste)

    stats = {
        "total": liste.count(),
        "par_type": liste.values("type").annotate(n=Count("id")).order_by("-n"),
        "par_statut": liste.values("statut").annotate(n=Count("id")).order_by("-n"),
        "jours": liste.filter(statut=Demande.Statut.APPROUVEE).aggregate(t=Sum("nb_jours"))["t"] or 0,
    }
    pages = Paginator(liste, 30).get_page(request.GET.get("page"))
    return render(
        request,
        "intranet/registre.html",
        {"page_obj": pages, "form": form, "stats": stats, "parametres": request.GET.urlencode()},
    )


def _export_csv(liste):
    reponse = HttpResponse(content_type="text/csv; charset=utf-8-sig")
    reponse["Content-Disposition"] = (
        f"attachment; filename=registre-actes-dpfc-{timezone.localdate():%Y%m%d}.csv"
    )
    plume = csv.writer(reponse, delimiter=";")
    plume.writerow(
        ["Numero", "Type", "Matricule", "Agent", "Structure", "Affectation", "Du", "Au",
         "Jours", "Statut", "Soumise le", "Decision le"]
    )
    for d in liste.select_related("agent", "agent__structure"):
        plume.writerow([
            d.numero, d.get_type_display(), d.agent.matricule, d.agent.nom_complet,
            d.agent.structure.nom if d.agent.structure_id else "",
            d.agent.get_affectation_display() if hasattr(d.agent, "get_affectation_display") else d.agent.affectation,
            d.date_debut.strftime("%d/%m/%Y"), d.date_fin.strftime("%d/%m/%Y"), d.nb_jours,
            d.get_statut_display(),
            d.soumise_le.strftime("%d/%m/%Y %H:%M") if d.soumise_le else "",
            d.cloturee_le.strftime("%d/%m/%Y %H:%M") if d.cloturee_le else "",
        ])
    return reponse


# --- Soldes de conge ---------------------------------------------------------
@login_required
def mes_soldes(request):
    return render(
        request,
        "intranet/mes_soldes.html",
        {
            "soldes": SoldeConge.objects.filter(agent=request.user),
            "solde": SoldeConge.pour(request.user),
            "conges": Demande.objects.filter(
                agent=request.user, type__in=[TypeDemande.CONGE_ANNUEL, TypeDemande.CONGE_EXCEPTIONNEL]
            )[:10],
        },
    )


@login_required
def soldes_gestion(request):
    if not (request.user.est_rh or request.user.peut_administrer):
        messages.error(request, "Gestion reservee au service du personnel.")
        return redirect("rh:tableau_bord")
    annee = int(request.GET.get("annee", timezone.localdate().year))
    form = SoldeForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        donnees = form.cleaned_data
        solde, _ = SoldeConge.objects.update_or_create(
            agent=donnees["agent"],
            annee=donnees["annee"],
            defaults={
                "droit_jours": donnees["droit_jours"],
                "jours_reportes": donnees["jours_reportes"],
                "jours_consommes": donnees["jours_consommes"],
            },
        )
        JournalAction.tracer(request.user, "Mise a jour d'un solde de conge", str(solde), requete=request)
        messages.success(request, f"Solde mis a jour pour {solde.agent.nom_complet}.")
        return redirect("rh:soldes_gestion")
    return render(
        request,
        "intranet/soldes_gestion.html",
        {
            "form": form,
            "annee": annee,
            "soldes": SoldeConge.objects.filter(annee=annee).select_related("agent", "agent__structure"),
        },
    )


@login_required
def jours_feries(request):
    if not (request.user.est_rh or request.user.peut_administrer):
        return redirect("rh:tableau_bord")
    from .forms import JourFerieForm

    form = JourFerieForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Jour ferie enregistre.")
        return redirect("rh:jours_feries")
    return render(
        request,
        "intranet/jours_feries.html",
        {"form": form, "jours": JourFerie.objects.filter(date__year__gte=timezone.localdate().year - 1)},
    )


# --- Document officiel -------------------------------------------------------
@login_required
def document(request, pk):
    demande = get_object_or_404(
        Demande.objects.select_related("agent", "agent__structure", "agent__structure__region"), pk=pk
    )
    if demande.statut != Demande.Statut.APPROUVEE:
        messages.error(request, "Le document officiel n'est disponible qu'apres approbation.")
        return redirect("rh:demande_detail", pk=pk)
    autorise = (
        demande.agent_id == request.user.pk
        or request.user.est_rh
        or request.user.est_direction
        or demande.validations.filter(valideur=request.user).exists()
    )
    if not autorise:
        return redirect("rh:tableau_bord")
    signatures = list(demande.signatures.select_related("signataire").all())
    qr = None
    if signatures:
        from apps.signature.services import qrcode_svg

        url = request.build_absolute_uri(signatures[-1].get_absolute_url())
        qr = {"svg": qrcode_svg(url), "url": url, "signature": signatures[-1]}
    return render(
        request,
        "intranet/document_officiel.html",
        {
            "demande": demande,
            "signataires": demande.validations.filter(
                decision=Validation.Decision.FAVORABLE
            ).select_related("valideur", "signature"),
            "signatures": signatures,
            "qr": qr,
        },
    )

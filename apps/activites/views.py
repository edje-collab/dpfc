"""Ecrans du pilotage : plans d'action, activites, avancement, tableaux de bord."""
import csv

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.core.models import JournalAction, Perimetre

from .forms import (
    ActiviteForm,
    AvancementForm,
    DecisionPlanForm,
    FiltreActivitesForm,
    IndicateurForm,
    PlanActionForm,
    ReportForm,
)
from .models import Activite, Axe, PlanAction
from .services import (
    ErreurPlan,
    annuler_activite,
    chronogramme,
    clore_plan,
    consolidation_nationale,
    enregistrer_avancement,
    renvoyer_plan,
    reporter_activite,
    soumettre_plan,
    tableau_de_bord,
    valider_plan,
)


# --- Droits ------------------------------------------------------------------
def _peut_piloter(agent, perimetre):
    """Qui etablit et modifie le plan d'un perimetre."""
    if agent.peut_administrer or agent.est_direction:
        return True
    return agent.est_responsable_perimetre and agent.perimetre == perimetre


def _peut_valider(agent):
    """La validation des plans releve de la direction centrale."""
    return agent.est_direction or agent.peut_administrer


def _peut_rendre_compte(agent, activite):
    """Le responsable de l'activite, son chef de perimetre, ou la direction."""
    if agent.peut_administrer or agent.est_direction:
        return True
    if activite.responsable_id == agent.pk:
        return True
    return agent.est_responsable_perimetre and agent.perimetre == activite.perimetre


def _plan_visible(agent, pk):
    return get_object_or_404(
        PlanAction.objects.visibles_par(agent).select_related("perimetre", "valide_par"), pk=pk
    )


# --- Tableau de bord ---------------------------------------------------------
@login_required
def pilotage(request):
    """Vue d'ensemble du pilotage, limitee au perimetre de l'agent."""
    annee = int(request.GET.get("annee", timezone.localdate().year))
    contexte = tableau_de_bord(request.user, annee)
    contexte.update(
        {
            "annees": sorted(
                PlanAction.objects.visibles_par(request.user)
                .values_list("annee", flat=True)
                .distinct(),
                reverse=True,
            ),
            "consolidation": consolidation_nationale(annee)
            if (request.user.est_direction or request.user.peut_administrer)
            else [],
            "statuts": Activite.Statut,
        }
    )
    return render(request, "intranet/pilotage.html", contexte)


# --- Plans d'action ----------------------------------------------------------
@login_required
def plans(request):
    liste = (
        PlanAction.objects.visibles_par(request.user)
        .select_related("perimetre", "valide_par")
        .order_by("-annee", "perimetre__type", "perimetre__code")
    )
    mon_perimetre = request.user.perimetre
    return render(
        request,
        "intranet/plans.html",
        {
            "plans": liste,
            "peut_creer": mon_perimetre is not None and _peut_piloter(request.user, mon_perimetre),
            "mon_perimetre": mon_perimetre,
        },
    )


@login_required
def plan_creer(request):
    perimetre = request.user.perimetre
    if perimetre is None or not _peut_piloter(request.user, perimetre):
        messages.error(request, "Vous n'etes pas habilite a etablir un plan d'action.")
        return redirect("activites:plans")

    form = PlanActionForm(request.POST or None, perimetre=perimetre)
    if request.method == "POST" and form.is_valid():
        plan = form.save(commit=False)
        plan.perimetre = perimetre
        plan.save()
        JournalAction.tracer(request.user, "Creation d'un plan d'action", str(plan), requete=request)
        messages.success(request, "Plan d'action cree. Inscrivez-y vos activites.")
        return redirect(plan.get_absolute_url())
    return render(request, "intranet/plan_form.html", {"form": form, "perimetre": perimetre})


@login_required
def plan_detail(request, pk):
    plan = _plan_visible(request.user, pk)
    activites = (
        plan.activites.select_related("axe", "responsable", "structure")
        .prefetch_related("indicateurs")
        .order_by("date_debut_prevue", "code")
    )
    return render(
        request,
        "intranet/plan_detail.html",
        {
            "plan": plan,
            "activites": activites,
            "synthese": plan.synthese_par_axe(),
            "en_retard": plan.activites.en_retard().count(),
            "peut_piloter": _peut_piloter(request.user, plan.perimetre),
            "peut_valider": _peut_valider(request.user) and plan.statut == PlanAction.Statut.SOUMIS,
            "form_decision": DecisionPlanForm(),
        },
    )


@login_required
def plan_chronogramme(request, pk):
    plan = _plan_visible(request.user, pk)
    return render(
        request,
        "intranet/plan_chronogramme.html",
        {
            "plan": plan,
            "lignes": chronogramme(plan),
            "mois": ["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"],
        },
    )


@login_required
def plan_action(request, pk, operation):
    """Soumission, validation, renvoi ou cloture d'un plan."""
    plan = _plan_visible(request.user, pk)
    if request.method != "POST":
        return redirect(plan.get_absolute_url())

    try:
        if operation == "soumettre":
            if not _peut_piloter(request.user, plan.perimetre):
                raise ErreurPlan("Vous n'etes pas habilite a soumettre ce plan.")
            soumettre_plan(plan, par=request.user, requete=request)
            messages.success(request, "Plan transmis a la direction pour validation.")
        elif operation == "valider":
            if not _peut_valider(request.user):
                raise ErreurPlan("La validation des plans releve de la direction.")
            valider_plan(plan, par=request.user, requete=request)
            messages.success(request, "Plan valide : les activites peuvent demarrer.")
        elif operation == "renvoyer":
            if not _peut_valider(request.user):
                raise ErreurPlan("Le renvoi d'un plan releve de la direction.")
            form = DecisionPlanForm(request.POST)
            form.is_valid()
            renvoyer_plan(plan, par=request.user,
                          motif=form.cleaned_data.get("motif", ""), requete=request)
            messages.warning(request, "Plan renvoye en preparation.")
        elif operation == "clore":
            if not _peut_valider(request.user):
                raise ErreurPlan("La cloture d'un exercice releve de la direction.")
            _, reportees = clore_plan(plan, par=request.user, requete=request)
            messages.success(
                request,
                f"Exercice clos. {reportees} activite(s) non achevee(s) ont ete reportee(s).",
            )
        else:
            raise ErreurPlan("Operation inconnue.")
    except ErreurPlan as erreur:
        messages.error(request, str(erreur))
    return redirect(plan.get_absolute_url())


# --- Activites ---------------------------------------------------------------
@login_required
def activites(request):
    """Registre des activites, filtrable."""
    form = FiltreActivitesForm(request.GET or None, agent=request.user)
    liste = (
        Activite.objects.visibles_par(request.user)
        .select_related("plan__perimetre", "axe", "responsable")
    )
    if form.is_valid():
        if q := form.cleaned_data.get("q"):
            liste = liste.filter(
                Q(intitule__icontains=q) | Q(code__icontains=q) | Q(lieu__icontains=q)
            )
        if axe := form.cleaned_data.get("axe"):
            liste = liste.filter(axe__code=axe)
        if statut := form.cleaned_data.get("statut"):
            liste = liste.filter(statut=statut)
        if perimetre := form.cleaned_data.get("perimetre"):
            liste = liste.filter(plan__perimetre__code=perimetre)
        if form.cleaned_data.get("retard"):
            liste = liste.en_retard()

    annee = request.GET.get("annee")
    if annee:
        liste = liste.filter(plan__annee=annee)

    return render(
        request,
        "intranet/activites.html",
        {
            "form": form,
            "page_obj": Paginator(liste.order_by("date_debut_prevue"), 25).get_page(
                request.GET.get("page")
            ),
            "total": liste.count(),
            "annee": annee,
        },
    )


@login_required
def activite_creer(request, plan_pk):
    plan = _plan_visible(request.user, plan_pk)
    if not _peut_piloter(request.user, plan.perimetre):
        messages.error(request, "Vous n'etes pas habilite a modifier ce plan.")
        return redirect(plan.get_absolute_url())
    if not plan.est_modifiable:
        messages.error(
            request, "Un plan valide ou clos ne peut plus accueillir de nouvelle activite."
        )
        return redirect(plan.get_absolute_url())

    form = ActiviteForm(request.POST or None, plan=plan)
    if request.method == "POST" and form.is_valid():
        activite = form.save()
        messages.success(request, f"Activite {activite.code} inscrite au plan.")
        return redirect(plan.get_absolute_url())
    return render(request, "intranet/activite_form.html", {"form": form, "plan": plan})


@login_required
def activite_detail(request, pk):
    activite = get_object_or_404(
        Activite.objects.visibles_par(request.user).select_related(
            "plan__perimetre", "axe", "responsable", "structure"
        ),
        pk=pk,
    )
    return render(
        request,
        "intranet/activite_detail.html",
        {
            "activite": activite,
            "avancements": activite.avancements.select_related("auteur"),
            "indicateurs": activite.indicateurs.all(),
            "peut_rendre_compte": _peut_rendre_compte(request.user, activite)
            and activite.plan.est_en_execution
            and not activite.est_close,
            "peut_piloter": _peut_piloter(request.user, activite.perimetre),
            "form_report": ReportForm(),
        },
    )


@login_required
def activite_modifier(request, pk):
    activite = get_object_or_404(Activite.objects.visibles_par(request.user), pk=pk)
    if not _peut_piloter(request.user, activite.perimetre):
        messages.error(request, "Vous n'etes pas habilite a modifier cette activite.")
        return redirect(activite.get_absolute_url())

    form = ActiviteForm(request.POST or None, instance=activite, plan=activite.plan)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Activite mise a jour.")
        return redirect(activite.get_absolute_url())
    return render(
        request, "intranet/activite_form.html", {"form": form, "plan": activite.plan, "activite": activite}
    )


@login_required
def activite_avancement(request, pk):
    activite = get_object_or_404(Activite.objects.visibles_par(request.user), pk=pk)
    if not _peut_rendre_compte(request.user, activite):
        messages.error(request, "Vous n'etes pas habilite a rendre compte de cette activite.")
        return redirect(activite.get_absolute_url())

    form = AvancementForm(request.POST or None, request.FILES or None, activite=activite)
    if request.method == "POST" and form.is_valid():
        try:
            enregistrer_avancement(
                activite,
                request.user,
                form.cleaned_data["taux"],
                form.cleaned_data["realisations"],
                difficultes=form.cleaned_data.get("difficultes", ""),
                effectif_touche=form.cleaned_data.get("effectif_touche") or 0,
                montant_engage=form.cleaned_data.get("montant_engage") or 0,
                piece_jointe=form.cleaned_data.get("piece_jointe"),
                date=form.cleaned_data.get("date"),
            )
            messages.success(request, "Point d'avancement enregistre.")
            return redirect(activite.get_absolute_url())
        except ErreurPlan as erreur:
            messages.error(request, str(erreur))
    return render(
        request, "intranet/avancement_form.html", {"form": form, "activite": activite}
    )


@login_required
def activite_decision(request, pk, operation):
    """Report ou annulation d'une activite."""
    activite = get_object_or_404(Activite.objects.visibles_par(request.user), pk=pk)
    if request.method != "POST":
        return redirect(activite.get_absolute_url())
    if not _peut_piloter(request.user, activite.perimetre):
        messages.error(request, "Vous n'etes pas habilite a prendre cette decision.")
        return redirect(activite.get_absolute_url())

    form = ReportForm(request.POST)
    form.is_valid()
    motif = form.cleaned_data.get("motif", "")
    try:
        if operation == "reporter":
            reporter_activite(
                activite, request.user, motif,
                nouvelle_fin=form.cleaned_data.get("nouvelle_fin"), requete=request,
            )
            messages.warning(request, "Activite reportee.")
        elif operation == "annuler":
            annuler_activite(activite, request.user, motif, requete=request)
            messages.warning(request, "Activite annulee.")
        else:
            raise ErreurPlan("Operation inconnue.")
    except ErreurPlan as erreur:
        messages.error(request, str(erreur))
    return redirect(activite.get_absolute_url())


@login_required
def indicateur_creer(request, pk):
    activite = get_object_or_404(Activite.objects.visibles_par(request.user), pk=pk)
    if not _peut_rendre_compte(request.user, activite):
        messages.error(request, "Vous n'etes pas habilite a modifier les indicateurs.")
        return redirect(activite.get_absolute_url())

    form = IndicateurForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        indicateur = form.save(commit=False)
        indicateur.activite = activite
        indicateur.save()
        messages.success(request, "Indicateur enregistre.")
        return redirect(activite.get_absolute_url())
    return render(
        request, "intranet/indicateur_form.html", {"form": form, "activite": activite}
    )


# --- Export ------------------------------------------------------------------
@login_required
def export_activites(request):
    """Registre des activites au format CSV, dans le perimetre visible."""
    liste = (
        Activite.objects.visibles_par(request.user)
        .select_related("plan__perimetre", "axe", "responsable")
        .order_by("plan__annee", "plan__perimetre__code", "code")
    )
    if annee := request.GET.get("annee"):
        liste = liste.filter(plan__annee=annee)

    reponse = HttpResponse(content_type="text/csv; charset=utf-8")
    reponse["Content-Disposition"] = 'attachment; filename="activites-dpfc.csv"'
    reponse.write("﻿")
    ecrivain = csv.writer(reponse, delimiter=";")
    ecrivain.writerow([
        "Annee", "Perimetre", "Code", "Intitule", "Axe", "Type", "Responsable",
        "Debut prevu", "Fin prevue", "Statut", "Avancement (%)",
        "Budget prevu", "Budget execute", "Beneficiaires prevus", "Beneficiaires touches",
    ])
    for a in liste:
        ecrivain.writerow([
            a.plan.annee, a.plan.perimetre.code, a.code, a.intitule,
            a.axe.code if a.axe_id else "", a.get_type_display(),
            a.responsable.nom_complet if a.responsable_id else "",
            a.date_debut_prevue, a.date_fin_prevue, a.get_statut_display(), a.avancement,
            a.budget_prevu, a.budget_execute, a.effectif_prevu, a.effectif_realise,
        ])
    JournalAction.tracer(request.user, "Export du registre des activites", requete=request)
    return reponse


@login_required
def axes(request):
    """Referentiel des axes strategiques, en lecture."""
    return render(
        request,
        "intranet/axes.html",
        {"axes": Axe.objects.filter(actif=True), "perimetres": Perimetre.objects.actifs()},
    )

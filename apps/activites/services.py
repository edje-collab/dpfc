"""
Pilotage des plans d'action : cycle de vie, avancement, consolidation.

Le plan suit un cycle court — preparation, soumission, validation, cloture —
dont les regles dependent du perimetre : un perimetre deconcentre fait valider
son plan par la direction centrale, qui valide le sien elle-meme.
"""
from django.db import models, transaction
from django.utils import timezone

from apps.accounts.models import Notification
from apps.core.models import JournalAction, Perimetre

from .models import Activite, Avancement, PlanAction


class ErreurPlan(Exception):
    """Operation refusee sur un plan d'action."""


# --- Cycle de vie du plan ----------------------------------------------------
def valideur_du_plan(plan):
    """
    Qui valide le plan d'action d'un perimetre.

    Un perimetre deconcentre (antenne, CNRPN) soumet son plan au directeur ;
    la direction centrale valide le sien par son propre directeur.
    """
    centrale = Perimetre.centrale()
    if centrale is not None and centrale.responsable is not None:
        return centrale.responsable
    return plan.perimetre.responsable


@transaction.atomic
def soumettre_plan(plan, par=None, requete=None):
    """Transmet le plan a la validation. Un plan sans activite est refuse."""
    if plan.statut != PlanAction.Statut.BROUILLON:
        raise ErreurPlan("Seul un plan en preparation peut etre soumis.")
    if not plan.activites.exists():
        raise ErreurPlan("Inscrivez au moins une activite avant de soumettre le plan.")

    plan.statut = PlanAction.Statut.SOUMIS
    plan.soumis_le = timezone.now()
    plan.motif_rejet = ""
    plan.save(update_fields=["statut", "soumis_le", "motif_rejet", "modifie_le"])

    valideur = valideur_du_plan(plan)
    if valideur is not None and valideur.pk != getattr(par, "pk", None):
        _notifier(
            valideur,
            f"Plan d'action {plan.annee} a valider : {plan.perimetre.code}",
            f"{plan.perimetre.nom} a soumis son plan d'action "
            f"({plan.nb_activites} activite(s)).",
            plan.get_absolute_url(),
        )
    JournalAction.tracer(par, "Soumission d'un plan d'action", str(plan), requete=requete)
    return plan


@transaction.atomic
def valider_plan(plan, par, requete=None):
    """Valide le plan : les activites entrent en execution."""
    if plan.statut != PlanAction.Statut.SOUMIS:
        raise ErreurPlan("Seul un plan soumis peut etre valide.")

    plan.statut = PlanAction.Statut.VALIDE
    plan.valide_le = timezone.now()
    plan.valide_par = par
    plan.save(update_fields=["statut", "valide_le", "valide_par", "modifie_le"])

    responsable = plan.perimetre.responsable
    if responsable is not None and responsable.pk != par.pk:
        _notifier(
            responsable,
            f"Plan d'action {plan.annee} valide",
            f"Le plan d'action de {plan.perimetre.nom} est valide. Les activites peuvent demarrer.",
            plan.get_absolute_url(),
            Notification.Niveau.SUCCES,
        )
    JournalAction.tracer(par, "Validation d'un plan d'action", str(plan), requete=requete)
    return plan


@transaction.atomic
def renvoyer_plan(plan, par, motif, requete=None):
    """Renvoie le plan en preparation, avec le motif."""
    if plan.statut != PlanAction.Statut.SOUMIS:
        raise ErreurPlan("Seul un plan soumis peut etre renvoye.")
    if not motif.strip():
        raise ErreurPlan("Indiquez le motif du renvoi.")

    plan.statut = PlanAction.Statut.BROUILLON
    plan.motif_rejet = motif
    plan.soumis_le = None
    plan.save(update_fields=["statut", "motif_rejet", "soumis_le", "modifie_le"])

    responsable = plan.perimetre.responsable
    if responsable is not None and responsable.pk != par.pk:
        _notifier(
            responsable,
            f"Plan d'action {plan.annee} renvoye",
            f"Motif : {motif}",
            plan.get_absolute_url(),
            Notification.Niveau.ALERTE,
        )
    JournalAction.tracer(par, "Renvoi d'un plan d'action", str(plan), motif, requete)
    return plan


@transaction.atomic
def clore_plan(plan, par, requete=None):
    """
    Clot l'exercice.

    Les activites restees planifiees ou en cours sont reportees : un plan clos
    ne doit pas laisser d'activite dans un etat ouvert.
    """
    if plan.statut != PlanAction.Statut.VALIDE:
        raise ErreurPlan("Seul un plan valide peut etre clos.")

    reportees = plan.activites.filter(
        statut__in=[Activite.Statut.PLANIFIEE, Activite.Statut.EN_COURS]
    ).update(
        statut=Activite.Statut.REPORTEE,
        motif_report="Report automatique a la cloture de l'exercice.",
    )
    plan.statut = PlanAction.Statut.CLOS
    plan.clos_le = timezone.now()
    plan.save(update_fields=["statut", "clos_le", "modifie_le"])

    JournalAction.tracer(
        par, "Cloture d'un plan d'action", str(plan),
        f"{reportees} activite(s) reportee(s).", requete,
    )
    return plan, reportees


# --- Avancement des activites ------------------------------------------------
@transaction.atomic
def enregistrer_avancement(activite, auteur, taux, realisations, **extra):
    """
    Enregistre un point d'avancement et met l'activite a jour.

    L'avancement de l'activite suit toujours le dernier compte rendu ; les
    beneficiaires et les montants se cumulent.
    """
    if activite.plan.statut not in {PlanAction.Statut.VALIDE, PlanAction.Statut.SOUMIS}:
        raise ErreurPlan("Le plan doit etre valide pour rendre compte de son execution.")
    if activite.statut == Activite.Statut.ANNULEE:
        raise ErreurPlan("Cette activite est annulee.")
    if taux > 100:
        raise ErreurPlan("L'avancement ne peut depasser 100 %.")

    point = Avancement.objects.create(
        activite=activite,
        taux=taux,
        realisations=realisations,
        difficultes=extra.get("difficultes", ""),
        effectif_touche=extra.get("effectif_touche", 0),
        montant_engage=extra.get("montant_engage", 0),
        piece_jointe=extra.get("piece_jointe") or "",
        date=extra.get("date") or timezone.localdate(),
        auteur=auteur,
    )

    activite.avancement = taux
    activite.effectif_realise = (
        activite.avancements.aggregate(t=models.Sum("effectif_touche"))["t"] or 0
    )
    activite.budget_execute = (
        activite.avancements.aggregate(t=models.Sum("montant_engage"))["t"] or 0
    )
    if taux >= 100:
        activite.statut = Activite.Statut.REALISEE
        activite.date_fin_reelle = activite.date_fin_reelle or point.date
    elif taux > 0 and activite.statut == Activite.Statut.PLANIFIEE:
        activite.statut = Activite.Statut.EN_COURS
        activite.date_debut_reelle = activite.date_debut_reelle or point.date
    activite.save(
        update_fields=[
            "avancement", "effectif_realise", "budget_execute", "statut",
            "date_debut_reelle", "date_fin_reelle", "modifie_le",
        ]
    )
    return point


@transaction.atomic
def reporter_activite(activite, par, motif, nouvelle_fin=None, requete=None):
    """Reporte une activite, en consignant le motif."""
    if activite.est_close:
        raise ErreurPlan("Une activite realisee ou annulee ne peut etre reportee.")
    if not motif.strip():
        raise ErreurPlan("Indiquez le motif du report.")
    activite.statut = Activite.Statut.REPORTEE
    activite.motif_report = motif
    if nouvelle_fin:
        activite.date_fin_prevue = nouvelle_fin
    activite.save(update_fields=["statut", "motif_report", "date_fin_prevue", "modifie_le"])
    JournalAction.tracer(par, "Report d'une activite", str(activite), motif, requete)
    return activite


@transaction.atomic
def annuler_activite(activite, par, motif, requete=None):
    if activite.statut == Activite.Statut.REALISEE:
        raise ErreurPlan("Une activite realisee ne peut etre annulee.")
    if not motif.strip():
        raise ErreurPlan("Indiquez le motif de l'annulation.")
    activite.statut = Activite.Statut.ANNULEE
    activite.motif_report = motif
    activite.save(update_fields=["statut", "motif_report", "modifie_le"])
    JournalAction.tracer(par, "Annulation d'une activite", str(activite), motif, requete)
    return activite


# --- Consolidation -----------------------------------------------------------
def tableau_de_bord(agent, annee=None):
    """Synthese du pilotage, limitee au perimetre visible par l'agent."""
    annee = annee or timezone.localdate().year
    plans = PlanAction.objects.visibles_par(agent).filter(annee=annee).select_related("perimetre")
    activites = Activite.objects.visibles_par(agent).de_l_annee(annee)

    return {
        "annee": annee,
        "plans": plans,
        "nb_activites": activites.count(),
        "par_statut": {
            ligne["statut"]: ligne["n"]
            for ligne in activites.values("statut").annotate(n=models.Count("id"))
        },
        "en_retard": activites.en_retard().select_related("plan__perimetre", "responsable"),
        "taux_execution": round(
            activites.exclude(statut=Activite.Statut.ANNULEE).aggregate(
                m=models.Avg("avancement")
            )["m"] or 0
        ),
        "budget_prevu": activites.aggregate(t=models.Sum("budget_prevu"))["t"] or 0,
        "budget_execute": activites.aggregate(t=models.Sum("budget_execute"))["t"] or 0,
        "beneficiaires": activites.aggregate(t=models.Sum("effectif_realise"))["t"] or 0,
    }


def consolidation_nationale(annee=None):
    """Execution de chaque perimetre, pour la direction centrale."""
    annee = annee or timezone.localdate().year
    lignes = []
    for plan in (
        PlanAction.objects.filter(annee=annee)
        .select_related("perimetre")
        .order_by("perimetre__type", "perimetre__code")
    ):
        lignes.append(
            {
                "perimetre": plan.perimetre,
                "plan": plan,
                "statut": plan.get_statut_display(),
                "nb_activites": plan.nb_activites,
                "taux_execution": plan.taux_execution,
                "budget_prevu": plan.budget_prevu,
                "budget_execute": plan.budget_execute,
                "en_retard": plan.activites.en_retard().count(),
            }
        )
    return lignes


def chronogramme(plan):
    """
    Positionne les activites du plan sur les douze mois de l'exercice.

    Retourne, par activite, le mois de depart et le nombre de mois couverts,
    de quoi dessiner un diagramme sans calcul dans le gabarit.
    """
    lignes = []
    for activite in plan.activites.select_related("axe", "responsable").order_by("date_debut_prevue"):
        debut = max(1, activite.date_debut_prevue.month)
        fin = activite.date_fin_prevue.month if activite.date_fin_prevue.year == plan.annee else 12
        fin = max(debut, fin)
        lignes.append(
            {
                "activite": activite,
                "debut": debut,
                "duree": fin - debut + 1,
                "avant": debut - 1,
                "apres": 12 - fin,
            }
        )
    return lignes


def _notifier(destinataire, titre, message, lien="", niveau=Notification.Niveau.INFO):
    if destinataire is None:
        return
    Notification.objects.create(
        destinataire=destinataire, titre=titre, message=message, lien=lien, niveau=niveau
    )

"""
Instruction des actes administratifs : soumission, decisions, cloture.

Le trace du circuit n'est plus code ici : il est parametre dans l'application
`circuits`, par perimetre de gestion et par type d'acte (voir
apps/circuits/modeles.py pour les circuits livres par defaut). Ce module se
limite aux actions du workflow et a leurs effets de bord : numerotation,
notifications, soldes de conge, journal d'audit.
"""
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Notification
from apps.circuits.services import etapes_resolues
from apps.core.models import JournalAction

from .models import Demande, SoldeConge, TypeDemande, Validation

Agent = get_user_model()


def circuit_theorique(demande):
    """Liste ordonnee [(libelle, valideur)] sans l'enregistrer."""
    return etapes_resolues(demande)


# --- Actions du workflow -----------------------------------------------------
@transaction.atomic
def soumettre(demande, requete=None):
    """Genere le numero, construit le circuit et notifie le premier valideur."""
    if demande.statut != Demande.Statut.BROUILLON:
        return demande

    etapes = circuit_theorique(demande)
    if not etapes:
        raise ValueError(
            "Aucun valideur n'est configure pour votre perimetre. "
            "Contactez le service du personnel de la DPFC."
        )

    demande.validations.all().delete()
    for i, (libelle, valideur) in enumerate(etapes, start=1):
        Validation.objects.create(demande=demande, ordre=i, libelle=libelle, valideur=valideur)

    demande.attribuer_numero()
    demande.statut = Demande.Statut.SOUMISE
    demande.soumise_le = timezone.now()
    demande.save()

    premier = etapes[0][1]
    _notifier(
        premier,
        f"Nouvelle demande a valider : {demande.get_type_display()}",
        f"{demande.agent.nom_complet} a soumis la demande {demande.numero} "
        f"du {demande.date_debut:%d/%m/%Y} au {demande.date_fin:%d/%m/%Y}.",
        reverse("rh:demande_detail", args=[demande.pk]),
    )
    JournalAction.tracer(demande.agent, "Soumission d'une demande", demande.numero, requete=requete)
    return demande


@transaction.atomic
def decider(validation, favorable, commentaire="", requete=None):
    """Enregistre la decision d'un valideur et fait avancer le circuit."""
    demande = validation.demande
    validation.decision = (
        Validation.Decision.FAVORABLE if favorable else Validation.Decision.DEFAVORABLE
    )
    validation.commentaire = commentaire
    validation.decide_le = timezone.now()
    validation.save()

    if not favorable:
        demande.statut = Demande.Statut.REJETEE
        demande.motif_rejet = commentaire
        demande.cloturee_le = timezone.now()
        demande.save(update_fields=["statut", "motif_rejet", "cloturee_le", "modifie_le"])
        demande.validations.filter(decision=Validation.Decision.ATTENTE).update(
            decision=Validation.Decision.IGNOREE
        )
        _notifier(
            demande.agent,
            f"Demande {demande.numero} rejetee",
            f"Motif : {commentaire or 'non precise'}.",
            reverse("rh:demande_detail", args=[demande.pk]),
            Notification.Niveau.ALERTE,
        )
        JournalAction.tracer(validation.valideur, "Rejet d'une demande", demande.numero, commentaire, requete)
        return demande

    suivante = demande.etape_courante()
    if suivante:
        demande.statut = Demande.Statut.EN_COURS
        demande.save(update_fields=["statut", "modifie_le"])
        _notifier(
            suivante.valideur,
            f"Demande a valider : {demande.get_type_display()}",
            f"{demande.agent.nom_complet} - {demande.numero} ({suivante.libelle}).",
            reverse("rh:demande_detail", args=[demande.pk]),
        )
    else:
        approuver(demande, requete=requete)

    JournalAction.tracer(
        validation.valideur, "Avis favorable sur une demande", demande.numero, commentaire, requete
    )
    return demande


@transaction.atomic
def approuver(demande, requete=None):
    demande.statut = Demande.Statut.APPROUVEE
    demande.cloturee_le = timezone.now()
    demande.save(update_fields=["statut", "cloturee_le", "modifie_le"])

    if demande.regles.get("decompte_solde") and not demande.solde_impacte:
        solde = SoldeConge.pour(demande.agent, demande.date_debut.year)
        solde.jours_consommes = solde.jours_consommes + demande.nb_jours
        solde.save(update_fields=["jours_consommes"])
        Demande.objects.filter(pk=demande.pk).update(solde_impacte=True)

    if demande.type == TypeDemande.ORDRE_MISSION:
        Agent.objects.filter(pk=demande.agent_id).update(situation=Agent.Situation.EN_MISSION)
    elif demande.type in {TypeDemande.CONGE_ANNUEL, TypeDemande.CONGE_EXCEPTIONNEL}:
        Agent.objects.filter(pk=demande.agent_id).update(situation=Agent.Situation.EN_CONGE)

    _notifier(
        demande.agent,
        f"Demande {demande.numero} approuvee",
        f"Votre {demande.get_type_display().lower()} est accorde(e). "
        f"Le document officiel est disponible dans votre espace.",
        reverse("rh:demande_detail", args=[demande.pk]),
        Notification.Niveau.SUCCES,
    )
    if demande.interimaire_id:
        _notifier(
            demande.interimaire,
            "Interim a assurer",
            f"Vous assurez l'interim de {demande.agent.nom_complet} "
            f"du {demande.date_debut:%d/%m/%Y} au {demande.date_fin:%d/%m/%Y}.",
            reverse("rh:demande_detail", args=[demande.pk]),
        )
    JournalAction.tracer(demande.agent, "Approbation d'une demande", demande.numero, requete=requete)
    return demande


@transaction.atomic
def annuler(demande, par, requete=None):
    if demande.statut == Demande.Statut.APPROUVEE and demande.solde_impacte:
        solde = SoldeConge.pour(demande.agent, demande.date_debut.year)
        solde.jours_consommes = max(0, solde.jours_consommes - demande.nb_jours)
        solde.save(update_fields=["jours_consommes"])
        demande.solde_impacte = False
    demande.statut = Demande.Statut.ANNULEE
    demande.cloturee_le = timezone.now()
    demande.save(update_fields=["statut", "cloturee_le", "solde_impacte", "modifie_le"])
    demande.validations.filter(decision=Validation.Decision.ATTENTE).update(
        decision=Validation.Decision.IGNOREE
    )
    if par.pk != demande.agent_id:
        _notifier(
            demande.agent,
            f"Demande {demande.numero} annulee",
            f"Annulation effectuee par {par.nom_complet}.",
            reverse("rh:demande_detail", args=[demande.pk]),
            Notification.Niveau.ALERTE,
        )
    JournalAction.tracer(par, "Annulation d'une demande", demande.numero, requete=requete)
    return demande


def demandes_a_traiter(agent):
    """Demandes dont l'agent est le valideur de l'etape courante."""
    en_attente = Validation.objects.filter(
        valideur=agent, decision=Validation.Decision.ATTENTE
    ).values_list("demande_id", "ordre")
    ids = []
    for demande_id, ordre in en_attente:
        anterieures = Validation.objects.filter(
            demande_id=demande_id, ordre__lt=ordre, decision=Validation.Decision.ATTENTE
        ).exists()
        if not anterieures:
            ids.append(demande_id)
    return (
        Demande.objects.filter(pk__in=ids, statut__in=[Demande.Statut.SOUMISE, Demande.Statut.EN_COURS])
        .select_related("agent", "agent__structure", "structure")
        .order_by("date_debut")
    )


def _notifier(destinataire, titre, message, lien="", niveau=Notification.Niveau.INFO):
    Notification.envoyer(destinataire, titre, message, lien, niveau)
    if destinataire and destinataire.email:
        try:
            send_mail(
                subject=f"[Portail DPFC] {titre}",
                message=f"{message}\n\nConnectez-vous au portail : {lien}",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[destinataire.email],
                fail_silently=True,
            )
        except Exception:  # le workflow ne doit jamais echouer a cause du courriel
            pass

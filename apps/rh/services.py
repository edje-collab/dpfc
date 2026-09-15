"""
Circuit de validation des actes administratifs.

Deux regimes coexistent, conformement a l'organisation de la direction.

1. Antennes (APFC) : chaque antenne est autonome dans la gestion de son
   personnel. L'agent adresse sa demande directement au chef d'antenne, le
   depot etant assure par le secretariat de l'antenne. Une seule etape.

   Exception : une mission hors du perimetre de la DRENAET. L'agent joint les
   termes de reference et la lettre d'invitation ou d'information ; le chef
   d'antenne donne son avis, puis l'ordre de mission est etabli et signe par
   le DRENAET.

   Les actes du chef d'antenne lui-meme remontent au DRENAET puis, si le type
   d'acte l'exige, a la direction centrale.

2. Direction centrale : chef de service -> sous-directeur -> service du
   personnel -> directeur, les deux dernieres etapes n'etant ajoutees que si le
   type d'acte l'exige (voir REGLES_TYPE dans models.py).
"""
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.conf import settings
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Notification
from apps.core.models import JournalAction, Structure

from .models import Demande, SoldeConge, TypeDemande, Validation

Agent = get_user_model()


# --- Recherche des valideurs -------------------------------------------------
def _responsable_structure(structure):
    return structure.responsable if structure and structure.responsable_id else None


def _remonter_jusqu_a(structure, types):
    """Remonte la chaine des structures jusqu'a trouver un type donne."""
    noeud, garde = structure, 0
    while noeud is not None and garde < 10:
        if noeud.type in types:
            return noeud
        noeud = noeud.parent
        garde += 1
    return None


def _premier_role(role, region=None):
    qs = Agent.objects.filter(role=role, is_active=True)
    if region is not None:
        regional = qs.filter(structure__region=region).first()
        if regional:
            return regional
    return qs.order_by("last_name").first()


def _chef_antenne_de(structure):
    """Chef de l'antenne dont depend la structure."""
    antenne = _remonter_jusqu_a(structure, {Structure.Type.ANTENNE})
    if antenne is not None and antenne.responsable_id:
        return antenne.responsable
    region = getattr(structure, "region", None)
    return _premier_role(Agent.Role.CHEF_ANTENNE, region)


def _directeur_regional_de(structure):
    """Directeur de la DRENAET dans le perimetre de laquelle l'antenne exerce."""
    if structure is None:
        return None
    perimetre = structure.perimetre_drenaet
    if perimetre is not None and perimetre.responsable_id:
        return perimetre.responsable
    return _premier_role(Agent.Role.DIRECTEUR_REGIONAL, getattr(structure, "region", None))


def _circuit_antenne(demande):
    """Circuit applicable a un agent affecte en antenne regionale."""
    agent = demande.agent
    structure = agent.structure
    chef = _chef_antenne_de(structure)
    drenaet = _directeur_regional_de(structure)
    etapes = []

    # Mission hors perimetre DRENAET : avis du chef d'antenne puis etablissement
    # de l'ordre de mission par la direction regionale.
    if demande.est_mission_hors_perimetre:
        if chef:
            etapes.append(("Avis du chef d'antenne (APFC)", chef))
        if drenaet:
            etapes.append(("Etablissement de l'ordre de mission par le DRENAET", drenaet))
        elif not etapes:
            etapes.append(("Signature du directeur", _premier_role(Agent.Role.DIRECTEUR)))
        return etapes

    # Cas courant : l'antenne est autonome, le chef d'antenne decide seul.
    if chef and chef.pk != agent.pk:
        return [("Decision du chef d'antenne (APFC)", chef)]

    # L'agent est lui-meme chef d'antenne : son acte remonte au DRENAET,
    # puis a la direction centrale lorsque le type d'acte l'exige.
    if drenaet:
        etapes.append(("Avis du directeur regional (DRENAET)", drenaet))
    if demande.regles.get("signature_directeur"):
        directeur = _premier_role(Agent.Role.DIRECTEUR)
        if directeur:
            etapes.append(("Signature du directeur de la pedagogie", directeur))
    elif demande.regles.get("visa_rh"):
        rh = _premier_role(Agent.Role.RH)
        if rh:
            etapes.append(("Visa du service du personnel", rh))
    return etapes


def _circuit_central(demande):
    """Circuit applicable a un agent de la direction centrale."""
    agent = demande.agent
    structure = agent.structure
    regles = demande.regles
    etapes = []

    superieur = agent.superieur or _responsable_structure(structure)
    if superieur and superieur.pk != agent.pk:
        libelle = (
            "Avis du chef de service"
            if superieur.role == Agent.Role.CHEF_SERVICE
            else f"Avis du superieur hierarchique ({superieur.get_role_display().lower()})"
        )
        etapes.append((libelle, superieur))

    if structure is not None:
        sous_direction = _remonter_jusqu_a(
            structure.parent if structure.parent_id else None, {Structure.Type.SOUS_DIRECTION}
        )
        responsable = _responsable_structure(sous_direction)
        if responsable:
            etapes.append(("Avis du sous-directeur", responsable))

    if regles.get("visa_rh"):
        rh = _premier_role(Agent.Role.RH)
        if rh:
            etapes.append(("Visa du service du personnel", rh))

    if regles.get("signature_directeur"):
        directeur = _premier_role(Agent.Role.DIRECTEUR)
        if directeur:
            etapes.append(("Signature du directeur", directeur))
    return etapes


def circuit_theorique(demande):
    """Retourne la liste ordonnee [(libelle, valideur)] sans l'enregistrer."""
    agent = demande.agent
    en_region = agent.structure_id and agent.structure.rattachement == Structure.Rattachement.REGION
    etapes = _circuit_antenne(demande) if en_region else _circuit_central(demande)

    # Deduplication : un meme agent ne valide qu'une fois, et jamais sa propre demande
    vus, finales = set(), []
    for libelle, valideur in etapes:
        if valideur is None or valideur.pk == agent.pk or valideur.pk in vus:
            continue
        vus.add(valideur.pk)
        finales.append((libelle, valideur))

    if not finales:
        secours = (
            _directeur_regional_de(agent.structure) if en_region else None
        ) or _premier_role(Agent.Role.RH) or _premier_role(Agent.Role.DIRECTEUR)
        if secours and secours.pk != agent.pk:
            libelle = (
                "Etablissement par le DRENAET" if en_region else "Visa du service du personnel"
            )
            finales = [(libelle, secours)]
    return finales


# --- Actions du workflow -----------------------------------------------------
@transaction.atomic
def soumettre(demande, requete=None):
    """Genere le numero, construit le circuit et notifie le premier valideur."""
    if demande.statut != Demande.Statut.BROUILLON:
        return demande

    etapes = circuit_theorique(demande)
    if not etapes:
        raise ValueError(
            "Aucun valideur n'est configure pour votre structure. "
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

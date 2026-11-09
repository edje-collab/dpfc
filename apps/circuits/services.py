"""
Resolution des circuits : d'une definition parametree aux valideurs reels.

`etapes_resolues(demande)` est le seul point d'entree utilise par les
applications metier. Il ne connait de la demande que quelques attributs
(`agent`, `regles`, `est_mission_hors_perimetre`), ce qui laisse le socle
independant des applications metier.
"""
from django.contrib.auth import get_user_model

from apps.core.models import Structure

from .models import Circuit, Condition, Designation

Agent = get_user_model()


# --- Recherche des agents ----------------------------------------------------
def _actif(agent):
    """Un agent desactive (mute, retraite) ne peut pas valider."""
    return agent if agent is not None and agent.is_active else None


def _premier_role(role, region=None):
    qs = Agent.objects.filter(role=role, is_active=True)
    if region is not None:
        regional = qs.filter(structure__region=region).first()
        if regional is not None:
            return regional
    return qs.order_by("last_name").first()


def _remonter_jusqu_a(structure, types):
    """Remonte la chaine des structures jusqu'a trouver un type donne."""
    noeud, garde = structure, 0
    while noeud is not None and garde < 10:
        if noeud.type in types:
            return noeud
        noeud = noeud.parent
        garde += 1
    return None


def _responsable_perimetre(agent):
    perimetre = agent.perimetre
    return _actif(perimetre.responsable) if perimetre is not None else None


def _responsable_structure(agent):
    """
    Responsable de la structure de l'agent, et lui seul.

    On ne remonte pas au parent : l'etape suivante du circuit s'en charge, dans
    l'ordre hierarchique voulu. Remonter ici ferait intervenir le directeur
    avant le visa du service du personnel.
    """
    structure = agent.structure
    if structure is None or not structure.responsable_id or structure.responsable_id == agent.pk:
        return None
    return _actif(structure.responsable)


def _responsable_sous_direction(agent):
    structure = agent.structure
    if structure is None:
        return None
    depart = structure.parent if structure.parent_id else structure
    sous_direction = _remonter_jusqu_a(depart, {Structure.Type.SOUS_DIRECTION})
    if sous_direction is not None and sous_direction.responsable_id:
        return _actif(sous_direction.responsable)
    return None


def _directeur_regional(agent):
    structure = agent.structure
    if structure is None:
        return None
    ressort = structure.perimetre_drena
    if ressort is not None and ressort.responsable_id:
        trouve = _actif(ressort.responsable)
        if trouve is not None:
            return trouve
    return _premier_role(Agent.Role.DIRECTEUR_REGIONAL, getattr(structure, "region", None))


RESOLVEURS = {
    Designation.SUPERIEUR: lambda agent, etape: _actif(agent.superieur) or _responsable_structure(agent),
    Designation.RESPONSABLE_STRUCTURE: lambda agent, etape: _responsable_structure(agent),
    Designation.RESPONSABLE_SOUS_DIRECTION: lambda agent, etape: _responsable_sous_direction(agent),
    Designation.RESPONSABLE_PERIMETRE: lambda agent, etape: _responsable_perimetre(agent),
    Designation.DIRECTEUR_REGIONAL: lambda agent, etape: _directeur_regional(agent),
    Designation.ROLE: lambda agent, etape: _premier_role(
        etape.role, getattr(agent.structure, "region", None) if agent.structure_id else None
    ),
}


def _montant(demande):
    """
    Montant porte par l'objet, ou zero.

    Les actes administratifs n'en portent pas ; les expressions de besoin si.
    Le moteur reste ainsi ignorant de ce qu'il fait circuler.
    """
    return getattr(demande, "montant_circuit", 0) or 0


# --- Evaluation des conditions ----------------------------------------------
def _condition_remplie(condition, demande):
    agent = demande.agent
    regles = demande.regles
    if condition == Condition.SI_VISA_RH:
        return bool(regles.get("visa_rh"))
    if condition == Condition.SI_SIGNATURE_DIRECTEUR:
        return bool(regles.get("signature_directeur"))
    if condition == Condition.SI_SANS_SIGNATURE_DIRECTEUR:
        return not regles.get("signature_directeur")
    if condition == Condition.SI_HORS_PERIMETRE:
        return bool(demande.est_mission_hors_perimetre)
    if condition == Condition.SI_DANS_PERIMETRE:
        return not demande.est_mission_hors_perimetre
    if condition == Condition.SI_AGENT_EST_RESPONSABLE:
        return agent.dirige_son_perimetre
    if condition == Condition.SI_AGENT_NEST_PAS_RESPONSABLE:
        return not agent.dirige_son_perimetre
    return True


# --- Point d'entree ----------------------------------------------------------
def circuit_applicable(demande):
    """Circuit parametre qui s'applique a la demande, ou None."""
    return Circuit.objects.pour(demande.agent.perimetre, demande.type)


def etapes_resolues(demande):
    """
    Liste ordonnee [(libelle, valideur)] pour la demande.

    Un meme agent ne valide qu'une fois et ne valide jamais sa propre demande.
    """
    circuit = circuit_applicable(demande)
    if circuit is None:
        return []

    agent = demande.agent
    vus, resultat = set(), []
    for etape in circuit.etapes.all():
        if etape.seuil_montant and _montant(demande) < etape.seuil_montant:
            continue
        if not all(_condition_remplie(c, demande) for c in etape.conditions or []):
            continue
        resolveur = RESOLVEURS.get(etape.designation)
        valideur = resolveur(agent, etape) if resolveur else None
        if valideur is None:
            if etape.facultative:
                continue
            raise ValueError(
                f"Aucun agent ne peut assurer l'etape « {etape.libelle} » "
                f"du circuit {circuit}. Completez l'organigramme ou le circuit."
            )
        if valideur.pk == agent.pk or valideur.pk in vus:
            continue
        vus.add(valideur.pk)
        resultat.append((etape.libelle, valideur))
    return resultat

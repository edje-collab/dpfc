"""
Emargement, etats de paiement et attestations.

L'emargement par lot est le coeur du dispositif : l'application mobile scanne
hors ligne, met en file, puis envoie tout d'un coup des que le reseau revient.
Le serveur doit donc accepter d'etre appele plusieurs fois avec les memes
elements sans rien dupliquer ni rien perdre.
"""
import uuid

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.core.models import JournalAction

from .models import (
    Atelier,
    DoublonEmargement,
    Emargement,
    Participant,
    Session,
)
from .qr import lire


class ErreurAtelier(Exception):
    """Operation refusee sur un atelier, un participant ou un emargement."""


# --- Lecture d'un jeton ------------------------------------------------------
def participant_du_jeton(atelier, valeur):
    """
    Participant designe par un jeton de presence, ou None.

    Un jeton d'un autre atelier, altere ou mal forme est rejete sans
    distinction : le controleur voit « jeton invalide », rien de plus.
    """
    id_court = lire(valeur, atelier.cle, atelier.id_court)
    if id_court is None:
        return None
    return atelier.participants.filter(id_court=id_court).first()


# --- Emargement --------------------------------------------------------------
@transaction.atomic
def enregistrer_emargement(
    session, participant, par, identifiant=None, horodatage=None,
    mode=Emargement.Mode.SCAN, appareil="", motif="",
):
    """
    Enregistre une presence.

    Retourne le couple (emargement, cree). `cree` vaut faux lorsque la presence
    etait deja constatee : le second envoi est alors journalise comme doublon
    plutot que rejete en silence.
    """
    atelier = session.atelier
    if not atelier.accepte_emargement:
        raise ErreurAtelier("Cet atelier est clos : l'emargement n'est plus possible.")
    if participant.atelier_id != atelier.pk:
        raise ErreurAtelier("Ce participant n'est pas inscrit a cet atelier.")
    if not participant.est_actif:
        raise ErreurAtelier("Ce participant a ete revoque.")
    if mode == Emargement.Mode.MANUEL and not motif.strip():
        raise ErreurAtelier("Un emargement manuel doit etre motive.")

    horodatage = horodatage or timezone.now()
    existant = Emargement.objects.filter(participant=participant, session=session).first()
    if existant is not None:
        # Renvoi du meme emargement apres une coupure : rien a faire.
        if identifiant is not None and str(existant.pk) == str(identifiant):
            return existant, False
        DoublonEmargement.objects.get_or_create(
            id=identifiant or uuid.uuid4(),
            defaults={
                "participant": participant, "session": session,
                "horodatage": horodatage, "appareil": appareil, "saisi_par": par,
            },
        )
        return existant, False

    donnees = {
        "participant": participant, "session": session, "horodatage": horodatage,
        "mode": mode, "appareil": appareil, "motif": motif, "saisi_par": par,
    }
    if identifiant is not None:
        donnees["id"] = identifiant
    try:
        with transaction.atomic():
            return Emargement.objects.create(**donnees), True
    except IntegrityError:
        # Deux appareils ont scanne le meme participant au meme instant :
        # le premier arrive gagne, le second devient un doublon.
        existant = Emargement.objects.filter(participant=participant, session=session).first()
        if existant is None:
            raise
        return existant, False


@transaction.atomic
def enregistrer_lot(atelier, session, par, lignes, appareil=""):
    """
    Enregistre un lot d'emargements remontes par un appareil.

    Chaque ligne porte `jeton` ou `participant`, un `identifiant` (UUID produit
    par l'appareil) et un `horodatage`. Le traitement est idempotent : renvoyer
    le meme lot ne cree rien de plus.

    Retourne un compte rendu detaille, pour que le terrain sache exactement ce
    qui a ete retenu et ce qui a ete ecarte.
    """
    if not atelier.accepte_emargement:
        raise ErreurAtelier("Cet atelier est clos : l'emargement n'est plus possible.")
    if session.atelier_id != atelier.pk:
        raise ErreurAtelier("Cette session n'appartient pas a cet atelier.")

    resultat = {"enregistres": 0, "doublons": 0, "invalides": 0, "details": []}
    for ligne in lignes:
        participant = ligne.get("participant")
        if participant is None and ligne.get("jeton"):
            participant = participant_du_jeton(atelier, ligne["jeton"])
        if participant is None or not participant.est_actif:
            resultat["invalides"] += 1
            resultat["details"].append({"jeton": ligne.get("jeton", ""), "etat": "invalide"})
            continue
        try:
            _, cree = enregistrer_emargement(
                session, participant, par,
                identifiant=ligne.get("identifiant"),
                horodatage=ligne.get("horodatage"),
                mode=ligne.get("mode", Emargement.Mode.SCAN),
                appareil=ligne.get("appareil", appareil),
                motif=ligne.get("motif", ""),
            )
        except ErreurAtelier:
            resultat["invalides"] += 1
            resultat["details"].append(
                {"participant": participant.nom_complet, "etat": "refuse"}
            )
            continue
        if cree:
            resultat["enregistres"] += 1
        else:
            resultat["doublons"] += 1
        resultat["details"].append(
            {
                "participant": participant.nom_complet,
                "etat": "enregistre" if cree else "deja emarge",
            }
        )

    JournalAction.tracer(
        par, "Emargement par lot", f"{atelier.intitule} - {session}",
        f"{resultat['enregistres']} enregistre(s), {resultat['doublons']} doublon(s), "
        f"{resultat['invalides']} invalide(s).",
    )
    return resultat


@transaction.atomic
def annuler_emargement(emargement, par, motif):
    """Retire une presence constatee a tort, en consignant le motif."""
    if not motif.strip():
        raise ErreurAtelier("Indiquez le motif de l'annulation.")
    JournalAction.tracer(
        par, "Annulation d'un emargement",
        f"{emargement.participant} - {emargement.session}", motif,
    )
    emargement.delete()


# --- Etat de paiement --------------------------------------------------------
def etat_de_paiement(atelier):
    """
    Etat de paiement de l'atelier.

    Il ne retient que les participants ayant effectivement emarge : nul n'est
    paye pour une presence non constatee. Le montant suit le barème de la
    categorie, au prorata des journees constatees.
    """
    lignes = []
    participants = (
        atelier.participants.exclude(statut=Participant.Statut.REVOQUE)
        .select_related("categorie")
        .prefetch_related("emargements__session")
        .order_by("nom", "prenoms")
    )
    for participant in participants:
        jours = participant.jours_de_presence
        if not jours:
            continue
        montant_jour = participant.categorie.montant_journalier if participant.categorie_id else 0
        lignes.append(
            {
                "participant": participant,
                "categorie": participant.categorie.libelle if participant.categorie_id else "-",
                "jours": jours,
                "montant_journalier": montant_jour,
                "montant": round(float(montant_jour) * jours),
            }
        )
    return {
        "lignes": lignes,
        "total": sum(ligne["montant"] for ligne in lignes),
        "nb_payes": len(lignes),
        "nb_absents": atelier.nb_participants - len(lignes),
    }


def feuille_de_presence(atelier):
    """
    Grille de presence : une ligne par participant, une colonne par session.

    Elle sert a la fois a l'ecran de suivi et a l'impression de la feuille
    d'emargement.
    """
    sessions = list(atelier.sessions.all())
    emarges = {
        (e.participant_id, e.session_id): e
        for e in Emargement.objects.filter(session__atelier=atelier).select_related("session")
    }
    lignes = []
    for participant in atelier.participants.exclude(
        statut=Participant.Statut.REVOQUE
    ).order_by("nom", "prenoms"):
        presences = [emarges.get((participant.pk, s.pk)) for s in sessions]
        lignes.append(
            {
                "participant": participant,
                "presences": presences,
                "nb_presences": sum(1 for p in presences if p is not None),
            }
        )
    return {"sessions": sessions, "lignes": lignes}


# --- Attestations ------------------------------------------------------------
def peut_recevoir_attestation(participant):
    """
    Une attestation ne se delivre qu'a qui a reellement participe.

    La regle : avoir emarge au moins la moitie des sessions de l'atelier.
    """
    total_sessions = participant.atelier.sessions.count()
    if not total_sessions:
        return False
    return participant.nb_sessions_emargees * 2 >= total_sessions


def donnees_attestation(participant):
    """Elements de l'attestation, ou None si le participant n'y a pas droit."""
    if not peut_recevoir_attestation(participant):
        return None
    atelier = participant.atelier
    return {
        "participant": participant,
        "atelier": atelier,
        "jours": participant.jours_de_presence,
        "sessions_emargees": participant.nb_sessions_emargees,
        "sessions_total": atelier.sessions.count(),
        "delivree_le": timezone.localdate(),
        "signataire": atelier.perimetre.responsable,
        "qualite": atelier.perimetre.libelle_responsable,
    }


# --- Cycle de vie ------------------------------------------------------------
@transaction.atomic
def ouvrir(atelier, par, requete=None):
    if atelier.statut != Atelier.Statut.PLANIFIE:
        raise ErreurAtelier("Seul un atelier planifie peut etre ouvert.")
    if not atelier.sessions.exists():
        raise ErreurAtelier("Definissez au moins une session avant d'ouvrir l'atelier.")
    atelier.statut = Atelier.Statut.EN_COURS
    atelier.save(update_fields=["statut", "modifie_le"])
    JournalAction.tracer(par, "Ouverture d'un atelier", atelier.intitule, requete=requete)
    return atelier


@transaction.atomic
def clore(atelier, par, requete=None):
    """
    Clot l'atelier et reporte sa realisation sur le plan d'action.

    Si l'atelier est rattache a une activite, le nombre de beneficiaires
    constate y est verse : le pilotage se nourrit du terrain.
    """
    if atelier.statut not in {Atelier.Statut.PLANIFIE, Atelier.Statut.EN_COURS}:
        raise ErreurAtelier("Cet atelier est deja clos ou annule.")

    atelier.statut = Atelier.Statut.CLOS
    atelier.save(update_fields=["statut", "modifie_le"])

    # L'atelier rattache a une activite y verse ses presences constatees :
    # le pilotage se nourrit de ce qui a ete fait sur le terrain.
    rapporte = False
    if atelier.activite_id is not None:
        from apps.activites.models import Activite

        activite = atelier.activite
        Activite.objects.filter(pk=activite.pk).update(
            effectif_realise=(activite.effectif_realise or 0) + atelier.nb_emarges
        )
        rapporte = True

    JournalAction.tracer(
        par, "Cloture d'un atelier", atelier.intitule,
        f"{atelier.nb_emarges} participant(s) ayant emarge.", requete,
    )
    return atelier, rapporte


@transaction.atomic
def annuler(atelier, par, motif, requete=None):
    if atelier.statut == Atelier.Statut.ANNULE:
        raise ErreurAtelier("Cet atelier est deja annule.")
    if not motif.strip():
        raise ErreurAtelier("Indiquez le motif de l'annulation.")
    atelier.statut = Atelier.Statut.ANNULE
    atelier.motif_annulation = motif
    atelier.save(update_fields=["statut", "motif_annulation", "modifie_le"])
    JournalAction.tracer(par, "Annulation d'un atelier", atelier.intitule, motif, requete)
    return atelier


@transaction.atomic
def generer_sessions(atelier, creneaux_par_jour=1):
    """
    Cree les sessions de l'atelier, de sa date de debut a sa date de fin.

    Un creneau par jour produit des journees ; deux produisent une matinee et
    une apres-midi, ce qui permet de constater les presences partielles.
    """
    from datetime import timedelta

    creees = []
    jour = atelier.date_debut
    while jour <= atelier.date_fin:
        creneaux = (
            [Session.Creneau.JOURNEE]
            if creneaux_par_jour == 1
            else [Session.Creneau.MATIN, Session.Creneau.APRES_MIDI]
        )
        for creneau in creneaux:
            session, cree = Session.objects.get_or_create(
                atelier=atelier, date=jour, creneau=creneau
            )
            if cree:
                creees.append(session)
        jour += timedelta(days=1)
    return creees


# --- Consolidation -----------------------------------------------------------
def tableau_ateliers(agent):
    """Synthese des ateliers visibles par l'agent."""
    ateliers = Atelier.objects.visibles_par(agent).select_related("perimetre")
    return {
        "nb_ateliers": ateliers.count(),
        "nb_a_venir": ateliers.a_venir().count(),
        "nb_en_cours": ateliers.filter(statut=Atelier.Statut.EN_COURS).count(),
        "prochains": ateliers.a_venir().order_by("date_debut")[:5],
        "en_cours": ateliers.filter(statut=Atelier.Statut.EN_COURS)[:5],
        "mes_controles": Atelier.objects.filter(
            controleurs=agent, statut=Atelier.Statut.EN_COURS
        ),
    }

"""
Traitement du courrier et des documents.

Le parapheur reutilise le moteur de circuits : `PieceParapheur` expose la meme
interface qu'une demande administrative, de sorte que `circuits.services` n'a
pas a connaitre le courrier.
"""
from django.db import models, transaction
from django.utils import timezone

from apps.accounts.models import Notification
from apps.circuits.services import etapes_resolues
from apps.core.models import JournalAction

from .extraction import extraire_texte
from .models import Courrier, Document, Imputation, PieceParapheur, VersionDocument, Visa


class ErreurCourrier(Exception):
    """Operation refusee sur un courrier, un document ou une piece."""


# --- Courrier ----------------------------------------------------------------
@transaction.atomic
def imputer(courrier, par, affectations, requete=None):
    """
    Impute un courrier arrive a un ou plusieurs agents.

    `affectations` : liste de dictionnaires {destinataire, instructions, delai,
    structure, pour_information}. Une imputation pour information est close des
    sa creation : elle n'appelle pas de suite.
    """
    if not courrier.est_arrive:
        raise ErreurCourrier("Seul un courrier arrive peut etre impute.")
    if courrier.est_clos:
        raise ErreurCourrier("Ce courrier est clos.")
    if not affectations:
        raise ErreurCourrier("Indiquez au moins un destinataire.")

    creees = []
    for affectation in affectations:
        destinataire = affectation["destinataire"]
        if courrier.imputations.filter(destinataire=destinataire).exists():
            continue
        imputation = Imputation.objects.create(
            courrier=courrier,
            destinataire=destinataire,
            structure=affectation.get("structure") or destinataire.structure,
            instructions=affectation["instructions"],
            delai=affectation["delai"],
            pour_information=affectation.get("pour_information", False),
            impute_par=par,
        )
        if imputation.pour_information:
            imputation.traite_le = timezone.now()
            imputation.compte_rendu = "Imputation pour information."
            imputation.save(update_fields=["traite_le", "compte_rendu"])
        creees.append(imputation)
        _notifier(
            destinataire,
            f"Courrier impute : {courrier.numero}",
            f"{courrier.objet} — a traiter avant le {imputation.delai:%d/%m/%Y}."
            if not imputation.pour_information
            else f"{courrier.objet} — pour information.",
            courrier.get_absolute_url(),
        )

    if not creees:
        raise ErreurCourrier("Ces agents sont deja imputataires de ce courrier.")

    courrier.statut = Courrier.Statut.IMPUTE
    courrier.save(update_fields=["statut", "modifie_le"])
    _recalculer_statut(courrier)
    JournalAction.tracer(par, "Imputation d'un courrier", courrier.numero, requete=requete)
    return creees


@transaction.atomic
def traiter_imputation(imputation, par, compte_rendu, requete=None):
    """Enregistre la suite donnee par l'imputataire."""
    if imputation.est_traitee:
        raise ErreurCourrier("Cette imputation est deja traitee.")
    if imputation.destinataire_id != par.pk and not (par.est_direction or par.peut_administrer):
        raise ErreurCourrier("Seul l'imputataire peut rendre compte de son imputation.")
    if not compte_rendu.strip():
        raise ErreurCourrier("Indiquez la suite donnee au courrier.")

    imputation.compte_rendu = compte_rendu
    imputation.traite_le = timezone.now()
    imputation.save(update_fields=["compte_rendu", "traite_le", "modifie_le"])

    courrier = imputation.courrier
    _recalculer_statut(courrier)
    if imputation.impute_par_id and imputation.impute_par_id != par.pk:
        _notifier(
            imputation.impute_par,
            f"Suite donnee au courrier {courrier.numero}",
            f"{par.nom_complet} a rendu compte de son imputation.",
            courrier.get_absolute_url(),
            Notification.Niveau.SUCCES,
        )
    JournalAction.tracer(par, "Traitement d'une imputation", courrier.numero, requete=requete)
    return imputation


def _recalculer_statut(courrier):
    """Un courrier est traite lorsque toutes ses imputations le sont."""
    if courrier.statut == Courrier.Statut.CLASSE:
        return courrier
    imputations = courrier.imputations.all()
    if not imputations:
        nouveau = Courrier.Statut.ENREGISTRE
    elif imputations.filter(traite_le__isnull=True).exists():
        nouveau = Courrier.Statut.IMPUTE
    else:
        nouveau = Courrier.Statut.TRAITE
    if nouveau != courrier.statut:
        courrier.statut = nouveau
        courrier.save(update_fields=["statut", "modifie_le"])
    return courrier


@transaction.atomic
def classer(courrier, par, motif, requete=None):
    """Classe un courrier sans suite, en consignant le motif."""
    if courrier.statut == Courrier.Statut.CLASSE:
        raise ErreurCourrier("Ce courrier est deja classe.")
    if not motif.strip():
        raise ErreurCourrier("Indiquez le motif du classement.")
    courrier.statut = Courrier.Statut.CLASSE
    courrier.motif_classement = motif
    courrier.classe_le = timezone.now()
    courrier.save(update_fields=["statut", "motif_classement", "classe_le", "modifie_le"])
    JournalAction.tracer(par, "Classement d'un courrier", courrier.numero, motif, requete)
    return courrier


# --- Documents ---------------------------------------------------------------
@transaction.atomic
def deposer_version(document, fichier, par, commentaire="", indexer=True):
    """
    Ajoute une version au document et met a jour son index de recherche.

    L'extraction du texte ne bloque jamais le depot : un document illisible est
    enregistre sans texte, donc simplement absent de la recherche plein texte.
    """
    version = VersionDocument(
        document=document, fichier=fichier, commentaire=commentaire, deposee_par=par
    )
    version.save()

    if indexer:
        indexer_document(document, version)
    return version


def indexer_document(document, version=None, ocr=False):
    """Extrait le texte de la version courante et le stocke sur le document."""
    version = version or document.version_courante
    if version is None or not version.fichier:
        return ""
    try:
        version.fichier.open("rb")
        contenu = version.fichier.read()
    except Exception:
        return ""
    finally:
        try:
            version.fichier.close()
        except Exception:
            pass

    texte = extraire_texte(version.fichier.name, contenu, ocr=ocr)
    Document.objects.filter(pk=document.pk).update(
        texte_extrait=texte, indexe_le=timezone.now()
    )
    document.texte_extrait = texte
    return texte


def rechercher_documents(agent, requete, **filtres):
    """
    Recherche plein texte dans le perimetre visible par l'agent.

    PostgreSQL utilise son moteur de recherche francais ; les autres bases
    retombent sur une recherche par sous-chaine, suffisante en developpement.
    """
    qs = Document.objects.visibles_par(agent).select_related("perimetre", "deposant")
    if type_document := filtres.get("type_document"):
        qs = qs.filter(type_document=type_document)
    if annee := filtres.get("annee"):
        qs = qs.filter(annee=annee)
    if perimetre := filtres.get("perimetre"):
        qs = qs.filter(perimetre__code=perimetre)

    requete = (requete or "").strip()
    if not requete:
        return qs.order_by("-annee", "titre")

    from django.db import connection

    if connection.vendor == "postgresql":
        from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector

        vecteur = SearchVector("titre", weight="A", config="french") + SearchVector(
            "description", "texte_extrait", weight="B", config="french"
        )
        recherche = SearchQuery(requete, config="french")
        return (
            qs.annotate(rang=SearchRank(vecteur, recherche))
            .filter(rang__gt=0)
            .order_by("-rang", "-annee")
        )

    return qs.filter(
        models.Q(titre__icontains=requete)
        | models.Q(description__icontains=requete)
        | models.Q(texte_extrait__icontains=requete)
    ).order_by("-annee", "titre")


# --- Parapheur ---------------------------------------------------------------
@transaction.atomic
def soumettre_au_parapheur(piece, requete=None):
    """Construit le circuit des visas et notifie le premier viseur."""
    if piece.statut != PieceParapheur.Statut.BROUILLON:
        raise ErreurCourrier("Cette piece est deja au parapheur.")

    etapes = etapes_resolues(piece)
    if not etapes:
        raise ErreurCourrier(
            "Aucun viseur n'est configure pour votre perimetre. "
            "Completez le circuit « PARAPHEUR » dans l'administration."
        )

    piece.visas.all().delete()
    for ordre, (libelle, viseur) in enumerate(etapes, start=1):
        Visa.objects.create(piece=piece, ordre=ordre, libelle=libelle, viseur=viseur)

    piece.statut = PieceParapheur.Statut.EN_CIRCUIT
    piece.soumise_le = timezone.now()
    piece.motif_rejet = ""
    piece.save(update_fields=["statut", "soumise_le", "motif_rejet", "modifie_le"])

    _notifier(
        etapes[0][1],
        f"Piece a viser : {piece.objet}",
        f"{piece.demandeur.nom_complet} soumet une piece a votre visa.",
        piece.get_absolute_url(),
    )
    JournalAction.tracer(piece.demandeur, "Depot au parapheur", piece.objet, requete=requete)
    return piece


@transaction.atomic
def viser(visa, favorable, observation="", requete=None):
    """Enregistre un visa et fait avancer le parapheur."""
    piece = visa.piece
    if visa.decision != Visa.Decision.ATTENTE:
        raise ErreurCourrier("Ce visa est deja donne.")

    visa.decision = Visa.Decision.VISE if favorable else Visa.Decision.REFUSE
    visa.observation = observation
    visa.decide_le = timezone.now()
    visa.save(update_fields=["decision", "observation", "decide_le"])

    if not favorable:
        piece.statut = PieceParapheur.Statut.REJETEE
        piece.motif_rejet = observation
        piece.close_le = timezone.now()
        piece.save(update_fields=["statut", "motif_rejet", "close_le", "modifie_le"])
        piece.visas.filter(decision=Visa.Decision.ATTENTE).update(decision=Visa.Decision.IGNORE)
        _notifier(
            piece.demandeur,
            f"Piece refusee : {piece.objet}",
            f"Motif : {observation or 'non precise'}.",
            piece.get_absolute_url(),
            Notification.Niveau.ALERTE,
        )
        JournalAction.tracer(visa.viseur, "Refus au parapheur", piece.objet, observation, requete)
        return piece

    suivante = piece.etape_courante()
    if suivante is not None:
        _notifier(
            suivante.viseur,
            f"Piece a viser : {piece.objet}",
            f"{piece.demandeur.nom_complet} — {suivante.libelle}.",
            piece.get_absolute_url(),
        )
    else:
        piece.statut = PieceParapheur.Statut.VISEE
        piece.close_le = timezone.now()
        piece.save(update_fields=["statut", "close_le", "modifie_le"])
        _notifier(
            piece.demandeur,
            f"Piece visee : {piece.objet}",
            "Tous les visas sont recueillis.",
            piece.get_absolute_url(),
            Notification.Niveau.SUCCES,
        )
    JournalAction.tracer(visa.viseur, "Visa au parapheur", piece.objet, observation, requete)
    return piece


def pieces_a_viser(agent):
    """Pieces dont l'agent doit donner le visa a l'etape courante."""
    en_attente = Visa.objects.filter(
        viseur=agent, decision=Visa.Decision.ATTENTE,
        piece__statut=PieceParapheur.Statut.EN_CIRCUIT,
    ).select_related("piece__demandeur", "piece__document")
    return [
        visa for visa in en_attente
        if (courante := visa.piece.etape_courante()) is not None and courante.pk == visa.pk
    ]


# --- Consolidation -----------------------------------------------------------
def tableau_courrier(agent):
    """Synthese du courrier, limitee au perimetre visible par l'agent."""
    courriers = Courrier.objects.visibles_par(agent)
    mes_imputations = Imputation.objects.filter(
        destinataire=agent, traite_le__isnull=True
    ).select_related("courrier")
    return {
        "nb_arrivees": courriers.filter(sens=Courrier.Sens.ARRIVEE).count(),
        "nb_departs": courriers.filter(sens=Courrier.Sens.DEPART).count(),
        "nb_a_imputer": courriers.filter(
            sens=Courrier.Sens.ARRIVEE, statut=Courrier.Statut.ENREGISTRE
        ).count(),
        "nb_en_retard": courriers.en_retard().count(),
        "mes_imputations": mes_imputations,
        "nb_mes_imputations": mes_imputations.count(),
        "recents": courriers.select_related("perimetre")[:8],
    }


def _notifier(destinataire, titre, message, lien="", niveau=Notification.Niveau.INFO):
    if destinataire is None:
        return
    Notification.objects.create(
        destinataire=destinataire, titre=titre, message=message, lien=lien, niveau=niveau
    )

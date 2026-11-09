"""
Instruction des achats et tenue du magasin.

La procedure suit cinq temps : expression du besoin, validation, consultation
des fournisseurs, commande, reception. La reception alimente le magasin — c'est
le point ou l'achat et le stock se rejoignent.
"""
from django.db import models, transaction
from django.utils import timezone

from apps.accounts.models import Notification
from apps.circuits.services import etapes_resolues
from apps.core.models import JournalAction

from .models import (
    Article,
    BonCommande,
    ExpressionBesoin,
    MouvementStock,
    ValidationBesoin,
)


class ErreurAchat(Exception):
    """Operation refusee sur un besoin, une commande ou un mouvement de stock."""


# --- Expression de besoin ----------------------------------------------------
@transaction.atomic
def soumettre_besoin(besoin, requete=None):
    """Construit le circuit de validation et notifie le premier valideur."""
    if besoin.statut != ExpressionBesoin.Statut.BROUILLON:
        raise ErreurAchat("Ce besoin est deja soumis.")
    if not besoin.lignes.exists():
        raise ErreurAchat("Inscrivez au moins un article avant de soumettre le besoin.")

    etapes = etapes_resolues(besoin)
    if not etapes:
        raise ErreurAchat(
            "Aucun valideur n'est configure pour votre perimetre. "
            "Completez le circuit « BESOIN » dans l'administration."
        )

    besoin.validations.all().delete()
    for ordre, (libelle, valideur) in enumerate(etapes, start=1):
        ValidationBesoin.objects.create(
            besoin=besoin, ordre=ordre, libelle=libelle, valideur=valideur
        )

    besoin.statut = ExpressionBesoin.Statut.EN_CIRCUIT
    besoin.soumis_le = timezone.now()
    besoin.motif_rejet = ""
    besoin.save(update_fields=["statut", "soumis_le", "motif_rejet", "modifie_le"])

    _notifier(
        etapes[0][1],
        f"Besoin a valider : {besoin.numero}",
        f"{besoin.demandeur.nom_complet} exprime un besoin de "
        f"{besoin.montant_estime:.0f} FCFA — {besoin.objet}.",
        besoin.get_absolute_url(),
    )
    JournalAction.tracer(besoin.demandeur, "Soumission d'un besoin", besoin.numero, requete=requete)
    return besoin


@transaction.atomic
def decider_besoin(validation, favorable, commentaire="", requete=None):
    """Enregistre une decision et fait avancer le circuit."""
    besoin = validation.besoin
    if validation.decision != ValidationBesoin.Decision.ATTENTE:
        raise ErreurAchat("Cette etape est deja tranchee.")

    validation.decision = (
        ValidationBesoin.Decision.FAVORABLE if favorable else ValidationBesoin.Decision.DEFAVORABLE
    )
    validation.commentaire = commentaire
    validation.decide_le = timezone.now()
    validation.save(update_fields=["decision", "commentaire", "decide_le"])

    if not favorable:
        besoin.statut = ExpressionBesoin.Statut.REJETE
        besoin.motif_rejet = commentaire
        besoin.clos_le = timezone.now()
        besoin.save(update_fields=["statut", "motif_rejet", "clos_le", "modifie_le"])
        besoin.validations.filter(decision=ValidationBesoin.Decision.ATTENTE).update(
            decision=ValidationBesoin.Decision.IGNOREE
        )
        _notifier(
            besoin.demandeur,
            f"Besoin rejete : {besoin.numero}",
            f"Motif : {commentaire or 'non precise'}.",
            besoin.get_absolute_url(),
            Notification.Niveau.ALERTE,
        )
        JournalAction.tracer(validation.valideur, "Rejet d'un besoin", besoin.numero, commentaire, requete)
        return besoin

    suivante = besoin.etape_courante()
    if suivante is not None:
        _notifier(
            suivante.valideur,
            f"Besoin a valider : {besoin.numero}",
            f"{besoin.demandeur.nom_complet} — {suivante.libelle}.",
            besoin.get_absolute_url(),
        )
    else:
        besoin.statut = ExpressionBesoin.Statut.VALIDE
        besoin.save(update_fields=["statut", "modifie_le"])
        _notifier(
            besoin.demandeur,
            f"Besoin valide : {besoin.numero}",
            "Le besoin est valide : la consultation des fournisseurs peut commencer.",
            besoin.get_absolute_url(),
            Notification.Niveau.SUCCES,
        )
    JournalAction.tracer(
        validation.valideur, "Validation d'un besoin", besoin.numero, commentaire, requete
    )
    return besoin


def besoins_a_valider(agent):
    """Besoins dont l'agent doit trancher l'etape courante."""
    en_attente = ValidationBesoin.objects.filter(
        valideur=agent, decision=ValidationBesoin.Decision.ATTENTE,
        besoin__statut=ExpressionBesoin.Statut.EN_CIRCUIT,
    ).select_related("besoin__demandeur", "besoin__perimetre")
    return [
        validation for validation in en_attente
        if (courante := validation.besoin.etape_courante()) is not None
        and courante.pk == validation.pk
    ]


# --- Offres et commande ------------------------------------------------------
@transaction.atomic
def retenir_offre(offre, par, requete=None):
    """
    Retient une offre, les autres cessant de l'etre.

    La consultation doit avoir eu lieu : on exige au moins deux offres pour
    qu'un choix en soit un.
    """
    besoin = offre.besoin
    if not besoin.est_validee:
        raise ErreurAchat("Le besoin doit etre valide avant de retenir une offre.")
    if besoin.offres.count() < 2:
        raise ErreurAchat(
            "Consultez au moins deux fournisseurs avant de retenir une offre."
        )

    besoin.offres.update(retenue=False)
    offre.retenue = True
    offre.save(update_fields=["retenue"])
    JournalAction.tracer(
        par, "Choix d'une offre", besoin.numero,
        f"{offre.fournisseur} pour {offre.montant:.0f} FCFA.", requete,
    )
    return offre


@transaction.atomic
def emettre_commande(besoin, par, requete=None):
    """Emet le bon de commande au fournisseur retenu."""
    if not besoin.est_validee:
        raise ErreurAchat("Le besoin doit etre valide avant d'etre commande.")
    if hasattr(besoin, "bon_commande"):
        raise ErreurAchat("Un bon de commande existe deja pour ce besoin.")
    offre = besoin.offre_retenue
    if offre is None:
        raise ErreurAchat("Retenez une offre avant d'emettre le bon de commande.")
    if not offre.fournisseur.ncc:
        raise ErreurAchat(
            f"Le compte contribuable de {offre.fournisseur} est manquant : "
            "completez sa fiche avant de commander."
        )

    commande = BonCommande.objects.create(
        besoin=besoin, fournisseur=offre.fournisseur, montant=offre.montant, emis_par=par
    )
    besoin.statut = ExpressionBesoin.Statut.COMMANDE
    besoin.save(update_fields=["statut", "modifie_le"])
    JournalAction.tracer(par, "Emission d'un bon de commande", commande.numero, requete=requete)
    return commande


@transaction.atomic
def receptionner(commande, par, lignes=None, observations="", requete=None):
    """
    Constate la reception et alimente le magasin.

    `lignes` associe a chaque article recu la quantite effectivement livree.
    Les articles non tenus au magasin sont receptionnes sans mouvement : tout
    n'a pas vocation a etre stocke.
    """
    if commande.statut == BonCommande.Statut.ANNULE:
        raise ErreurAchat("Ce bon de commande est annule.")
    if commande.est_receptionne:
        raise ErreurAchat("Cette commande est deja receptionnee.")

    commande.statut = BonCommande.Statut.RECEPTIONNE
    commande.date_reception = timezone.localdate()
    commande.observations_reception = observations
    commande.receptionne_par = par
    commande.save(
        update_fields=["statut", "date_reception", "observations_reception",
                       "receptionne_par", "modifie_le"]
    )

    entrees = []
    for ligne in commande.besoin.lignes.select_related("article"):
        if ligne.article_id is None:
            continue
        quantite = (lignes or {}).get(ligne.pk, ligne.quantite)
        if not quantite:
            continue
        entrees.append(
            enregistrer_mouvement(
                ligne.article, MouvementStock.Type.ENTREE, quantite, par,
                motif=f"Reception du bon de commande {commande.numero}",
                bon_commande=commande,
            )
        )

    JournalAction.tracer(
        par, "Reception d'une commande", commande.numero,
        f"{len(entrees)} article(s) entre(s) au magasin.", requete,
    )
    return commande, entrees


@transaction.atomic
def solder(commande, par, numero_facture, montant_facture, fichier=None, requete=None):
    """Enregistre la facture et solde le besoin."""
    if not commande.est_receptionne:
        raise ErreurAchat("Receptionnez la commande avant d'enregistrer la facture.")
    if not numero_facture.strip():
        raise ErreurAchat("Indiquez le numero de la facture.")

    commande.facture_numero = numero_facture
    commande.facture_montant = montant_facture
    if fichier is not None:
        commande.facture_fichier = fichier
    commande.statut = BonCommande.Statut.PAYE
    commande.paye_le = timezone.localdate()
    commande.save()

    besoin = commande.besoin
    besoin.statut = ExpressionBesoin.Statut.SOLDE
    besoin.clos_le = timezone.now()
    besoin.save(update_fields=["statut", "clos_le", "modifie_le"])

    # La depense rejoint le plan d'action, si le besoin y etait rattache.
    rapporte = False
    if besoin.activite_id is not None:
        from apps.activites.models import Activite

        activite = besoin.activite
        Activite.objects.filter(pk=activite.pk).update(
            budget_execute=(activite.budget_execute or 0) + montant_facture
        )
        rapporte = True

    JournalAction.tracer(par, "Solde d'une commande", commande.numero, numero_facture, requete)
    return commande, rapporte


@transaction.atomic
def annuler_commande(commande, par, motif, requete=None):
    if commande.statut == BonCommande.Statut.PAYE:
        raise ErreurAchat("Une commande payee ne peut etre annulee.")
    if not motif.strip():
        raise ErreurAchat("Indiquez le motif de l'annulation.")
    commande.statut = BonCommande.Statut.ANNULE
    commande.motif_annulation = motif
    commande.save(update_fields=["statut", "motif_annulation", "modifie_le"])
    JournalAction.tracer(par, "Annulation d'un bon de commande", commande.numero, motif, requete)
    return commande


# --- Magasin -----------------------------------------------------------------
@transaction.atomic
def enregistrer_mouvement(
    article, type_mouvement, quantite, par, motif="", beneficiaire="",
    bon_commande=None, date=None,
):
    """
    Inscrit un mouvement au journal et met le stock a jour.

    Une sortie superieure au stock est refusee : le magasin ne distribue pas
    ce qu'il n'a pas. Un inventaire, lui, fixe la quantite comptee, quelle
    qu'elle soit — c'est son objet.
    """
    if quantite <= 0:
        raise ErreurAchat("La quantite doit etre superieure a zero.")

    article = Article.objects.select_for_update().get(pk=article.pk)
    if type_mouvement == MouvementStock.Type.SORTIE and quantite > article.stock:
        raise ErreurAchat(
            f"Stock insuffisant : {article.stock} {article.unite}(s) disponible(s) "
            f"pour {quantite} demande(s)."
        )
    if type_mouvement == MouvementStock.Type.SORTIE and not beneficiaire.strip():
        raise ErreurAchat("Indiquez le beneficiaire de la sortie.")

    mouvement = MouvementStock(
        article=article, type=type_mouvement, quantite=quantite, motif=motif,
        beneficiaire=beneficiaire, bon_commande=bon_commande, saisi_par=par,
        date=date or timezone.localdate(),
    )
    mouvement.stock_apres = mouvement.appliquer(article.stock)
    mouvement.save()

    Article.objects.filter(pk=article.pk).update(stock=mouvement.stock_apres)
    article.stock = mouvement.stock_apres
    return mouvement


def recalculer_stock(article):
    """
    Recalcule le stock depuis le journal et corrige la vue cachee.

    Utile apres une reprise de donnees ou la suppression d'un mouvement.
    Retourne l'ecart constate, qui doit normalement etre nul.
    """
    reel = article.stock_reel
    ecart = reel - article.stock
    if ecart:
        Article.objects.filter(pk=article.pk).update(stock=reel)
        article.stock = reel
    return ecart


def articles_sous_seuil(agent):
    """Articles a reapprovisionner, dans le perimetre visible par l'agent."""
    qs = Article.objects.filter(actif=True)
    if not (agent.est_rh or agent.est_direction or agent.peut_administrer):
        perimetre = agent.perimetre
        qs = qs.filter(perimetre=perimetre) if perimetre else qs.none()
    return qs.filter(stock__lte=models.F("seuil_alerte")).order_by("designation")


# --- Consolidation -----------------------------------------------------------
def tableau_achats(agent):
    """Synthese des achats et du magasin, limitee au perimetre de l'agent."""
    besoins = ExpressionBesoin.objects.visibles_par(agent)
    commandes = BonCommande.objects.filter(besoin__in=besoins)
    sous_seuil = articles_sous_seuil(agent)

    return {
        "nb_besoins": besoins.count(),
        "nb_en_circuit": besoins.filter(statut=ExpressionBesoin.Statut.EN_CIRCUIT).count(),
        "nb_a_commander": besoins.filter(statut=ExpressionBesoin.Statut.VALIDE).count(),
        "nb_a_receptionner": commandes.filter(statut=BonCommande.Statut.EMIS).count(),
        "montant_engage": commandes.exclude(statut=BonCommande.Statut.ANNULE).aggregate(
            t=models.Sum("montant")
        )["t"] or 0,
        "sous_seuil": sous_seuil,
        "nb_sous_seuil": sous_seuil.count(),
        "mes_validations": besoins_a_valider(agent),
        "recents": besoins.select_related("perimetre", "demandeur")[:8],
    }


def _notifier(destinataire, titre, message, lien="", niveau=Notification.Niveau.INFO):
    if destinataire is None:
        return
    Notification.objects.create(
        destinataire=destinataire, titre=titre, message=message, lien=lien, niveau=niveau
    )

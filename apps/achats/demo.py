"""
Jeu de demonstration des achats et du magasin.

Il parcourt la procedure de bout en bout et laisse, a chaque etape, un dossier
a voir :

  - un besoin en brouillon, un en validation, un valide en attente d'offres ;
  - un besoin rejete, avec son motif ;
  - un dossier complet : consultation, commande, reception, facture ;
  - un magasin dont certains articles passent sous le seuil d'alerte ;
  - un inventaire qui corrige un ecart constate au comptage ;
  - un parc d'equipements, dont un en panne.
"""
from datetime import timedelta

from django.utils import timezone

from apps.core.models import Perimetre

from .models import Article, Equipement, ExpressionBesoin, Fournisseur, MouvementStock
from .services import (
    decider_besoin,
    emettre_commande,
    enregistrer_mouvement,
    receptionner,
    retenir_offre,
    solder,
    soumettre_besoin,
)

FOURNISSEURS = [
    ("Papeterie du Centre", "CI-2019-004512", "Fournitures de bureau",
     "M. KOUADIO", "+225 27 22 44 11 00"),
    ("Bureau Plus Cote d'Ivoire", "CI-2015-008841", "Fournitures et mobilier",
     "Mme AKA", "+225 27 21 35 60 12"),
    ("Informatique Services SA", "CI-2012-001277", "Materiel informatique",
     "M. DIALLO", "+225 27 20 30 40 50"),
    ("Imprimerie Nationale", "CI-1998-000031", "Impression et reprographie",
     "Service commercial", "+225 27 20 21 22 23"),
]

ARTICLES = [
    ("RAM-A4", "Rame de papier A4 80g", "rame", 20),
    ("TON-HP", "Toner imprimante HP noir", "cartouche", 4),
    ("STY-BLE", "Stylo a bille bleu", "boite de 50", 3),
    ("CAH-200", "Cahier de 200 pages", "piece", 50),
    ("CRA-BLA", "Craie blanche", "boite", 10),
    ("CHE-CAR", "Chemise cartonnee", "paquet de 100", 5),
]

EQUIPEMENTS = [
    ("ORD-001", "Ordinateur portable", "HP ProBook 450", "BON", 650_000),
    ("ORD-002", "Ordinateur portable", "Dell Latitude 5420", "BON", 720_000),
    ("IMP-001", "Imprimante multifonction", "HP LaserJet Pro M428", "BON", 380_000),
    ("IMP-002", "Imprimante laser", "Canon LBP-6030", "PANNE", 95_000),
    ("VID-001", "Videoprojecteur", "Epson EB-X49", "BON", 340_000),
    ("ARM-001", "Armoire metallique", "2 portes", "PASSABLE", 180_000),
]


def installer_fournisseurs():
    fournisseurs = {}
    for nom, ncc, domaine, contact, telephone in FOURNISSEURS:
        fournisseur, _ = Fournisseur.objects.get_or_create(
            nom=nom,
            defaults={"ncc": ncc, "domaine": domaine, "contact": contact,
                      "telephone": telephone},
        )
        fournisseurs[nom] = fournisseur
    return fournisseurs


def _besoin(perimetre, demandeur, objet, lignes, **extra):
    besoin = ExpressionBesoin.objects.create(
        perimetre=perimetre, objet=objet, demandeur=demandeur, **extra
    )
    for article, designation, quantite, unite, prix in lignes:
        besoin.lignes.create(
            article=article, designation=designation, quantite=quantite,
            unite=unite, prix_unitaire=prix,
        )
    return besoin


def _valider_entierement(besoin):
    garde = 0
    while (etape := besoin.etape_courante()) is not None and garde < 8:
        decider_besoin(etape, True, "Avis favorable.")
        besoin.refresh_from_db()
        garde += 1
    return besoin


def charger(stdout=None):
    """Construit le jeu de demonstration. Sans effet s'il existe deja."""
    def dire(message):
        if stdout is not None:
            stdout.write(message)

    fournisseurs = installer_fournisseurs()

    if ExpressionBesoin.objects.exists():
        dire("  Achats deja presents : inchanges.")
        return

    centrale = Perimetre.centrale()
    antennes = list(Perimetre.objects.filter(type=Perimetre.Type.ANTENNE).order_by("code"))
    if centrale is None or centrale.responsable is None:
        dire("  Organisation incomplete : achats de demonstration ignores.")
        return

    directeur = centrale.responsable
    from apps.accounts.models import Agent

    agents = list(centrale.agents().exclude(pk=directeur.pk).order_by("matricule"))
    if not agents:
        dire("  Aucun agent au central : achats de demonstration ignores.")
        return
    # Un agent de base : son besoin traverse toute la voie hierarchique.
    agent = next((a for a in agents if a.role == Agent.Role.AGENT), agents[0])
    secretaire = next((a for a in agents if a.est_secretariat), directeur)
    aujourdhui = timezone.localdate()

    # --- Magasin de la direction centrale ----------------------------------
    articles = {}
    for code, designation, unite, seuil in ARTICLES:
        article, _ = Article.objects.get_or_create(
            perimetre=centrale, code=code,
            defaults={"designation": designation, "unite": unite, "seuil_alerte": seuil},
        )
        articles[code] = article

    # Approvisionnement initial, puis consommation courante.
    stocks_initiaux = {"RAM-A4": 120, "TON-HP": 12, "STY-BLE": 15,
                       "CAH-200": 300, "CRA-BLA": 40, "CHE-CAR": 20}
    for code, quantite in stocks_initiaux.items():
        enregistrer_mouvement(
            articles[code], MouvementStock.Type.ENTREE, quantite, secretaire,
            motif="Dotation de debut d'exercice", date=aujourdhui - timedelta(days=120),
        )
    sorties = [
        ("RAM-A4", 45, "Sous-direction de la formation pedagogique continue", 60),
        ("RAM-A4", 60, "Atelier de validation des guides", 30),
        ("TON-HP", 9, "Service du personnel", 45),
        ("STY-BLE", 13, "Atelier regional", 20),
        ("CAH-200", 120, "Formation des conseillers pedagogiques", 15),
    ]
    for code, quantite, beneficiaire, il_y_a in sorties:
        enregistrer_mouvement(
            articles[code], MouvementStock.Type.SORTIE, quantite, secretaire,
            beneficiaire=beneficiaire, date=aujourdhui - timedelta(days=il_y_a),
        )
    # Un comptage revele un ecart : l'inventaire fait foi.
    enregistrer_mouvement(
        articles["CRA-BLA"], MouvementStock.Type.INVENTAIRE, 31, secretaire,
        motif="Comptage trimestriel : neuf boites manquantes, casse constatee.",
        date=aujourdhui - timedelta(days=10),
    )

    # --- 1. Dossier complet : consultation, commande, reception, facture ----
    complet = _besoin(
        centrale, agent, "Reapprovisionnement en papier et toner",
        [
            (articles["RAM-A4"], "Rame de papier A4 80g", 100, "rame", 4_500),
            (articles["TON-HP"], "Toner imprimante HP noir", 10, "cartouche", 45_000),
        ],
        justification="Les stocks de papier et de toner sont sous le seuil d'alerte.",
    )
    soumettre_besoin(complet)
    _valider_entierement(complet)
    complet.offres.create(
        fournisseur=fournisseurs["Papeterie du Centre"], montant=880_000, delai_jours=7
    )
    complet.offres.create(
        fournisseur=fournisseurs["Bureau Plus Cote d'Ivoire"], montant=935_000, delai_jours=5,
        observations="Delai plus court mais montant superieur.",
    )
    retenir_offre(complet.offres.order_by("montant").first(), secretaire)
    commande = emettre_commande(complet, secretaire)
    receptionner(
        commande, secretaire,
        lignes={complet.lignes.get(article=articles["RAM-A4"]).pk: 100,
                complet.lignes.get(article=articles["TON-HP"]).pk: 10},
        observations="Livraison conforme au bon de commande.",
    )
    commande.refresh_from_db()
    solder(commande, secretaire, "FAC-2026-0312", 880_000)

    # --- 2. Besoin valide, consultation en cours ----------------------------
    consultation = _besoin(
        centrale, agent, "Acquisition de deux videoprojecteurs",
        [(None, "Videoprojecteur de salle", 2, "piece", 340_000)],
        justification="Les salles de formation n'en disposent plus qu'un, en fin de vie.",
    )
    soumettre_besoin(consultation)
    _valider_entierement(consultation)
    consultation.offres.create(
        fournisseur=fournisseurs["Informatique Services SA"], montant=695_000, delai_jours=14
    )

    # --- 3. Besoin en cours de validation ------------------------------------
    en_circuit = _besoin(
        centrale, agent, "Impression des guides d'execution du primaire",
        [(None, "Impression couleur, 500 exemplaires", 500, "exemplaire", 6_500)],
        justification="Diffusion aux antennes regionales avant la rentree.",
    )
    soumettre_besoin(en_circuit)

    # --- 4. Besoin rejete -----------------------------------------------------
    rejete = _besoin(
        centrale, agent, "Renouvellement du mobilier de bureau",
        [(None, "Fauteuil de bureau", 12, "piece", 85_000)],
        justification="Mobilier vieillissant.",
    )
    soumettre_besoin(rejete)
    decider_besoin(
        rejete.etape_courante(), False,
        "Depense non prioritaire cette annee : a reinscrire au plan de l'exercice suivant.",
    )

    # --- 5. Besoin encore en brouillon ----------------------------------------
    _besoin(
        centrale, agent, "Fournitures du prochain trimestre",
        [(articles["CHE-CAR"], "Chemise cartonnee", 20, "paquet de 100", 12_000)],
    )

    # --- 6. Besoin d'antenne, serie propre ------------------------------------
    if antennes:
        antenne = antennes[0]
        chef = antenne.responsable
        if chef is not None:
            agents_antenne = list(antenne.agents().exclude(pk=chef.pk))
            demandeur = agents_antenne[0] if agents_antenne else chef
            craie = Article.objects.create(
                perimetre=antenne, code="CRA-BLA", designation="Craie blanche",
                unite="boite", seuil_alerte=15,
            )
            enregistrer_mouvement(
                craie, MouvementStock.Type.ENTREE, 60, chef,
                motif="Dotation de l'antenne", date=aujourdhui - timedelta(days=90),
            )
            enregistrer_mouvement(
                craie, MouvementStock.Type.SORTIE, 48, chef,
                beneficiaire="Ecoles de la region", date=aujourdhui - timedelta(days=20),
            )
            besoin_antenne = _besoin(
                antenne, demandeur, "Fournitures pedagogiques de l'antenne",
                [(craie, "Craie blanche", 100, "boite", 1_200)],
                justification="Dotation des ecoles du ressort.",
            )
            soumettre_besoin(besoin_antenne)

    # --- 7. Parc d'equipements -------------------------------------------------
    for code, designation, marque, etat, valeur in EQUIPEMENTS:
        Equipement.objects.get_or_create(
            code_inventaire=f"DPFC-{code}",
            defaults={
                "perimetre": centrale, "designation": designation, "marque": marque,
                "etat": etat, "valeur": valeur,
                "date_acquisition": aujourdhui - timedelta(days=500),
                "affecte_a": agent if code.startswith("ORD") else None,
                "observations": "Carte mere hors service, devis de reparation demande."
                if etat == "PANNE" else "",
            },
        )

    dire(
        f"  Achats : {ExpressionBesoin.objects.count()} besoin(s), "
        f"{Article.objects.count()} article(s), "
        f"{MouvementStock.objects.count()} mouvement(s), "
        f"{Equipement.objects.count()} equipement(s)."
    )

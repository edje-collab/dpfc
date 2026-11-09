"""
Jeu de demonstration du courrier et de la gestion documentaire.

Il couvre les cas de gestion que les ecrans doivent savoir montrer :

  - courrier arrive en attente d'imputation, impute en cours, traite, classe
    sans suite, et un courrier dont le delai est depasse ;
  - courrier depart repondant a un courrier arrive ;
  - un courrier confidentiel, visible des seuls habilites ;
  - documents versionnes, document partage entre perimetres, document a acces
    restreint ;
  - une piece visee au parapheur et une piece en cours de visa.
"""
from datetime import timedelta

from django.core.files.base import ContentFile
from django.db import models
from django.utils import timezone

from apps.core.models import Perimetre

from .models import Courrier, Document, ModeleDocument, PieceParapheur, TypeDocument
from .services import (
    classer,
    deposer_version,
    imputer,
    soumettre_au_parapheur,
    traiter_imputation,
    viser,
)

MODELES = [
    (
        "note-de-service",
        "Note de service",
        Courrier.Nature.NOTE,
        "MINISTERE DE L'EDUCATION NATIONALE, DE L'ALPHABETISATION\n"
        "ET DE L'ENSEIGNEMENT TECHNIQUE\n"
        "Direction Generale de la Pedagogie, des Curricula et du Suivi des Programmes\n"
        "{{ perimetre }}\n\n"
        "NOTE DE SERVICE\n\n"
        "Objet : {{ objet }}\n"
        "A : {{ correspondant }}\n\n"
        "[Corps de la note]\n\n"
        "Fait a Abidjan, le {{ date }}\n"
        "{{ signataire }}",
    ),
    (
        "lettre-de-transmission",
        "Lettre de transmission",
        Courrier.Nature.LETTRE,
        "MINISTERE DE L'EDUCATION NATIONALE, DE L'ALPHABETISATION\n"
        "ET DE L'ENSEIGNEMENT TECHNIQUE\n"
        "{{ perimetre }}\n\n"
        "A : {{ correspondant }}\n\n"
        "Objet : {{ objet }}\n\n"
        "J'ai l'honneur de vous transmettre, ci-joint, les documents relatifs a l'objet\n"
        "cite en reference.\n\n"
        "Fait a Abidjan, le {{ date }}\n"
        "{{ signataire }}",
    ),
    (
        "convocation-atelier",
        "Convocation a un atelier",
        Courrier.Nature.INVITATION,
        "{{ perimetre }}\n\n"
        "CONVOCATION\n\n"
        "Objet : {{ objet }}\n"
        "A : {{ correspondant }}\n\n"
        "Vous etes convie(e) a participer a l'atelier cite en objet.\n"
        "Votre presence est vivement souhaitee.\n\n"
        "Fait a Abidjan, le {{ date }}\n"
        "{{ signataire }}",
    ),
]


def installer_modeles():
    for code, titre, nature, corps in MODELES:
        ModeleDocument.objects.get_or_create(
            code=code, defaults={"titre": titre, "nature": nature, "corps": corps}
        )


def _document(perimetre, titre, type_document, deposant, contenu, **extra):
    document = Document.objects.create(
        perimetre=perimetre, titre=titre, type_document=type_document,
        annee=timezone.localdate().year, deposant=deposant, **extra,
    )
    deposer_version(
        document,
        ContentFile(contenu.encode("utf-8"), name=f"{document.pk}-v1.txt"),
        deposant,
        "Version initiale",
    )
    return document


def charger(stdout=None):
    """Construit le jeu de demonstration. Sans effet s'il existe deja."""
    def dire(message):
        if stdout is not None:
            stdout.write(message)

    installer_modeles()

    if Courrier.objects.exists():
        dire("  Courrier deja present : inchange.")
        return

    centrale = Perimetre.centrale()
    antennes = list(Perimetre.objects.filter(type=Perimetre.Type.ANTENNE).order_by("code"))
    cnrpn = Perimetre.objects.filter(type=Perimetre.Type.CENTRE).first()
    if centrale is None or centrale.responsable is None:
        dire("  Organisation incomplete : courrier de demonstration ignore.")
        return

    directeur = centrale.responsable
    # On privilegie un agent de base : son circuit de parapheur traverse toute
    # la voie hierarchique, ce que la demonstration doit montrer.
    from apps.accounts.models import Agent

    agents_centraux = list(
        centrale.agents().exclude(pk=directeur.pk).order_by(
            models.Case(
                models.When(role=Agent.Role.AGENT, then=0),
                default=1,
                output_field=models.IntegerField(),
            ),
            "matricule",
        )[:3]
    )
    if not agents_centraux:
        dire("  Aucun agent au central : courrier de demonstration ignore.")
        return
    agent = agents_centraux[0]
    second = agents_centraux[1] if len(agents_centraux) > 1 else agent
    aujourdhui = timezone.localdate()

    # --- 1. Courrier arrive, en attente d'imputation ----------------------
    Courrier.objects.create(
        perimetre=centrale, sens=Courrier.Sens.ARRIVEE, nature=Courrier.Nature.CIRCULAIRE,
        correspondant="Cabinet du Ministre",
        objet="Circulaire relative a la preparation de la rentree scolaire",
        reference_expediteur="0312/MENAET/CAB",
        date_courrier=aujourdhui - timedelta(days=3),
        date_enregistrement=aujourdhui - timedelta(days=2),
        resume="Orientations du Ministre pour la preparation de la prochaine rentree.",
        enregistre_par=directeur,
    )

    # --- 2. Courrier impute, traitement en cours ---------------------------
    en_cours = Courrier.objects.create(
        perimetre=centrale, sens=Courrier.Sens.ARRIVEE, nature=Courrier.Nature.DEMANDE,
        correspondant="Direction des Examens et Concours",
        objet="Demande d'avis sur le calendrier des evaluations",
        reference_expediteur="0088/MENAET/DEC",
        date_courrier=aujourdhui - timedelta(days=10),
        date_enregistrement=aujourdhui - timedelta(days=9),
        enregistre_par=directeur,
    )
    imputer(en_cours, directeur, [
        {"destinataire": agent, "instructions": "Preparer un projet d'avis technique.",
         "delai": aujourdhui + timedelta(days=5)},
        {"destinataire": second, "instructions": "Pour information.",
         "delai": aujourdhui + timedelta(days=5), "pour_information": True},
    ])

    # --- 3. Courrier dont le delai est depasse -----------------------------
    retard = Courrier.objects.create(
        perimetre=centrale, sens=Courrier.Sens.ARRIVEE, nature=Courrier.Nature.LETTRE,
        correspondant="DRENA de Bouake",
        objet="Transmission des besoins en formation continue",
        date_courrier=aujourdhui - timedelta(days=40),
        date_enregistrement=aujourdhui - timedelta(days=38),
        enregistre_par=directeur,
    )
    imputer(retard, directeur, [
        {"destinataire": agent, "instructions": "Consolider les besoins exprimes.",
         "delai": aujourdhui - timedelta(days=6)},
    ])

    # --- 4. Courrier traite, puis sa reponse au depart ---------------------
    traite = Courrier.objects.create(
        perimetre=centrale, sens=Courrier.Sens.ARRIVEE, nature=Courrier.Nature.INVITATION,
        correspondant="Partenaire technique et financier",
        objet="Invitation a l'atelier regional sur les curricula",
        date_courrier=aujourdhui - timedelta(days=25),
        date_enregistrement=aujourdhui - timedelta(days=24),
        enregistre_par=directeur,
    )
    [imputation] = imputer(traite, directeur, [
        {"destinataire": agent, "instructions": "Preparer la reponse et designer les participants.",
         "delai": aujourdhui - timedelta(days=15)},
    ])
    traiter_imputation(
        imputation, agent,
        "Reponse preparee et transmise a la signature ; trois participants designes.",
    )
    Courrier.objects.create(
        perimetre=centrale, sens=Courrier.Sens.DEPART, nature=Courrier.Nature.LETTRE,
        correspondant="Partenaire technique et financier",
        objet="Reponse a l'invitation a l'atelier regional sur les curricula",
        date_courrier=aujourdhui - timedelta(days=18),
        date_enregistrement=aujourdhui - timedelta(days=18),
        courrier_lie=traite, enregistre_par=directeur,
    )

    # --- 5. Courrier classe sans suite -------------------------------------
    sans_suite = Courrier.objects.create(
        perimetre=centrale, sens=Courrier.Sens.ARRIVEE, nature=Courrier.Nature.AUTRE,
        correspondant="Societe de fournitures scolaires",
        objet="Offre commerciale de manuels",
        date_courrier=aujourdhui - timedelta(days=12),
        date_enregistrement=aujourdhui - timedelta(days=12),
        enregistre_par=directeur,
    )
    classer(sans_suite, directeur, "Offre non sollicitee, hors procedure de marche public.")

    # --- 6. Courrier confidentiel ------------------------------------------
    Courrier.objects.create(
        perimetre=centrale, sens=Courrier.Sens.ARRIVEE, nature=Courrier.Nature.LETTRE,
        correspondant="Inspection Generale",
        objet="Suites d'une mission de controle",
        date_courrier=aujourdhui - timedelta(days=6),
        date_enregistrement=aujourdhui - timedelta(days=5),
        confidentiel=True, enregistre_par=directeur,
    )

    # --- 7. Courrier d'antenne, serie propre --------------------------------
    if antennes:
        antenne = antennes[0]
        chef = antenne.responsable
        if chef is not None:
            arrivee = Courrier.objects.create(
                perimetre=antenne, sens=Courrier.Sens.ARRIVEE, nature=Courrier.Nature.DEMANDE,
                correspondant="IEPP de la region",
                objet="Demande d'appui pour l'encadrement des nouveaux enseignants",
                date_courrier=aujourdhui - timedelta(days=8),
                date_enregistrement=aujourdhui - timedelta(days=7),
                enregistre_par=chef,
            )
            agents_antenne = list(antenne.agents().exclude(pk=chef.pk)[:1])
            if agents_antenne:
                imputer(arrivee, chef, [
                    {"destinataire": agents_antenne[0],
                     "instructions": "Programmer une tournee d'encadrement.",
                     "delai": aujourdhui + timedelta(days=10)},
                ])
            Courrier.objects.create(
                perimetre=antenne, sens=Courrier.Sens.DEPART, nature=Courrier.Nature.LETTRE,
                correspondant="Direction de la Pedagogie et de la Formation Continue",
                objet="Rapport mensuel d'activites de l'antenne",
                date_courrier=aujourdhui - timedelta(days=2),
                date_enregistrement=aujourdhui - timedelta(days=2),
                enregistre_par=chef,
            )

    # --- 8. Documents -------------------------------------------------------
    guide = _document(
        centrale, "Guide d'execution du programme de francais CM2", TypeDocument.GUIDE,
        agent,
        "Guide d'execution du programme de francais du CM2. Il precise les competences "
        "attendues, la progression annuelle et les situations d'apprentissage.",
        description="Guide valide en atelier national, diffuse aux antennes.",
        partage=True,
    )
    deposer_version(
        guide,
        ContentFile(
            b"Guide d'execution du programme de francais du CM2, version corrigee apres "
            b"relecture des inspecteurs.",
            name="guide-cm2-v2.txt",
        ),
        agent,
        "Corrections apres relecture",
    )
    _document(
        centrale, "Rapport annuel de la formation continue", TypeDocument.RAPPORT, directeur,
        "Rapport annuel sur la formation continue des personnels enseignants et "
        "d'encadrement pedagogique. Bilan des sessions et perspectives.",
        description="Bilan de l'exercice, transmis a la direction generale.",
    )
    _document(
        centrale, "Dossier disciplinaire", TypeDocument.AUTRE, directeur,
        "Piece a acces restreint.",
        description="Acces limite au directeur et aux agents expressement autorises.",
        acces=Document.Acces.RESTREINT,
    )
    if cnrpn is not None and cnrpn.responsable is not None:
        _document(
            cnrpn, "Catalogue des ressources numeriques", TypeDocument.SUPPORT,
            cnrpn.responsable,
            "Catalogue national des ressources pedagogiques numeriques : capsules video, "
            "exercices interactifs et fiches d'accompagnement.",
            description="Catalogue mis a jour chaque trimestre.",
            partage=True,
        )

    # --- 9. Parapheur -------------------------------------------------------
    note = _document(
        centrale, "Projet de note de service sur les evaluations", TypeDocument.NOTE, agent,
        "Projet de note de service relative a l'organisation des evaluations trimestrielles.",
        description="Soumis aux visas avant signature.",
    )
    piece = PieceParapheur.objects.create(
        perimetre=centrale, objet="Note de service sur les evaluations trimestrielles",
        document=note, demandeur=agent,
        note="Note preparee a la demande du directeur, pour diffusion aux antennes.",
    )
    soumettre_au_parapheur(piece)

    circulaire = _document(
        centrale, "Projet de circulaire sur la rentree", TypeDocument.NOTE, agent,
        "Projet de circulaire relative a la preparation de la rentree scolaire.",
    )
    visee = PieceParapheur.objects.create(
        perimetre=centrale, objet="Circulaire de rentree", document=circulaire, demandeur=agent,
    )
    soumettre_au_parapheur(visee)
    garde = 0
    while (etape := visee.etape_courante()) is not None and garde < 6:
        viser(etape, True, "Vise.")
        visee.refresh_from_db()
        garde += 1

    dire(
        f"  Courrier : {Courrier.objects.count()} courrier(s), "
        f"{Document.objects.count()} document(s), "
        f"{PieceParapheur.objects.count()} piece(s) au parapheur."
    )

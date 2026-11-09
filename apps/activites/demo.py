"""
Jeu de donnees de demonstration du pilotage.

Il couvre deliberement tous les cas de figure de gestion, de facon que chaque
ecran ait quelque chose a montrer et que chaque regle soit verifiable :

  - un plan en preparation, un plan soumis en attente de validation, un plan
    valide en cours d'execution et un plan clos de l'exercice precedent ;
  - des activites planifiees, en cours, realisees, en retard, reportees et
    annulees ;
  - les trois types de perimetre : direction centrale, antennes, CNRPN ;
  - des indicateurs atteints, partiellement atteints et depasses.
"""
from datetime import date, timedelta

from django.utils import timezone

from apps.core.models import Perimetre

from .models import Activite, Axe, PlanAction
from .services import (
    annuler_activite,
    clore_plan,
    enregistrer_avancement,
    reporter_activite,
    soumettre_plan,
    valider_plan,
)

AXES = [
    ("AX1", "Qualite des apprentissages",
     "Programmes, guides d'execution et supports d'accompagnement."),
    ("AX2", "Formation continue des personnels",
     "Renforcement des capacites des enseignants et des encadreurs pedagogiques."),
    ("AX3", "Numerique educatif",
     "Production et diffusion des ressources pedagogiques numeriques."),
    ("AX4", "Encadrement de proximite",
     "Suivi pedagogique des etablissements et accompagnement des antennes."),
]


def installer_axes():
    axes = {}
    for ordre, (code, libelle, description) in enumerate(AXES, start=1):
        axe, _ = Axe.objects.get_or_create(
            code=code, defaults={"libelle": libelle, "description": description, "ordre": ordre}
        )
        axes[code] = axe
    return axes


def _jours(n):
    """Date relative a aujourd'hui, bornee a l'annee du plan."""
    return timezone.localdate() + timedelta(days=n)


def _activite(plan, axe, intitule, debut, fin, **extra):
    return Activite.objects.create(
        plan=plan, axe=axe, intitule=intitule,
        date_debut_prevue=debut, date_fin_prevue=fin, **extra,
    )


def charger(stdout=None):
    """Construit les plans de demonstration. Sans effet s'ils existent deja."""
    def dire(message):
        if stdout is not None:
            stdout.write(message)

    axes = installer_axes()
    annee = timezone.localdate().year
    aujourdhui = timezone.localdate()

    centrale = Perimetre.centrale()
    cnrpn = Perimetre.objects.filter(type=Perimetre.Type.CENTRE).first()
    antennes = list(
        Perimetre.objects.filter(type=Perimetre.Type.ANTENNE).order_by("code")
    )
    if centrale is None or not antennes:
        dire("  Organisation incomplete : plans de demonstration ignores.")
        return

    if PlanAction.objects.filter(annee=annee).exists():
        dire("  Plans d'action deja presents : inchanges.")
        return

    directeur = centrale.responsable

    # --- 1. Direction centrale : plan valide, en cours d'execution ---------
    plan_central = PlanAction.objects.create(
        perimetre=centrale, annee=annee,
        contexte="Priorites de l'exercice : revision des guides d'execution du primaire, "
                 "montee en charge de la formation a distance et consolidation du suivi des antennes.",
    )
    revision = _activite(
        plan_central, axes["AX1"], "Revision des guides d'execution du primaire",
        date(annee, 2, 1), aujourdhui - timedelta(days=100),
        type=Activite.Type.ELABORATION, responsable=directeur,
        lieu="Abidjan", public_cible="Concepteurs de programmes et inspecteurs",
        effectif_prevu=45, budget_prevu=18_000_000, source_financement="Budget de l'Etat",
    )
    formation = _activite(
        plan_central, axes["AX2"], "Formation des conseillers pedagogiques au numerique educatif",
        aujourdhui - timedelta(days=60), aujourdhui + timedelta(days=25),
        type=Activite.Type.FORMATION, responsable=directeur,
        lieu="Grand-Bassam", public_cible="Conseillers pedagogiques",
        effectif_prevu=200, budget_prevu=32_000_000, source_financement="Partenaire technique",
    )
    plateforme = _activite(
        plan_central, axes["AX3"], "Deploiement de la plateforme de formation a distance",
        date(annee, 1, 15), aujourdhui + timedelta(days=40),
        type=Activite.Type.PRODUCTION, responsable=directeur,
        lieu="National", public_cible="Enseignants du secondaire",
        effectif_prevu=2_000, budget_prevu=55_000_000, source_financement="Partenaire technique",
    )
    tournee = _activite(
        plan_central, axes["AX4"], "Tournee de supervision des antennes regionales",
        date(annee, 3, 1), aujourdhui - timedelta(days=12),
        type=Activite.Type.SUIVI, responsable=directeur,
        lieu="Toutes regions", public_cible="Chefs d'antenne",
        effectif_prevu=8, budget_prevu=12_000_000, source_financement="Budget de l'Etat",
    )
    seminaire = _activite(
        plan_central, axes["AX2"], "Seminaire bilan de fin d'exercice",
        aujourdhui + timedelta(days=30), aujourdhui + timedelta(days=34),
        type=Activite.Type.REUNION, responsable=directeur,
        lieu="Yamoussoukro", effectif_prevu=60, budget_prevu=9_000_000,
    )
    abandonnee = _activite(
        plan_central, axes["AX3"], "Acquisition de tablettes pour les antennes",
        aujourdhui - timedelta(days=90), aujourdhui - timedelta(days=20),
        type=Activite.Type.AUTRE, responsable=directeur,
        effectif_prevu=0, budget_prevu=40_000_000,
    )

    soumettre_plan(plan_central, par=directeur)
    valider_plan(plan_central, par=directeur)

    # Activite achevee, avec indicateurs atteints.
    enregistrer_avancement(
        revision, directeur, 100,
        "Les guides du CP au CM2 ont ete revises et valides en atelier national.",
        effectif_touche=48, montant_engage=17_400_000, date=aujourdhui - timedelta(days=102),
    )
    revision.indicateurs.create(
        libelle="Guides d'execution revises", unite="guides", valeur_cible=12, valeur_realisee=12
    )
    revision.indicateurs.create(
        libelle="Inspecteurs associes", unite="inspecteurs", valeur_cible=40, valeur_realisee=48
    )

    # Activite en cours, en deux points d'avancement successifs.
    enregistrer_avancement(
        formation, directeur, 35, "Premiere cohorte formee a Grand-Bassam.",
        effectif_touche=70, montant_engage=11_000_000, date=date(annee, 5, 2),
    )
    enregistrer_avancement(
        formation, directeur, 60, "Deuxieme cohorte formee ; supports remis aux antennes.",
        difficultes="Connexion internet instable sur le site de formation.",
        effectif_touche=55, montant_engage=8_500_000, date=date(annee, 6, 10),
    )
    formation.indicateurs.create(
        libelle="Conseillers formes", unite="conseillers", valeur_cible=200, valeur_realisee=125
    )

    # Activite longue, a mi-parcours.
    enregistrer_avancement(
        plateforme, directeur, 45,
        "Modules de mathematiques et de francais mis en ligne ; ouverture aux antennes pilotes.",
        effectif_touche=840, montant_engage=23_000_000, date=aujourdhui - timedelta(days=30),
    )
    plateforme.indicateurs.create(
        libelle="Enseignants inscrits", unite="enseignants", valeur_cible=2000, valeur_realisee=840
    )
    plateforme.indicateurs.create(
        libelle="Modules en ligne", unite="modules", valeur_cible=20, valeur_realisee=9
    )

    # Activite echue sans etre achevee : apparait en retard.
    enregistrer_avancement(
        tournee, directeur, 55, "Cinq antennes visitees sur huit.",
        difficultes="Indisponibilite du vehicule de service en juin.",
        effectif_touche=5, montant_engage=7_200_000, date=aujourdhui - timedelta(days=20),
    )

    # Activite reportee, puis activite annulee.
    reporter_activite(
        seminaire, directeur,
        "Report a decembre pour tenir compte du calendrier des examens.",
        nouvelle_fin=aujourdhui + timedelta(days=55),
    )
    annuler_activite(
        abandonnee, directeur,
        "Acquisition reprise par la Direction des Technologies et des Systemes d'Information.",
    )

    # --- 2. Antenne : plan valide, execution engagee ------------------------
    antenne_active = antennes[0]
    chef_actif = antenne_active.responsable
    plan_antenne = PlanAction.objects.create(
        perimetre=antenne_active, annee=annee,
        contexte="Declinaison regionale des orientations de la direction centrale.",
    )
    atelier = _activite(
        plan_antenne, axes["AX1"], "Atelier regional de production de fiches de lecture",
        aujourdhui - timedelta(days=75), aujourdhui - timedelta(days=65),
        type=Activite.Type.ATELIER, responsable=chef_actif,
        lieu=antenne_active.region.chef_lieu if antenne_active.region_id else "Region",
        public_cible="Enseignants du primaire", effectif_prevu=60, budget_prevu=4_500_000,
    )
    suivi = _activite(
        plan_antenne, axes["AX4"], "Suivi pedagogique des ecoles de la region",
        date(annee, 1, 20), aujourdhui - timedelta(days=6),
        type=Activite.Type.SUIVI, responsable=chef_actif,
        public_cible="Directeurs d'ecole", effectif_prevu=120, budget_prevu=3_000_000,
    )
    _activite(
        plan_antenne, axes["AX2"], "Journees pedagogiques du second cycle",
        aujourdhui + timedelta(days=20), aujourdhui + timedelta(days=24),
        type=Activite.Type.FORMATION, responsable=chef_actif,
        public_cible="Professeurs de lycee", effectif_prevu=90, budget_prevu=6_200_000,
    )
    soumettre_plan(plan_antenne, par=chef_actif)
    valider_plan(plan_antenne, par=directeur)
    enregistrer_avancement(
        atelier, chef_actif, 100, "Atelier tenu ; 240 fiches produites et diffusees.",
        effectif_touche=58, montant_engage=4_300_000, date=aujourdhui - timedelta(days=64),
    )
    atelier.indicateurs.create(
        libelle="Fiches de lecture produites", unite="fiches", valeur_cible=200, valeur_realisee=240
    )
    enregistrer_avancement(
        suivi, chef_actif, 40, "Quarante-huit ecoles visitees.",
        difficultes="Routes impraticables dans deux departements.",
        effectif_touche=48, montant_engage=1_250_000, date=aujourdhui - timedelta(days=15),
    )

    # --- 3. Antenne : plan soumis, en attente de validation -----------------
    if len(antennes) > 1:
        antenne_attente = antennes[1]
        chef_attente = antenne_attente.responsable
        plan_attente = PlanAction.objects.create(perimetre=antenne_attente, annee=annee)
        _activite(
            plan_attente, axes["AX2"], "Renforcement des capacites des directeurs d'ecole",
            aujourdhui + timedelta(days=15), aujourdhui + timedelta(days=25),
            type=Activite.Type.FORMATION, responsable=chef_attente,
            public_cible="Directeurs d'ecole", effectif_prevu=75, budget_prevu=5_800_000,
        )
        _activite(
            plan_attente, axes["AX4"], "Encadrement des enseignants nouvellement affectes",
            aujourdhui + timedelta(days=10), aujourdhui + timedelta(days=70),
            type=Activite.Type.SUIVI, responsable=chef_attente,
            effectif_prevu=140, budget_prevu=2_400_000,
        )
        soumettre_plan(plan_attente, par=chef_attente)

    # --- 4. Antenne : plan encore en preparation ----------------------------
    if len(antennes) > 2:
        antenne_brouillon = antennes[2]
        plan_brouillon = PlanAction.objects.create(perimetre=antenne_brouillon, annee=annee)
        _activite(
            plan_brouillon, axes["AX1"], "Revue des supports pedagogiques du prescolaire",
            aujourdhui + timedelta(days=35), aujourdhui + timedelta(days=46),
            type=Activite.Type.ELABORATION,
            responsable=antenne_brouillon.responsable,
            effectif_prevu=35, budget_prevu=3_100_000,
        )

    # --- 5. CNRPN : plan valide, production numerique -----------------------
    if cnrpn is not None and cnrpn.responsable is not None:
        chef_centre = cnrpn.responsable
        plan_cnrpn = PlanAction.objects.create(
            perimetre=cnrpn, annee=annee,
            contexte="Production et diffusion des ressources pedagogiques numeriques.",
        )
        capsules = _activite(
            plan_cnrpn, axes["AX3"], "Production de capsules video pour le secondaire",
            date(annee, 2, 15), aujourdhui + timedelta(days=45),
            type=Activite.Type.PRODUCTION, responsable=chef_centre,
            lieu="Abidjan", public_cible="Eleves et enseignants du secondaire",
            effectif_prevu=0, budget_prevu=21_000_000,
        )
        catalogue = _activite(
            plan_cnrpn, axes["AX3"], "Mise en ligne du catalogue national de ressources",
            date(annee, 4, 1), aujourdhui - timedelta(days=3),
            type=Activite.Type.PRODUCTION, responsable=chef_centre,
            effectif_prevu=0, budget_prevu=8_000_000,
        )
        soumettre_plan(plan_cnrpn, par=chef_centre)
        valider_plan(plan_cnrpn, par=directeur)
        enregistrer_avancement(
            capsules, chef_centre, 70, "Cent-quarante capsules produites et indexees.",
            montant_engage=14_500_000, date=aujourdhui - timedelta(days=25),
        )
        capsules.indicateurs.create(
            libelle="Capsules produites", unite="capsules", valeur_cible=200, valeur_realisee=140
        )
        enregistrer_avancement(
            catalogue, chef_centre, 65, "Catalogue en recette ; mise en ligne reportee.",
            difficultes="Attente de la validation des metadonnees par la direction.",
            montant_engage=5_100_000, date=aujourdhui - timedelta(days=10),
        )

    # --- 6. Exercice precedent clos, pour l'historique ----------------------
    precedent = annee - 1
    if not PlanAction.objects.filter(perimetre=centrale, annee=precedent).exists():
        plan_clos = PlanAction.objects.create(
            perimetre=centrale, annee=precedent,
            contexte="Exercice clos, conserve pour la comparaison interannuelle.",
        )
        achevee = _activite(
            plan_clos, axes["AX1"], "Elaboration des programmes educatifs du second cycle",
            date(precedent, 2, 1), date(precedent, 10, 31),
            type=Activite.Type.ELABORATION, responsable=directeur,
            effectif_prevu=50, budget_prevu=25_000_000,
        )
        inachevee = _activite(
            plan_clos, axes["AX2"], "Formation des formateurs en langues nationales",
            date(precedent, 6, 1), date(precedent, 12, 15),
            type=Activite.Type.FORMATION, responsable=directeur,
            effectif_prevu=80, budget_prevu=14_000_000,
        )
        soumettre_plan(plan_clos, par=directeur)
        valider_plan(plan_clos, par=directeur)
        enregistrer_avancement(
            achevee, directeur, 100, "Programmes elabores et valides.",
            effectif_touche=52, montant_engage=24_100_000, date=date(precedent, 10, 28),
        )
        enregistrer_avancement(
            inachevee, directeur, 75, "Trois sessions sur quatre tenues.",
            effectif_touche=60, montant_engage=10_500_000, date=date(precedent, 12, 10),
        )
        clore_plan(plan_clos, par=directeur)

    dire(
        f"  Plans d'action : {PlanAction.objects.count()} plan(s), "
        f"{Activite.objects.count()} activite(s)."
    )

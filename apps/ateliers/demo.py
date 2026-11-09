"""
Jeu de demonstration des ateliers.

Il couvre les situations que les ecrans doivent savoir montrer :

  - un atelier clos, entierement emarge, avec son compte rendu et son etat de
    paiement ;
  - un atelier en cours, a mi-parcours, avec des presences partielles et un
    emargement manuel motive ;
  - un atelier planifie, dont les badges restent a imprimer ;
  - un atelier d'antenne decoupe en demi-journees ;
  - un atelier annule.
"""
from datetime import timedelta

from django.utils import timezone

from apps.core.models import Perimetre

from .models import Atelier, Bareme, CompteRendu, Emargement, Participant
from .services import (
    annuler,
    clore,
    enregistrer_emargement,
    generer_sessions,
    ouvrir,
)

BAREMES = [
    ("INSP", "Inspecteur / encadreur", 30_000),
    ("CP", "Conseiller pedagogique", 25_000),
    ("ENS", "Enseignant", 15_000),
    ("APP", "Personnel d'appui", 10_000),
]

# Participants fictifs, pour les ateliers accueillant des personnes exterieures.
EXTERIEURS = [
    ("ADJOUA", "Kouame Felicite", "Enseignante", "EPP Sakassou 1", "ENS"),
    ("BAKAYOKO", "Souleymane", "Directeur d'ecole", "EPP Bouake Nord", "CP"),
    ("COULIBALY", "Mariam", "Conseillere pedagogique", "IEPP Bouake 2", "CP"),
    ("DIOMANDE", "Vamara", "Inspecteur", "IEPP Sakassou", "INSP"),
    ("ESSOH", "Ahou Carine", "Enseignante", "EPP Brobo", "ENS"),
    ("FOFANA", "Ibrahim", "Enseignant", "EPP Diabo", "ENS"),
    ("GNAMIEN", "Kouassi Serge", "Directeur d'ecole", "EPP Botro", "CP"),
    ("HIEN", "Sansan Paul", "Enseignant", "EPP Beoumi", "ENS"),
    ("IRIE", "Lou Marcelle", "Secretaire", "IEPP Bouake 1", "APP"),
    ("JOHNSON", "Akissi Prisca", "Enseignante", "EPP Bouake Sud", "ENS"),
    ("KOFFI", "Yao Michel", "Conseiller pedagogique", "IEPP Beoumi", "CP"),
    ("LOUKOU", "N'Guessan Eric", "Enseignant", "EPP Sakassou 2", "ENS"),
]


def installer_baremes():
    baremes = {}
    for code, libelle, montant in BAREMES:
        bareme, _ = Bareme.objects.get_or_create(
            code=code, defaults={"libelle": libelle, "montant_journalier": montant}
        )
        baremes[code] = bareme
    return baremes


def _inscrire_exterieurs(atelier, baremes, nombre, decalage=0, par=None):
    crees = []
    for nom, prenoms, fonction, structure, categorie in EXTERIEURS[decalage:decalage + nombre]:
        crees.append(
            Participant.objects.create(
                atelier=atelier, nom=nom, prenoms=prenoms, fonction=fonction,
                structure_origine=structure, categorie=baremes[categorie],
                provenance=structure.split()[-1], inscrit_par=par,
            )
        )
    return crees


def _inscrire_agents(atelier, agents, bareme, par=None):
    crees = []
    for agent in agents:
        crees.append(
            Participant.objects.create(
                atelier=atelier, agent=agent, nom="", categorie=bareme, inscrit_par=par
            )
        )
    return crees


def charger(stdout=None):
    """Construit le jeu de demonstration. Sans effet s'il existe deja."""
    def dire(message):
        if stdout is not None:
            stdout.write(message)

    baremes = installer_baremes()

    if Atelier.objects.exists():
        dire("  Ateliers deja presents : inchanges.")
        return

    centrale = Perimetre.centrale()
    antennes = list(Perimetre.objects.filter(type=Perimetre.Type.ANTENNE).order_by("code"))
    if centrale is None or centrale.responsable is None or not antennes:
        dire("  Organisation incomplete : ateliers de demonstration ignores.")
        return

    directeur = centrale.responsable
    agents_centraux = list(centrale.agents().exclude(pk=directeur.pk)[:4])
    aujourdhui = timezone.localdate()

    # --- 1. Atelier clos, entierement emarge -------------------------------
    clos = Atelier.objects.create(
        perimetre=centrale, intitule="Atelier de validation des guides d'execution du primaire",
        type=Atelier.Type.ATELIER, lieu="Grand-Bassam",
        date_debut=aujourdhui - timedelta(days=40), date_fin=aujourdhui - timedelta(days=38),
        public_cible="Concepteurs de programmes et inspecteurs",
        budget=12_000_000, organisateur=directeur,
        ordre_du_jour="Revue des guides du CP au CM2, harmonisation des progressions, "
                      "validation des situations d'apprentissage.",
    )
    generer_sessions(clos)
    participants_clos = _inscrire_exterieurs(clos, baremes, 8, par=directeur)
    participants_clos += _inscrire_agents(clos, agents_centraux[:2], baremes["INSP"], directeur)
    ouvrir(clos, directeur)
    sessions_closes = list(clos.sessions.all())
    for session in sessions_closes:
        for participant in participants_clos:
            enregistrer_emargement(
                session, participant, directeur,
                horodatage=timezone.now() - timedelta(days=40), appareil="tablette-01",
            )
    CompteRendu.objects.create(
        atelier=clos,
        contenu="Les guides d'execution du CP au CM2 ont ete passes en revue puis valides. "
                "Les participants ont harmonise les progressions annuelles et arrete la "
                "presentation des situations d'apprentissage.",
        decisions="Diffusion des guides valides aux antennes regionales avant la rentree. "
                  "Constitution d'une equipe de relecture pour le secondaire.",
        recommandations="Prevoir une session de restitution dans chaque antenne.",
        redige_par=directeur,
    )
    clore(clos, directeur)

    # --- 2. Atelier en cours, presences partielles --------------------------
    en_cours = Atelier.objects.create(
        perimetre=centrale, intitule="Formation des conseillers pedagogiques au numerique",
        type=Atelier.Type.FORMATION, lieu="Abidjan",
        date_debut=aujourdhui - timedelta(days=1), date_fin=aujourdhui + timedelta(days=1),
        public_cible="Conseillers pedagogiques", budget=8_500_000, organisateur=directeur,
        ordre_du_jour="Prise en main des ressources numeriques et scenarisation des sequences.",
    )
    generer_sessions(en_cours)
    participants_cours = _inscrire_exterieurs(en_cours, baremes, 6, decalage=4, par=directeur)
    if agents_centraux:
        en_cours.controleurs.add(agents_centraux[0])
    ouvrir(en_cours, directeur)
    hier, ce_jour = list(en_cours.sessions.all())[:2]
    # La veille, tout le monde etait la.
    for participant in participants_cours:
        enregistrer_emargement(
            hier, participant, directeur, horodatage=timezone.now() - timedelta(days=1)
        )
    # Aujourd'hui, quatre sur six, dont un emargement manuel motive.
    for participant in participants_cours[:3]:
        enregistrer_emargement(ce_jour, participant, directeur, appareil="tablette-02")
    enregistrer_emargement(
        ce_jour, participants_cours[3], directeur,
        mode=Emargement.Mode.MANUEL,
        motif="Badge oublie a l'hotel, identite verifiee sur piece.",
    )

    # --- 3. Atelier planifie, badges a imprimer -----------------------------
    planifie = Atelier.objects.create(
        perimetre=centrale, intitule="Seminaire bilan de fin d'exercice",
        type=Atelier.Type.SEMINAIRE, lieu="Yamoussoukro",
        date_debut=aujourdhui + timedelta(days=30), date_fin=aujourdhui + timedelta(days=32),
        public_cible="Chefs d'antenne et sous-directeurs", budget=9_000_000,
        organisateur=directeur,
    )
    generer_sessions(planifie)
    chefs = [p.responsable for p in antennes if p.responsable is not None]
    _inscrire_agents(planifie, chefs[:6], baremes["INSP"], directeur)

    # --- 4. Atelier d'antenne, decoupe en demi-journees ---------------------
    antenne = antennes[0]
    chef = antenne.responsable
    if chef is not None:
        regional = Atelier.objects.create(
            perimetre=antenne, intitule="Journee pedagogique des directeurs d'ecole",
            type=Atelier.Type.JOURNEE,
            lieu=antenne.region.chef_lieu if antenne.region_id else "Region",
            date_debut=aujourdhui - timedelta(days=7), date_fin=aujourdhui - timedelta(days=7),
            public_cible="Directeurs d'ecole", budget=1_800_000, organisateur=chef,
        )
        generer_sessions(regional, creneaux_par_jour=2)
        participants_regionaux = _inscrire_exterieurs(regional, baremes, 5, decalage=6, par=chef)
        ouvrir(regional, chef)
        matin, apres_midi = list(regional.sessions.all())
        for participant in participants_regionaux:
            enregistrer_emargement(
                matin, participant, chef, horodatage=timezone.now() - timedelta(days=7)
            )
        # Deux participants sont repartis apres le dejeuner.
        for participant in participants_regionaux[:3]:
            enregistrer_emargement(
                apres_midi, participant, chef, horodatage=timezone.now() - timedelta(days=7)
            )
        clore(regional, chef)

    # --- 5. Atelier annule ---------------------------------------------------
    annule = Atelier.objects.create(
        perimetre=centrale, intitule="Atelier d'elaboration des supports en langues nationales",
        type=Atelier.Type.ATELIER, lieu="Abidjan",
        date_debut=aujourdhui + timedelta(days=15), date_fin=aujourdhui + timedelta(days=17),
        budget=6_000_000, organisateur=directeur,
    )
    generer_sessions(annule)
    annuler(annule, directeur, "Report a l'exercice suivant faute de financement disponible.")

    dire(
        f"  Ateliers : {Atelier.objects.count()} atelier(s), "
        f"{Participant.objects.count()} participant(s), "
        f"{Emargement.objects.count()} emargement(s)."
    )

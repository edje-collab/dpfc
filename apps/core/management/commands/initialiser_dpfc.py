"""
Jeu de donnees initial du portail : organisation, comptes de demonstration
et contenus editoriaux. Ne remplace jamais un enregistrement existant.

    python manage.py initialiser_dpfc
    python manage.py initialiser_dpfc --demo   (ajoute des demandes d'exemple)
"""
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.circuits.modeles import installer_circuits_modeles
from apps.core.models import ConfigurationSite, Perimetre, Region, Structure
from apps.rh.models import JourFerie, SoldeConge, TypeDemande
from apps.site_public import arborescence
from apps.site_public.models import PageEvenement, Ressource

Agent = get_user_model()

REGIONS = [
    ("Abidjan", "ABJ", "Abidjan", "DRENA Abidjan 1"),
    ("Gbeke", "GBK", "Bouake", "DRENA Bouake 1"),
    ("Poro", "PORO", "Korhogo", "DRENA Korhogo"),
    ("Haut-Sassandra", "HSA", "Daloa", "DRENA Daloa"),
    ("Gontougo", "GTG", "Bondoukou", "DRENA Bondoukou"),
    ("Bas-Sassandra", "BSA", "San-Pedro", "DRENA San-Pedro"),
    ("Yamoussoukro", "YAM", "Yamoussoukro", "DRENA Yamoussoukro"),
    ("Indenie-Djuablin", "IDJ", "Abengourou", "DRENA Abengourou"),
]

# Titulaires des postes regionaux, un par region : chaque perimetre a son chef.
DIRECTEURS_REGIONAUX = {
    "ABJ": ("ASSAMOI", "Kouassi Bertin"), "GBK": ("ADJOUMANI", "Kouadio"),
    "PORO": ("TOURE", "Lassina"), "HSA": ("GBAGBO", "Marius"),
    "GTG": ("KOFFI", "Yao Daniel"), "BSA": ("DAGO", "Honore"),
    "YAM": ("N'DRI", "Konan Paul"), "IDJ": ("ANOH", "Amenan Rose"),
}
CHEFS_ANTENNE = {
    "ABJ": ("KACOU", "Marie-Louise"), "GBK": ("KONE", "Adama"),
    "PORO": ("SORO", "Nabintou"), "HSA": ("ZIE", "Gnepa Olivier"),
    "GTG": ("OUATTARA", "Salimata"), "BSA": ("TANOH", "Kouame Felix"),
    "YAM": ("BROU", "Akissi Georgette"), "IDJ": ("YEBOUE", "Kouadio Armand"),
}
SECRETAIRES = {
    "ABJ": ("ABLE", "Aya Chantal"), "GBK": ("KOUASSI", "Akissi"),
    "PORO": ("SILUE", "Awa"), "HSA": ("GOUE", "Bleu Alphonse"),
    "GTG": ("KONAN", "Ama Julienne"), "BSA": ("DJE", "Bi Tra"),
    "YAM": ("AKA", "Affoue Prisca"), "IDJ": ("MEL", "Ahou Nadege"),
}
CONSEILLERS = {
    "ABJ": ("DOUMBIA", "Moussa"), "GBK": ("OUATTARA", "Fatoumata"),
    "PORO": ("COULIBALY", "Seydou"), "HSA": ("IRIE", "Lou Pauline"),
    "GTG": ("KAMAGATE", "Vakaba"), "BSA": ("GNAGNE", "Seri Patrice"),
    "YAM": ("KOUAKOU", "Yao Thierry"), "IDJ": ("ADOU", "Kouassi Landry"),
}

# Sous-directions de la DPFC, article 28 du decret n° 2026-509 du 05 aout 2026.
SOUS_DIRECTIONS = [
    ("Sous-direction des Programmes Pedagogiques et des Bibliotheques Scolaires", "SDPPBS"),
    ("Sous-direction des Innovations Pedagogiques", "SDIP"),
    ("Sous-direction de la Formation Pedagogique Continue", "SDFPC"),
]

# Services d'appui de la direction, crees par arrete d'organisation.
SERVICES_APPUI = [
    ("Service du personnel et des affaires administratives", "SPAA"),
]


class Command(BaseCommand):
    help = "Initialise l'organisation, les comptes et les contenus du portail DPFC."

    def add_arguments(self, parseur):
        parseur.add_argument("--demo", action="store_true", help="Ajoute des demandes de demonstration.")

    def handle(self, *args, **options):
        self.stdout.write("Initialisation du portail DPFC...")
        config = ConfigurationSite.actuelle()
        config.save()

        regions = {}
        for nom, code, chef_lieu, dren in REGIONS:
            region, _ = Region.objects.get_or_create(
                code=code, defaults={"nom": nom, "chef_lieu": chef_lieu, "dren": dren}
            )
            regions[code] = region

        # --- Perimetres de gestion -----------------------------------------
        # La direction centrale, chaque antenne et le CNRPN instruisent et
        # numerotent leurs propres actes.
        perimetre_central, _ = Perimetre.objects.get_or_create(
            code="DPFC",
            defaults={
                "nom": "Direction de la Pedagogie et de la Formation Continue",
                "type": Perimetre.Type.CENTRALE,
            },
        )

        # --- Direction generale de rattachement (article 27) ---------------
        direction_generale, _ = Structure.objects.get_or_create(
            sigle="DGPCSP",
            defaults={
                "nom": "Direction Generale de la Pedagogie, des Curricula et du Suivi des Programmes",
                "type": Structure.Type.DIRECTION_GENERALE,
                "rattachement": Structure.Rattachement.CENTRALE,
                "perimetre": perimetre_central,
                "ordre": 1,
                "email": "dgpcsp@education.ci",
                "presentation": (
                    "Direction generale chargee de la politique nationale en matiere de pedagogie, "
                    "de curricula et de suivi des programmes d'enseignement."
                ),
            },
        )

        direction, _ = Structure.objects.get_or_create(
            sigle="DPFC",
            defaults={
                "nom": "Direction de la Pedagogie et de la Formation Continue",
                "type": Structure.Type.DIRECTION,
                "rattachement": Structure.Rattachement.CENTRALE,
                "parent": direction_generale,
                "perimetre": perimetre_central,
                "perimetre_racine": True,
                "ordre": 1,
                "adresse": "Cocody II Plateaux, Abidjan",
                "telephone": "+225 27 22 41 00 00",
                "email": "contact@dpfc.education.ci",
                "presentation": (
                    "Direction centrale chargee des activites pedagogiques du prescolaire, du primaire "
                    "et du secondaire general, et de la formation continue des personnels enseignants "
                    "et d'encadrement pedagogique."
                ),
            },
        )

        centrales = {}
        for ordre, (nom, sigle) in enumerate(SOUS_DIRECTIONS, start=1):
            structure, _ = Structure.objects.get_or_create(
                sigle=sigle,
                defaults={
                    "nom": nom,
                    "type": Structure.Type.SOUS_DIRECTION,
                    "rattachement": Structure.Rattachement.CENTRALE,
                    "parent": direction,
                    "perimetre": perimetre_central,
                    "ordre": ordre,
                    "email": f"{sigle.lower()}@dpfc.education.ci",
                },
            )
            centrales[sigle] = structure

        for ordre, (nom, sigle) in enumerate(SERVICES_APPUI, start=10):
            structure, _ = Structure.objects.get_or_create(
                sigle=sigle,
                defaults={
                    "nom": nom,
                    "type": Structure.Type.SERVICE,
                    "rattachement": Structure.Rattachement.CENTRALE,
                    "parent": direction,
                    "perimetre": perimetre_central,
                    "ordre": ordre,
                    "email": f"{sigle.lower()}@dpfc.education.ci",
                },
            )
            centrales[sigle] = structure

        # --- CNRPN : service rattache, gestion autonome --------------------
        perimetre_cnrpn, _ = Perimetre.objects.get_or_create(
            code="CNRPN",
            defaults={
                "nom": "Centre National de Ressources Pedagogiques Numeriques",
                "type": Perimetre.Type.CENTRE,
            },
        )
        cnrpn, _ = Structure.objects.get_or_create(
            sigle="CNRPN",
            defaults={
                "nom": "Centre National de Ressources Pedagogiques Numeriques",
                "type": Structure.Type.CENTRE,
                "rattachement": Structure.Rattachement.CENTRALE,
                "parent": direction,
                "perimetre": perimetre_cnrpn,
                "perimetre_racine": True,
                "ordre": 20,
                "adresse": "Abidjan",
                "email": "cnrpn@dpfc.education.ci",
                "presentation": (
                    "Service rattache a la direction, charge de la production et de la diffusion des "
                    "ressources pedagogiques numeriques. Sa gestion est assuree par un chef de centre."
                ),
            },
        )
        centrales["CNRPN"] = cnrpn

        # --- Services exterieurs du ministere (article 41) -----------------
        drenas = {}
        for code, region in regions.items():
            drena, _ = Structure.objects.get_or_create(
                sigle=f"DRENA-{code}",
                defaults={
                    "nom": f"Direction Regionale de l'Education Nationale et de l'Alphabetisation "
                           f"de {region.chef_lieu}",
                    "type": Structure.Type.DRENA,
                    "rattachement": Structure.Rattachement.REGION,
                    "region": region,
                    "adresse": f"{region.chef_lieu}, {region.nom}",
                    "email": f"drena.{code.lower()}@education.ci",
                },
            )
            drenas[code] = drena

        # --- Antennes regionales : un perimetre autonome chacune -----------
        antennes = {}
        for code, region in regions.items():
            perimetre_antenne, _ = Perimetre.objects.get_or_create(
                code=f"APFC-{code}",
                defaults={
                    "nom": f"Antenne de la Pedagogie et de la Formation Continue de {region.chef_lieu}",
                    "type": Perimetre.Type.ANTENNE,
                    "region": region,
                },
            )
            antenne, _ = Structure.objects.get_or_create(
                sigle=f"APFC-{code}",
                defaults={
                    "drena": drenas[code],
                    "nom": f"Antenne de la Pedagogie et de la Formation Continue de {region.chef_lieu}",
                    "type": Structure.Type.ANTENNE,
                    "rattachement": Structure.Rattachement.REGION,
                    "parent": direction,
                    "perimetre": perimetre_antenne,
                    "perimetre_racine": True,
                    "region": region,
                    "adresse": f"{region.chef_lieu}, {region.nom}",
                    "telephone": "+225 27 00 00 00 00",
                    "email": f"apfc.{code.lower()}@dpfc.education.ci",
                    "presentation": (
                        f"L'antenne de {region.chef_lieu} encadre les enseignants de la region "
                        f"{region.nom} et relaie les orientations de la direction centrale. "
                        f"Sa gestion est autonome, sous l'autorite d'un chef d'antenne."
                    ),
                },
            )
            antennes[code] = antenne

        # --- Circuits de validation ----------------------------------------
        installer_circuits_modeles()

        # --- Comptes -------------------------------------------------------
        def creer(matricule, nom, prenoms, role, structure, fonction, superieur=None, grade="Inspecteur"):
            agent, cree = Agent.objects.get_or_create(
                matricule=matricule,
                defaults={
                    "last_name": nom,
                    "first_name": prenoms,
                    "role": role,
                    "structure": structure,
                    "fonction": fonction,
                    "grade": grade,
                    "email": f"{prenoms.split()[0].lower()}.{nom.lower()}@dpfc.education.ci",
                    "telephone": "+225 07 00 00 00 00",
                    "superieur": superieur,
                    "date_prise_service": date(2019, 10, 1),
                    "doit_changer_mot_de_passe": True,
                },
            )
            if cree:
                agent.set_password(matricule)
                agent.save()
                SoldeConge.pour(agent)
            return agent

        directeur = creer("100001D", "KOUAME", "Ahou Sylvie", Agent.Role.DIRECTEUR, direction,
                          "Directrice de la pedagogie et de la formation continue", grade="Inspecteur general")
        rh = creer("100002R", "TRAORE", "Ibrahim", Agent.Role.RH, centrales["SPAA"],
                   "Chef du service du personnel", directeur, grade="Administrateur")
        sous_directeur = creer("100003S", "BAMBA", "Aminata", Agent.Role.SOUS_DIRECTEUR, centrales["SDFPC"],
                               "Sous-directrice de la formation pedagogique continue", directeur)
        sd_innovations = creer("100007S", "KOUADIO", "Eric", Agent.Role.SOUS_DIRECTEUR, centrales["SDIP"],
                               "Sous-directeur des innovations pedagogiques", directeur)
        sd_programmes = creer("100008S", "GNAMIEN", "Affoue", Agent.Role.SOUS_DIRECTEUR, centrales["SDPPBS"],
                              "Sous-directrice des programmes pedagogiques et des bibliotheques scolaires",
                              directeur)
        chef_service = creer("100004C", "N'GORAN", "Koffi Evariste", Agent.Role.CHEF_SERVICE, centrales["SDFPC"],
                             "Chef de service", sous_directeur)
        creer("100005A", "DIALLO", "Mariam", Agent.Role.AGENT, centrales["SDIP"],
              "Chargee d'etudes - innovations pedagogiques", sd_innovations, grade="Professeur")
        creer("100006A", "YAO", "Serge", Agent.Role.AGENT, centrales["SDPPBS"],
              "Charge d'etudes - programmes", sd_programmes, grade="Professeur")

        # CNRPN : perimetre autonome dirige par un chef de centre.
        chef_centre = creer("400001N", "ZADI", "Gnagne Hubert", Agent.Role.CHEF_CENTRE, cnrpn,
                            "Chef du centre national de ressources pedagogiques numeriques",
                            directeur, grade="Inspecteur")
        creer("400002N", "AKA", "Esther", Agent.Role.AGENT, cnrpn,
              "Chargee de production de ressources numeriques", chef_centre, grade="Professeur")

        # Chaque DRENA et chaque antenne recoivent leur responsable : aucun
        # perimetre ne doit rester sans autorite capable de decider.
        directeurs_regionaux, chefs_antenne = {}, {}
        for rang, (code, region) in enumerate(regions.items(), start=1):
            dr = creer(
                f"3000{rang:02d}R", DIRECTEURS_REGIONAUX[code][0], DIRECTEURS_REGIONAUX[code][1],
                Agent.Role.DIRECTEUR_REGIONAL, drenas[code],
                f"Directeur regional de {region.chef_lieu}", grade="Inspecteur general",
            )
            directeurs_regionaux[code] = dr
            chef = creer(
                f"2000{rang:02d}C", CHEFS_ANTENNE[code][0], CHEFS_ANTENNE[code][1],
                Agent.Role.CHEF_ANTENNE, antennes[code],
                f"Chef de l'antenne de {region.chef_lieu}", dr,
            )
            chefs_antenne[code] = chef
            creer(
                f"2000{rang:02d}S", SECRETAIRES[code][0], SECRETAIRES[code][1],
                Agent.Role.SECRETARIAT, antennes[code],
                "Secretaire de l'antenne", chef, grade="Secretaire administratif",
            )
            creer(
                f"2000{rang:02d}A", CONSEILLERS[code][0], CONSEILLERS[code][1],
                Agent.Role.AGENT, antennes[code],
                "Conseiller pedagogique", chef, grade="Conseiller pedagogique",
            )
        dr_bouake = directeurs_regionaux["GBK"]
        dr_korhogo = directeurs_regionaux["PORO"]
        chef_bouake = chefs_antenne["GBK"]
        chef_korhogo = chefs_antenne["PORO"]

        direction.responsable = directeur
        direction.save()
        centrales["SDFPC"].responsable = sous_directeur
        centrales["SDFPC"].save()
        centrales["SDIP"].responsable = sd_innovations
        centrales["SDIP"].save()
        centrales["SDPPBS"].responsable = sd_programmes
        centrales["SDPPBS"].save()
        centrales["SPAA"].responsable = rh
        centrales["SPAA"].save()
        cnrpn.responsable = chef_centre
        cnrpn.save()
        for code, antenne in antennes.items():
            antenne.responsable = chefs_antenne[code]
            if antenne.drena_id is None:
                antenne.drena = drenas[code]
            antenne.save(update_fields=["responsable", "drena"])
            drenas[code].responsable = directeurs_regionaux[code]
            drenas[code].save(update_fields=["responsable"])

        if not Agent.objects.filter(is_superuser=True).exists():
            admin = Agent.objects.create_superuser("ADMIN01", "admin@dpfc.education.ci", "dpfc2026!")
            admin.last_name, admin.first_name = "ADMINISTRATEUR", "Portail"
            admin.structure = direction
            admin.fonction = "Administrateur du portail"
            admin.save()
            self.stdout.write("  Compte administrateur : ADMIN01 / dpfc2026!")

        # --- Jours feries ---------------------------------------------------
        annee = timezone.localdate().year
        for jour, libelle in [
            ((1, 1), "Jour de l'an"), ((5, 1), "Fete du travail"),
            ((8, 7), "Fete nationale"), ((11, 15), "Journee nationale de la paix"),
            ((12, 25), "Noel"),
        ]:
            JourFerie.objects.get_or_create(date=date(annee, *jour), defaults={"libelle": libelle})

        # --- Site public (Wagtail) -----------------------------------------
        pages = arborescence.assurer_site()
        categories = {}
        for nom, couleur in [("Vie de la direction", "#14958a"), ("Formation", "#4cbb6d"),
                             ("Programmes", "#f0a83c"), ("Partenariats", "#4ec3e8")]:
            categories[nom] = arborescence.ajouter_categorie(nom, couleur)

        actualites = [
            ("Validation des guides d'execution du primaire",
             "Les guides revises ont ete valides au terme d'un atelier de quatre jours.",
             "Vie de la direction",
             "Reunis en atelier, les concepteurs et les inspecteurs ont passe en revue les guides d'execution "
             "des programmes du primaire. Les versions validees seront diffusees aux antennes regionales "
             "puis mises en ligne sur ce portail."),
            ("Formation des conseillers pedagogiques au numerique educatif",
             "Deux cents conseillers formes a l'usage des ressources numeriques en classe.",
             "Formation",
             "La session a porte sur la scenarisation des sequences, la prise en main des ressources "
             "numeriques et l'accompagnement des enseignants dans les ecoles."),
            ("Nouvelle convention avec un partenaire technique",
             "Un appui est apporte a la production de ressources pedagogiques.",
             "Partenariats",
             "La convention prevoit la production de supports pedagogiques et le renforcement des capacites "
             "des equipes de la direction et des antennes."),
        ]
        for i, (titre, chapeau, categorie, contenu) in enumerate(actualites):
            arborescence.ajouter_actualite(
                pages["actualites"], titre, chapeau, f"<p>{contenu}</p>",
                categorie=categories[categorie], a_la_une=i == 0, auteur=chef_service,
                date_publication=timezone.now() - timedelta(days=3 * i + 1),
            )

        ressources = [
            ("Programme educatif de francais - CP1", Ressource.Type.PROGRAMME, Ressource.Niveau.PRIMAIRE, "Francais", "CP1"),
            ("Programme educatif de mathematiques - CM2", Ressource.Type.PROGRAMME, Ressource.Niveau.PRIMAIRE, "Mathematiques", "CM2"),
            ("Guide d'execution - sciences de la vie et de la terre 6e", Ressource.Type.GUIDE, Ressource.Niveau.SECONDAIRE_1, "SVT", "6e"),
            ("Fiche de travaux pratiques - physique-chimie 2nde", Ressource.Type.FICHE_TP, Ressource.Niveau.SECONDAIRE_2, "Physique-Chimie", "2nde"),
            ("Module de formation - evaluation par competences", Ressource.Type.MODULE, Ressource.Niveau.TOUS, "Pedagogie", ""),
            ("Arrete portant organisation de la formation continue", Ressource.Type.TEXTE, Ressource.Niveau.TOUS, "Textes", ""),
        ]
        for titre, type_, niveau, discipline, classe in ressources:
            arborescence.ajouter_ressource(
                titre, type=type_, niveau=niveau, discipline=discipline, classe=classe, annee=annee,
                description=f"{titre}. Document officiel diffuse par la direction.", publiee=True,
            )

        projets = [
            ("Systeme d'information pour la gestion de l'education", "SIGE", "#14958a", "sigle",
             "Collecte et exploitation des donnees du systeme educatif."),
            ("Programme national d'amelioration des pratiques d'apprentissage scolaire", "PNAPAS", "#4cbb6d", "reseau",
             "Renforcement des pratiques de classe et de l'encadrement de proximite."),
            ("Formation ouverte et a distance", "FOAD", "#f0a83c", "ecran",
             "Modules en ligne pour la formation continue des enseignants."),
            ("Centre national de ressources pedagogiques numeriques", "CNRPN", "#4ec3e8", "livre",
             "Production et diffusion des ressources pedagogiques numeriques."),
        ]
        for i, (nom, sigle, couleur, icone, accroche) in enumerate(projets):
            arborescence.ajouter_projet(
                pages["projets"], sigle, nom, accroche,
                f"<p>{accroche} Le projet est pilote par la direction, en lien avec les antennes regionales.</p>",
                couleur=couleur, icone=icone, ordre=i + 1,
                objectifs="<p>Renforcer la qualite des apprentissages et l'encadrement pedagogique.</p>",
            )

        aujourdhui = timezone.localdate()
        evenements = [
            ("Atelier de conception des fiches de lecture", PageEvenement.Type.ATELIER, 12, "Abidjan", "Concepteurs de programmes"),
            ("Session de formation des enseignants du prescolaire", PageEvenement.Type.FORMATION, 25, "Bouake", "Enseignants du prescolaire"),
            ("Seminaire des chefs d'antenne", PageEvenement.Type.SEMINAIRE, 40, "Yamoussoukro", "Chefs d'antenne"),
        ]
        for titre, type_, delta, lieu, cible in evenements:
            arborescence.ajouter_evenement(
                pages["evenements"], titre, aujourdhui + timedelta(days=delta),
                f"{titre}. Les modalites de participation sont communiquees aux structures concernees.",
                type=type_, date_fin=aujourdhui + timedelta(days=delta + 2), lieu=lieu, public_cible=cible,
            )

        # --- Pilotage : axes strategiques et plans d'action ----------------
        from apps.activites.demo import charger as charger_pilotage
        from apps.activites.demo import installer_axes

        installer_axes()
        if options["demo"]:
            charger_pilotage(stdout=self.stdout)

        if options["demo"]:
            self._cles_de_signature([directeur, chef_bouake, chef_korhogo, dr_bouake, dr_korhogo])
            self._demandes_demo()

        self.stdout.write(self.style.SUCCESS("Initialisation terminee."))
        self.stdout.write("  Comptes de demonstration : le mot de passe initial est le matricule.")
        self.stdout.write(
            "  100001D directrice | 100002R personnel | 100003S sous-directrice | 100004C chef de service\n"
            "  200002C chef d'antenne Bouake | 200002S secretariat | 200002A conseiller\n"
            "  400001N chef de centre CNRPN | 400002N agent CNRPN\n"
            "  300002R directeur regional DRENA Bouake\n"
            "  Chaque antenne a son chef, son secretariat et son conseiller "
            "(suffixes C, S et A)."
        )

    def _cles_de_signature(self, signataires):
        """Bi-cles de demonstration pour les autorites signataires (code : signature2026)."""
        from apps.signature.services import creer_cle

        for agent in signataires:
            if agent is not None and not hasattr(agent, "cle_signature"):
                creer_cle(agent, "signature2026")
        self.stdout.write("  Cles de signature de demonstration creees (code : signature2026).")

    def _demandes_demo(self):
        from apps.rh.models import Demande
        from apps.rh.services import decider, soumettre

        agent = Agent.objects.filter(matricule="200002B").first()
        auteur_central = Agent.objects.filter(matricule="100005A").first()
        if agent is None or Demande.objects.exists():
            return
        aujourdhui = timezone.localdate()

        conge = Demande.objects.create(
            agent=agent, type=TypeDemande.CONGE_ANNUEL,
            motif="Conge annuel au titre de l'annee en cours.",
            date_debut=aujourdhui + timedelta(days=20), date_fin=aujourdhui + timedelta(days=34),
            lieu_jouissance="Bouake", contact_pendant_absence="+225 07 11 22 33 44",
        )
        soumettre(conge)

        secretaire = Agent.objects.filter(matricule="200005B").first()
        mission_hors = Demande.objects.create(
            agent=agent, type=TypeDemande.ORDRE_MISSION, depose_par=secretaire,
            motif="Participation a un atelier national de conception de ressources.",
            date_debut=aujourdhui + timedelta(days=12), date_fin=aujourdhui + timedelta(days=15),
            destination="Abidjan", moyen_transport="Transport en commun",
            hors_perimetre_drena=True,
            structures_visitees="Direction de la Pedagogie et de la Formation Continue",
        )
        mission_hors.termes_de_reference.save(
            "tdr-atelier.txt",
            ContentFile(b"Termes de reference de l'atelier national (document de demonstration)."),
            save=False,
        )
        mission_hors.lettre_invitation.save(
            "invitation-atelier.txt",
            ContentFile(b"Lettre d'invitation a l'atelier national (document de demonstration)."),
            save=True,
        )
        soumettre(mission_hors)

        mission = Demande.objects.create(
            agent=auteur_central, type=TypeDemande.ORDRE_MISSION,
            motif="Suivi du deploiement des ressources numeriques dans les ecoles pilotes.",
            date_debut=aujourdhui + timedelta(days=5), date_fin=aujourdhui + timedelta(days=8),
            destination="Korhogo", moyen_transport="Vehicule de service",
            structures_visitees="Antenne de Korhogo, ecoles pilotes",
        )
        soumettre(mission)
        etape = mission.etape_courante()
        if etape:
            decider(etape, True, "Mission conforme au programme d'activites.")

        Demande.objects.create(
            agent=auteur_central, type=TypeDemande.PERMISSION,
            motif="Demarche administrative personnelle.",
            date_debut=aujourdhui + timedelta(days=2), date_fin=aujourdhui + timedelta(days=2),
        )
        self.stdout.write("  Demandes de demonstration creees.")

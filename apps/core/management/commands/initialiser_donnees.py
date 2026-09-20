"""
Jeu de donnees de demonstration : organisation, comptes agents et contenus.

    python manage.py initialiser_donnees

Tous les comptes crees ont pour mot de passe leur matricule.
"""
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.core.models import ConfigurationSite, Region, Structure
from apps.site_public import arborescence
from apps.site_public.models import PageActualite, PageEvenement, PageProjet, Ressource
from apps.rh.models import Demande, JourFerie, SoldeConge, TypeDemande
from apps.rh.services import decider, soumettre

Agent = get_user_model()

REGIONS = [
    ("Abidjan", "AB", "Abidjan"),
    ("Gbeke", "GB", "Bouake"),
    ("Poro", "PO", "Korhogo"),
    ("Haut-Sassandra", "HS", "Daloa"),
    ("Gôh", "GO", "Gagnoa"),
    ("Indenie-Djuablin", "ID", "Abengourou"),
    ("Tonkpi", "TO", "Man"),
    ("Bas-Sassandra", "BS", "San-Pedro"),
    ("Belier", "BE", "Yamoussoukro"),
    ("Gontougo", "GT", "Bondoukou"),
]


class Command(BaseCommand):
    help = "Charge un jeu de donnees complet pour la demonstration du portail."

    def add_arguments(self, parser):
        parser.add_argument("--vider", action="store_true", help="Supprime les donnees existantes.")

    @transaction.atomic
    def handle(self, *args, **options):
        if options["vider"]:
            Demande.objects.all().delete()
            SoldeConge.objects.all().delete()
            Agent.objects.filter(is_superuser=False).delete()
            Structure.objects.all().delete()
            Region.objects.all().delete()
            PageActualite.objects.all().delete()
            PageProjet.objects.all().delete()
            PageEvenement.objects.all().delete()
            Ressource.objects.all().delete()
            self.stdout.write("Donnees precedentes supprimees.")

        self.configurer_site()
        regions = self.creer_regions()
        centrale, services, antennes = self.creer_structures(regions)
        agents = self.creer_agents(centrale, services, antennes)
        self.creer_contenus(antennes, agents)
        self.creer_jours_feries()
        self.creer_demandes(agents)
        self.stdout.write(self.style.SUCCESS("\nJeu de donnees installe."))
        self.stdout.write(
            "\nComptes de demonstration (mot de passe = matricule) :\n"
            "  DIR001  directeur\n"
            "  SD001   sous-directeur\n"
            "  CS001   chef de service (central)\n"
            "  RH001   service du personnel\n"
            "  AG001   agent au central\n"
            "  CA002   chef de l'antenne de Bouake\n"
            "  AG010   agent de l'antenne de Bouake\n"
        )

    # ------------------------------------------------------------------
    def configurer_site(self):
        ConfigurationSite.actuelle().save()
        self.pages = arborescence.assurer_site()
        accueil = self.pages["accueil"]
        accueil.slogan = "Oeuvrons pour une ecole ivoirienne de qualite"
        accueil.sous_titre = (
            "Programmes educatifs, guides d'execution et formation continue "
            "au service des enseignants de Cote d'Ivoire."
        )
        accueil.save_revision().publish()

    def creer_regions(self):
        regions = {}
        for nom, code, chef_lieu in REGIONS:
            region, _ = Region.objects.get_or_create(
                code=code,
                defaults={"nom": nom, "chef_lieu": chef_lieu, "dren": f"DRENA de {chef_lieu}"},
            )
            regions[code] = region
        self.stdout.write(f"{len(regions)} regions enregistrees.")
        return regions

    def creer_structures(self, regions):
        centrale, _ = Structure.objects.get_or_create(
            sigle="DPFC",
            defaults={
                "nom": "Direction de la Pedagogie et de la Formation Continue",
                "type": Structure.Type.DIRECTION,
                "rattachement": Structure.Rattachement.CENTRALE,
                "adresse": "Cocody II Plateaux, Abidjan",
                "telephone": "+225 27 22 41 00 00",
                "email": "contact@dpfc.education.ci",
            },
        )
        services = {}
        plan = [
            ("SDP", "Sous-direction de la Pedagogie", Structure.Type.SOUS_DIRECTION, None),
            ("SDFC", "Sous-direction de la Formation Continue", Structure.Type.SOUS_DIRECTION, None),
            ("SDAF", "Sous-direction des Affaires Administratives et Financieres",
             Structure.Type.SOUS_DIRECTION, None),
            ("SRPN", "Service Developpement et Production de Ressources Pedagogiques Numeriques",
             Structure.Type.SERVICE, "SDP"),
            ("SPROG", "Service des Programmes et Guides d'Execution", Structure.Type.SERVICE, "SDP"),
            ("SFORM", "Service de l'Ingenierie de Formation", Structure.Type.SERVICE, "SDFC"),
            ("SPERS", "Service du Personnel", Structure.Type.SERVICE, "SDAF"),
        ]
        for sigle, nom, type_, parent in plan:
            structure, _ = Structure.objects.get_or_create(
                sigle=sigle,
                defaults={
                    "nom": nom,
                    "type": type_,
                    "rattachement": Structure.Rattachement.CENTRALE,
                    "parent": services.get(parent, centrale) if parent else centrale,
                },
            )
            services[sigle] = structure

        antennes = {}
        for code, region in regions.items():
            antenne, _ = Structure.objects.get_or_create(
                sigle=f"APFC-{code}",
                defaults={
                    "nom": f"Antenne de la Pedagogie et de la Formation Continue de {region.chef_lieu}",
                    "type": Structure.Type.ANTENNE,
                    "rattachement": Structure.Rattachement.REGION,
                    "region": region,
                    "parent": centrale,
                    "adresse": f"{region.chef_lieu}, {region.nom}",
                    "telephone": "+225 27 00 00 00 00",
                    "email": f"apfc.{code.lower()}@dpfc.education.ci",
                    "presentation": (
                        f"L'antenne de {region.chef_lieu} relaie l'action de la direction aupres des "
                        "inspections, des etablissements et des enseignants de la region."
                    ),
                },
            )
            antennes[code] = antenne
        self.stdout.write(f"{len(services) + len(antennes) + 1} structures enregistrees.")
        return centrale, services, antennes

    def creer_agents(self, centrale, services, antennes):
        def creer(matricule, nom, prenoms, role, structure, fonction, superieur=None, email=None):
            agent, cree = Agent.objects.get_or_create(
                matricule=matricule,
                defaults={
                    "last_name": nom,
                    "first_name": prenoms,
                    "role": role,
                    "structure": structure,
                    "fonction": fonction,
                    "superieur": superieur,
                    "email": email or f"{matricule.lower()}@dpfc.education.ci",
                    "telephone": "+225 07 00 00 00 00",
                    "date_prise_service": date(2018, 10, 1),
                },
            )
            if cree:
                agent.set_password(matricule)
                agent.save()
                SoldeConge.pour(agent)
            return agent

        directeur = creer("DIR001", "KOUAME", "Affoue", Agent.Role.DIRECTEUR, centrale, "Directrice")
        sous_directeur = creer("SD001", "TRAORE", "Ibrahim", Agent.Role.SOUS_DIRECTEUR,
                               services["SDP"], "Sous-directeur de la pedagogie", directeur)
        chef_service = creer("CS001", "N'GORAN", "Evariste", Agent.Role.CHEF_SERVICE, services["SRPN"],
                             "Chef de service", sous_directeur)
        rh = creer("RH001", "BAMBA", "Mariam", Agent.Role.RH, services["SPERS"],
                   "Gestionnaire du personnel", directeur)
        creer("CS002", "DIALLO", "Aminata", Agent.Role.CHEF_SERVICE, services["SPROG"],
              "Chef de service des programmes", sous_directeur)
        agent_central = creer("AG001", "KONE", "Salif", Agent.Role.AGENT, services["SRPN"],
                              "Ingenieur pedagogique", chef_service)
        creer("AG002", "YAO", "Christelle", Agent.Role.AGENT, services["SRPN"],
              "Chargee de production multimedia", chef_service)
        creer("AG003", "OUATTARA", "Moussa", Agent.Role.AGENT, services["SPROG"],
              "Redacteur de programmes", Agent.objects.get(matricule="CS002"))

        centrale.responsable = directeur
        centrale.save(update_fields=["responsable"])
        services["SDP"].responsable = sous_directeur
        services["SDP"].save(update_fields=["responsable"])
        services["SRPN"].responsable = chef_service
        services["SRPN"].save(update_fields=["responsable"])
        services["SPERS"].responsable = rh
        services["SPERS"].save(update_fields=["responsable"])

        agents_antennes = []
        noms = [("AB", "ADOU", "Serge"), ("GB", "COULIBALY", "Fatoumata"), ("PO", "SORO", "Gnenema"),
                ("HS", "GNAMIEN", "Paul"), ("GO", "ZIGUI", "Marc"), ("ID", "ANIN", "Julie"),
                ("TO", "GBE", "Landry"), ("BS", "KOFFI", "Adjoua"), ("BE", "BROU", "Kouassi"),
                ("GT", "KAMAGATE", "Issa")]
        for i, (code, nom, prenoms) in enumerate(noms, start=1):
            chef = creer(f"CA{i:03d}", nom, prenoms, Agent.Role.CHEF_ANTENNE, antennes[code],
                         f"Chef de l'antenne de {antennes[code].region.chef_lieu}", directeur)
            antennes[code].responsable = chef
            antennes[code].save(update_fields=["responsable"])
            agent = creer(f"AG{9 + i:03d}", f"{nom}-ADJOINT", "Konan", Agent.Role.AGENT,
                          antennes[code], "Conseiller pedagogique", chef)
            agents_antennes.append((chef, agent))

        self.stdout.write(f"{Agent.objects.count()} comptes agents enregistres.")
        return {
            "directeur": directeur,
            "sous_directeur": sous_directeur,
            "chef_service": chef_service,
            "rh": rh,
            "agent_central": agent_central,
            "chef_antenne_gb": agents_antennes[1][0],
            "agent_antenne_gb": agents_antennes[1][1],
        }

    def creer_contenus(self, antennes, agents):
        pages = self.pages
        categories = {}
        for nom, couleur in [("Communique", "#0e9b8c"), ("Formation", "#45b65c"),
                             ("Atelier", "#f5a623"), ("Numerique educatif", "#4fc3f7")]:
            categories[nom] = arborescence.ajouter_categorie(nom, couleur)

        articles = [
            ("Validation des nouveaux guides d'execution du primaire",
             "Les guides d'execution des programmes du CP au CM2 ont ete valides lors d'un atelier national.",
             "Communique"),
            ("Lancement de la formation continue des enseignants du secondaire",
             "Plus de 2 000 enseignants sont attendus dans les sessions ouvertes par les antennes regionales.",
             "Formation"),
            ("Atelier de production de ressources numeriques a Bouake",
             "L'antenne de Bouake a accueilli trois jours d'atelier consacres aux ressources numeriques.",
             "Atelier"),
            ("Deploiement de la plateforme de formation a distance",
             "La plateforme est desormais accessible aux enseignants de toutes les regions.",
             "Numerique educatif"),
            ("Rentree pedagogique : les orientations de la direction",
             "Les priorites pedagogiques de l'annee scolaire ont ete presentees aux inspections.",
             "Communique"),
        ]
        suite = (
            "Les travaux ont reuni les responsables de la direction centrale, les chefs "
            "d'antennes regionales et les partenaires techniques. Les conclusions seront "
            "diffusees aux inspections et aux etablissements dans les prochains jours."
        )
        for i, (titre, chapeau, categorie) in enumerate(articles):
            arborescence.ajouter_actualite(
                pages["actualites"], titre, chapeau, f"<p>{chapeau}</p><p>{suite}</p>",
                categorie=categories[categorie], auteur=agents["chef_service"],
                structure=antennes["GB"] if i == 2 else None, a_la_une=i == 0,
                date_publication=timezone.now() - timedelta(days=i * 6),
            )

        ressources = [
            ("Programme educatif de mathematiques CM2", Ressource.Type.PROGRAMME,
             Ressource.Niveau.PRIMAIRE, "Mathematiques", "CM2"),
            ("Programme educatif de francais 6e", Ressource.Type.PROGRAMME,
             Ressource.Niveau.SECONDAIRE_1, "Francais", "6e"),
            ("Guide d'execution SVT 4e", Ressource.Type.GUIDE,
             Ressource.Niveau.SECONDAIRE_1, "Sciences de la vie et de la terre", "4e"),
            ("Guide d'execution lecture CP1", Ressource.Type.GUIDE,
             Ressource.Niveau.PRIMAIRE, "Lecture", "CP1"),
            ("Fiche de travaux pratiques : circuit electrique", Ressource.Type.FICHE_TP,
             Ressource.Niveau.SECONDAIRE_2, "Physique-Chimie", "1re C"),
            ("Module FOAD : differenciation pedagogique", Ressource.Type.MODULE,
             Ressource.Niveau.TOUS, "Pedagogie generale", ""),
            ("Module FOAD : evaluation par competences", Ressource.Type.MODULE,
             Ressource.Niveau.TOUS, "Evaluation", ""),
            ("Arrete portant organisation de la formation continue", Ressource.Type.TEXTE,
             Ressource.Niveau.TOUS, "Textes officiels", ""),
        ]
        for titre, type_, niveau, discipline, classe in ressources:
            arborescence.ajouter_ressource(
                titre, type=type_, niveau=niveau, discipline=discipline, classe=classe,
                description=f"{titre}. Document elabore et valide par la direction.",
                annee=2025, publiee=True,
            )

        projets = [
            ("SIGE", "Systeme d'Information et de Gestion de l'Education",
             "Collecte et exploitation des donnees du systeme educatif.", "#0e9b8c", "graphique", 1),
            ("PNAPAS", "Programme National d'Amelioration des Pratiques et Acquis Scolaires",
             "Appui aux pratiques de classe et suivi des acquis des eleves.", "#45b65c", "reseau", 2),
            ("FOAD", "Formation Ouverte et A Distance",
             "Formation continue en ligne des enseignants.", "#f5a623", "ecran", 3),
            ("CNRPN", "Centre National de Ressources Pedagogiques Numeriques",
             "Production et diffusion des ressources pedagogiques numeriques.", "#4fc3f7", "livre", 4),
        ]
        for sigle, nom, accroche, couleur, icone, ordre in projets:
            arborescence.ajouter_projet(
                pages["projets"], sigle, nom, accroche,
                f"<p>{accroche} Le projet est pilote par la direction avec l'appui de ses "
                "antennes regionales et de ses partenaires.</p>",
                couleur=couleur, icone=icone, ordre=ordre,
                objectifs="<p>Renforcer la qualite des apprentissages et l'encadrement des enseignants.</p>",
                partenaires="Etat de Cote d'Ivoire, partenaires techniques et financiers",
            )

        aujourdhui = timezone.localdate()
        evenements = [
            ("Atelier national de validation des ressources numeriques", PageEvenement.Type.ATELIER, 12, "Grand-Bassam"),
            ("Session de formation des conseillers pedagogiques", PageEvenement.Type.FORMATION, 25, "Bouake"),
            ("Seminaire sur l'evaluation par competences", PageEvenement.Type.SEMINAIRE, 40, "Abidjan"),
            ("Reunion des chefs d'antennes regionales", PageEvenement.Type.REUNION, 55, "Yamoussoukro"),
        ]
        for titre, type_, jours, lieu in evenements:
            arborescence.ajouter_evenement(
                pages["evenements"], titre, aujourdhui + timedelta(days=jours),
                f"{titre}, organise par la direction.",
                type=type_, date_fin=aujourdhui + timedelta(days=jours + 2), lieu=lieu,
                public_cible="Encadreurs pedagogiques et enseignants",
            )
        self.stdout.write("Contenus publics enregistres.")

    def creer_jours_feries(self):
        annee = timezone.localdate().year
        feries = [
            (date(annee, 1, 1), "Jour de l'An"), (date(annee, 5, 1), "Fete du Travail"),
            (date(annee, 8, 7), "Fete Nationale"), (date(annee, 11, 15), "Journee Nationale de la Paix"),
            (date(annee, 12, 25), "Noel"),
        ]
        for jour, libelle in feries:
            JourFerie.objects.get_or_create(date=jour, defaults={"libelle": libelle})

    def creer_demandes(self, agents):
        if Demande.objects.exists():
            return
        aujourdhui = timezone.localdate()

        # 1. Conge d'un agent du central, valide jusqu'au directeur
        conge = Demande.objects.create(
            agent=agents["agent_central"], type=TypeDemande.CONGE_ANNUEL,
            motif="Conge annuel au titre de l'annee en cours.",
            date_debut=aujourdhui + timedelta(days=20), date_fin=aujourdhui + timedelta(days=34),
            lieu_jouissance="Abidjan", contact_pendant_absence="+225 07 00 00 00 01",
        )
        soumettre(conge)
        while conge.etape_courante():
            decider(conge.etape_courante(), True, "Avis favorable.")

        # 2. Ordre de mission d'un agent d'antenne, en cours de circuit
        mission = Demande.objects.create(
            agent=agents["agent_antenne_gb"], type=TypeDemande.ORDRE_MISSION,
            motif="Suivi de la mise en oeuvre des guides d'execution dans les ecoles pilotes.",
            date_debut=aujourdhui + timedelta(days=5), date_fin=aujourdhui + timedelta(days=8),
            destination="Sakassou", moyen_transport="Vehicule de service",
            structures_visitees="IEPP Sakassou, EPP Sakassou 1",
        )
        soumettre(mission)

        # 3. Permission en attente de decision du chef de service
        Demande.objects.create(
            agent=agents["agent_central"], type=TypeDemande.PERMISSION,
            motif="Demarches administratives personnelles.",
            date_debut=aujourdhui + timedelta(days=3), date_fin=aujourdhui + timedelta(days=3),
            heure_debut="08:00", heure_fin="12:00",
        ).pk
        permission = Demande.objects.filter(type=TypeDemande.PERMISSION).first()
        soumettre(permission)
        self.stdout.write("Demandes de demonstration creees.")

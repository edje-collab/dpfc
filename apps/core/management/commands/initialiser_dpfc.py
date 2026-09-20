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

from apps.core.models import ConfigurationSite, Region, Structure
from apps.site_public import arborescence
from apps.site_public.models import PageEvenement, PageProjet, Ressource
from apps.rh.models import JourFerie, SoldeConge, TypeDemande

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

SERVICES_CENTRAUX = [
    ("Sous-direction des programmes et manuels scolaires", "SDPMS", Structure.Type.SOUS_DIRECTION),
    ("Sous-direction de la formation continue", "SDFC", Structure.Type.SOUS_DIRECTION),
    ("Service developpement et production de ressources pedagogiques numeriques", "SDPRPN", Structure.Type.SERVICE),
    ("Service du personnel et des affaires administratives", "SPAA", Structure.Type.SERVICE),
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

        direction, _ = Structure.objects.get_or_create(
            sigle="DPFC",
            defaults={
                "nom": "Direction de la Pedagogie et de la Formation Continue",
                "type": Structure.Type.DIRECTION,
                "rattachement": Structure.Rattachement.CENTRALE,
                "adresse": "Cocody II Plateaux, Abidjan",
                "telephone": "+225 27 22 41 00 00",
                "email": "contact@dpfc.education.ci",
                "presentation": "Structure centrale chargee des programmes educatifs et de la formation continue.",
            },
        )

        centrales = {}
        for nom, sigle, type_ in SERVICES_CENTRAUX:
            structure, _ = Structure.objects.get_or_create(
                sigle=sigle,
                defaults={
                    "nom": nom,
                    "type": type_,
                    "rattachement": Structure.Rattachement.CENTRALE,
                    "parent": direction,
                    "email": f"{sigle.lower()}@dpfc.education.ci",
                },
            )
            centrales[sigle] = structure

        drenaets = {}
        for code, region in regions.items():
            drenaet, _ = Structure.objects.get_or_create(
                sigle=f"DRENAET-{code}",
                defaults={
                    "nom": f"Direction Regionale de l'Education Nationale, de l'Alphabetisation "
                           f"et de l'Enseignement Technique de {region.chef_lieu}",
                    "type": Structure.Type.DRENAET,
                    "rattachement": Structure.Rattachement.REGION,
                    "region": region,
                    "adresse": f"{region.chef_lieu}, {region.nom}",
                    "email": f"drenaet.{code.lower()}@education.ci",
                },
            )
            drenaets[code] = drenaet

        antennes = {}
        for code, region in regions.items():
            antenne, _ = Structure.objects.get_or_create(
                sigle=f"APFC-{code}",
                defaults={
                    "drenaet": drenaets[code],
                    "nom": f"Antenne de la Pedagogie et de la Formation Continue de {region.chef_lieu}",
                    "type": Structure.Type.ANTENNE,
                    "rattachement": Structure.Rattachement.REGION,
                    "parent": direction,
                    "region": region,
                    "adresse": f"{region.chef_lieu}, {region.nom}",
                    "telephone": "+225 27 00 00 00 00",
                    "email": f"apfc.{code.lower()}@dpfc.education.ci",
                    "presentation": (
                        f"L'antenne de {region.chef_lieu} encadre les enseignants de la region "
                        f"{region.nom} et relaie les orientations de la direction centrale."
                    ),
                },
            )
            antennes[code] = antenne

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
        sous_directeur = creer("100003S", "BAMBA", "Aminata", Agent.Role.SOUS_DIRECTEUR, centrales["SDFC"],
                               "Sous-directrice de la formation continue", directeur)
        chef_service = creer("100004C", "N'GORAN", "Koffi Evariste", Agent.Role.CHEF_SERVICE, centrales["SDPRPN"],
                             "Chef de service", sous_directeur)
        creer("100005A", "DIALLO", "Mariam", Agent.Role.AGENT, centrales["SDPRPN"],
              "Chargee d'etudes - ressources numeriques", chef_service, grade="Professeur")
        creer("100006A", "YAO", "Serge", Agent.Role.AGENT, centrales["SDPMS"],
              "Charge d'etudes - programmes", sous_directeur, grade="Professeur")

        dr_bouake = creer("300001B", "ADJOUMANI", "Kouadio", Agent.Role.DIRECTEUR_REGIONAL,
                          drenaets["GBK"], "Directeur regional (DRENAET)", grade="Inspecteur general")
        dr_korhogo = creer("300003K", "TOURE", "Lassina", Agent.Role.DIRECTEUR_REGIONAL,
                           drenaets["PORO"], "Directeur regional (DRENAET)", grade="Inspecteur general")
        chef_bouake = creer("200001B", "KONE", "Adama", Agent.Role.CHEF_ANTENNE, antennes["GBK"],
                            "Chef d'antenne", dr_bouake)
        creer("200005B", "KOUASSI", "Akissi", Agent.Role.SECRETARIAT, antennes["GBK"],
              "Secretaire de l'antenne", chef_bouake, grade="Secretaire administratif")
        creer("200002B", "OUATTARA", "Fatoumata", Agent.Role.AGENT, antennes["GBK"],
              "Conseillere pedagogique", chef_bouake, grade="Conseiller pedagogique")
        chef_korhogo = creer("200003K", "SORO", "Nabintou", Agent.Role.CHEF_ANTENNE, antennes["PORO"],
                             "Chef d'antenne", dr_korhogo)
        creer("200004K", "COULIBALY", "Seydou", Agent.Role.AGENT, antennes["PORO"],
              "Conseiller pedagogique", chef_korhogo, grade="Conseiller pedagogique")

        direction.responsable = directeur
        direction.save()
        centrales["SDFC"].responsable = sous_directeur
        centrales["SDFC"].save()
        centrales["SDPRPN"].responsable = chef_service
        centrales["SDPRPN"].parent = centrales["SDFC"]
        centrales["SDPRPN"].save()
        centrales["SPAA"].responsable = rh
        centrales["SPAA"].save()
        antennes["GBK"].responsable = chef_bouake
        antennes["GBK"].save()
        antennes["PORO"].responsable = chef_korhogo
        antennes["PORO"].save()
        drenaets["GBK"].responsable = dr_bouake
        drenaets["GBK"].save()
        drenaets["PORO"].responsable = dr_korhogo
        drenaets["PORO"].save()
        for code, antenne in antennes.items():
            if antenne.drenaet_id is None:
                antenne.drenaet = drenaets[code]
                antenne.save(update_fields=["drenaet"])

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

        if options["demo"]:
            self._cles_de_signature([directeur, chef_bouake, chef_korhogo, dr_bouake, dr_korhogo])
            self._demandes_demo()

        self.stdout.write(self.style.SUCCESS("Initialisation terminee."))
        self.stdout.write("  Comptes de demonstration : le mot de passe initial est le matricule.")
        self.stdout.write(
            "  100001D directrice | 100002R personnel | 100004C chef de service\n"
            "  200001B chef d'antenne Bouake | 200005B secretariat d'antenne | 200002B agent d'antenne\n"
            "  300001B directeur regional DRENAET Bouake"
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
            hors_perimetre_drenaet=True,
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

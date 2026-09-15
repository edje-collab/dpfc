import io

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from apps.accounts.imports import analyser, appliquer, generer_modele, lire_fichier
from apps.core.models import Region, Structure
from apps.rh.models import SoldeConge

Agent = get_user_model()

CSV_AGENTS = """matricule;civilite;nom;prenoms;email;telephone;structure;fonction;grade;role;superieur;date_prise_service;lieu_service;droit_conge
200010B;M;KOFFI;Jean Marc;jean.koffi@dpfc.education.ci;+225 07 11 11 11 11;APFC-GBK;Conseiller pedagogique;Conseiller;AGENT;200001B;01/10/2020;Bouake;30
200011B;MME;AKA;Adjoua;adjoua.aka@dpfc.education.ci;;APFC-GBK;Secretaire;Secretaire;SECRETARIAT;200001B;15/03/2021;Bouake;
200012B;M;BROU;Yao;;;STRUCTURE-INCONNUE;Agent;;AGENT;;;;
;M;SANS;Matricule;;;APFC-GBK;Agent;;AGENT;;;;
"""


class ImportAgentsTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        region = Region.objects.create(nom="Gbeke", code="GBK", chef_lieu="Bouake")
        cls.antenne = Structure.objects.create(
            nom="Antenne de Bouake", sigle="APFC-GBK", type=Structure.Type.ANTENNE, region=region
        )
        cls.chef = Agent.objects.create_user(
            "200001B", password="motdepasse123", last_name="KONE", first_name="Adama",
            role=Agent.Role.CHEF_ANTENNE, structure=cls.antenne,
        )
        cls.rh = Agent.objects.create_user(
            "100002R", password="motdepasse123", last_name="TRAORE", first_name="Ibrahim",
            role=Agent.Role.RH, structure=cls.antenne,
        )

    def _analyser_csv(self):
        lignes, erreur = lire_fichier(io.BytesIO(CSV_AGENTS.encode()), "agents.csv")
        self.assertIsNone(erreur)
        return analyser(lignes)

    def test_lecture_csv_et_analyse(self):
        resultats = self._analyser_csv()
        self.assertEqual(len(resultats), 4)
        actions = [r["action"] for r in resultats]
        self.assertEqual(actions, ["creation", "creation", "erreur", "erreur"])
        self.assertIn("structure inconnue", " ".join(resultats[2]["erreurs"]))
        self.assertIn("matricule manquant", resultats[3]["erreurs"])

    def test_application_cree_les_comptes(self):
        compte = appliquer(self._analyser_csv())
        self.assertEqual(compte["crees"], 2)
        self.assertEqual(compte["ignores"], 2)
        agent = Agent.objects.get(matricule="200010B")
        self.assertEqual(agent.last_name, "KOFFI")
        self.assertEqual(agent.structure, self.antenne)
        self.assertEqual(agent.superieur, self.chef)
        self.assertTrue(agent.check_password("200010B"))
        self.assertTrue(agent.doit_changer_mot_de_passe)
        self.assertEqual(SoldeConge.pour(agent).droit_jours, 30)

    def test_agent_existant_est_mis_a_jour(self):
        appliquer(self._analyser_csv())
        Agent.objects.filter(matricule="200010B").update(fonction="Ancienne fonction")
        compte = appliquer(self._analyser_csv())
        self.assertEqual(compte["crees"], 0)
        self.assertEqual(compte["mis_a_jour"], 2)
        self.assertEqual(Agent.objects.get(matricule="200010B").fonction, "Conseiller pedagogique")

    def test_entete_invalide(self):
        _, erreur = lire_fichier(io.BytesIO(b"colonne1;colonne2\na;b\n"), "mauvais.csv")
        self.assertIn("En-tete invalide", erreur)

    def test_format_non_reconnu(self):
        _, erreur = lire_fichier(io.BytesIO(b"contenu"), "agents.docx")
        self.assertIn("Format non reconnu", erreur)

    def test_modele_excel_genere(self):
        contenu = generer_modele()
        self.assertTrue(contenu.startswith(b"PK"))
        from openpyxl import load_workbook

        classeur = load_workbook(io.BytesIO(contenu))
        self.assertEqual(classeur.sheetnames, ["Agents", "Aide"])
        self.assertEqual(classeur["Agents"]["A1"].value, "matricule")

    def test_parcours_complet_depuis_l_intranet(self):
        self.client.force_login(self.rh)
        fichier = SimpleUploadedFile("agents.csv", CSV_AGENTS.encode(), content_type="text/csv")
        reponse = self.client.post(reverse("accounts:import_agents"), {"fichier": fichier}, follow=True)
        self.assertContains(reponse, "Creation")
        reponse = self.client.post(
            reverse("accounts:import_agents"), {"action": "appliquer"}, follow=True
        )
        self.assertTrue(Agent.objects.filter(matricule="200011B").exists())

    def test_import_refuse_a_un_agent_simple(self):
        simple = Agent.objects.create_user("A0009", password="motdepasse123", last_name="YAO",
                                           first_name="Paul", structure=self.antenne)
        self.client.force_login(simple)
        reponse = self.client.get(reverse("accounts:import_agents"), follow=True)
        self.assertContains(reponse, "reserve")

    def test_telechargement_du_modele(self):
        self.client.force_login(self.rh)
        reponse = self.client.get(reverse("accounts:modele_import"))
        self.assertEqual(reponse.status_code, 200)
        self.assertIn("spreadsheetml", reponse["Content-Type"])

from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.core.models import Perimetre, Region, Structure
from apps.rh.models import Demande, TypeDemande
from apps.rh.services import soumettre
from apps.signature.services import creer_cle

Agent = get_user_model()
CODE_SIGNATURE = "signature2026"


class ApiTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.perimetre = Perimetre.objects.create(
            code="DPFC", nom="Direction centrale", type=Perimetre.Type.CENTRALE
        )
        cls.direction = Structure.objects.create(
            nom="Direction de la Pedagogie", sigle="DPFC", type=Structure.Type.DIRECTION,
            perimetre=cls.perimetre, perimetre_racine=True,
        )
        cls.rh = Agent.objects.create_user("R0001", password="motdepasse123", last_name="TRAORE",
                                           first_name="Ibrahim", role=Agent.Role.RH, structure=cls.direction)
        cls.agent = Agent.objects.create_user("A0001", password="motdepasse123", last_name="DIALLO",
                                              first_name="Mariam", structure=cls.direction, superieur=cls.rh)

    def _jeton(self):
        reponse = self.client.post(
            reverse("api:connexion"), {"matricule": "A0001", "password": "motdepasse123"},
            content_type="application/json",
        )
        self.assertEqual(reponse.status_code, 200)
        return reponse.json()

    def test_connexion_retourne_le_profil(self):
        donnees = self._jeton()
        self.assertIn("access", donnees)
        self.assertEqual(donnees["agent"]["matricule"], "A0001")

    def test_acces_refuse_sans_jeton(self):
        self.assertEqual(self.client.get("/api/v1/demandes/").status_code, 401)

    def test_cycle_de_vie_d_une_demande(self):
        jeton = self._jeton()["access"]
        entetes = {"HTTP_AUTHORIZATION": f"Bearer {jeton}"}
        debut = date.today() + timedelta(days=10)
        creation = self.client.post(
            "/api/v1/demandes/",
            {"type": "PERMISSION", "motif": "Demarche administrative",
             "date_debut": str(debut), "date_fin": str(debut)},
            content_type="application/json", **entetes,
        )
        self.assertEqual(creation.status_code, 201, creation.content)
        identifiant = creation.json()["id"]
        soumission = self.client.post(f"/api/v1/demandes/{identifiant}/soumettre/", **entetes)
        self.assertEqual(soumission.status_code, 200)
        self.assertEqual(soumission.json()["statut"], "SOUMISE")

    def test_contenus_publics_sans_authentification(self):
        for chemin in ["/api/v1/public/actualites/", "/api/v1/public/ressources/",
                       "/api/v1/public/projets/", "/api/v1/public/antennes/"]:
            with self.subTest(chemin=chemin):
                self.assertEqual(self.client.get(chemin).status_code, 200)


class ApiAntenneTest(TestCase):
    """Parcours terrain : depot d'une mission hors perimetre et signature mobile."""

    @classmethod
    def setUpTestData(cls):
        region = Region.objects.create(nom="Gbeke", code="GBK", chef_lieu="Bouake")
        cls.drena = Structure.objects.create(
            nom="DRENA de Bouake", sigle="DRENA-GBK", type=Structure.Type.DRENA, region=region
        )
        perimetre_antenne = Perimetre.objects.create(
            code="APFC-GBK", nom="Antenne de Bouake", type=Perimetre.Type.ANTENNE, region=region
        )
        cls.antenne = Structure.objects.create(
            nom="Antenne de Bouake", sigle="APFC-GBK", type=Structure.Type.ANTENNE,
            region=region, drena=cls.drena,
            perimetre=perimetre_antenne, perimetre_racine=True,
        )
        cls.dr = Agent.objects.create_user(
            "G0001", password="motdepasse123", last_name="ADJOUMANI", first_name="Kouadio",
            role=Agent.Role.DIRECTEUR_REGIONAL, structure=cls.drena,
        )
        cls.drena.responsable = cls.dr
        cls.drena.save()
        cls.chef = Agent.objects.create_user(
            "C0001", password="motdepasse123", last_name="KONE", first_name="Adama",
            role=Agent.Role.CHEF_ANTENNE, structure=cls.antenne,
        )
        cls.antenne.responsable = cls.chef
        cls.antenne.save()
        cls.agent = Agent.objects.create_user(
            "A0001", password="motdepasse123", last_name="OUATTARA", first_name="Fatoumata",
            structure=cls.antenne, superieur=cls.chef,
        )

    def _entetes(self, matricule):
        reponse = self.client.post(
            reverse("api:connexion"), {"matricule": matricule, "password": "motdepasse123"},
            content_type="application/json",
        )
        return {"HTTP_AUTHORIZATION": f"Bearer {reponse.json()['access']}"}

    def test_depot_de_pieces_et_circuit_hors_perimetre(self):
        entetes = self._entetes("A0001")
        debut = date.today() + timedelta(days=15)
        creation = self.client.post(
            "/api/v1/demandes/",
            {"type": "ORDRE_MISSION", "motif": "Atelier national", "destination": "Abidjan",
             "hors_perimetre_drena": True, "date_debut": str(debut),
             "date_fin": str(debut + timedelta(days=2))},
            content_type="application/json", **entetes,
        )
        self.assertEqual(creation.status_code, 201, creation.content)
        identifiant = creation.json()["id"]
        self.assertEqual(creation.json()["autorite_signataire"], "Directeur regional (DRENA)")

        depot = self.client.post(
            f"/api/v1/demandes/{identifiant}/pieces/",
            {
                "termes_de_reference": SimpleUploadedFile("tdr.txt", b"Termes de reference"),
                "lettre_invitation": SimpleUploadedFile("invitation.txt", b"Invitation"),
            },
            **entetes,
        )
        self.assertEqual(depot.status_code, 200, depot.content)
        self.assertEqual(sorted(depot.json()["pieces_enregistrees"]),
                         ["lettre_invitation", "termes_de_reference"])

        soumission = self.client.post(f"/api/v1/demandes/{identifiant}/soumettre/", **entetes)
        self.assertEqual(soumission.status_code, 200)
        validations = soumission.json()["validations"]
        self.assertEqual(len(validations), 2)
        self.assertIn("DRENA", validations[-1]["libelle"])

    def test_signature_mobile_a_la_derniere_etape(self):
        creer_cle(self.chef, CODE_SIGNATURE)
        debut = date.today() + timedelta(days=10)
        demande = Demande.objects.create(
            agent=self.agent, type=TypeDemande.PERMISSION, motif="Demarche",
            date_debut=debut, date_fin=debut,
        )
        soumettre(demande)
        entetes = self._entetes("C0001")

        sans_code = self.client.post(
            f"/api/v1/demandes/{demande.pk}/decision/", {"favorable": True, "commentaire": "Accorde"},
            content_type="application/json", **entetes,
        )
        self.assertEqual(sans_code.status_code, 400)

        avec_code = self.client.post(
            f"/api/v1/demandes/{demande.pk}/decision/",
            {"favorable": True, "commentaire": "Accorde", "code_signature": CODE_SIGNATURE},
            content_type="application/json", **entetes,
        )
        self.assertEqual(avec_code.status_code, 200, avec_code.content)
        code = avec_code.json()["code_verification"]
        demande.refresh_from_db()
        self.assertEqual(demande.statut, Demande.Statut.APPROUVEE)

        verification = self.client.get(f"/api/v1/verification/{code}/")
        self.assertEqual(verification.status_code, 200)
        self.assertTrue(verification.json()["signature_valide"])
        self.assertTrue(verification.json()["document_intact"])

    def test_verification_code_inconnu(self):
        self.assertEqual(self.client.get("/api/v1/verification/DPFC-0000-0000-0000/").status_code, 404)


class ApiPilotageTest(TestCase):
    """L'application mobile consulte les activites et rend compte depuis le terrain."""

    @classmethod
    def setUpTestData(cls):
        from apps.activites.models import Activite, Axe, PlanAction
        from apps.activites.services import soumettre_plan, valider_plan

        region = Region.objects.create(nom="Poro", code="PORO", chef_lieu="Korhogo")
        cls.p_centrale = Perimetre.objects.create(
            code="DPFC", nom="Direction centrale", type=Perimetre.Type.CENTRALE
        )
        cls.p_antenne = Perimetre.objects.create(
            code="APFC-PORO", nom="Antenne de Korhogo", type=Perimetre.Type.ANTENNE, region=region
        )
        cls.direction = Structure.objects.create(
            nom="Direction de la Pedagogie", sigle="DPFC", type=Structure.Type.DIRECTION,
            perimetre=cls.p_centrale, perimetre_racine=True,
        )
        cls.antenne = Structure.objects.create(
            nom="Antenne de Korhogo", sigle="APFC-PORO", type=Structure.Type.ANTENNE,
            region=region, perimetre=cls.p_antenne, perimetre_racine=True,
        )
        cls.directeur = Agent.objects.create_user(
            "D0001", password="motdepasse123", last_name="KOUAME", first_name="Sylvie",
            role=Agent.Role.DIRECTEUR, structure=cls.direction,
        )
        cls.chef = Agent.objects.create_user(
            "C0001", password="motdepasse123", last_name="SORO", first_name="Nabintou",
            role=Agent.Role.CHEF_ANTENNE, structure=cls.antenne,
        )
        cls.direction.responsable = cls.directeur
        cls.direction.save(update_fields=["responsable"])
        cls.antenne.responsable = cls.chef
        cls.antenne.save(update_fields=["responsable"])

        annee = timezone.localdate().year
        axe = Axe.objects.create(code="AX1", libelle="Qualite des apprentissages")
        cls.plan = PlanAction.objects.create(perimetre=cls.p_antenne, annee=annee)
        cls.activite = Activite.objects.create(
            plan=cls.plan, axe=axe, intitule="Suivi pedagogique des ecoles",
            date_debut_prevue=date(annee, 1, 15), date_fin_prevue=date(annee, 12, 15),
            responsable=cls.chef, effectif_prevu=100, budget_prevu=2_000_000,
        )
        # Plan d'un autre perimetre, qui ne doit pas apparaitre.
        autre = PlanAction.objects.create(perimetre=cls.p_centrale, annee=annee)
        Activite.objects.create(
            plan=autre, intitule="Activite centrale",
            date_debut_prevue=date(annee, 2, 1), date_fin_prevue=date(annee, 3, 1),
        )
        soumettre_plan(cls.plan, par=cls.chef)
        valider_plan(cls.plan, par=cls.directeur)

    def _entetes(self, matricule="C0001"):
        reponse = self.client.post(
            reverse("api:connexion"), {"matricule": matricule, "password": "motdepasse123"},
            content_type="application/json",
        )
        return {"HTTP_AUTHORIZATION": f"Bearer {reponse.json()['access']}"}

    def test_le_terrain_ne_voit_que_les_activites_de_son_perimetre(self):
        reponse = self.client.get("/api/v1/activites/", **self._entetes())
        self.assertEqual(reponse.status_code, 200)
        donnees = reponse.json()["results"]
        self.assertEqual(len(donnees), 1)
        self.assertEqual(donnees[0]["perimetre"], "APFC-PORO")
        self.assertEqual(donnees[0]["code"], "A-001")

    def test_la_direction_voit_tous_les_perimetres(self):
        reponse = self.client.get("/api/v1/activites/", **self._entetes("D0001"))
        self.assertEqual(reponse.json()["count"], 2)

    def test_compte_rendu_depuis_le_telephone(self):
        reponse = self.client.post(
            f"/api/v1/activites/{self.activite.pk}/avancement/",
            {"taux": 60, "realisations": "Soixante ecoles visitees.", "effectif_touche": 60,
             "montant_engage": 900000},
            **self._entetes(),
        )
        self.assertEqual(reponse.status_code, 200)
        donnees = reponse.json()
        self.assertEqual(donnees["avancement"], 60)
        self.assertEqual(donnees["statut"], "EN_COURS")
        self.activite.refresh_from_db()
        self.assertEqual(self.activite.effectif_realise, 60)

    def test_compte_rendu_refuse_au_dela_de_cent(self):
        reponse = self.client.post(
            f"/api/v1/activites/{self.activite.pk}/avancement/",
            {"taux": 150, "realisations": "Impossible."}, **self._entetes(),
        )
        self.assertEqual(reponse.status_code, 400)

    def test_compte_rendu_refuse_sur_une_activite_annulee(self):
        """Chemin d'erreur metier, distinct de la validation du formulaire."""
        from apps.activites.services import annuler_activite

        annuler_activite(self.activite, self.directeur, "Sans objet.")
        reponse = self.client.post(
            f"/api/v1/activites/{self.activite.pk}/avancement/",
            {"taux": 50, "realisations": "Trop tard."}, **self._entetes(),
        )
        self.assertEqual(reponse.status_code, 400)
        self.assertIn("annulee", reponse.json()["detail"])

    def test_tableau_de_bord_mobile(self):
        reponse = self.client.get("/api/v1/pilotage/", **self._entetes())
        self.assertEqual(reponse.status_code, 200)
        donnees = reponse.json()
        self.assertEqual(donnees["nb_activites"], 1)
        self.assertIn("taux_execution", donnees)

    def test_les_plans_sont_filtres_par_perimetre(self):
        reponse = self.client.get("/api/v1/plans/", **self._entetes())
        codes = [p["perimetre_code"] for p in reponse.json()["results"]]
        self.assertEqual(codes, ["APFC-PORO"])

    def test_acces_refuse_sans_jeton(self):
        self.assertEqual(self.client.get("/api/v1/activites/").status_code, 401)


class ApiCourrierTest(TestCase):
    """Le terrain consulte son courrier et rend compte de ses imputations."""

    @classmethod
    def setUpTestData(cls):
        from apps.courrier.models import Courrier, Document
        from apps.courrier.services import deposer_version, imputer

        cls.p_centrale = Perimetre.objects.create(
            code="DPFC", nom="Direction centrale", type=Perimetre.Type.CENTRALE
        )
        cls.p_antenne = Perimetre.objects.create(
            code="APFC-GBK", nom="Antenne de Bouake", type=Perimetre.Type.ANTENNE
        )
        cls.direction = Structure.objects.create(
            nom="Direction", sigle="DPFC", type=Structure.Type.DIRECTION,
            perimetre=cls.p_centrale, perimetre_racine=True,
        )
        cls.antenne = Structure.objects.create(
            nom="Antenne", sigle="APFC-GBK", type=Structure.Type.ANTENNE,
            perimetre=cls.p_antenne, perimetre_racine=True,
        )
        cls.directeur = Agent.objects.create_user(
            "D0001", password="motdepasse123", last_name="KOUAME", first_name="S",
            role=Agent.Role.DIRECTEUR, structure=cls.direction,
        )
        cls.chef = Agent.objects.create_user(
            "C0001", password="motdepasse123", last_name="KONE", first_name="A",
            role=Agent.Role.CHEF_ANTENNE, structure=cls.antenne,
        )
        cls.agent = Agent.objects.create_user(
            "A0001", password="motdepasse123", last_name="OUATTARA", first_name="F",
            role=Agent.Role.AGENT, structure=cls.antenne, superieur=cls.chef,
        )
        cls.direction.responsable = cls.directeur
        cls.direction.save(update_fields=["responsable"])
        cls.antenne.responsable = cls.chef
        cls.antenne.save(update_fields=["responsable"])

        cls.courrier = Courrier.objects.create(
            perimetre=cls.p_antenne, sens=Courrier.Sens.ARRIVEE,
            correspondant="IEPP", objet="Demande d'appui", enregistre_par=cls.chef,
        )
        Courrier.objects.create(
            perimetre=cls.p_centrale, sens=Courrier.Sens.ARRIVEE,
            correspondant="Cabinet", objet="Circulaire", enregistre_par=cls.directeur,
        )
        [cls.imputation] = imputer(cls.courrier, cls.chef, [
            {"destinataire": cls.agent, "instructions": "Traiter.",
             "delai": timezone.localdate() + timedelta(days=5)},
        ])
        cls.document = Document.objects.create(
            perimetre=cls.p_antenne, titre="Note regionale", annee=timezone.localdate().year,
            deposant=cls.chef,
        )
        deposer_version(
            cls.document,
            SimpleUploadedFile("note.txt", b"Note sur l'encadrement des enseignants."),
            cls.chef,
        )

    def _entetes(self, matricule="A0001"):
        reponse = self.client.post(
            reverse("api:connexion"), {"matricule": matricule, "password": "motdepasse123"},
            content_type="application/json",
        )
        return {"HTTP_AUTHORIZATION": f"Bearer {reponse.json()['access']}"}

    def test_le_courrier_est_cloisonne_par_perimetre(self):
        reponse = self.client.get("/api/v1/courriers/", **self._entetes())
        self.assertEqual(reponse.status_code, 200)
        numeros = [c["perimetre_code"] for c in reponse.json()["results"]]
        self.assertEqual(numeros, ["APFC-GBK"])
        self.assertEqual(
            self.client.get("/api/v1/courriers/", **self._entetes("D0001")).json()["count"], 2
        )

    def test_mes_imputations_en_attente(self):
        reponse = self.client.get("/api/v1/imputations/?en_attente=1", **self._entetes())
        donnees = reponse.json()["results"]
        self.assertEqual(len(donnees), 1)
        self.assertEqual(donnees[0]["courrier_objet"], "Demande d'appui")

    def test_compte_rendu_depuis_le_telephone(self):
        reponse = self.client.post(
            f"/api/v1/imputations/{self.imputation.pk}/traiter/",
            {"compte_rendu": "Tournee programmee."}, **self._entetes(),
        )
        self.assertEqual(reponse.status_code, 200)
        self.assertIsNotNone(reponse.json()["traite_le"])
        self.courrier.refresh_from_db()
        self.assertEqual(self.courrier.statut, "TRAITE")

    def test_compte_rendu_vide_refuse(self):
        reponse = self.client.post(
            f"/api/v1/imputations/{self.imputation.pk}/traiter/",
            {"compte_rendu": "   "}, **self._entetes(),
        )
        self.assertEqual(reponse.status_code, 400)

    def test_recherche_documentaire(self):
        reponse = self.client.get("/api/v1/documents/?q=encadrement", **self._entetes())
        titres = [d["titre"] for d in reponse.json()["results"]]
        self.assertEqual(titres, ["Note regionale"])
        self.assertIsNotNone(reponse.json()["results"][0]["fichier"])

    def test_acces_refuse_sans_jeton(self):
        self.assertEqual(self.client.get("/api/v1/courriers/").status_code, 401)

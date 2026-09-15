from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.core.models import Region, Structure
from apps.rh.models import Demande, JourFerie, SoldeConge, TypeDemande, jours_ouvrables
from apps.rh.services import circuit_theorique, decider, demandes_a_traiter, soumettre

Agent = get_user_model()


class BaseRH(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.region = Region.objects.create(nom="Gbeke", code="GBK", chef_lieu="Bouake")
        cls.direction = Structure.objects.create(
            nom="Direction de la Pedagogie", sigle="DPFC", type=Structure.Type.DIRECTION
        )
        cls.service_rh = Structure.objects.create(
            nom="Service du personnel", sigle="SPAA", type=Structure.Type.SERVICE, parent=cls.direction
        )
        cls.sous_direction = Structure.objects.create(
            nom="Sous-direction de la formation continue", sigle="SDFC",
            type=Structure.Type.SOUS_DIRECTION, parent=cls.direction,
        )
        cls.service_central = Structure.objects.create(
            nom="Service des ressources numeriques", sigle="SDPRPN",
            type=Structure.Type.SERVICE, parent=cls.sous_direction,
        )
        cls.drenaet = Structure.objects.create(
            nom="DRENAET de Bouake", sigle="DRENAET-GBK", type=Structure.Type.DRENAET, region=cls.region
        )
        cls.antenne = Structure.objects.create(
            nom="Antenne de Bouake", sigle="APFC-GBK", type=Structure.Type.ANTENNE,
            parent=cls.direction, region=cls.region, drenaet=cls.drenaet,
        )
        cls.directeur = cls._agent("D0001", "KOUAME", Agent.Role.DIRECTEUR, cls.direction)
        cls.rh = cls._agent("R0001", "TRAORE", Agent.Role.RH, cls.service_rh)
        cls.directeur_regional = cls._agent(
            "G0001", "ADJOUMANI", Agent.Role.DIRECTEUR_REGIONAL, cls.drenaet
        )
        cls.drenaet.responsable = cls.directeur_regional
        cls.drenaet.save()
        cls.chef_antenne = cls._agent("C0001", "KONE", Agent.Role.CHEF_ANTENNE, cls.antenne,
                                      cls.directeur_regional)
        cls.antenne.responsable = cls.chef_antenne
        cls.antenne.save()
        cls.secretaire = cls._agent("S0001", "KOUASSI", Agent.Role.SECRETARIAT, cls.antenne, cls.chef_antenne)
        cls.agent = cls._agent("A0001", "OUATTARA", Agent.Role.AGENT, cls.antenne, cls.chef_antenne)

        cls.sous_directeur = cls._agent("B0001", "BAMBA", Agent.Role.SOUS_DIRECTEUR, cls.sous_direction,
                                        cls.directeur)
        cls.sous_direction.responsable = cls.sous_directeur
        cls.sous_direction.save()
        cls.chef_service = cls._agent("F0001", "NGORAN", Agent.Role.CHEF_SERVICE, cls.service_central,
                                      cls.sous_directeur)
        cls.service_central.responsable = cls.chef_service
        cls.service_central.save()
        cls.agent_central = cls._agent("A0002", "DIALLO", Agent.Role.AGENT, cls.service_central,
                                       cls.chef_service)

    @staticmethod
    def _agent(matricule, nom, role, structure, superieur=None):
        agent = Agent.objects.create_user(
            matricule=matricule, password="motdepasse123", last_name=nom, first_name="Test",
            role=role, structure=structure, superieur=superieur,
        )
        return agent


class CalculJoursTest(BaseRH):
    def test_weekend_exclu(self):
        lundi = date(2026, 9, 7)
        vendredi = date(2026, 9, 11)
        self.assertEqual(jours_ouvrables(lundi, vendredi), 5)
        self.assertEqual(jours_ouvrables(lundi, lundi + timedelta(days=6)), 5)

    def test_jour_ferie_exclu(self):
        JourFerie.objects.create(date=date(2026, 9, 9), libelle="Ferie test")
        self.assertEqual(jours_ouvrables(date(2026, 9, 7), date(2026, 9, 11)), 4)

    def test_dates_inversees(self):
        self.assertEqual(jours_ouvrables(date(2026, 9, 11), date(2026, 9, 7)), 0)


class CircuitTest(BaseRH):
    def _demande(self, type_acte=TypeDemande.CONGE_ANNUEL, agent=None, **extra):
        debut = date.today() + timedelta(days=10)
        donnees = {
            "agent": agent or self.agent, "type": type_acte, "motif": "Motif de test",
            "date_debut": debut, "date_fin": debut + timedelta(days=4),
        }
        if type_acte == TypeDemande.ORDRE_MISSION:
            donnees["destination"] = "Korhogo"
        donnees.update(extra)
        return Demande.objects.create(**donnees)

    # --- Antennes : autonomie de gestion ---------------------------------
    def test_agent_antenne_adresse_sa_demande_au_chef_apfc(self):
        circuit = circuit_theorique(self._demande())
        self.assertEqual([v.matricule for _, v in circuit], ["C0001"])
        self.assertIn("chef d'antenne", circuit[0][0].lower())

    def test_antenne_sans_visa_central(self):
        for type_acte in (TypeDemande.PERMISSION, TypeDemande.ABSENCE, TypeDemande.CONGE_ANNUEL):
            with self.subTest(acte=type_acte):
                valideurs = [v.matricule for _, v in circuit_theorique(self._demande(type_acte))]
                self.assertNotIn("R0001", valideurs)
                self.assertNotIn("D0001", valideurs)

    def test_mission_dans_le_perimetre_reste_a_l_antenne(self):
        circuit = circuit_theorique(self._demande(TypeDemande.ORDRE_MISSION))
        self.assertEqual([v.matricule for _, v in circuit], ["C0001"])

    def test_mission_hors_perimetre_etablie_par_le_drenaet(self):
        demande = self._demande(TypeDemande.ORDRE_MISSION, hors_perimetre_drenaet=True,
                                destination="Abidjan")
        circuit = circuit_theorique(demande)
        self.assertEqual([v.matricule for _, v in circuit], ["C0001", "G0001"])
        self.assertIn("DRENAET", circuit[-1][0])
        self.assertEqual(demande.autorite_signataire, "DRENAET")

    def test_mission_hors_perimetre_exige_tdr_et_invitation(self):
        from django.core.exceptions import ValidationError

        demande = self._demande(TypeDemande.ORDRE_MISSION, hors_perimetre_drenaet=True)
        demande.statut = Demande.Statut.SOUMISE
        with self.assertRaises(ValidationError) as erreur:
            demande.full_clean(exclude=["numero", "structure", "nb_jours"])
        self.assertIn("termes_de_reference", erreur.exception.message_dict)
        self.assertIn("lettre_invitation", erreur.exception.message_dict)

    def test_acte_du_chef_antenne_remonte_au_drenaet(self):
        circuit = circuit_theorique(self._demande(agent=self.chef_antenne))
        self.assertEqual([v.matricule for _, v in circuit], ["G0001", "D0001"])

    # --- Direction centrale ----------------------------------------------
    def test_circuit_central_complet(self):
        circuit = circuit_theorique(self._demande(agent=self.agent_central))
        self.assertEqual([v.matricule for _, v in circuit], ["F0001", "B0001", "R0001", "D0001"])

    def test_permission_centrale_sans_signature_directeur(self):
        valideurs = [
            v.matricule
            for _, v in circuit_theorique(self._demande(TypeDemande.PERMISSION, agent=self.agent_central))
        ]
        self.assertNotIn("D0001", valideurs)

    # --- Deroulement ------------------------------------------------------
    def test_soumission_numerote_et_notifie(self):
        demande = self._demande()
        soumettre(demande)
        demande.refresh_from_db()
        self.assertTrue(demande.numero.startswith("CG-"))
        self.assertEqual(demande.statut, Demande.Statut.SOUMISE)
        self.assertEqual(demande.validations.count(), 1)
        self.assertEqual(self.chef_antenne.notifications.count(), 1)

    def test_decision_du_chef_apfc_approuve_et_decompte_le_solde(self):
        demande = self._demande()
        soumettre(demande)
        decider(demande.etape_courante(), True, "Accorde")
        demande.refresh_from_db()
        self.assertEqual(demande.statut, Demande.Statut.APPROUVEE)
        solde = SoldeConge.pour(self.agent, demande.date_debut.year)
        self.assertEqual(solde.jours_consommes, demande.nb_jours)

    def test_rejet_stoppe_le_circuit(self):
        demande = self._demande()
        soumettre(demande)
        decider(demande.etape_courante(), False, "Periode de forte activite")
        demande.refresh_from_db()
        self.assertEqual(demande.statut, Demande.Statut.REJETEE)
        self.assertEqual(demande.motif_rejet, "Periode de forte activite")
        self.assertIsNone(demande.etape_courante())

    def test_file_de_validation_respecte_l_ordre(self):
        demande = self._demande(TypeDemande.ORDRE_MISSION, hors_perimetre_drenaet=True)
        soumettre(demande)
        self.assertEqual(list(demandes_a_traiter(self.chef_antenne)), [demande])
        self.assertEqual(list(demandes_a_traiter(self.directeur_regional)), [])
        decider(demande.etape_courante(), True)
        self.assertEqual(list(demandes_a_traiter(self.directeur_regional)), [demande])

    def test_ordre_de_mission_exige_une_destination(self):
        from django.core.exceptions import ValidationError

        demande = self._demande(TypeDemande.ORDRE_MISSION)
        demande.destination = ""
        with self.assertRaises(ValidationError):
            demande.full_clean(exclude=["numero", "structure", "nb_jours"])


class VuesRHTest(BaseRH):
    def setUp(self):
        self.client.force_login(self.agent)

    def test_tableau_de_bord(self):
        reponse = self.client.get(reverse("rh:tableau_bord"))
        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, "jours de conge restants")

    def test_depot_et_transmission(self):
        debut = date.today() + timedelta(days=15)
        reponse = self.client.post(
            reverse("rh:demande_creer", args=["CONGE_ANNUEL"]),
            {"motif": "Conge annuel", "date_debut": debut, "date_fin": debut + timedelta(days=6),
             "lieu_jouissance": "Bouake", "action": "soumettre"},
            follow=True,
        )
        self.assertEqual(reponse.status_code, 200)
        demande = Demande.objects.get(agent=self.agent)
        self.assertEqual(demande.statut, Demande.Statut.SOUMISE)

    def test_agent_ne_voit_pas_la_demande_d_un_tiers(self):
        autre = self._agent("A0003", "YAO", Agent.Role.AGENT, self.antenne, self.chef_antenne)
        demande = Demande.objects.create(
            agent=autre, type=TypeDemande.PERMISSION, motif="Test",
            date_debut=date.today(), date_fin=date.today(),
        )
        reponse = self.client.get(reverse("rh:demande_detail", args=[demande.pk]), follow=True)
        self.assertContains(reponse, "pas acces")

    def test_registre_refuse_a_un_agent_simple(self):
        reponse = self.client.get(reverse("rh:registre"), follow=True)
        self.assertContains(reponse, "reserve")

    def test_depot_par_le_secretariat_pour_un_agent(self):
        self.client.force_login(self.secretaire)
        debut = date.today() + timedelta(days=12)
        self.client.post(
            reverse("rh:demande_creer", args=["PERMISSION"]) + "?pour=agent",
            {"agent_concerne": self.agent.pk, "motif": "Demarche administrative",
             "date_debut": debut, "date_fin": debut, "action": "soumettre"},
            follow=True,
        )
        demande = Demande.objects.filter(agent=self.agent, type=TypeDemande.PERMISSION).first()
        self.assertIsNotNone(demande)
        self.assertEqual(demande.depose_par, self.secretaire)
        self.assertEqual(demande.statut, Demande.Statut.SOUMISE)
        self.assertEqual(demande.validations.first().valideur, self.chef_antenne)

    def test_registre_accessible_au_personnel(self):
        self.client.force_login(self.rh)
        self.assertEqual(self.client.get(reverse("rh:registre")).status_code, 200)

    def test_connexion_requise(self):
        self.client.logout()
        reponse = self.client.get(reverse("rh:tableau_bord"))
        self.assertEqual(reponse.status_code, 302)
        self.assertIn("connexion", reponse.url)

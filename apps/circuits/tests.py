"""
Tests du socle : perimetres de gestion autonome et circuits parametrables.

L'organisation de reference est celle du decret n° 2026-509 : la DPFC releve de
la DGPCSP, comprend trois sous-directions, et deux familles de perimetres
autonomes lui sont rattachees — les antennes regionales et le CNRPN.
"""
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.circuits.modeles import installer_circuits_modeles
from apps.circuits.models import Circuit, Condition, Designation, Etape
from apps.circuits.services import etapes_resolues
from apps.core.models import Perimetre, Region, Structure
from apps.rh.models import Demande, TypeDemande
from apps.rh.services import soumettre

Agent = get_user_model()


class BaseOrganisation(TestCase):
    """Organigramme minimal : direction centrale, une antenne, le CNRPN."""

    @classmethod
    def setUpTestData(cls):
        cls.region = Region.objects.create(nom="Gbeke", code="GBK", chef_lieu="Bouake")

        cls.p_centrale = Perimetre.objects.create(
            code="DPFC", nom="Direction centrale", type=Perimetre.Type.CENTRALE
        )
        cls.p_antenne = Perimetre.objects.create(
            code="APFC-GBK", nom="Antenne de Bouake", type=Perimetre.Type.ANTENNE, region=cls.region
        )
        cls.p_cnrpn = Perimetre.objects.create(
            code="CNRPN", nom="Centre national de ressources pedagogiques numeriques",
            type=Perimetre.Type.CENTRE,
        )

        cls.dgpcsp = Structure.objects.create(
            nom="Direction Generale de la Pedagogie, des Curricula et du Suivi des Programmes",
            sigle="DGPCSP", type=Structure.Type.DIRECTION_GENERALE, perimetre=cls.p_centrale,
        )
        cls.direction = Structure.objects.create(
            nom="Direction de la Pedagogie et de la Formation Continue", sigle="DPFC",
            type=Structure.Type.DIRECTION, parent=cls.dgpcsp,
            perimetre=cls.p_centrale, perimetre_racine=True,
        )
        cls.sous_direction = Structure.objects.create(
            nom="Sous-direction de la Formation Pedagogique Continue", sigle="SDFPC",
            type=Structure.Type.SOUS_DIRECTION, parent=cls.direction, perimetre=cls.p_centrale,
        )
        cls.service = Structure.objects.create(
            nom="Service du personnel", sigle="SPAA", type=Structure.Type.SERVICE,
            parent=cls.direction, perimetre=cls.p_centrale,
        )
        cls.drena = Structure.objects.create(
            nom="DRENA de Bouake", sigle="DRENA-GBK", type=Structure.Type.DRENA, region=cls.region
        )
        cls.antenne = Structure.objects.create(
            nom="Antenne de Bouake", sigle="APFC-GBK", type=Structure.Type.ANTENNE,
            parent=cls.direction, region=cls.region, drena=cls.drena,
            perimetre=cls.p_antenne, perimetre_racine=True,
        )
        cls.cnrpn = Structure.objects.create(
            nom="Centre National de Ressources Pedagogiques Numeriques", sigle="CNRPN",
            type=Structure.Type.CENTRE, parent=cls.direction,
            perimetre=cls.p_cnrpn, perimetre_racine=True,
        )

        cls.directeur = cls._agent("D0001", "KOUAME", Agent.Role.DIRECTEUR, cls.direction)
        cls.rh = cls._agent("R0001", "TRAORE", Agent.Role.RH, cls.service)
        cls.sous_directeur = cls._agent("B0001", "BAMBA", Agent.Role.SOUS_DIRECTEUR,
                                        cls.sous_direction, cls.directeur)
        cls.agent_central = cls._agent("A0001", "YAO", Agent.Role.AGENT,
                                       cls.sous_direction, cls.sous_directeur)
        cls.dr = cls._agent("G0001", "ADJOUMANI", Agent.Role.DIRECTEUR_REGIONAL, cls.drena)
        cls.chef_antenne = cls._agent("C0001", "KONE", Agent.Role.CHEF_ANTENNE, cls.antenne, cls.dr)
        cls.agent_antenne = cls._agent("A0002", "OUATTARA", Agent.Role.AGENT,
                                       cls.antenne, cls.chef_antenne)
        cls.chef_centre = cls._agent("N0001", "ZADI", Agent.Role.CHEF_CENTRE, cls.cnrpn, cls.directeur)
        cls.agent_centre = cls._agent("N0002", "AKA", Agent.Role.AGENT, cls.cnrpn, cls.chef_centre)

        for structure, responsable in [
            (cls.direction, cls.directeur),
            (cls.sous_direction, cls.sous_directeur),
            (cls.service, cls.rh),
            (cls.drena, cls.dr),
            (cls.antenne, cls.chef_antenne),
            (cls.cnrpn, cls.chef_centre),
        ]:
            structure.responsable = responsable
            structure.save(update_fields=["responsable"])

    @classmethod
    def _agent(cls, matricule, nom, role, structure, superieur=None):
        return Agent.objects.create_user(
            matricule, password="motdepasse123", last_name=nom, first_name="Prenom",
            role=role, structure=structure, superieur=superieur,
        )

    def _demande(self, agent, type_acte=TypeDemande.CONGE_ANNUEL, **extra):
        debut = date.today() + timedelta(days=20)
        return Demande.objects.create(
            agent=agent, type=type_acte, motif="Motif de l'acte",
            date_debut=debut, date_fin=debut + timedelta(days=4),
            destination=extra.pop("destination", "Sakassou" if type_acte == TypeDemande.ORDRE_MISSION else ""),
            **extra,
        )


class PerimetreTest(BaseOrganisation):
    def test_l_agent_herite_du_perimetre_de_sa_structure(self):
        self.assertEqual(self.agent_central.perimetre, self.p_centrale)
        self.assertEqual(self.agent_antenne.perimetre, self.p_antenne)
        self.assertEqual(self.agent_centre.perimetre, self.p_cnrpn)

    def test_les_trois_perimetres_sont_autonomes(self):
        """Chacun instruit ses actes ; seule l'implantation les distingue."""
        for perimetre in (self.p_centrale, self.p_antenne, self.p_cnrpn):
            self.assertTrue(perimetre.est_autonome)
        self.assertFalse(self.p_centrale.est_deconcentre)
        self.assertTrue(self.p_antenne.est_deconcentre)
        self.assertTrue(self.p_cnrpn.est_deconcentre)

    def test_le_responsable_est_celui_de_la_structure_de_tete(self):
        self.assertEqual(self.p_antenne.responsable, self.chef_antenne)
        self.assertEqual(self.p_cnrpn.responsable, self.chef_centre)
        self.assertEqual(self.p_centrale.responsable, self.directeur)
        self.assertTrue(self.chef_centre.dirige_son_perimetre)
        self.assertFalse(self.agent_centre.dirige_son_perimetre)

    def test_un_responsable_ne_voit_que_son_perimetre(self):
        vus = set(self.chef_centre.perimetre_agents().values_list("matricule", flat=True))
        self.assertEqual(vus, {"N0001", "N0002"})
        vus = set(self.chef_antenne.perimetre_agents().values_list("matricule", flat=True))
        self.assertEqual(vus, {"C0001", "A0002"})

    def test_le_service_du_personnel_voit_tous_les_perimetres(self):
        self.assertEqual(self.rh.perimetre_agents().count(), Agent.objects.filter(is_active=True).count())

    def test_les_actes_sont_numerotes_par_perimetre(self):
        for agent in (self.agent_antenne, self.agent_centre, self.agent_central):
            soumettre(self._demande(agent, TypeDemande.PERMISSION))
        numeros = dict(
            Demande.objects.values_list("agent__matricule", "numero")
        )
        self.assertTrue(numeros["A0002"].endswith("/APFC-GBK"))
        self.assertTrue(numeros["N0002"].endswith("/CNRPN"))
        self.assertTrue(numeros["A0001"].endswith("/DPFC"))
        # Chaque perimetre tient sa propre serie : tous commencent au rang 1.
        self.assertTrue(all(n.startswith("PA-0001/") for n in numeros.values()))


class CircuitTest(BaseOrganisation):
    def test_circuit_central_suit_la_voie_hierarchique(self):
        etapes = etapes_resolues(self._demande(self.agent_central))
        self.assertEqual(
            [v.matricule for _, v in etapes], ["B0001", "R0001", "D0001"]
        )

    def test_le_chef_d_antenne_decide_seul_pour_son_agent(self):
        etapes = etapes_resolues(self._demande(self.agent_antenne))
        self.assertEqual([v.matricule for _, v in etapes], ["C0001"])

    def test_le_chef_de_centre_decide_seul_pour_son_agent(self):
        etapes = etapes_resolues(self._demande(self.agent_centre))
        self.assertEqual([v.matricule for _, v in etapes], ["N0001"])

    def test_mission_hors_ressort_est_etablie_par_la_drena(self):
        demande = self._demande(
            self.agent_antenne, TypeDemande.ORDRE_MISSION, hors_perimetre_drena=True
        )
        etapes = etapes_resolues(demande)
        self.assertEqual([v.matricule for _, v in etapes], ["C0001", "G0001"])
        self.assertEqual(demande.autorite_signataire, "Directeur regional (DRENA)")

    def test_l_acte_du_chef_d_antenne_remonte_a_la_drena(self):
        etapes = etapes_resolues(self._demande(self.chef_antenne))
        self.assertEqual([v.matricule for _, v in etapes], ["G0001", "D0001"])

    def test_l_acte_du_chef_de_centre_remonte_a_la_direction(self):
        """Le CNRPN n'a pas de ressort regional : l'acte va droit au directeur."""
        etapes = etapes_resolues(self._demande(self.chef_centre))
        self.assertEqual([v.matricule for _, v in etapes], ["D0001"])

    def test_un_perimetre_peut_avoir_son_propre_circuit(self):
        """Le circuit propre d'un perimetre prime sur le circuit modele."""
        circuit = Circuit.objects.create(
            perimetre=self.p_antenne, type_perimetre=Perimetre.Type.ANTENNE,
            type_acte=TypeDemande.CONGE_ANNUEL, libelle="Circuit renforce de Bouake",
        )
        Etape.objects.create(
            circuit=circuit, ordre=1, libelle="Decision du chef d'antenne",
            designation=Designation.RESPONSABLE_PERIMETRE,
            conditions=[Condition.SI_AGENT_NEST_PAS_RESPONSABLE],
        )
        Etape.objects.create(
            circuit=circuit, ordre=2, libelle="Visa du service du personnel",
            designation=Designation.ROLE, role=Agent.Role.RH, conditions=[Condition.SI_VISA_RH],
        )
        etapes = etapes_resolues(self._demande(self.agent_antenne))
        self.assertEqual([v.matricule for _, v in etapes], ["C0001", "R0001"])
        # Les autres perimetres gardent le circuit modele.
        self.assertEqual(
            [v.matricule for _, v in etapes_resolues(self._demande(self.agent_centre))], ["N0001"]
        )

    def test_une_etape_sans_titulaire_est_ignoree_si_facultative(self):
        """Le sous-directeur part a la retraite : le circuit saute son etape."""
        Agent.objects.filter(matricule="B0001").update(is_active=False)
        Structure.objects.filter(pk=self.sous_direction.pk).update(responsable=None)
        # Relecture depuis la base : l'objet en memoire porte encore l'ancien etat.
        agent = Agent.objects.get(pk=self.agent_central.pk)
        etapes = etapes_resolues(self._demande(agent))
        self.assertEqual([v.matricule for _, v in etapes], ["R0001", "D0001"])

    def test_une_etape_obligatoire_sans_titulaire_bloque(self):
        circuit = Circuit.objects.pour(self.p_centrale, TypeDemande.CONGE_ANNUEL)
        circuit.etapes.all().delete()
        Etape.objects.create(
            circuit=circuit, ordre=1, libelle="Avis du directeur general",
            designation=Designation.ROLE, role=Agent.Role.DIRECTEUR_GENERAL,
            conditions=[], facultative=False,
        )
        with self.assertRaises(ValueError):
            etapes_resolues(self._demande(self.agent_central))

    def test_un_agent_ne_valide_jamais_sa_propre_demande(self):
        etapes = etapes_resolues(self._demande(self.directeur))
        self.assertNotIn(self.directeur.pk, [v.pk for _, v in etapes])

    def test_les_circuits_modeles_couvrent_tous_les_types_d_actes(self):
        installer_circuits_modeles()
        for type_perimetre in Perimetre.Type.values:
            for type_acte in TypeDemande.values:
                with self.subTest(perimetre=type_perimetre, acte=type_acte):
                    self.assertIsNotNone(
                        Circuit.objects.filter(
                            perimetre__isnull=True, type_perimetre=type_perimetre,
                            type_acte=type_acte,
                        ).first()
                    )


class NettoyageOrganisationTest(BaseOrganisation):
    """Mise en conformite de l'organigramme avec le decret n° 2026-509."""

    def _obsolete(self, sigle, nom, **extra):
        return Structure.objects.create(
            nom=nom, sigle=sigle, type=Structure.Type.SOUS_DIRECTION,
            parent=self.direction, perimetre=self.p_centrale, **extra,
        )

    def _nettoyer(self, **options):
        from io import StringIO

        from django.core.management import call_command

        sortie = StringIO()
        call_command("nettoyer_organisation", stdout=sortie, **options)
        return sortie.getvalue()

    def test_simulation_ne_modifie_rien(self):
        self._obsolete("SDFC", "Sous-direction de la formation continue")
        sortie = self._nettoyer()
        self.assertIn("SIMULATION", sortie)
        self.assertTrue(Structure.objects.filter(sigle="SDFC").exists())

    def test_les_structures_hors_decret_sont_retirees(self):
        self._obsolete("SDFC", "Sous-direction de la formation continue")
        self._obsolete("SDPMS", "Sous-direction des programmes et manuels")
        self._nettoyer(appliquer=True)
        self.assertFalse(Structure.objects.filter(sigle__in=["SDFC", "SDPMS"]).exists())

    def test_le_service_du_personnel_est_conserve(self):
        """Decision expresse de la direction : SPAA subsiste."""
        Structure.objects.create(
            nom="Service du personnel et des affaires administratives", sigle="SPAA",
            type=Structure.Type.SERVICE, parent=self.direction, perimetre=self.p_centrale,
        )
        sortie = self._nettoyer(appliquer=True)
        self.assertTrue(Structure.objects.filter(sigle="SPAA", active=True).exists())
        self.assertIn("Conserve sur decision de la direction", sortie)

    def test_les_sous_directions_du_decret_sont_conservees(self):
        for sigle in ("SDPPBS", "SDIP"):
            self._obsolete(sigle, f"Sous-direction {sigle}")
        self._nettoyer(appliquer=True)
        self.assertEqual(
            Structure.objects.filter(sigle__in=["SDPPBS", "SDIP"], active=True).count(), 2
        )

    def test_les_agents_suivent_les_attributions_de_leur_structure(self):
        """
        La repartition suit les missions, non les personnes : chaque structure
        retiree designe la sous-direction qui reprend ses attributions.
        """
        sdppbs = Structure.objects.create(
            nom="Sous-direction des Programmes Pedagogiques", sigle="SDPPBS",
            type=Structure.Type.SOUS_DIRECTION, parent=self.direction,
            perimetre=self.p_centrale,
        )
        sdip = Structure.objects.create(
            nom="Sous-direction des Innovations Pedagogiques", sigle="SDIP",
            type=Structure.Type.SOUS_DIRECTION, parent=self.direction,
            perimetre=self.p_centrale,
        )
        # La SDFPC existe deja dans l'organigramme de reference.
        sdfpc = self.sous_direction
        formation = self._obsolete("SDFC", "Sous-direction de la formation continue")
        programmes = self._obsolete("SDPMS", "Sous-direction des programmes et manuels")
        numerique = self._obsolete("SDPRPN", "Service des ressources numeriques")

        agents = {
            "SDFC": self._agent("X0001", "FORMATION", Agent.Role.AGENT, formation),
            "SDPMS": self._agent("X0002", "PROGRAMMES", Agent.Role.AGENT, programmes),
            "SDPRPN": self._agent("X0003", "NUMERIQUE", Agent.Role.AGENT, numerique),
        }
        self._nettoyer(appliquer=True)

        attendu = {"SDFC": sdfpc, "SDPMS": sdppbs, "SDPRPN": sdip}
        for origine, agent in agents.items():
            with self.subTest(origine=origine):
                agent.refresh_from_db()
                self.assertEqual(agent.structure, attendu[origine])

    def test_sans_correspondance_les_agents_vont_a_la_direction(self):
        """Mieux vaut les remettre a la direction que de les placer au juge."""
        inconnue = self._obsolete("XXXX", "Service sans correspondance connue")
        agent = self._agent("X0001", "ORPHELIN", Agent.Role.AGENT, inconnue)
        sortie = self._nettoyer(appliquer=True)
        agent.refresh_from_db()
        self.assertEqual(agent.structure, self.direction)
        self.assertIn("DPFC", sortie)

    def test_une_correspondance_peut_etre_precisee_en_ligne_de_commande(self):
        cible = Structure.objects.create(
            nom="Sous-direction des Innovations Pedagogiques", sigle="SDIP",
            type=Structure.Type.SOUS_DIRECTION, parent=self.direction,
            perimetre=self.p_centrale,
        )
        inconnue = self._obsolete("XXXX", "Service sans correspondance connue")
        agent = self._agent("X0001", "ORPHELIN", Agent.Role.AGENT, inconnue)
        self._nettoyer(appliquer=True, correspondance=["XXXX=SDIP"])
        agent.refresh_from_db()
        self.assertEqual(agent.structure, cible)

    def test_une_correspondance_vers_une_structure_absente_se_replie(self):
        inconnue = self._obsolete("XXXX", "Service sans correspondance connue")
        agent = self._agent("X0001", "ORPHELIN", Agent.Role.AGENT, inconnue)
        self._nettoyer(appliquer=True, correspondance=["XXXX=INEXISTANTE"])
        agent.refresh_from_db()
        self.assertEqual(agent.structure, self.direction)

    def test_une_structure_porteuse_d_historique_est_desactivee(self):
        """Effacer la structure effacerait la provenance des actes deja pris."""
        from apps.rh.models import Demande, TypeDemande

        obsolete = self._obsolete("SDPRPN", "Service des ressources numeriques")
        debut = date.today() + timedelta(days=10)
        Demande.objects.create(
            agent=self.agent_central, type=TypeDemande.PERMISSION, motif="Historique",
            date_debut=debut, date_fin=debut, structure=obsolete,
        )
        sortie = self._nettoyer(appliquer=True)
        obsolete.refresh_from_db()
        self.assertFalse(obsolete.active)
        self.assertIn("historique a preserver", sortie)

    def test_la_dpfc_est_rattachee_a_la_direction_generale(self):
        """Article 27 : une base anterieure au decret n'a pas ce rattachement."""
        Structure.objects.filter(pk=self.direction.pk).update(parent=None)
        self._nettoyer(appliquer=True)
        self.direction.refresh_from_db()
        self.assertEqual(self.direction.parent, self.dgpcsp)

    def test_un_second_passage_est_sans_effet(self):
        obsolete = self._obsolete("SDPRPN", "Service des ressources numeriques")
        from apps.rh.models import Demande, TypeDemande

        debut = date.today() + timedelta(days=10)
        Demande.objects.create(
            agent=self.agent_central, type=TypeDemande.PERMISSION, motif="Historique",
            date_debut=debut, date_fin=debut, structure=obsolete,
        )
        self._nettoyer(appliquer=True)
        sortie = self._nettoyer(appliquer=True)
        self.assertIn("conforme au decret", sortie)
        self.assertIn("Deja retirees", sortie)

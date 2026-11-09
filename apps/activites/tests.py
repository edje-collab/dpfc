"""Tests du pilotage des activites : plans, avancement, consolidation."""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.activites.models import Activite, Axe, PlanAction
from apps.activites.services import (
    ErreurPlan,
    annuler_activite,
    chronogramme,
    clore_plan,
    consolidation_nationale,
    enregistrer_avancement,
    renvoyer_plan,
    reporter_activite,
    soumettre_plan,
    tableau_de_bord,
    valider_plan,
)
from apps.core.models import Perimetre, Region, Structure

Agent = get_user_model()
ANNEE = timezone.localdate().year


class BasePilotage(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.region = Region.objects.create(nom="Gbeke", code="GBK", chef_lieu="Bouake")
        cls.p_centrale = Perimetre.objects.create(
            code="DPFC", nom="Direction centrale", type=Perimetre.Type.CENTRALE
        )
        cls.p_antenne = Perimetre.objects.create(
            code="APFC-GBK", nom="Antenne de Bouake", type=Perimetre.Type.ANTENNE, region=cls.region
        )
        cls.direction = Structure.objects.create(
            nom="Direction de la Pedagogie", sigle="DPFC", type=Structure.Type.DIRECTION,
            perimetre=cls.p_centrale, perimetre_racine=True,
        )
        cls.antenne = Structure.objects.create(
            nom="Antenne de Bouake", sigle="APFC-GBK", type=Structure.Type.ANTENNE,
            region=cls.region, perimetre=cls.p_antenne, perimetre_racine=True,
        )
        cls.directeur = Agent.objects.create_user(
            "D0001", password="motdepasse123", last_name="KOUAME", first_name="Sylvie",
            role=Agent.Role.DIRECTEUR, structure=cls.direction,
        )
        cls.chef = Agent.objects.create_user(
            "C0001", password="motdepasse123", last_name="KONE", first_name="Adama",
            role=Agent.Role.CHEF_ANTENNE, structure=cls.antenne,
        )
        cls.agent = Agent.objects.create_user(
            "A0001", password="motdepasse123", last_name="OUATTARA", first_name="Fatou",
            role=Agent.Role.AGENT, structure=cls.antenne, superieur=cls.chef,
        )
        cls.direction.responsable = cls.directeur
        cls.direction.save(update_fields=["responsable"])
        cls.antenne.responsable = cls.chef
        cls.antenne.save(update_fields=["responsable"])

        cls.axe = Axe.objects.create(code="AX1", libelle="Qualite des apprentissages", ordre=1)
        cls.axe2 = Axe.objects.create(code="AX2", libelle="Formation continue", ordre=2)

    def _plan(self, perimetre=None, annee=ANNEE):
        return PlanAction.objects.create(perimetre=perimetre or self.p_antenne, annee=annee)

    def _activite(self, plan, **extra):
        debut = extra.pop("debut", date(ANNEE, 3, 1))
        fin = extra.pop("fin", date(ANNEE, 3, 10))
        return Activite.objects.create(
            plan=plan,
            axe=extra.pop("axe", self.axe),
            intitule=extra.pop("intitule", "Atelier de production de guides"),
            date_debut_prevue=debut,
            date_fin_prevue=fin,
            budget_prevu=extra.pop("budget_prevu", 1_000_000),
            effectif_prevu=extra.pop("effectif_prevu", 50),
            responsable=extra.pop("responsable", self.agent),
            **extra,
        )


class PlanActionTest(BasePilotage):
    def test_un_seul_plan_par_perimetre_et_par_annee(self):
        self._plan()
        from django.db import IntegrityError, transaction

        with self.assertRaises(IntegrityError), transaction.atomic():
            PlanAction.objects.create(perimetre=self.p_antenne, annee=ANNEE)

    def test_le_code_des_activites_est_sequentiel_dans_le_plan(self):
        plan = self._plan()
        codes = [self._activite(plan).code for _ in range(3)]
        self.assertEqual(codes, ["A-001", "A-002", "A-003"])
        # Un autre plan repart a 1.
        autre = self._plan(self.p_centrale)
        self.assertEqual(self._activite(autre).code, "A-001")

    def test_un_plan_sans_activite_ne_peut_etre_soumis(self):
        plan = self._plan()
        with self.assertRaises(ErreurPlan):
            soumettre_plan(plan, par=self.chef)

    def test_cycle_soumission_validation(self):
        plan = self._plan()
        self._activite(plan)
        soumettre_plan(plan, par=self.chef)
        plan.refresh_from_db()
        self.assertEqual(plan.statut, PlanAction.Statut.SOUMIS)

        valider_plan(plan, par=self.directeur)
        plan.refresh_from_db()
        self.assertEqual(plan.statut, PlanAction.Statut.VALIDE)
        self.assertEqual(plan.valide_par, self.directeur)
        self.assertTrue(plan.est_en_execution)

    def test_le_plan_d_une_antenne_est_valide_par_le_directeur(self):
        plan = self._plan()
        self._activite(plan)
        soumettre_plan(plan, par=self.chef)
        self.assertEqual(self.directeur.notifications.count(), 1)

    def test_renvoi_exige_un_motif_et_ramene_en_preparation(self):
        plan = self._plan()
        self._activite(plan)
        soumettre_plan(plan, par=self.chef)
        with self.assertRaises(ErreurPlan):
            renvoyer_plan(plan, par=self.directeur, motif="   ")
        renvoyer_plan(plan, par=self.directeur, motif="Budget a revoir.")
        plan.refresh_from_db()
        self.assertEqual(plan.statut, PlanAction.Statut.BROUILLON)
        self.assertEqual(plan.motif_rejet, "Budget a revoir.")
        self.assertIsNone(plan.soumis_le)

    def test_cloture_reporte_les_activites_restees_ouvertes(self):
        plan = self._plan()
        ouverte = self._activite(plan)
        achevee = self._activite(plan, intitule="Seminaire")
        self._activite(plan, intitule="Annulee")
        soumettre_plan(plan, par=self.chef)
        valider_plan(plan, par=self.directeur)
        enregistrer_avancement(achevee, self.agent, 100, "Termine.")
        annuler_activite(plan.activites.get(intitule="Annulee"), self.directeur, "Sans objet.")

        plan, reportees = clore_plan(plan, par=self.directeur)
        self.assertEqual(reportees, 1)
        ouverte.refresh_from_db()
        achevee.refresh_from_db()
        self.assertEqual(ouverte.statut, Activite.Statut.REPORTEE)
        self.assertEqual(achevee.statut, Activite.Statut.REALISEE)
        self.assertEqual(plan.statut, PlanAction.Statut.CLOS)

    def test_un_plan_non_valide_ne_peut_etre_clos(self):
        plan = self._plan()
        with self.assertRaises(ErreurPlan):
            clore_plan(plan, par=self.directeur)


class AvancementTest(BasePilotage):
    def setUp(self):
        self.plan = self._plan()
        self.activite = self._activite(self.plan)
        soumettre_plan(self.plan, par=self.chef)
        valider_plan(self.plan, par=self.directeur)

    def test_le_premier_point_fait_passer_l_activite_en_cours(self):
        enregistrer_avancement(self.activite, self.agent, 40, "Conception des supports.")
        self.activite.refresh_from_db()
        self.assertEqual(self.activite.statut, Activite.Statut.EN_COURS)
        self.assertEqual(self.activite.avancement, 40)
        self.assertIsNotNone(self.activite.date_debut_reelle)

    def test_cent_pour_cent_cloture_l_activite(self):
        enregistrer_avancement(self.activite, self.agent, 100, "Atelier tenu.")
        self.activite.refresh_from_db()
        self.assertEqual(self.activite.statut, Activite.Statut.REALISEE)
        self.assertTrue(self.activite.est_achevee)
        self.assertIsNotNone(self.activite.date_fin_reelle)

    def test_les_beneficiaires_et_les_montants_se_cumulent(self):
        enregistrer_avancement(self.activite, self.agent, 30, "Premiere session.",
                               effectif_touche=20, montant_engage=300_000)
        enregistrer_avancement(self.activite, self.agent, 70, "Deuxieme session.",
                               effectif_touche=25, montant_engage=400_000)
        self.activite.refresh_from_db()
        self.assertEqual(self.activite.effectif_realise, 45)
        self.assertEqual(self.activite.budget_execute, Decimal("700000"))
        self.assertEqual(self.activite.taux_execution_budgetaire, 70)
        self.assertEqual(self.activite.taux_couverture_beneficiaires, 90)

    def test_l_avancement_suit_le_dernier_point(self):
        enregistrer_avancement(self.activite, self.agent, 60, "Avance.")
        enregistrer_avancement(self.activite, self.agent, 45, "Correction apres verification.")
        self.activite.refresh_from_db()
        self.assertEqual(self.activite.avancement, 45)

    def test_avancement_refuse_au_dela_de_cent(self):
        with self.assertRaises(ErreurPlan):
            enregistrer_avancement(self.activite, self.agent, 120, "Impossible.")

    def test_avancement_refuse_sur_un_plan_non_valide(self):
        plan = self._plan(self.p_centrale)
        activite = self._activite(plan)
        with self.assertRaises(ErreurPlan):
            enregistrer_avancement(activite, self.directeur, 10, "Trop tot.")

    def test_avancement_refuse_sur_une_activite_annulee(self):
        annuler_activite(self.activite, self.directeur, "Sans objet.")
        with self.assertRaises(ErreurPlan):
            enregistrer_avancement(self.activite, self.agent, 10, "Non.")

    def test_report_exige_un_motif(self):
        with self.assertRaises(ErreurPlan):
            reporter_activite(self.activite, self.chef, "")
        reporter_activite(self.activite, self.chef, "Financement non disponible.",
                          nouvelle_fin=date(ANNEE, 11, 30))
        self.activite.refresh_from_db()
        self.assertEqual(self.activite.statut, Activite.Statut.REPORTEE)
        self.assertEqual(self.activite.date_fin_prevue, date(ANNEE, 11, 30))

    def test_une_activite_realisee_ne_peut_etre_annulee(self):
        enregistrer_avancement(self.activite, self.agent, 100, "Fait.")
        with self.assertRaises(ErreurPlan):
            annuler_activite(self.activite, self.directeur, "Trop tard.")


class RetardEtConsolidationTest(BasePilotage):
    def setUp(self):
        self.plan = self._plan()
        hier = timezone.localdate() - timedelta(days=5)
        self.en_retard = self._activite(
            self.plan, intitule="Suivi des ecoles", debut=date(ANNEE, 1, 10), fin=hier
        )
        self.a_venir = self._activite(
            self.plan, intitule="Atelier de decembre", axe=self.axe2,
            debut=date(ANNEE, 12, 1), fin=date(ANNEE, 12, 5), budget_prevu=500_000,
        )
        soumettre_plan(self.plan, par=self.chef)
        valider_plan(self.plan, par=self.directeur)

    def test_une_activite_echue_et_non_achevee_est_en_retard(self):
        self.assertTrue(self.en_retard.est_en_retard)
        self.assertGreater(self.en_retard.jours_de_retard, 0)
        self.assertFalse(self.a_venir.est_en_retard)
        self.assertEqual(self.plan.activites.en_retard().count(), 1)

    def test_une_activite_reportee_ou_realisee_n_est_plus_en_retard(self):
        enregistrer_avancement(self.en_retard, self.agent, 100, "Rattrape.")
        self.en_retard.refresh_from_db()
        self.assertFalse(self.en_retard.est_en_retard)

    def test_taux_d_execution_du_plan_est_la_moyenne_des_activites(self):
        enregistrer_avancement(self.en_retard, self.agent, 100, "Fait.")
        enregistrer_avancement(self.a_venir, self.agent, 50, "A mi-parcours.")
        self.assertEqual(self.plan.taux_execution, 75)

    def test_les_activites_annulees_sortent_du_taux(self):
        enregistrer_avancement(self.en_retard, self.agent, 100, "Fait.")
        annuler_activite(self.a_venir, self.directeur, "Sans objet.")
        self.assertEqual(self.plan.taux_execution, 100)

    def test_synthese_par_axe(self):
        enregistrer_avancement(self.en_retard, self.agent, 100, "Fait.", montant_engage=800_000)
        lignes = {ligne["code"]: ligne for ligne in self.plan.synthese_par_axe()}
        self.assertEqual(lignes["AX1"]["avancement"], 100)
        self.assertEqual(lignes["AX1"]["execute"], Decimal("800000"))
        self.assertEqual(lignes["AX2"]["avancement"], 0)

    def test_le_tableau_de_bord_est_limite_au_perimetre(self):
        plan_central = self._plan(self.p_centrale)
        self._activite(plan_central, intitule="Activite centrale")

        vue_chef = tableau_de_bord(self.chef)
        self.assertEqual(vue_chef["nb_activites"], 2)
        self.assertEqual(list(vue_chef["plans"]), [self.plan])

        vue_directeur = tableau_de_bord(self.directeur)
        self.assertEqual(vue_directeur["nb_activites"], 3)
        self.assertEqual(vue_directeur["plans"].count(), 2)

    def test_consolidation_nationale_liste_chaque_perimetre(self):
        self._plan(self.p_centrale)
        lignes = consolidation_nationale()
        self.assertEqual(len(lignes), 2)
        par_code = {ligne["perimetre"].code: ligne for ligne in lignes}
        self.assertEqual(par_code["APFC-GBK"]["nb_activites"], 2)
        self.assertEqual(par_code["APFC-GBK"]["en_retard"], 1)
        self.assertEqual(par_code["DPFC"]["nb_activites"], 0)

    def test_le_chronogramme_positionne_les_activites_sur_les_mois(self):
        lignes = {ligne["activite"].intitule: ligne for ligne in chronogramme(self.plan)}
        decembre = lignes["Atelier de decembre"]
        self.assertEqual(decembre["debut"], 12)
        self.assertEqual(decembre["duree"], 1)
        self.assertEqual(decembre["avant"], 11)
        self.assertEqual(decembre["apres"], 0)
        janvier = lignes["Suivi des ecoles"]
        self.assertEqual(janvier["debut"], 1)
        self.assertEqual(janvier["avant"], 0)


class IndicateurTest(BasePilotage):
    def test_taux_d_atteinte_borne_a_cent(self):
        plan = self._plan()
        activite = self._activite(plan)
        indicateur = activite.indicateurs.create(
            libelle="Enseignants formes", unite="enseignants", valeur_cible=100, valeur_realisee=60
        )
        self.assertEqual(indicateur.taux_atteinte, 60)
        indicateur.valeur_realisee = 150
        self.assertEqual(indicateur.taux_atteinte, 100)

    def test_cible_nulle_ne_divise_pas_par_zero(self):
        plan = self._plan()
        activite = self._activite(plan)
        indicateur = activite.indicateurs.create(libelle="Sans cible", valeur_cible=0)
        self.assertEqual(indicateur.taux_atteinte, 0)

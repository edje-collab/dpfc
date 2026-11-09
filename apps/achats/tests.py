"""Tests des achats et des stocks."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.achats.models import (
    Article,
    BonCommande,
    Equipement,
    ExpressionBesoin,
    Fournisseur,
    MouvementStock,
)
from apps.achats.services import (
    ErreurAchat,
    annuler_commande,
    articles_sous_seuil,
    besoins_a_valider,
    decider_besoin,
    emettre_commande,
    enregistrer_mouvement,
    recalculer_stock,
    receptionner,
    retenir_offre,
    solder,
    soumettre_besoin,
    tableau_achats,
)
from apps.activites.models import Activite, Axe, PlanAction
from apps.circuits.modeles import SEUIL_DIRECTION, SEUIL_RESPONSABLE, installer_circuits_modeles
from apps.core.models import Perimetre, Region, Structure

Agent = get_user_model()


class BaseAchats(TestCase):
    @classmethod
    def setUpTestData(cls):
        installer_circuits_modeles()
        cls.region = Region.objects.create(nom="Gbeke", code="GBK", chef_lieu="Bouake")
        cls.p_centrale = Perimetre.objects.create(
            code="DPFC", nom="Direction centrale", type=Perimetre.Type.CENTRALE
        )
        cls.p_antenne = Perimetre.objects.create(
            code="APFC-GBK", nom="Antenne de Bouake", type=Perimetre.Type.ANTENNE, region=cls.region
        )
        cls.direction = Structure.objects.create(
            nom="Direction", sigle="DPFC", type=Structure.Type.DIRECTION,
            perimetre=cls.p_centrale, perimetre_racine=True,
        )
        cls.sous_direction = Structure.objects.create(
            nom="Sous-direction", sigle="SDFPC", type=Structure.Type.SOUS_DIRECTION,
            parent=cls.direction, perimetre=cls.p_centrale,
        )
        cls.antenne = Structure.objects.create(
            nom="Antenne de Bouake", sigle="APFC-GBK", type=Structure.Type.ANTENNE,
            region=cls.region, perimetre=cls.p_antenne, perimetre_racine=True,
        )
        cls.directeur = cls._agent("D0001", "KOUAME", Agent.Role.DIRECTEUR, cls.direction)
        cls.sous_directeur = cls._agent("B0001", "BAMBA", Agent.Role.SOUS_DIRECTEUR,
                                        cls.sous_direction, cls.directeur)
        cls.agent = cls._agent("A0001", "YAO", Agent.Role.AGENT, cls.sous_direction,
                               cls.sous_directeur)
        cls.chef = cls._agent("C0001", "KONE", Agent.Role.CHEF_ANTENNE, cls.antenne)
        cls.agent_antenne = cls._agent("A0002", "OUATTARA", Agent.Role.AGENT, cls.antenne, cls.chef)
        for structure, responsable in [
            (cls.direction, cls.directeur),
            (cls.sous_direction, cls.sous_directeur),
            (cls.antenne, cls.chef),
        ]:
            structure.responsable = responsable
            structure.save(update_fields=["responsable"])

        cls.fournisseur = Fournisseur.objects.create(
            nom="Papeterie du Centre", ncc="CI-123456", domaine="Fournitures"
        )
        cls.autre_fournisseur = Fournisseur.objects.create(
            nom="Bureau Plus", ncc="CI-654321", domaine="Fournitures"
        )

    @classmethod
    def _agent(cls, matricule, nom, role, structure, superieur=None):
        return Agent.objects.create_user(
            matricule, password="motdepasse123", last_name=nom, first_name="Prenom",
            role=role, structure=structure, superieur=superieur,
        )

    def _article(self, perimetre=None, code="RAM-A4", **extra):
        return Article.objects.create(
            perimetre=perimetre or self.p_centrale, code=code,
            designation=extra.pop("designation", "Rame de papier A4"),
            unite=extra.pop("unite", "rame"), **extra,
        )

    def _besoin(self, perimetre=None, demandeur=None, lignes=None, **extra):
        besoin = ExpressionBesoin.objects.create(
            perimetre=perimetre or self.p_centrale,
            objet=extra.pop("objet", "Fournitures de bureau du trimestre"),
            demandeur=demandeur or self.agent, **extra,
        )
        for designation, quantite, prix in (lignes or [("Rame de papier A4", 10, 5_000)]):
            besoin.lignes.create(designation=designation, quantite=quantite, prix_unitaire=prix)
        return besoin


class NumerotationTest(BaseAchats):
    def test_serie_annuelle_par_perimetre(self):
        annee = timezone.localdate().year
        central = self._besoin()
        antenne = self._besoin(self.p_antenne, self.agent_antenne)
        self.assertEqual(central.numero, f"EB-0001/{annee}/DPFC")
        self.assertEqual(antenne.numero, f"EB-0001/{annee}/APFC-GBK")
        self.assertEqual(self._besoin().numero, f"EB-0002/{annee}/DPFC")

    def test_le_montant_estime_derive_des_lignes(self):
        besoin = self._besoin(lignes=[("Papier", 10, 5_000), ("Stylos", 4, 2_500)])
        self.assertEqual(besoin.montant_estime, 60_000)

    def test_un_besoin_sans_ligne_ne_se_soumet_pas(self):
        besoin = ExpressionBesoin.objects.create(
            perimetre=self.p_centrale, objet="Vide", demandeur=self.agent
        )
        with self.assertRaises(ErreurAchat):
            soumettre_besoin(besoin)


class CircuitSeuilTest(BaseAchats):
    """Le circuit s'allonge avec le montant engage."""

    def test_petite_depense_s_arrete_au_superieur(self):
        besoin = self._besoin(lignes=[("Stylos", 10, 500)])  # 5 000 FCFA
        soumettre_besoin(besoin)
        self.assertEqual(
            [v.valideur.matricule for v in besoin.validations.all()], ["B0001"]
        )

    def test_depense_moyenne_remonte_au_responsable_du_perimetre(self):
        montant = SEUIL_RESPONSABLE + 50_000
        besoin = self._besoin(lignes=[("Mobilier", 1, montant)])
        soumettre_besoin(besoin)
        matricules = [v.valideur.matricule for v in besoin.validations.all()]
        # Superieur, sous-directeur, puis le directeur comme responsable du perimetre.
        self.assertEqual(matricules, ["B0001", "D0001"])

    def test_engagement_important_remonte_a_la_direction(self):
        besoin = self._besoin(lignes=[("Vehicule", 1, SEUIL_DIRECTION + 1)])
        soumettre_besoin(besoin)
        matricules = [v.valideur.matricule for v in besoin.validations.all()]
        self.assertIn("D0001", matricules)
        self.assertEqual(matricules[-1], "D0001")

    def test_le_seuil_s_applique_aussi_en_antenne(self):
        petit = self._besoin(self.p_antenne, self.agent_antenne, lignes=[("Craie", 20, 500)])
        soumettre_besoin(petit)
        self.assertEqual([v.valideur.matricule for v in petit.validations.all()], ["C0001"])

        gros = self._besoin(
            self.p_antenne, self.agent_antenne, objet="Photocopieur",
            lignes=[("Photocopieur", 1, SEUIL_DIRECTION + 100_000)],
        )
        soumettre_besoin(gros)
        matricules = [v.valideur.matricule for v in gros.validations.all()]
        self.assertEqual(matricules, ["C0001", "D0001"])


class ValidationTest(BaseAchats):
    def setUp(self):
        self.besoin = self._besoin(lignes=[("Mobilier", 1, SEUIL_RESPONSABLE + 10_000)])
        soumettre_besoin(self.besoin)

    def test_parcours_favorable_complet(self):
        while (etape := self.besoin.etape_courante()) is not None:
            decider_besoin(etape, True, "Avis favorable.")
            self.besoin.refresh_from_db()
        self.assertEqual(self.besoin.statut, ExpressionBesoin.Statut.VALIDE)
        self.assertTrue(self.besoin.est_validee)
        self.assertEqual(self.besoin.progression(), 100)

    def test_un_avis_defavorable_ferme_le_besoin(self):
        decider_besoin(self.besoin.etape_courante(), False, "Credit indisponible.")
        self.besoin.refresh_from_db()
        self.assertEqual(self.besoin.statut, ExpressionBesoin.Statut.REJETE)
        self.assertEqual(self.besoin.motif_rejet, "Credit indisponible.")
        self.assertTrue(
            self.besoin.validations.filter(decision="IGNOREE").exists()
        )

    def test_une_etape_ne_se_tranche_pas_deux_fois(self):
        etape = self.besoin.etape_courante()
        decider_besoin(etape, True)
        with self.assertRaises(ErreurAchat):
            decider_besoin(etape, True)

    def test_la_corbeille_ne_montre_que_l_etape_courante(self):
        self.assertEqual(len(besoins_a_valider(self.sous_directeur)), 1)
        self.assertEqual(len(besoins_a_valider(self.directeur)), 0)
        decider_besoin(self.besoin.etape_courante(), True)
        self.assertEqual(len(besoins_a_valider(self.sous_directeur)), 0)
        self.assertEqual(len(besoins_a_valider(self.directeur)), 1)

    def test_un_besoin_ne_se_soumet_pas_deux_fois(self):
        with self.assertRaises(ErreurAchat):
            soumettre_besoin(self.besoin)


class CommandeTest(BaseAchats):
    def setUp(self):
        self.besoin = self._besoin(lignes=[("Papier", 20, 5_000)])
        soumettre_besoin(self.besoin)
        while (etape := self.besoin.etape_courante()) is not None:
            decider_besoin(etape, True)
        self.besoin.refresh_from_db()

    def _offres(self):
        a = self.besoin.offres.create(fournisseur=self.fournisseur, montant=95_000)
        b = self.besoin.offres.create(fournisseur=self.autre_fournisseur, montant=110_000)
        return a, b

    def test_une_seule_offre_ne_fait_pas_une_consultation(self):
        offre = self.besoin.offres.create(fournisseur=self.fournisseur, montant=95_000)
        with self.assertRaises(ErreurAchat):
            retenir_offre(offre, self.directeur)

    def test_retenir_une_offre_ecarte_les_autres(self):
        a, b = self._offres()
        retenir_offre(a, self.directeur)
        a.refresh_from_db()
        b.refresh_from_db()
        self.assertTrue(a.retenue)
        self.assertFalse(b.retenue)
        self.assertEqual(self.besoin.offre_retenue, a)

    def test_commande_sans_offre_retenue_refusee(self):
        self._offres()
        with self.assertRaises(ErreurAchat):
            emettre_commande(self.besoin, self.directeur)

    def test_commande_refusee_si_le_compte_contribuable_manque(self):
        sans_ncc = Fournisseur.objects.create(nom="Sans NCC")
        self.besoin.offres.create(fournisseur=sans_ncc, montant=90_000)
        offre = self.besoin.offres.create(fournisseur=self.fournisseur, montant=95_000)
        retenir_offre(offre, self.directeur)
        self.besoin.offres.update(retenue=False)
        offre_sans_ncc = self.besoin.offres.get(fournisseur=sans_ncc)
        offre_sans_ncc.retenue = True
        offre_sans_ncc.save()
        with self.assertRaises(ErreurAchat):
            emettre_commande(self.besoin, self.directeur)

    def test_emission_du_bon_de_commande(self):
        a, _ = self._offres()
        retenir_offre(a, self.directeur)
        commande = emettre_commande(self.besoin, self.directeur)
        self.besoin.refresh_from_db()
        annee = timezone.localdate().year
        self.assertEqual(commande.numero, f"BC-0001/{annee}/DPFC")
        self.assertEqual(commande.montant, 95_000)
        self.assertEqual(self.besoin.statut, ExpressionBesoin.Statut.COMMANDE)

    def test_un_besoin_non_valide_ne_se_commande_pas(self):
        autre = self._besoin(objet="Non valide")
        with self.assertRaises(ErreurAchat):
            emettre_commande(autre, self.directeur)

    def test_une_commande_payee_ne_s_annule_pas(self):
        a, _ = self._offres()
        retenir_offre(a, self.directeur)
        commande = emettre_commande(self.besoin, self.directeur)
        receptionner(commande, self.directeur)
        solder(commande, self.directeur, "FAC-001", 95_000)
        commande.refresh_from_db()
        with self.assertRaises(ErreurAchat):
            annuler_commande(commande, self.directeur, "Trop tard.")


class StockTest(BaseAchats):
    def setUp(self):
        self.article = self._article(seuil_alerte=5)

    def test_le_stock_part_de_zero(self):
        self.assertEqual(self.article.stock, 0)
        self.assertTrue(self.article.sous_seuil)

    def test_entree_et_sortie(self):
        enregistrer_mouvement(self.article, MouvementStock.Type.ENTREE, 20, self.directeur)
        self.article.refresh_from_db()
        self.assertEqual(self.article.stock, 20)
        self.assertFalse(self.article.sous_seuil)

        enregistrer_mouvement(
            self.article, MouvementStock.Type.SORTIE, 8, self.directeur,
            beneficiaire="Sous-direction de la formation",
        )
        self.article.refresh_from_db()
        self.assertEqual(self.article.stock, 12)

    def test_une_sortie_superieure_au_stock_est_refusee(self):
        enregistrer_mouvement(self.article, MouvementStock.Type.ENTREE, 5, self.directeur)
        with self.assertRaises(ErreurAchat) as erreur:
            enregistrer_mouvement(
                self.article, MouvementStock.Type.SORTIE, 6, self.directeur, beneficiaire="X"
            )
        self.assertIn("insuffisant", str(erreur.exception))
        self.article.refresh_from_db()
        self.assertEqual(self.article.stock, 5)

    def test_une_sortie_exige_un_beneficiaire(self):
        enregistrer_mouvement(self.article, MouvementStock.Type.ENTREE, 5, self.directeur)
        with self.assertRaises(ErreurAchat):
            enregistrer_mouvement(self.article, MouvementStock.Type.SORTIE, 1, self.directeur)

    def test_une_quantite_nulle_ou_negative_est_refusee(self):
        for quantite in (0, -3):
            with self.subTest(quantite=quantite):
                with self.assertRaises(ErreurAchat):
                    enregistrer_mouvement(
                        self.article, MouvementStock.Type.ENTREE, quantite, self.directeur
                    )

    def test_l_inventaire_fixe_la_quantite_comptee(self):
        enregistrer_mouvement(self.article, MouvementStock.Type.ENTREE, 20, self.directeur)
        enregistrer_mouvement(
            self.article, MouvementStock.Type.INVENTAIRE, 17, self.directeur,
            motif="Comptage annuel : trois rames manquantes.",
        )
        self.article.refresh_from_db()
        self.assertEqual(self.article.stock, 17)

    def test_le_stock_s_explique_par_le_journal(self):
        """La vue cachee doit toujours coincider avec le journal."""
        enregistrer_mouvement(self.article, MouvementStock.Type.ENTREE, 30, self.directeur)
        enregistrer_mouvement(
            self.article, MouvementStock.Type.SORTIE, 12, self.directeur, beneficiaire="X"
        )
        enregistrer_mouvement(self.article, MouvementStock.Type.INVENTAIRE, 15, self.directeur)
        enregistrer_mouvement(self.article, MouvementStock.Type.ENTREE, 10, self.directeur)
        self.article.refresh_from_db()
        self.assertEqual(self.article.stock, 25)
        self.assertEqual(self.article.stock_reel, 25)
        self.assertEqual(recalculer_stock(self.article), 0)

    def test_chaque_mouvement_conserve_le_stock_resultant(self):
        enregistrer_mouvement(self.article, MouvementStock.Type.ENTREE, 10, self.directeur)
        enregistrer_mouvement(
            self.article, MouvementStock.Type.SORTIE, 4, self.directeur, beneficiaire="X"
        )
        self.assertEqual(
            list(self.article.mouvements.order_by("id").values_list("stock_apres", flat=True)),
            [10, 6],
        )

    def test_recalcul_apres_suppression_d_un_mouvement(self):
        enregistrer_mouvement(self.article, MouvementStock.Type.ENTREE, 10, self.directeur)
        sortie = enregistrer_mouvement(
            self.article, MouvementStock.Type.SORTIE, 4, self.directeur, beneficiaire="X"
        )
        sortie.delete()
        self.article.refresh_from_db()
        self.assertEqual(recalculer_stock(self.article), 4)
        self.assertEqual(self.article.stock, 10)

    def test_articles_sous_seuil_limites_au_perimetre(self):
        self._article(self.p_antenne, code="CRAIE", designation="Craie", seuil_alerte=10)
        self.assertEqual(articles_sous_seuil(self.chef).count(), 1)
        self.assertEqual(articles_sous_seuil(self.directeur).count(), 2)

    def test_un_code_article_est_unique_dans_le_perimetre(self):
        from django.db import IntegrityError, transaction

        with self.assertRaises(IntegrityError), transaction.atomic():
            self._article(code="RAM-A4")
        # Mais le meme code est libre dans un autre perimetre.
        self.assertIsNotNone(self._article(self.p_antenne, code="RAM-A4"))


class ReceptionTest(BaseAchats):
    def setUp(self):
        self.article = self._article(code="RAM-A4", seuil_alerte=5)
        self.besoin = self._besoin(lignes=[])
        self.besoin.lignes.create(
            article=self.article, designation="Rame A4", quantite=20,
            unite="rame", prix_unitaire=5_000,
        )
        self.besoin.lignes.create(
            designation="Prestation de reliure", quantite=1, prix_unitaire=30_000
        )
        soumettre_besoin(self.besoin)
        while (etape := self.besoin.etape_courante()) is not None:
            decider_besoin(etape, True)
        self.besoin.refresh_from_db()
        self.besoin.offres.create(fournisseur=self.fournisseur, montant=125_000)
        offre = self.besoin.offres.create(fournisseur=self.autre_fournisseur, montant=130_000)
        retenir_offre(self.besoin.offres.get(fournisseur=self.fournisseur), self.directeur)
        self.offre_ecartee = offre
        self.commande = emettre_commande(self.besoin, self.directeur)

    def test_la_reception_alimente_le_magasin(self):
        _, entrees = receptionner(self.commande, self.directeur)
        self.article.refresh_from_db()
        self.assertEqual(len(entrees), 1)  # la prestation n'est pas stockee
        self.assertEqual(self.article.stock, 20)
        self.assertEqual(entrees[0].bon_commande, self.commande)

    def test_reception_partielle(self):
        ligne = self.besoin.lignes.get(article=self.article)
        receptionner(self.commande, self.directeur, lignes={ligne.pk: 15},
                     observations="Cinq rames manquantes.")
        self.article.refresh_from_db()
        self.commande.refresh_from_db()
        self.assertEqual(self.article.stock, 15)
        self.assertIn("manquantes", self.commande.observations_reception)

    def test_une_commande_ne_se_receptionne_pas_deux_fois(self):
        receptionner(self.commande, self.directeur)
        self.commande.refresh_from_db()
        with self.assertRaises(ErreurAchat):
            receptionner(self.commande, self.directeur)

    def test_la_facture_solde_le_besoin(self):
        receptionner(self.commande, self.directeur)
        self.commande.refresh_from_db()
        solder(self.commande, self.directeur, "FAC-2026-14", 125_000)
        self.commande.refresh_from_db()
        self.besoin.refresh_from_db()
        self.assertEqual(self.commande.statut, BonCommande.Statut.PAYE)
        self.assertEqual(self.besoin.statut, ExpressionBesoin.Statut.SOLDE)

    def test_on_ne_facture_pas_avant_de_receptionner(self):
        with self.assertRaises(ErreurAchat):
            solder(self.commande, self.directeur, "FAC-1", 125_000)

    def test_la_depense_rejoint_le_plan_d_action(self):
        axe = Axe.objects.create(code="AX1", libelle="Qualite")
        plan = PlanAction.objects.create(
            perimetre=self.p_centrale, annee=timezone.localdate().year
        )
        activite = Activite.objects.create(
            plan=plan, axe=axe, intitule="Production de guides",
            date_debut_prevue=timezone.localdate(), date_fin_prevue=timezone.localdate(),
            budget_prevu=500_000, budget_execute=100_000,
        )
        self.besoin.activite = activite
        self.besoin.save(update_fields=["activite"])
        receptionner(self.commande, self.directeur)
        self.commande.refresh_from_db()
        _, rapporte = solder(self.commande, self.directeur, "FAC-9", 125_000)
        activite.refresh_from_db()
        self.assertTrue(rapporte)
        self.assertEqual(activite.budget_execute, 225_000)

    def test_sans_activite_rien_n_est_rapporte(self):
        receptionner(self.commande, self.directeur)
        self.commande.refresh_from_db()
        _, rapporte = solder(self.commande, self.directeur, "FAC-10", 125_000)
        self.assertFalse(rapporte)


class EcartFactureTest(BaseAchats):
    def test_un_ecart_de_plus_de_dix_pour_cent_est_signale(self):
        from django.core.exceptions import ValidationError

        commande = BonCommande(
            besoin=self._besoin(), fournisseur=self.fournisseur,
            montant=100_000, facture_montant=120_000,
        )
        with self.assertRaises(ValidationError):
            commande.clean()

    def test_un_ecart_raisonnable_passe(self):
        commande = BonCommande(
            besoin=self._besoin(), fournisseur=self.fournisseur,
            montant=100_000, facture_montant=105_000,
        )
        commande.clean()


class VisibiliteTest(BaseAchats):
    def test_les_besoins_sont_cloisonnes(self):
        self._besoin(self.p_centrale)
        self._besoin(self.p_antenne, self.agent_antenne)
        self.assertEqual(ExpressionBesoin.objects.visibles_par(self.agent).count(), 1)
        self.assertEqual(ExpressionBesoin.objects.visibles_par(self.chef).count(), 1)
        self.assertEqual(ExpressionBesoin.objects.visibles_par(self.directeur).count(), 2)

    def test_tableau_limite_au_perimetre(self):
        self._besoin(self.p_centrale)
        self._besoin(self.p_antenne, self.agent_antenne)
        self.assertEqual(tableau_achats(self.chef)["nb_besoins"], 1)
        self.assertEqual(tableau_achats(self.directeur)["nb_besoins"], 2)


class EquipementTest(BaseAchats):
    def test_inventaire_des_equipements(self):
        equipement = Equipement.objects.create(
            perimetre=self.p_centrale, code_inventaire="DPFC-ORD-001",
            designation="Ordinateur portable", affecte_a=self.agent,
            etat=Equipement.Etat.BON, valeur=450_000,
        )
        self.assertEqual(str(equipement), "DPFC-ORD-001 - Ordinateur portable")
        self.assertEqual(equipement.couleur_etat, "ok")
        equipement.etat = Equipement.Etat.PANNE
        self.assertEqual(equipement.couleur_etat, "ko")

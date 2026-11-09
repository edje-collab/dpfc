"""Tests du courrier et de la gestion documentaire."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone

from apps.circuits.modeles import installer_circuits_modeles
from apps.core.models import Perimetre, Region, Structure
from apps.courrier.extraction import extraire_texte
from apps.courrier.models import (
    Courrier,
    Document,
    Imputation,
    ModeleDocument,
    PieceParapheur,
    Visa,
)
from apps.courrier.services import (
    ErreurCourrier,
    classer,
    deposer_version,
    imputer,
    pieces_a_viser,
    rechercher_documents,
    soumettre_au_parapheur,
    tableau_courrier,
    traiter_imputation,
    viser,
)

Agent = get_user_model()
ANNEE = timezone.localdate().year


class BaseCourrier(TestCase):
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
            nom="Direction de la Pedagogie", sigle="DPFC", type=Structure.Type.DIRECTION,
            perimetre=cls.p_centrale, perimetre_racine=True,
        )
        cls.sous_direction = Structure.objects.create(
            nom="Sous-direction de la formation", sigle="SDFPC",
            type=Structure.Type.SOUS_DIRECTION, parent=cls.direction, perimetre=cls.p_centrale,
        )
        cls.antenne = Structure.objects.create(
            nom="Antenne de Bouake", sigle="APFC-GBK", type=Structure.Type.ANTENNE,
            region=cls.region, perimetre=cls.p_antenne, perimetre_racine=True,
        )
        cls.directeur = cls._agent("D0001", "KOUAME", Agent.Role.DIRECTEUR, cls.direction)
        cls.sous_directeur = cls._agent("B0001", "BAMBA", Agent.Role.SOUS_DIRECTEUR,
                                        cls.sous_direction, cls.directeur)
        cls.agent_central = cls._agent("A0001", "YAO", Agent.Role.AGENT,
                                       cls.sous_direction, cls.sous_directeur)
        cls.secretaire = cls._agent("S0001", "ABLE", Agent.Role.SECRETARIAT, cls.direction,
                                    cls.directeur)
        cls.chef_antenne = cls._agent("C0001", "KONE", Agent.Role.CHEF_ANTENNE, cls.antenne)
        cls.agent_antenne = cls._agent("A0002", "OUATTARA", Agent.Role.AGENT, cls.antenne,
                                       cls.chef_antenne)
        for structure, responsable in [
            (cls.direction, cls.directeur),
            (cls.sous_direction, cls.sous_directeur),
            (cls.antenne, cls.chef_antenne),
        ]:
            structure.responsable = responsable
            structure.save(update_fields=["responsable"])

    @classmethod
    def _agent(cls, matricule, nom, role, structure, superieur=None):
        return Agent.objects.create_user(
            matricule, password="motdepasse123", last_name=nom, first_name="Prenom",
            role=role, structure=structure, superieur=superieur,
        )

    def _courrier(self, perimetre=None, sens=Courrier.Sens.ARRIVEE, **extra):
        return Courrier.objects.create(
            perimetre=perimetre or self.p_centrale,
            sens=sens,
            correspondant=extra.pop("correspondant", "Cabinet du Ministre"),
            objet=extra.pop("objet", "Transmission des orientations de la rentree"),
            enregistre_par=extra.pop("enregistre_par", self.secretaire),
            **extra,
        )

    def _document(self, perimetre=None, **extra):
        return Document.objects.create(
            perimetre=perimetre or self.p_centrale,
            titre=extra.pop("titre", "Guide d'execution CM2"),
            annee=ANNEE,
            deposant=extra.pop("deposant", self.agent_central),
            **extra,
        )


class NumerotationTest(BaseCourrier):
    def test_series_distinctes_par_sens_et_par_perimetre(self):
        arrivee = self._courrier()
        depart = self._courrier(sens=Courrier.Sens.DEPART)
        antenne = self._courrier(self.p_antenne)

        self.assertEqual(arrivee.numero, f"ARR-0001/{ANNEE}/DPFC")
        self.assertEqual(depart.numero, f"DEP-0001/{ANNEE}/DPFC")
        self.assertEqual(antenne.numero, f"ARR-0001/{ANNEE}/APFC-GBK")

    def test_la_serie_s_incremente(self):
        numeros = [self._courrier().numero for _ in range(3)]
        self.assertEqual(
            numeros,
            [f"ARR-000{i}/{ANNEE}/DPFC" for i in (1, 2, 3)],
        )

    def test_un_courrier_ne_peut_etre_enregistre_avant_sa_date(self):
        from django.core.exceptions import ValidationError

        courrier = Courrier(
            perimetre=self.p_centrale, sens=Courrier.Sens.ARRIVEE,
            correspondant="X", objet="Y",
            date_courrier=timezone.localdate(),
            date_enregistrement=timezone.localdate() - timedelta(days=2),
        )
        with self.assertRaises(ValidationError):
            courrier.full_clean()


class ImputationTest(BaseCourrier):
    def setUp(self):
        self.courrier = self._courrier()
        self.demain = timezone.localdate() + timedelta(days=7)

    def test_imputation_notifie_et_change_le_statut(self):
        imputer(self.courrier, self.directeur, [
            {"destinataire": self.agent_central, "instructions": "Preparer une note.",
             "delai": self.demain},
        ])
        self.courrier.refresh_from_db()
        self.assertEqual(self.courrier.statut, Courrier.Statut.IMPUTE)
        self.assertEqual(self.agent_central.notifications.count(), 1)

    def test_imputation_pour_information_est_close_d_emblee(self):
        [imputation] = imputer(self.courrier, self.directeur, [
            {"destinataire": self.agent_central, "instructions": "Pour information.",
             "delai": self.demain, "pour_information": True},
        ])
        self.assertTrue(imputation.est_traitee)
        self.courrier.refresh_from_db()
        self.assertEqual(self.courrier.statut, Courrier.Statut.TRAITE)

    def test_un_courrier_depart_ne_s_impute_pas(self):
        depart = self._courrier(sens=Courrier.Sens.DEPART)
        with self.assertRaises(ErreurCourrier):
            imputer(depart, self.directeur, [
                {"destinataire": self.agent_central, "instructions": "x", "delai": self.demain},
            ])

    def test_imputation_sans_destinataire_refusee(self):
        with self.assertRaises(ErreurCourrier):
            imputer(self.courrier, self.directeur, [])

    def test_un_agent_n_est_impute_qu_une_fois(self):
        imputer(self.courrier, self.directeur, [
            {"destinataire": self.agent_central, "instructions": "a", "delai": self.demain},
        ])
        with self.assertRaises(ErreurCourrier):
            imputer(self.courrier, self.directeur, [
                {"destinataire": self.agent_central, "instructions": "b", "delai": self.demain},
            ])

    def test_le_courrier_est_traite_quand_toutes_les_imputations_le_sont(self):
        imputations = imputer(self.courrier, self.directeur, [
            {"destinataire": self.agent_central, "instructions": "Note.", "delai": self.demain},
            {"destinataire": self.sous_directeur, "instructions": "Avis.", "delai": self.demain},
        ])
        traiter_imputation(imputations[0], self.agent_central, "Note transmise.")
        self.courrier.refresh_from_db()
        self.assertEqual(self.courrier.statut, Courrier.Statut.IMPUTE)

        traiter_imputation(imputations[1], self.sous_directeur, "Avis rendu.")
        self.courrier.refresh_from_db()
        self.assertEqual(self.courrier.statut, Courrier.Statut.TRAITE)

    def test_seul_l_imputataire_rend_compte(self):
        [imputation] = imputer(self.courrier, self.directeur, [
            {"destinataire": self.agent_central, "instructions": "Note.", "delai": self.demain},
        ])
        with self.assertRaises(ErreurCourrier):
            traiter_imputation(imputation, self.sous_directeur, "Je m'en charge.")

    def test_compte_rendu_vide_refuse(self):
        [imputation] = imputer(self.courrier, self.directeur, [
            {"destinataire": self.agent_central, "instructions": "Note.", "delai": self.demain},
        ])
        with self.assertRaises(ErreurCourrier):
            traiter_imputation(imputation, self.agent_central, "   ")

    def test_retard_calcule_sur_l_imputation_la_plus_ancienne(self):
        hier = timezone.localdate() - timedelta(days=4)
        Imputation.objects.create(
            courrier=self.courrier, destinataire=self.agent_central,
            instructions="En retard.", delai=hier, impute_par=self.directeur,
        )
        self.courrier.statut = Courrier.Statut.IMPUTE
        self.courrier.save(update_fields=["statut"])
        self.assertTrue(self.courrier.est_en_retard)
        self.assertEqual(self.courrier.jours_de_retard, 4)
        self.assertEqual(Courrier.objects.en_retard().count(), 1)

    def test_classement_exige_un_motif_et_ferme_le_courrier(self):
        with self.assertRaises(ErreurCourrier):
            classer(self.courrier, self.directeur, " ")
        classer(self.courrier, self.directeur, "Sans objet pour la direction.")
        self.courrier.refresh_from_db()
        self.assertEqual(self.courrier.statut, Courrier.Statut.CLASSE)
        self.assertTrue(self.courrier.est_clos)
        self.assertFalse(self.courrier.est_en_retard)


class VisibiliteTest(BaseCourrier):
    def test_un_agent_ne_voit_que_le_courrier_de_son_perimetre(self):
        self._courrier(self.p_centrale)
        self._courrier(self.p_antenne)
        self.assertEqual(Courrier.objects.visibles_par(self.agent_central).count(), 1)
        self.assertEqual(Courrier.objects.visibles_par(self.agent_antenne).count(), 1)
        self.assertEqual(Courrier.objects.visibles_par(self.directeur).count(), 2)

    def test_un_courrier_confidentiel_reste_invisible_aux_autres(self):
        confidentiel = self._courrier(confidentiel=True, objet="Dossier disciplinaire")
        self.assertEqual(Courrier.objects.visibles_par(self.agent_central).count(), 0)
        self.assertFalse(confidentiel.peut_etre_vu_par(self.agent_central))
        # L'enregistreur et le responsable du perimetre y ont acces.
        self.assertTrue(confidentiel.peut_etre_vu_par(self.secretaire))
        self.assertTrue(confidentiel.peut_etre_vu_par(self.directeur))

    def test_l_imputataire_accede_au_courrier_confidentiel(self):
        confidentiel = self._courrier(confidentiel=True)
        imputer(confidentiel, self.directeur, [
            {"destinataire": self.agent_central, "instructions": "Traiter.",
             "delai": timezone.localdate() + timedelta(days=3)},
        ])
        self.assertTrue(confidentiel.peut_etre_vu_par(self.agent_central))
        self.assertEqual(Courrier.objects.visibles_par(self.agent_central).count(), 1)


class DocumentTest(BaseCourrier):
    def _fichier(self, nom="note.txt", contenu=b"Note sur les guides d'execution du primaire."):
        return SimpleUploadedFile(nom, contenu, content_type="text/plain")

    def test_versions_numerotees_et_conservees(self):
        document = self._document()
        v1 = deposer_version(document, self._fichier(), self.agent_central, "Version initiale")
        v2 = deposer_version(document, self._fichier(contenu=b"Version corrigee."),
                             self.agent_central, "Corrections")
        self.assertEqual([v1.numero, v2.numero], [1, 2])
        self.assertEqual(document.nb_versions, 2)
        self.assertEqual(document.version_courante.numero, 2)

    def test_empreinte_et_taille_calculees(self):
        document = self._document()
        version = deposer_version(document, self._fichier(), self.agent_central)
        self.assertEqual(len(version.empreinte), 64)
        self.assertGreater(version.taille, 0)
        self.assertIn("o", version.taille_lisible)

    def test_le_texte_est_extrait_et_rendu_cherchable(self):
        document = self._document(titre="Note de service")
        deposer_version(document, self._fichier(), self.agent_central)
        document.refresh_from_db()
        self.assertIn("guides d'execution", document.texte_extrait)
        self.assertIsNotNone(document.indexe_le)

        trouves = rechercher_documents(self.agent_central, "guides")
        self.assertIn(document, list(trouves))

    def test_un_fichier_illisible_n_empeche_pas_le_depot(self):
        document = self._document()
        version = deposer_version(
            document, SimpleUploadedFile("scan.pdf", b"%PDF-1.4 contenu binaire illisible"),
            self.agent_central,
        )
        document.refresh_from_db()
        self.assertIsNotNone(version.pk)
        self.assertEqual(document.texte_extrait, "")

    def test_recherche_limitee_au_perimetre(self):
        self._document(self.p_centrale, titre="Guide central")
        self._document(self.p_antenne, titre="Guide regional", deposant=self.agent_antenne)
        titres = [d.titre for d in rechercher_documents(self.agent_antenne, "Guide")]
        self.assertEqual(titres, ["Guide regional"])
        self.assertEqual(len(list(rechercher_documents(self.directeur, "Guide"))), 2)

    def test_un_document_partage_traverse_les_perimetres(self):
        self._document(self.p_centrale, titre="Circulaire nationale", partage=True)
        titres = [d.titre for d in rechercher_documents(self.agent_antenne, "Circulaire")]
        self.assertEqual(titres, ["Circulaire nationale"])

    def test_acces_restreint(self):
        document = self._document(
            titre="Dossier sensible", acces=Document.Acces.RESTREINT, deposant=self.directeur
        )
        self.assertFalse(document.peut_etre_vu_par(self.agent_central))
        self.assertTrue(document.peut_etre_vu_par(self.directeur))
        document.agents_autorises.add(self.agent_central)
        self.assertTrue(document.peut_etre_vu_par(self.agent_central))

    def test_filtres_de_recherche(self):
        self._document(titre="Rapport annuel", type_document="RAPPORT")
        self._document(titre="Guide CP1", type_document="GUIDE")
        resultats = rechercher_documents(self.directeur, "", type_document="GUIDE")
        self.assertEqual([d.titre for d in resultats], ["Guide CP1"])


class ExtractionTest(TestCase):
    def test_fichier_texte(self):
        self.assertEqual(
            extraire_texte("note.txt", b"Bonjour   la\ndirection"), "Bonjour la direction"
        )

    def test_type_non_gere_retourne_une_chaine_vide(self):
        self.assertEqual(extraire_texte("image.png", b"\x89PNG..."), "")

    def test_fichier_vide_ou_trop_gros(self):
        self.assertEqual(extraire_texte("vide.txt", b""), "")
        self.assertEqual(extraire_texte("gros.txt", b"x" * (26 * 1024 * 1024)), "")

    def test_encodage_latin1_tolere(self):
        self.assertEqual(extraire_texte("note.txt", "Évaluation".encode("latin-1")), "Évaluation")


class ParapheurTest(BaseCourrier):
    def setUp(self):
        self.document = self._document(titre="Projet de note de service")
        self.piece = PieceParapheur.objects.create(
            perimetre=self.p_centrale, objet="Note de service sur la rentree",
            document=self.document, demandeur=self.agent_central,
        )

    def test_le_circuit_remonte_la_voie_hierarchique(self):
        soumettre_au_parapheur(self.piece)
        self.piece.refresh_from_db()
        self.assertEqual(self.piece.statut, PieceParapheur.Statut.EN_CIRCUIT)
        self.assertEqual(
            [(v.ordre, v.viseur.matricule) for v in self.piece.visas.all()],
            [(1, "B0001"), (2, "D0001")],
        )

    def test_une_piece_d_antenne_s_arrete_au_chef_d_antenne(self):
        document = self._document(self.p_antenne, titre="Note regionale",
                                  deposant=self.agent_antenne)
        piece = PieceParapheur.objects.create(
            perimetre=self.p_antenne, objet="Note regionale", document=document,
            demandeur=self.agent_antenne,
        )
        soumettre_au_parapheur(piece)
        self.assertEqual([v.viseur.matricule for v in piece.visas.all()], ["C0001"])

    def test_visa_complet_cloture_la_piece(self):
        soumettre_au_parapheur(self.piece)
        viser(self.piece.etape_courante(), True, "Rien a signaler.")
        self.piece.refresh_from_db()
        self.assertEqual(self.piece.statut, PieceParapheur.Statut.EN_CIRCUIT)
        self.assertEqual(self.piece.progression(), 50)

        viser(self.piece.etape_courante(), True, "Vise.")
        self.piece.refresh_from_db()
        self.assertEqual(self.piece.statut, PieceParapheur.Statut.VISEE)
        self.assertEqual(self.piece.progression(), 100)

    def test_refus_ferme_la_piece_et_ignore_les_etapes_suivantes(self):
        soumettre_au_parapheur(self.piece)
        viser(self.piece.etape_courante(), False, "Formulation a revoir.")
        self.piece.refresh_from_db()
        self.assertEqual(self.piece.statut, PieceParapheur.Statut.REJETEE)
        self.assertEqual(self.piece.motif_rejet, "Formulation a revoir.")
        self.assertEqual(self.piece.visas.filter(decision=Visa.Decision.IGNORE).count(), 1)

    def test_une_piece_ne_se_soumet_pas_deux_fois(self):
        soumettre_au_parapheur(self.piece)
        with self.assertRaises(ErreurCourrier):
            soumettre_au_parapheur(self.piece)

    def test_un_visa_ne_se_donne_pas_deux_fois(self):
        soumettre_au_parapheur(self.piece)
        etape = self.piece.etape_courante()
        viser(etape, True)
        with self.assertRaises(ErreurCourrier):
            viser(etape, True)

    def test_la_corbeille_ne_montre_que_l_etape_courante(self):
        soumettre_au_parapheur(self.piece)
        self.assertEqual(len(pieces_a_viser(self.sous_directeur)), 1)
        self.assertEqual(len(pieces_a_viser(self.directeur)), 0)

        viser(self.piece.etape_courante(), True)
        self.assertEqual(len(pieces_a_viser(self.sous_directeur)), 0)
        self.assertEqual(len(pieces_a_viser(self.directeur)), 1)


class TableauCourrierTest(BaseCourrier):
    def test_synthese_limitee_au_perimetre(self):
        self._courrier(self.p_centrale)
        self._courrier(self.p_centrale, sens=Courrier.Sens.DEPART)
        self._courrier(self.p_antenne)

        vue = tableau_courrier(self.agent_central)
        self.assertEqual(vue["nb_arrivees"], 1)
        self.assertEqual(vue["nb_departs"], 1)
        self.assertEqual(vue["nb_a_imputer"], 1)

        vue_directeur = tableau_courrier(self.directeur)
        self.assertEqual(vue_directeur["nb_arrivees"], 2)

    def test_mes_imputations_en_attente(self):
        courrier = self._courrier()
        imputer(courrier, self.directeur, [
            {"destinataire": self.agent_central, "instructions": "Traiter.",
             "delai": timezone.localdate() + timedelta(days=5)},
        ])
        self.assertEqual(tableau_courrier(self.agent_central)["nb_mes_imputations"], 1)
        self.assertEqual(tableau_courrier(self.sous_directeur)["nb_mes_imputations"], 0)


class ModeleDocumentTest(TestCase):
    def test_substitution_des_variables(self):
        modele = ModeleDocument.objects.create(
            code="note-service", titre="Note de service",
            corps="Objet : {{ objet }}\nA : {{ correspondant }}\nLe {{ date }}",
        )
        rendu = modele.rendre(objet="Rentree", correspondant="Chefs d'antenne", date="01/09/2026")
        self.assertIn("Objet : Rentree", rendu)
        self.assertIn("A : Chefs d'antenne", rendu)
        self.assertNotIn("{{", rendu)

    def test_variable_absente_rendue_vide(self):
        modele = ModeleDocument.objects.create(
            code="x", titre="X", corps="Signataire : {{ signataire }}."
        )
        self.assertEqual(modele.rendre(signataire=None), "Signataire : .")


class DroitsTest(BaseCourrier):
    """Les droits tiennent a la designation effective, pas au role porte."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        # Un second agent portant le role de chef d'antenne, sans diriger
        # l'antenne : cas rencontre apres une mutation mal soldee.
        cls.faux_chef = cls._agent("C0002", "DIARRA", Agent.Role.CHEF_ANTENNE, cls.antenne)

    def test_porter_le_role_de_chef_ne_suffit_pas_a_imputer(self):
        from apps.courrier.views import _peut_enregistrer, _peut_imputer

        courrier = self._courrier(self.p_antenne, enregistre_par=self.chef_antenne)
        self.assertTrue(self.chef_antenne.dirige_son_perimetre)
        self.assertFalse(self.faux_chef.dirige_son_perimetre)

        self.assertTrue(_peut_imputer(self.chef_antenne, courrier))
        self.assertFalse(_peut_imputer(self.faux_chef, courrier))
        self.assertTrue(_peut_enregistrer(self.chef_antenne))
        self.assertFalse(_peut_enregistrer(self.faux_chef))

    def test_meme_regle_pour_le_plan_d_action(self):
        from apps.activites.views import _peut_piloter

        self.assertTrue(_peut_piloter(self.chef_antenne, self.p_antenne))
        self.assertFalse(_peut_piloter(self.faux_chef, self.p_antenne))
        # Un chef ne pilote pas le perimetre d'un autre.
        self.assertFalse(_peut_piloter(self.chef_antenne, self.p_centrale))

    def test_le_secretariat_enregistre_mais_n_impute_pas(self):
        from apps.courrier.views import _peut_enregistrer, _peut_imputer

        courrier = self._courrier(self.p_centrale)
        self.assertTrue(_peut_enregistrer(self.secretaire))
        self.assertFalse(_peut_imputer(self.secretaire, courrier))

    def test_la_direction_impute_dans_tous_les_perimetres(self):
        from apps.courrier.views import _peut_imputer

        self.assertTrue(_peut_imputer(self.directeur, self._courrier(self.p_antenne)))
        self.assertTrue(_peut_imputer(self.directeur, self._courrier(self.p_centrale)))

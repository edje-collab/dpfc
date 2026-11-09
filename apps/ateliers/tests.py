"""Tests des ateliers : jetons QR, emargement hors ligne, paiement, attestations."""
import uuid
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.activites.models import Activite, Axe, PlanAction
from apps.ateliers.models import (
    Atelier,
    Bareme,
    DoublonEmargement,
    Emargement,
    Participant,
    Session,
)
from apps.ateliers.qr import jeton, lire, signer
from apps.ateliers.services import (
    ErreurAtelier,
    annuler,
    annuler_emargement,
    clore,
    donnees_attestation,
    enregistrer_emargement,
    enregistrer_lot,
    etat_de_paiement,
    feuille_de_presence,
    generer_sessions,
    ouvrir,
    participant_du_jeton,
    peut_recevoir_attestation,
    tableau_ateliers,
)
from apps.core.models import Perimetre, Region, Structure

Agent = get_user_model()


class BaseAtelier(TestCase):
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
            nom="Direction", sigle="DPFC", type=Structure.Type.DIRECTION,
            perimetre=cls.p_centrale, perimetre_racine=True,
        )
        cls.antenne = Structure.objects.create(
            nom="Antenne de Bouake", sigle="APFC-GBK", type=Structure.Type.ANTENNE,
            region=cls.region, perimetre=cls.p_antenne, perimetre_racine=True,
        )
        cls.directeur = cls._agent("D0001", "KOUAME", Agent.Role.DIRECTEUR, cls.direction)
        cls.chef = cls._agent("C0001", "KONE", Agent.Role.CHEF_ANTENNE, cls.antenne)
        cls.agent = cls._agent("A0001", "OUATTARA", Agent.Role.AGENT, cls.antenne, cls.chef)
        cls.autre = cls._agent("A0002", "DIALLO", Agent.Role.AGENT, cls.direction)
        cls.direction.responsable = cls.directeur
        cls.direction.save(update_fields=["responsable"])
        cls.antenne.responsable = cls.chef
        cls.antenne.save(update_fields=["responsable"])

        cls.bareme_cp = Bareme.objects.create(
            code="CP", libelle="Conseiller pedagogique", montant_journalier=25_000
        )
        cls.bareme_ens = Bareme.objects.create(
            code="ENS", libelle="Enseignant", montant_journalier=15_000
        )

    @classmethod
    def _agent(cls, matricule, nom, role, structure, superieur=None):
        return Agent.objects.create_user(
            matricule, password="motdepasse123", last_name=nom, first_name="Prenom",
            role=role, structure=structure, superieur=superieur,
        )

    def _atelier(self, perimetre=None, jours=2, **extra):
        debut = extra.pop("debut", timezone.localdate())
        return Atelier.objects.create(
            perimetre=perimetre or self.p_antenne,
            intitule=extra.pop("intitule", "Atelier de production de fiches"),
            lieu=extra.pop("lieu", "Bouake"),
            date_debut=debut,
            date_fin=debut + timedelta(days=jours - 1),
            organisateur=extra.pop("organisateur", self.chef),
            **extra,
        )

    def _participant(self, atelier, nom="TRAORE", **extra):
        return Participant.objects.create(
            atelier=atelier, nom=nom, prenoms=extra.pop("prenoms", "Aminata"),
            categorie=extra.pop("categorie", self.bareme_cp), **extra,
        )


class JetonTest(BaseAtelier):
    def test_le_jeton_ne_contient_aucune_donnee_personnelle(self):
        atelier = self._atelier()
        participant = self._participant(atelier, nom="KOUASSI", prenoms="Akissi",
                                        telephone="+225 07 00 00 00 01",
                                        email="akissi@exemple.ci")
        valeur = participant.jeton
        for donnee in ("KOUASSI", "Akissi", "07 00 00 00 01", "akissi@exemple.ci"):
            self.assertNotIn(donnee, valeur)

        prefixe, id_atelier, id_participant, signature = valeur.split(".")
        self.assertEqual(prefixe, "DPFC1")
        # Les deux identifiants sont des jetons courts aleatoires, non les cles
        # primaires : rien ne permet de remonter a l'enregistrement sans la base.
        self.assertEqual(id_atelier, atelier.id_court)
        self.assertEqual(id_participant, participant.id_court)
        self.assertNotEqual(id_participant, str(participant.pk))
        self.assertEqual(len(signature), 16)

    def test_un_jeton_valide_designe_son_participant(self):
        atelier = self._atelier()
        participant = self._participant(atelier)
        self.assertEqual(participant_du_jeton(atelier, participant.jeton), participant)

    def test_un_jeton_altere_est_rejete(self):
        atelier = self._atelier()
        participant = self._participant(atelier)
        valeur = participant.jeton
        altere = valeur[:-1] + ("A" if valeur[-1] != "A" else "B")
        self.assertIsNone(participant_du_jeton(atelier, altere))

    def test_un_jeton_d_un_autre_atelier_est_rejete(self):
        atelier = self._atelier()
        autre = self._atelier(intitule="Autre atelier")
        participant = self._participant(autre)
        self.assertIsNone(participant_du_jeton(atelier, participant.jeton))

    def test_les_cles_sont_propres_a_chaque_atelier(self):
        a, b = self._atelier(), self._atelier(intitule="B")
        self.assertNotEqual(a.cle, b.cle)
        self.assertNotEqual(a.id_court, b.id_court)

    def test_un_jeton_mal_forme_est_rejete_sans_exception(self):
        atelier = self._atelier()
        for valeur in ("", "   ", "n'importe quoi", "DPFC1.X", "DPFC1.A.B.C.D", None):
            with self.subTest(valeur=valeur):
                self.assertIsNone(participant_du_jeton(atelier, valeur))

    def test_la_signature_depend_de_la_cle(self):
        self.assertNotEqual(signer("cle-a", "AT", "PA"), signer("cle-b", "AT", "PA"))

    def test_lire_rejette_un_identifiant_d_atelier_different(self):
        self.assertIsNone(lire(jeton(self._atelier(), self._participant(self._atelier())),
                               "cle", "AUTRE"))


class SessionTest(BaseAtelier):
    def test_generation_de_sessions_journalieres(self):
        atelier = self._atelier(jours=3)
        creees = generer_sessions(atelier)
        self.assertEqual(len(creees), 3)
        self.assertTrue(all(s.creneau == Session.Creneau.JOURNEE for s in creees))

    def test_generation_par_demi_journees(self):
        atelier = self._atelier(jours=2)
        creees = generer_sessions(atelier, creneaux_par_jour=2)
        self.assertEqual(len(creees), 4)
        self.assertEqual([s.poids_journee for s in creees], [0.5, 0.5, 0.5, 0.5])

    def test_la_generation_est_idempotente(self):
        atelier = self._atelier(jours=2)
        generer_sessions(atelier)
        self.assertEqual(len(generer_sessions(atelier)), 0)
        self.assertEqual(atelier.sessions.count(), 2)

    def test_le_matin_precede_l_apres_midi(self):
        atelier = self._atelier(jours=1)
        generer_sessions(atelier, creneaux_par_jour=2)
        creneaux = list(atelier.sessions.values_list("creneau", flat=True))
        self.assertEqual(creneaux, ["MATIN", "APRES_MIDI"])


class EmargementTest(BaseAtelier):
    def setUp(self):
        self.atelier = self._atelier(jours=2)
        generer_sessions(self.atelier)
        self.s1, self.s2 = list(self.atelier.sessions.all())
        self.p1 = self._participant(self.atelier, nom="TRAORE")
        self.p2 = self._participant(self.atelier, nom="BAMBA", categorie=self.bareme_ens)
        ouvrir(self.atelier, self.chef)

    def test_emargement_par_scan(self):
        emargement, cree = enregistrer_emargement(self.s1, self.p1, self.chef)
        self.assertTrue(cree)
        self.assertEqual(emargement.mode, Emargement.Mode.SCAN)
        self.assertEqual(self.p1.nb_sessions_emargees, 1)

    def test_renvoyer_le_meme_emargement_ne_cree_pas_de_doublon(self):
        """Cas du reseau coupe : l'appareil renvoie sa file a l'identique."""
        identifiant = uuid.uuid4()
        premier, cree = enregistrer_emargement(self.s1, self.p1, self.chef, identifiant=identifiant)
        self.assertTrue(cree)
        second, recree = enregistrer_emargement(self.s1, self.p1, self.chef, identifiant=identifiant)
        self.assertFalse(recree)
        self.assertEqual(premier.pk, second.pk)
        self.assertEqual(Emargement.objects.count(), 1)
        self.assertEqual(DoublonEmargement.objects.count(), 0)

    def test_un_second_scan_distinct_est_journalise_comme_doublon(self):
        enregistrer_emargement(self.s1, self.p1, self.chef, identifiant=uuid.uuid4())
        _, cree = enregistrer_emargement(self.s1, self.p1, self.chef, identifiant=uuid.uuid4())
        self.assertFalse(cree)
        self.assertEqual(Emargement.objects.count(), 1)
        self.assertEqual(DoublonEmargement.objects.count(), 1)

    def test_emargement_manuel_exige_un_motif(self):
        with self.assertRaises(ErreurAtelier):
            enregistrer_emargement(self.s1, self.p1, self.chef, mode=Emargement.Mode.MANUEL)
        emargement, _ = enregistrer_emargement(
            self.s1, self.p1, self.chef, mode=Emargement.Mode.MANUEL,
            motif="QR code illisible, piece d'identite verifiee.",
        )
        self.assertEqual(emargement.mode, Emargement.Mode.MANUEL)
        self.assertIn("illisible", emargement.motif)

    def test_on_n_emarge_pas_un_atelier_clos(self):
        clore(self.atelier, self.chef)
        self.atelier.refresh_from_db()
        with self.assertRaises(ErreurAtelier):
            enregistrer_emargement(self.s1, self.p1, self.chef)

    def test_un_participant_revoque_n_emarge_pas(self):
        self.p1.statut = Participant.Statut.REVOQUE
        self.p1.save(update_fields=["statut"])
        with self.assertRaises(ErreurAtelier):
            enregistrer_emargement(self.s1, self.p1, self.chef)

    def test_un_participant_d_un_autre_atelier_est_refuse(self):
        autre = self._atelier(intitule="Autre")
        etranger = self._participant(autre)
        with self.assertRaises(ErreurAtelier):
            enregistrer_emargement(self.s1, etranger, self.chef)

    def test_annulation_d_un_emargement_exige_un_motif(self):
        emargement, _ = enregistrer_emargement(self.s1, self.p1, self.chef)
        with self.assertRaises(ErreurAtelier):
            annuler_emargement(emargement, self.chef, "")
        annuler_emargement(emargement, self.chef, "Scan effectue par erreur.")
        self.assertEqual(Emargement.objects.count(), 0)


class LotTest(BaseAtelier):
    """Envoi groupe depuis le terrain, apres une collecte hors ligne."""

    def setUp(self):
        self.atelier = self._atelier(jours=1)
        generer_sessions(self.atelier)
        self.session = self.atelier.sessions.first()
        self.participants = [
            self._participant(self.atelier, nom=f"AGENT{i}") for i in range(5)
        ]
        ouvrir(self.atelier, self.chef)

    def _lignes(self, participants=None, identifiants=None):
        participants = participants or self.participants
        identifiants = identifiants or [uuid.uuid4() for _ in participants]
        return [
            {"jeton": p.jeton, "identifiant": i, "horodatage": timezone.now(),
             "appareil": "tablette-01"}
            for p, i in zip(participants, identifiants, strict=True)
        ]

    def test_un_lot_enregistre_toutes_les_presences(self):
        resultat = enregistrer_lot(self.atelier, self.session, self.chef, self._lignes())
        self.assertEqual(resultat["enregistres"], 5)
        self.assertEqual(resultat["doublons"], 0)
        self.assertEqual(resultat["invalides"], 0)
        self.assertEqual(Emargement.objects.count(), 5)

    def test_renvoyer_le_meme_lot_ne_cree_rien(self):
        """La coupure reseau conduit l'appareil a reemettre sa file entiere."""
        identifiants = [uuid.uuid4() for _ in self.participants]
        lignes = self._lignes(identifiants=identifiants)
        enregistrer_lot(self.atelier, self.session, self.chef, lignes)
        resultat = enregistrer_lot(self.atelier, self.session, self.chef, lignes)
        self.assertEqual(resultat["enregistres"], 0)
        self.assertEqual(resultat["doublons"], 5)
        self.assertEqual(Emargement.objects.count(), 5)
        self.assertEqual(DoublonEmargement.objects.count(), 0)

    def test_un_jeton_invalide_n_interrompt_pas_le_lot(self):
        lignes = self._lignes()
        lignes.insert(2, {"jeton": "DPFC1.XXXX.YYYY.ZZZZ", "identifiant": uuid.uuid4(),
                          "horodatage": timezone.now()})
        resultat = enregistrer_lot(self.atelier, self.session, self.chef, lignes)
        self.assertEqual(resultat["enregistres"], 5)
        self.assertEqual(resultat["invalides"], 1)

    def test_un_lot_sur_un_atelier_clos_est_refuse(self):
        clore(self.atelier, self.chef)
        self.atelier.refresh_from_db()
        with self.assertRaises(ErreurAtelier):
            enregistrer_lot(self.atelier, self.session, self.chef, self._lignes())

    def test_une_session_d_un_autre_atelier_est_refusee(self):
        autre = self._atelier(intitule="Autre")
        generer_sessions(autre)
        with self.assertRaises(ErreurAtelier):
            enregistrer_lot(self.atelier, autre.sessions.first(), self.chef, self._lignes())

    def test_atelier_de_cinquante_participants_hors_ligne(self):
        """Cas reel : une journee entiere collectee hors ligne, envoyee d'un coup."""
        atelier = self._atelier(jours=1, intitule="Atelier national")
        generer_sessions(atelier)
        session = atelier.sessions.first()
        participants = [self._participant(atelier, nom=f"P{i:03d}") for i in range(50)]
        ouvrir(atelier, self.chef)

        lignes = [
            {"jeton": p.jeton, "identifiant": uuid.uuid4(), "horodatage": timezone.now()}
            for p in participants
        ]
        resultat = enregistrer_lot(atelier, session, self.chef, lignes)
        self.assertEqual(resultat["enregistres"], 50)
        self.assertEqual(atelier.nb_emarges, 50)
        self.assertEqual(atelier.taux_presence, 100)


class PaiementTest(BaseAtelier):
    def setUp(self):
        self.atelier = self._atelier(jours=2)
        generer_sessions(self.atelier)
        self.s1, self.s2 = list(self.atelier.sessions.all())
        self.present = self._participant(self.atelier, nom="PRESENT", categorie=self.bareme_cp)
        self.partiel = self._participant(self.atelier, nom="PARTIEL", categorie=self.bareme_ens)
        self.absent = self._participant(self.atelier, nom="ABSENT", categorie=self.bareme_cp)
        ouvrir(self.atelier, self.chef)
        enregistrer_emargement(self.s1, self.present, self.chef)
        enregistrer_emargement(self.s2, self.present, self.chef)
        enregistrer_emargement(self.s1, self.partiel, self.chef)

    def test_l_etat_ne_retient_que_les_emarges(self):
        etat = etat_de_paiement(self.atelier)
        noms = [ligne["participant"].nom for ligne in etat["lignes"]]
        self.assertEqual(sorted(noms), ["PARTIEL", "PRESENT"])
        self.assertNotIn("ABSENT", noms)
        self.assertEqual(etat["nb_absents"], 1)

    def test_le_montant_suit_le_bareme_et_les_jours_constates(self):
        etat = {ligne["participant"].nom: ligne for ligne in etat_de_paiement(self.atelier)["lignes"]}
        self.assertEqual(etat["PRESENT"]["jours"], 2)
        self.assertEqual(etat["PRESENT"]["montant"], 50_000)
        self.assertEqual(etat["PARTIEL"]["jours"], 1)
        self.assertEqual(etat["PARTIEL"]["montant"], 15_000)

    def test_total_de_l_etat(self):
        self.assertEqual(etat_de_paiement(self.atelier)["total"], 65_000)

    def test_les_demi_journees_comptent_pour_moitie(self):
        atelier = self._atelier(jours=1, intitule="Demi-journees")
        generer_sessions(atelier, creneaux_par_jour=2)
        matin, _ = list(atelier.sessions.all())
        participant = self._participant(atelier, nom="MATINAL", categorie=self.bareme_cp)
        ouvrir(atelier, self.chef)
        enregistrer_emargement(matin, participant, self.chef)
        [ligne] = etat_de_paiement(atelier)["lignes"]
        self.assertEqual(ligne["jours"], 0.5)
        self.assertEqual(ligne["montant"], 12_500)

    def test_participant_sans_bareme_apparait_a_zero(self):
        participant = self._participant(self.atelier, nom="SANSBAREME", categorie=None)
        enregistrer_emargement(self.s1, participant, self.chef)
        ligne = next(
            candidate for candidate in etat_de_paiement(self.atelier)["lignes"]
            if candidate["participant"].nom == "SANSBAREME"
        )
        self.assertEqual(ligne["montant"], 0)
        self.assertEqual(ligne["categorie"], "-")

    def test_feuille_de_presence(self):
        feuille = feuille_de_presence(self.atelier)
        self.assertEqual(len(feuille["sessions"]), 2)
        lignes = {ligne["participant"].nom: ligne for ligne in feuille["lignes"]}
        self.assertEqual(lignes["PRESENT"]["nb_presences"], 2)
        self.assertEqual(lignes["PARTIEL"]["nb_presences"], 1)
        self.assertEqual(lignes["ABSENT"]["nb_presences"], 0)


class AttestationTest(BaseAtelier):
    def setUp(self):
        self.atelier = self._atelier(jours=2)
        generer_sessions(self.atelier)
        self.s1, self.s2 = list(self.atelier.sessions.all())
        ouvrir(self.atelier, self.chef)

    def test_attestation_reservee_a_qui_a_suffisamment_participe(self):
        assidu = self._participant(self.atelier, nom="ASSIDU")
        partiel = self._participant(self.atelier, nom="PARTIEL")
        absent = self._participant(self.atelier, nom="ABSENT")
        enregistrer_emargement(self.s1, assidu, self.chef)
        enregistrer_emargement(self.s2, assidu, self.chef)
        enregistrer_emargement(self.s1, partiel, self.chef)

        self.assertTrue(peut_recevoir_attestation(assidu))
        self.assertTrue(peut_recevoir_attestation(partiel))  # une session sur deux
        self.assertFalse(peut_recevoir_attestation(absent))
        self.assertIsNone(donnees_attestation(absent))

    def test_moins_de_la_moitie_des_sessions_ne_donne_pas_droit(self):
        atelier = self._atelier(jours=4, intitule="Atelier long")
        generer_sessions(atelier)
        sessions = list(atelier.sessions.all())
        participant = self._participant(atelier, nom="PEU")
        ouvrir(atelier, self.chef)
        enregistrer_emargement(sessions[0], participant, self.chef)
        self.assertFalse(peut_recevoir_attestation(participant))

    def test_donnees_de_l_attestation(self):
        participant = self._participant(self.atelier, nom="ASSIDU")
        enregistrer_emargement(self.s1, participant, self.chef)
        enregistrer_emargement(self.s2, participant, self.chef)
        donnees = donnees_attestation(participant)
        self.assertEqual(donnees["jours"], 2)
        self.assertEqual(donnees["sessions_emargees"], 2)
        self.assertEqual(donnees["signataire"], self.chef)
        self.assertEqual(donnees["qualite"], "Chef d'antenne (APFC)")

    def test_un_atelier_sans_session_ne_delivre_rien(self):
        atelier = self._atelier(intitule="Sans session")
        participant = self._participant(atelier)
        self.assertFalse(peut_recevoir_attestation(participant))


class CycleDeVieTest(BaseAtelier):
    def test_un_atelier_sans_session_ne_s_ouvre_pas(self):
        atelier = self._atelier()
        with self.assertRaises(ErreurAtelier):
            ouvrir(atelier, self.chef)

    def test_ouverture_puis_cloture(self):
        atelier = self._atelier()
        generer_sessions(atelier)
        ouvrir(atelier, self.chef)
        atelier.refresh_from_db()
        self.assertEqual(atelier.statut, Atelier.Statut.EN_COURS)
        clore(atelier, self.chef)
        atelier.refresh_from_db()
        self.assertEqual(atelier.statut, Atelier.Statut.CLOS)
        self.assertTrue(atelier.est_clos)

    def test_annulation_exige_un_motif(self):
        atelier = self._atelier()
        with self.assertRaises(ErreurAtelier):
            annuler(atelier, self.chef, "  ")
        annuler(atelier, self.chef, "Financement non disponible.")
        atelier.refresh_from_db()
        self.assertEqual(atelier.statut, Atelier.Statut.ANNULE)
        self.assertFalse(atelier.accepte_emargement)

    def test_la_cloture_reporte_les_presences_sur_le_plan_d_action(self):
        """Le pilotage se nourrit de ce qui a ete constate sur le terrain."""
        axe = Axe.objects.create(code="AX1", libelle="Formation continue")
        plan = PlanAction.objects.create(perimetre=self.p_antenne, annee=timezone.localdate().year)
        activite = Activite.objects.create(
            plan=plan, axe=axe, intitule="Formation des enseignants",
            date_debut_prevue=timezone.localdate(), date_fin_prevue=timezone.localdate(),
            effectif_prevu=40, effectif_realise=5,
        )
        atelier = self._atelier(activite=activite)
        generer_sessions(atelier)
        session = atelier.sessions.first()
        for i in range(3):
            enregistrer_emargement(session, self._participant(atelier, nom=f"P{i}"), self.chef)

        _, rapporte = clore(atelier, self.chef)
        activite.refresh_from_db()
        self.assertTrue(rapporte)
        self.assertEqual(activite.effectif_realise, 8)

    def test_cloture_sans_activite_ne_rapporte_rien(self):
        atelier = self._atelier()
        generer_sessions(atelier)
        _, rapporte = clore(atelier, self.chef)
        self.assertFalse(rapporte)


class DroitsTest(BaseAtelier):
    def test_qui_peut_controler_l_emargement(self):
        atelier = self._atelier(organisateur=self.agent)
        self.assertTrue(atelier.peut_etre_controle_par(self.agent))       # organisateur
        self.assertTrue(atelier.peut_etre_controle_par(self.chef))        # chef du perimetre
        self.assertTrue(atelier.peut_etre_controle_par(self.directeur))   # direction
        self.assertFalse(atelier.peut_etre_controle_par(self.autre))

        atelier.controleurs.add(self.autre)
        self.assertTrue(atelier.peut_etre_controle_par(self.autre))

    def test_qui_peut_organiser(self):
        atelier = self._atelier(organisateur=self.agent)
        self.assertTrue(atelier.peut_etre_organise_par(self.agent))
        self.assertTrue(atelier.peut_etre_organise_par(self.chef))
        self.assertFalse(atelier.peut_etre_organise_par(self.autre))

    def test_visibilite_par_perimetre(self):
        self._atelier(self.p_antenne)
        self._atelier(self.p_centrale, intitule="Atelier national", organisateur=self.directeur)
        self.assertEqual(Atelier.objects.visibles_par(self.agent).count(), 1)
        self.assertEqual(Atelier.objects.visibles_par(self.directeur).count(), 2)

    def test_tableau_limite_au_perimetre(self):
        self._atelier(self.p_antenne)
        self._atelier(self.p_centrale, intitule="National", organisateur=self.directeur)
        self.assertEqual(tableau_ateliers(self.agent)["nb_ateliers"], 1)
        self.assertEqual(tableau_ateliers(self.directeur)["nb_ateliers"], 2)


class ParticipantTest(BaseAtelier):
    def test_le_nom_est_normalise_en_majuscules(self):
        participant = self._participant(self._atelier(), nom="  kouassi ")
        self.assertEqual(participant.nom, "KOUASSI")

    def test_un_agent_renseigne_l_identite(self):
        atelier = self._atelier()
        participant = Participant.objects.create(atelier=atelier, agent=self.agent, nom="")
        self.assertEqual(participant.nom, self.agent.last_name)
        self.assertEqual(participant.prenoms, self.agent.first_name)

    def test_les_identifiants_courts_sont_distincts(self):
        atelier = self._atelier()
        identifiants = {self._participant(atelier, nom=f"N{i}").id_court for i in range(20)}
        self.assertEqual(len(identifiants), 20)

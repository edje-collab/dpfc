from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.core.models import Perimetre, Structure
from apps.rh.models import Demande, TypeDemande
from apps.signature.models import CleSignature, SignatureElectronique
from apps.signature.services import (
    ErreurSignature,
    creer_cle,
    empreinte_document,
    revoquer_cle,
    signer_demande,
    verifier_signature,
)

Agent = get_user_model()
CODE = "signature2026"


class SignatureTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        perimetre = Perimetre.objects.create(
            code="APFC-GBK", nom="Antenne de Bouake", type=Perimetre.Type.ANTENNE
        )
        cls.region_structure = Structure.objects.create(
            nom="Antenne de Bouake", sigle="APFC-GBK", type=Structure.Type.ANTENNE,
            perimetre=perimetre, perimetre_racine=True,
        )
        cls.chef = Agent.objects.create_user(
            "C0001", password="motdepasse123", last_name="KONE", first_name="Adama",
            role=Agent.Role.CHEF_ANTENNE, structure=cls.region_structure, fonction="Chef d'antenne",
        )
        cls.region_structure.responsable = cls.chef
        cls.region_structure.save()
        cls.agent = Agent.objects.create_user(
            "A0001", password="motdepasse123", last_name="OUATTARA", first_name="Fatoumata",
            structure=cls.region_structure, superieur=cls.chef,
        )
        debut = date.today() + timedelta(days=10)
        cls.demande = Demande.objects.create(
            agent=cls.agent, type=TypeDemande.CONGE_ANNUEL, motif="Conge annuel",
            date_debut=debut, date_fin=debut + timedelta(days=5), numero="CG-0001/2026/DPFC",
        )

    def test_creation_de_la_bi_cle(self):
        cle = creer_cle(self.chef, CODE)
        self.assertTrue(cle.est_valide)
        self.assertIn("BEGIN PUBLIC KEY", cle.cle_publique)
        self.assertIn("ENCRYPTED PRIVATE KEY", cle.cle_privee_chiffree)
        self.assertEqual(CleSignature.objects.filter(agent=self.chef).count(), 1)

    def test_code_trop_court_refuse(self):
        with self.assertRaises(ErreurSignature):
            creer_cle(self.chef, "1234")

    def test_signature_et_verification(self):
        creer_cle(self.chef, CODE)
        signature = signer_demande(self.demande, self.chef, CODE, qualite="Chef d'antenne")
        resultat = verifier_signature(signature)
        self.assertTrue(resultat["signature_valide"])
        self.assertTrue(resultat["document_intact"])
        self.assertTrue(signature.code_verification.startswith("DPFC-"))

    def test_code_incorrect_refuse_la_signature(self):
        creer_cle(self.chef, CODE)
        with self.assertRaises(ErreurSignature):
            signer_demande(self.demande, self.chef, "mauvais-code")

    def test_signature_impossible_sans_cle(self):
        with self.assertRaises(ErreurSignature):
            signer_demande(self.demande, self.agent, CODE)

    def test_modification_de_l_acte_invalide_la_signature(self):
        creer_cle(self.chef, CODE)
        signature = signer_demande(self.demande, self.chef, CODE)
        self.demande.date_fin = self.demande.date_fin + timedelta(days=10)
        self.demande.save()
        signature.refresh_from_db()
        resultat = verifier_signature(signature)
        self.assertTrue(resultat["signature_valide"])
        self.assertFalse(resultat["document_intact"])
        self.assertIn("modifie", resultat["message"])

    def test_revocation_signalee_a_la_verification(self):
        creer_cle(self.chef, CODE)
        signature = signer_demande(self.demande, self.chef, CODE)
        revoquer_cle(self.chef, "Depart a la retraite")
        resultat = verifier_signature(signature)
        self.assertTrue(resultat["signature_valide"])
        self.assertTrue(resultat["cle_revoquee"])

    def test_empreinte_stable_et_sensible(self):
        empreinte = empreinte_document(self.demande)
        self.assertEqual(len(empreinte), 64)
        self.assertEqual(empreinte, empreinte_document(self.demande))
        self.demande.destination = "Korhogo"
        self.assertNotEqual(empreinte, empreinte_document(self.demande))

    def test_page_publique_de_verification(self):
        creer_cle(self.chef, CODE)
        signature = signer_demande(self.demande, self.chef, CODE, qualite="Chef d'antenne")
        reponse = self.client.get(reverse("signature:verification", args=[signature.code_verification]))
        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, "authentique")
        self.assertContains(reponse, self.demande.numero)

    def test_code_inconnu(self):
        reponse = self.client.get(reverse("signature:verification", args=["DPFC-XXXX-XXXX-XXXX"]))
        self.assertContains(reponse, "Code inconnu")

    def test_signature_a_la_derniere_etape_depuis_l_intranet(self):
        from apps.rh.services import soumettre

        creer_cle(self.chef, CODE)
        self.region_structure.responsable = self.chef
        self.region_structure.save()
        debut = date.today() + timedelta(days=20)
        demande = Demande.objects.create(
            agent=self.agent, type=TypeDemande.PERMISSION, motif="Demarche",
            date_debut=debut, date_fin=debut,
        )
        soumettre(demande)
        self.client.force_login(self.chef)
        self.client.post(
            reverse("rh:demande_decider", args=[demande.pk]),
            {"decision": "FAVORABLE", "commentaire": "Accorde", "code_signature": CODE},
            follow=True,
        )
        demande.refresh_from_db()
        self.assertEqual(demande.statut, Demande.Statut.APPROUVEE)
        self.assertEqual(SignatureElectronique.objects.filter(demande=demande).count(), 1)

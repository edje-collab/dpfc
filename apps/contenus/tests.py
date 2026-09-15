from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.contenus.models import Actualite, Evenement, Projet, Ressource
from apps.core.models import Region, Structure


class SitePublicTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        region = Region.objects.create(nom="Poro", code="PORO", chef_lieu="Korhogo")
        cls.antenne = Structure.objects.create(
            nom="Antenne de Korhogo", sigle="APFC-PORO", type=Structure.Type.ANTENNE, region=region
        )
        cls.article = Actualite.objects.create(
            titre="Validation des guides", chapeau="Resume", contenu="Corps du texte", publiee=True
        )
        Actualite.objects.create(titre="Brouillon interne", chapeau="x", contenu="y", publiee=False)
        cls.ressource = Ressource.objects.create(
            titre="Programme de francais CP1", type=Ressource.Type.PROGRAMME,
            niveau=Ressource.Niveau.PRIMAIRE, discipline="Francais", lien_externe="https://exemple.ci/doc.pdf",
        )
        cls.projet = Projet.objects.create(nom="Formation a distance", sigle="FOAD")
        cls.evenement = Evenement.objects.create(
            titre="Atelier national", date_debut=timezone.localdate() + timezone.timedelta(days=10)
        )

    def test_pages_principales(self):
        for nom in ["accueil", "presentation", "actualites", "ressources", "foad",
                    "projets", "evenements", "antennes", "contact", "recherche"]:
            with self.subTest(page=nom):
                self.assertEqual(self.client.get(reverse(f"contenus:{nom}")).status_code, 200)

    def test_pages_de_detail(self):
        self.assertEqual(self.client.get(self.article.get_absolute_url()).status_code, 200)
        self.assertEqual(self.client.get(self.ressource.get_absolute_url()).status_code, 200)
        self.assertEqual(self.client.get(self.projet.get_absolute_url()).status_code, 200)
        self.assertEqual(self.client.get(self.evenement.get_absolute_url()).status_code, 200)
        self.assertEqual(self.client.get(self.antenne.get_absolute_url()).status_code, 200)

    def test_les_brouillons_restent_invisibles(self):
        reponse = self.client.get(reverse("contenus:actualites"))
        self.assertContains(reponse, "Validation des guides")
        self.assertNotContains(reponse, "Brouillon interne")

    def test_compteur_de_telechargement(self):
        self.client.get(reverse("contenus:ressource_telecharger", args=[self.ressource.slug]))
        self.ressource.refresh_from_db()
        self.assertEqual(self.ressource.telechargements, 1)

    def test_formulaire_de_contact(self):
        reponse = self.client.post(
            reverse("contenus:contact"),
            {"nom": "Kouassi Jean", "email": "jean@exemple.ci", "sujet": "Question",
             "message": "Bonjour, ou trouver le programme de CM2 ?"},
            follow=True,
        )
        self.assertContains(reponse, "Message envoye")

    def test_recherche(self):
        reponse = self.client.get(reverse("contenus:recherche"), {"q": "guides"})
        self.assertContains(reponse, "Validation des guides")

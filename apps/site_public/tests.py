from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.core.models import ConfigurationSite, Region, Structure
from apps.site_public import arborescence
from apps.site_public.models import PageActualite, Ressource


class SitePublicTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        region = Region.objects.create(nom="Poro", code="PORO", chef_lieu="Korhogo")
        cls.antenne = Structure.objects.create(
            nom="Antenne de Korhogo", sigle="APFC-PORO", type=Structure.Type.ANTENNE, region=region
        )
        cls.pages = arborescence.assurer_site(hote="testserver")
        cls.article = arborescence.ajouter_actualite(
            cls.pages["actualites"], "Validation des guides", "Resume", "<p>Corps du texte</p>"
        )
        brouillon = arborescence.ajouter_actualite(
            cls.pages["actualites"], "Brouillon interne", "x", "<p>y</p>"
        )
        brouillon.unpublish()
        cls.ressource = arborescence.ajouter_ressource(
            "Programme de francais CP1",
            type=Ressource.Type.PROGRAMME,
            niveau=Ressource.Niveau.PRIMAIRE,
            discipline="Francais",
            lien_externe="https://exemple.ci/doc.pdf",
        )
        cls.projet = arborescence.ajouter_projet(
            cls.pages["projets"], "FOAD", "Formation a distance", "Accroche", "<p>Description</p>"
        )
        cls.evenement = arborescence.ajouter_evenement(
            cls.pages["evenements"],
            "Atelier national",
            timezone.localdate() + timezone.timedelta(days=10),
            "Un atelier",
        )

    def test_pages_principales(self):
        for cle, page in self.pages.items():
            with self.subTest(page=cle):
                self.assertEqual(self.client.get(page.url).status_code, 200)
        self.assertEqual(self.client.get(reverse("site_public:recherche")).status_code, 200)

    def test_pages_de_detail(self):
        self.assertEqual(self.client.get(self.article.url).status_code, 200)
        self.assertEqual(self.client.get(self.ressource.get_absolute_url()).status_code, 200)
        self.assertEqual(self.client.get(self.projet.url).status_code, 200)
        self.assertEqual(self.client.get(self.evenement.url).status_code, 200)
        self.assertEqual(self.client.get(self.antenne.get_absolute_url()).status_code, 200)

    def test_les_brouillons_restent_invisibles(self):
        reponse = self.client.get(self.pages["actualites"].url)
        self.assertContains(reponse, "Validation des guides")
        self.assertNotContains(reponse, "Brouillon interne")
        self.assertEqual(PageActualite.publiees().count(), 1)

    def test_accueil_affiche_les_contenus(self):
        reponse = self.client.get("/")
        self.assertContains(reponse, "Validation des guides")
        self.assertContains(reponse, "Atelier national")
        self.assertContains(reponse, "FOAD")

    def test_compteur_de_telechargement(self):
        reponse = self.client.get(self.ressource.url_telechargement)
        self.assertEqual(reponse.status_code, 302)
        self.ressource.refresh_from_db()
        self.assertEqual(self.ressource.telechargements, 1)

    def test_formulaire_de_contact(self):
        reponse = self.client.post(
            self.pages["contact"].url,
            {"nom": "Kouassi Jean", "email": "jean@exemple.ci", "sujet": "Question",
             "message": "Bonjour, ou trouver le programme de CM2 ?"},
            follow=True,
        )
        self.assertContains(reponse, "Message envoye")

    def test_recherche(self):
        reponse = self.client.get(reverse("site_public:recherche"), {"q": "guides"})
        self.assertContains(reponse, "Validation des guides")
        reponse = self.client.get(reverse("site_public:recherche"), {"q": "francais"})
        self.assertContains(reponse, "Programme de francais CP1")

    def test_bouton_espace_agent_pilotable(self):
        self.assertContains(self.client.get("/"), "Espace agent</a>")
        config = ConfigurationSite.actuelle()
        config.afficher_espace_agent = False
        config.save()
        reponse = self.client.get("/")
        self.assertNotContains(reponse, "Espace agent</a>")
        self.assertNotContains(reponse, "<h4>Espace agent</h4>")

    def test_administration_wagtail_protegee(self):
        reponse = self.client.get("/cms/")
        self.assertEqual(reponse.status_code, 302)
        self.assertIn("/cms/login/", reponse["Location"])

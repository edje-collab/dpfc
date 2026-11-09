from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView, TokenVerifyView

from . import views

router = DefaultRouter()
router.register("demandes", views.DemandeViewSet, basename="demande")
router.register("rapports-mission", views.RapportMissionViewSet, basename="rapport")
router.register("notifications", views.NotificationViewSet, basename="notification")
router.register("annuaire", views.AnnuaireViewSet, basename="annuaire")
router.register("plans", views.PlanActionViewSet, basename="plan")
router.register("activites", views.ActiviteViewSet, basename="activite")
router.register("public/actualites", views.ActualitePubliqueViewSet, basename="api-actualite")
router.register("public/ressources", views.RessourcePubliqueViewSet, basename="api-ressource")
router.register("public/projets", views.ProjetPubliqueViewSet, basename="api-projet")
router.register("public/evenements", views.EvenementPubliqueViewSet, basename="api-evenement")
router.register("public/antennes", views.AntennePubliqueViewSet, basename="api-antenne")

app_name = "api"

urlpatterns = [
    path("auth/connexion/", views.ConnexionView.as_view(), name="connexion"),
    path("auth/rafraichir/", TokenRefreshView.as_view(), name="rafraichir"),
    path("auth/verifier/", TokenVerifyView.as_view(), name="verifier"),
    path("moi/", views.MonProfilView.as_view(), name="moi"),
    path("moi/mot-de-passe/", views.ChangerMotDePasseView.as_view(), name="mot_de_passe"),
    path("moi/solde/", views.SoldeView.as_view(), name="solde"),
    path("pilotage/", views.TableauPilotageView.as_view(), name="pilotage"),
    path("verification/<str:code>/", views.VerificationView.as_view(), name="verification"),
    path("", include(router.urls)),
]

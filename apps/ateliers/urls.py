from django.urls import path

from . import views

app_name = "ateliers"

urlpatterns = [
    path("", views.tableau, name="tableau"),
    path("liste/", views.liste, name="liste"),
    path("nouveau/", views.creer, name="creer"),
    path("<int:pk>/", views.detail, name="detail"),
    path("<int:pk>/modifier/", views.modifier, name="modifier"),
    path("<int:pk>/<str:operation>/", views.cycle, name="cycle"),
    # Participants et badges
    path("<int:pk>/participants/", views.participant_creer, name="participants"),
    path("<int:pk>/participants/importer/", views.participants_importer, name="participants_importer"),
    path("<int:pk>/badges/", views.badges, name="badges"),
    path("participants/<int:pk>/revoquer/", views.participant_revoquer, name="participant_revoquer"),
    path("participants/<int:pk>/qr/", views.qr_participant, name="qr"),
    path("participants/<int:pk>/attestation/", views.attestation, name="attestation"),
    # Emargement
    path("<int:pk>/emargement/", views.emargement, name="emargement"),
    path("<int:pk>/emargement/<int:session_pk>/", views.emargement, name="emargement_session"),
    path("<int:pk>/emargement/<int:session_pk>/manuel/", views.emargement_manuel, name="emargement_manuel"),
    path("emargements/<uuid:pk>/annuler/", views.emargement_annuler, name="emargement_annuler"),
    # Sorties
    path("<int:pk>/sessions/nouvelle/", views.session_creer, name="session_creer"),
    path("<int:pk>/paiement/", views.paiement, name="paiement"),
    path("<int:pk>/paiement/csv/", views.paiement_csv, name="paiement_csv"),
    path("<int:pk>/presence/csv/", views.presence_csv, name="presence_csv"),
    path("<int:pk>/compte-rendu/", views.compte_rendu, name="compte_rendu"),
]

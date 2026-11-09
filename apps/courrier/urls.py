from django.urls import path

from . import views

app_name = "courrier"

urlpatterns = [
    path("", views.tableau, name="tableau"),
    # Registre du courrier
    path("registre/", views.registre, name="registre"),
    path("registre/export/", views.export_registre, name="export_registre"),
    path("nouveau/", views.courrier_creer, name="creer"),
    path("<int:pk>/", views.courrier_detail, name="detail"),
    path("<int:pk>/imputer/", views.courrier_imputer, name="imputer"),
    path("<int:pk>/classer/", views.courrier_classer, name="classer"),
    path("imputations/<int:pk>/traiter/", views.imputation_traiter, name="imputation_traiter"),
    # Bibliotheque documentaire
    path("documents/", views.documents, name="documents"),
    path("documents/nouveau/", views.document_creer, name="document_creer"),
    path("documents/<int:pk>/", views.document_detail, name="document_detail"),
    path("documents/<int:pk>/version/", views.document_version, name="document_version"),
    # Parapheur
    path("parapheur/", views.parapheur, name="parapheur"),
    path("parapheur/nouvelle/", views.parapheur_creer, name="parapheur_creer"),
    path("parapheur/<int:pk>/", views.parapheur_detail, name="parapheur_detail"),
    path("parapheur/<int:pk>/soumettre/", views.parapheur_soumettre, name="parapheur_soumettre"),
    path("visas/<int:pk>/<str:decision>/", views.parapheur_viser, name="parapheur_viser"),
    # Modeles
    path("modeles/", views.modeles, name="modeles"),
]

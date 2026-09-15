from django.urls import path

from . import views

app_name = "contenus"

urlpatterns = [
    path("", views.accueil, name="accueil"),
    path("presentation/", views.presentation, name="presentation"),
    path("actualites/", views.actualites, name="actualites"),
    path("actualites/<slug:slug>/", views.actualite_detail, name="actualite_detail"),
    path("ressources/", views.ressources, name="ressources"),
    path("ressources/<slug:slug>/", views.ressource_detail, name="ressource_detail"),
    path("ressources/<slug:slug>/telecharger/", views.ressource_telecharger, name="ressource_telecharger"),
    path("foad/", views.foad, name="foad"),
    path("projets/", views.projets, name="projets"),
    path("projets/<slug:slug>/", views.projet_detail, name="projet_detail"),
    path("evenements/", views.evenements, name="evenements"),
    path("evenements/<slug:slug>/", views.evenement_detail, name="evenement_detail"),
    path("antennes/", views.antennes, name="antennes"),
    path("antennes/<slug:slug>/", views.antenne_detail, name="antenne_detail"),
    path("contact/", views.contact, name="contact"),
    path("recherche/", views.recherche, name="recherche"),
    path("page/<slug:slug>/", views.page, name="page"),
]

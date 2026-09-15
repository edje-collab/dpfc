from django.urls import path

from . import views

app_name = "rh"

urlpatterns = [
    path("", views.tableau_bord, name="tableau_bord"),
    path("demandes/", views.mes_demandes, name="mes_demandes"),
    path("demandes/nouvelle/<str:type_acte>/", views.demande_creer, name="demande_creer"),
    path("demandes/<int:pk>/", views.demande_detail, name="demande_detail"),
    path("demandes/<int:pk>/modifier/", views.demande_modifier, name="demande_modifier"),
    path("demandes/<int:pk>/soumettre/", views.demande_soumettre, name="demande_soumettre"),
    path("demandes/<int:pk>/annuler/", views.demande_annuler, name="demande_annuler"),
    path("demandes/<int:pk>/decision/", views.demande_decider, name="demande_decider"),
    path("demandes/<int:pk>/rapport/", views.rapport_mission, name="rapport_mission"),
    path("demandes/<int:pk>/document/", views.document, name="document"),
    path("a-valider/", views.a_valider, name="a_valider"),
    path("planning/", views.planning, name="planning"),
    path("registre/", views.registre, name="registre"),
    path("mes-soldes/", views.mes_soldes, name="mes_soldes"),
    path("soldes/", views.soldes_gestion, name="soldes_gestion"),
    path("jours-feries/", views.jours_feries, name="jours_feries"),
]

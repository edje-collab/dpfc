from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("connexion/", views.ConnexionView.as_view(), name="connexion"),
    path("deconnexion/", views.DeconnexionView.as_view(), name="deconnexion"),
    path("mot-de-passe/", views.ChangerMotDePasseView.as_view(), name="changer_mot_de_passe"),
    path("profil/", views.profil, name="profil"),
    path("annuaire/", views.annuaire, name="annuaire"),
    path("annuaire/<int:pk>/", views.agent_detail, name="agent_detail"),
    path("organigramme/", views.organigramme, name="organigramme"),
    path("notifications/", views.notifications, name="notifications"),
    path("notifications/<int:pk>/", views.notification_ouvrir, name="notification_ouvrir"),
    path("comptes/", views.comptes_liste, name="comptes_liste"),
    path("comptes/nouveau/", views.compte_editer, name="compte_creer"),
    path("comptes/<int:pk>/", views.compte_editer, name="compte_modifier"),
    path("comptes/<int:pk>/activation/", views.compte_basculer_activation, name="compte_activation"),
    path("comptes/<int:pk>/mot-de-passe/", views.compte_reinitialiser_mot_de_passe, name="compte_mdp"),
    path("comptes/import/", views.import_agents, name="import_agents"),
    path("comptes/import/modele/", views.modele_import, name="modele_import"),
]

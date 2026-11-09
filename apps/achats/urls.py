from django.urls import path

from . import views

app_name = "achats"

urlpatterns = [
    path("", views.tableau, name="tableau"),
    # Expressions de besoin
    path("besoins/", views.besoins, name="besoins"),
    path("besoins/nouveau/", views.besoin_creer, name="besoin_creer"),
    path("besoins/<int:pk>/", views.besoin_detail, name="besoin_detail"),
    path("besoins/<int:pk>/ligne/", views.ligne_ajouter, name="ligne_ajouter"),
    path("besoins/<int:pk>/soumettre/", views.besoin_soumettre, name="besoin_soumettre"),
    path("besoins/<int:pk>/offre/", views.offre_ajouter, name="offre_ajouter"),
    path("besoins/<int:pk>/commander/", views.besoin_commander, name="besoin_commander"),
    path("lignes/<int:pk>/supprimer/", views.ligne_supprimer, name="ligne_supprimer"),
    path("offres/<int:pk>/retenir/", views.offre_retenir, name="offre_retenir"),
    path("validations/<int:pk>/<str:decision>/", views.besoin_decider, name="besoin_decider"),
    # Commandes
    path("commandes/", views.commandes, name="commandes"),
    path("commandes/<int:pk>/receptionner/", views.commande_receptionner, name="commande_receptionner"),
    path("commandes/<int:pk>/facture/", views.commande_facture, name="commande_facture"),
    path("commandes/<int:pk>/annuler/", views.commande_annuler, name="commande_annuler"),
    # Magasin
    path("magasin/", views.magasin, name="magasin"),
    path("magasin/nouveau/", views.article_creer, name="article_creer"),
    path("magasin/export/", views.magasin_csv, name="magasin_csv"),
    path("magasin/<int:pk>/", views.article_detail, name="article_detail"),
    path("magasin/<int:pk>/mouvement/", views.mouvement_creer, name="mouvement_creer"),
    # Equipements
    path("equipements/", views.equipements, name="equipements"),
    path("equipements/nouveau/", views.equipement_creer, name="equipement_creer"),
]

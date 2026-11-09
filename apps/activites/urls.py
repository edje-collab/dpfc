from django.urls import path

from . import views

app_name = "activites"

urlpatterns = [
    path("", views.pilotage, name="pilotage"),
    path("plans/", views.plans, name="plans"),
    path("plans/nouveau/", views.plan_creer, name="plan_creer"),
    path("plans/<int:pk>/", views.plan_detail, name="plan_detail"),
    path("plans/<int:pk>/chronogramme/", views.plan_chronogramme, name="plan_chronogramme"),
    path("plans/<int:pk>/<str:operation>/", views.plan_action, name="plan_action"),
    path("plans/<int:plan_pk>/activites/nouvelle/", views.activite_creer, name="activite_creer"),
    path("activites/", views.activites, name="activites"),
    path("activites/export/", views.export_activites, name="export_activites"),
    path("activites/<int:pk>/", views.activite_detail, name="activite_detail"),
    path("activites/<int:pk>/modifier/", views.activite_modifier, name="activite_modifier"),
    path("activites/<int:pk>/avancement/", views.activite_avancement, name="activite_avancement"),
    path("activites/<int:pk>/indicateur/", views.indicateur_creer, name="indicateur_creer"),
    path("activites/<int:pk>/<str:operation>/", views.activite_decision, name="activite_decision"),
    path("axes/", views.axes, name="axes"),
]

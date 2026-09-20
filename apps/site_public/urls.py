from django.urls import path

from . import views

app_name = "site_public"

urlpatterns = [
    path("recherche/", views.recherche, name="recherche"),
]

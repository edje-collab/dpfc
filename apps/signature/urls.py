from django.urls import path

from . import views

app_name = "signature"

urlpatterns = [
    path("intranet/ma-signature/", views.ma_cle, name="ma_cle"),
    path("verification/", views.verification, name="verification_recherche"),
    path("verification/<str:code>/", views.verification, name="verification"),
    path("intranet/signature/<int:pk>/qr/", views.qr_acte, name="qr"),
]

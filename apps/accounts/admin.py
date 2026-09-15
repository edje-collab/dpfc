from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Agent, Notification


@admin.register(Agent)
class AgentAdmin(UserAdmin):
    ordering = ["last_name"]
    list_display = ("matricule", "nom_complet", "fonction", "structure", "role", "situation", "is_active")
    list_filter = ("role", "situation", "structure__rattachement", "structure", "is_active")
    search_fields = ("matricule", "last_name", "first_name", "email", "fonction")
    autocomplete_fields = ("structure", "superieur")
    fieldsets = (
        ("Identifiants", {"fields": ("matricule", "password")}),
        ("Identite", {"fields": ("civilite", "last_name", "first_name", "date_naissance", "photo")}),
        ("Contact", {"fields": ("email", "telephone")}),
        ("Affectation", {"fields": ("structure", "fonction", "grade", "superieur", "lieu_service",
                                    "date_prise_service", "situation")}),
        ("Droits", {"fields": ("role", "is_active", "is_staff", "is_superuser", "groups",
                               "user_permissions", "doit_changer_mot_de_passe")}),
        ("Suivi", {"fields": ("last_login", "derniere_activite", "date_joined")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("matricule", "last_name", "first_name", "email", "structure", "role",
                       "password1", "password2"),
        }),
    )
    readonly_fields = ("last_login", "date_joined", "derniere_activite")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("destinataire", "titre", "niveau", "lue", "creee_le")
    list_filter = ("niveau", "lue")
    search_fields = ("titre", "message")

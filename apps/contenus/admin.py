from django.contrib import admin

from .models import Actualite, Categorie, Evenement, MessageContact, PageStatique, Projet, Ressource


@admin.register(Categorie)
class CategorieAdmin(admin.ModelAdmin):
    list_display = ("nom", "couleur")
    search_fields = ("nom",)
    prepopulated_fields = {"slug": ("nom",)}


@admin.register(Actualite)
class ActualiteAdmin(admin.ModelAdmin):
    list_display = ("titre", "categorie", "structure", "date_publication", "publiee", "a_la_une", "vues")
    list_filter = ("publiee", "a_la_une", "categorie", "structure__rattachement")
    search_fields = ("titre", "chapeau", "contenu")
    prepopulated_fields = {"slug": ("titre",)}
    autocomplete_fields = ("structure", "auteur", "categorie")
    date_hierarchy = "date_publication"
    list_editable = ("publiee", "a_la_une")

    def save_model(self, request, obj, form, change):
        if not obj.auteur_id:
            obj.auteur = request.user
        super().save_model(request, obj, form, change)


@admin.register(Ressource)
class RessourceAdmin(admin.ModelAdmin):
    list_display = ("titre", "type", "niveau", "discipline", "classe", "telechargements", "publiee")
    list_filter = ("type", "niveau", "publiee")
    search_fields = ("titre", "description", "discipline")
    prepopulated_fields = {"slug": ("titre",)}


@admin.register(Projet)
class ProjetAdmin(admin.ModelAdmin):
    list_display = ("sigle", "nom", "etat", "ordre", "publie")
    list_editable = ("ordre", "publie")
    prepopulated_fields = {"slug": ("sigle",)}
    search_fields = ("sigle", "nom")


@admin.register(Evenement)
class EvenementAdmin(admin.ModelAdmin):
    list_display = ("titre", "type", "date_debut", "date_fin", "lieu", "structure", "publie")
    list_filter = ("type", "publie", "structure")
    search_fields = ("titre", "description", "lieu")
    date_hierarchy = "date_debut"
    autocomplete_fields = ("structure",)


@admin.register(PageStatique)
class PageStatiqueAdmin(admin.ModelAdmin):
    list_display = ("titre", "slug", "dans_le_menu", "ordre", "publiee")
    prepopulated_fields = {"slug": ("titre",)}


@admin.register(MessageContact)
class MessageContactAdmin(admin.ModelAdmin):
    list_display = ("sujet", "nom", "email", "structure_destinataire", "etat", "recu_le")
    list_filter = ("etat", "structure_destinataire")
    search_fields = ("nom", "email", "sujet", "message")
    list_editable = ("etat",)

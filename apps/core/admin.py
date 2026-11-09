from django.contrib import admin

from .models import JournalAction, Perimetre, Region, Structure


@admin.register(Region)
class RegionAdmin(admin.ModelAdmin):
    list_display = ("nom", "code", "chef_lieu", "dren")
    search_fields = ("nom", "code", "chef_lieu")


@admin.register(Perimetre)
class PerimetreAdmin(admin.ModelAdmin):
    list_display = ("code", "nom", "type", "region", "responsable_affiche", "nb_agents", "actif")
    list_filter = ("type", "actif", "region")
    search_fields = ("code", "nom")

    @admin.display(description="responsable")
    def responsable_affiche(self, perimetre):
        responsable = perimetre.responsable
        return responsable.nom_complet if responsable else "-"

    @admin.display(description="agents")
    def nb_agents(self, perimetre):
        return perimetre.agents().count()


@admin.register(Structure)
class StructureAdmin(admin.ModelAdmin):
    list_display = ("nom", "sigle", "type", "perimetre", "perimetre_racine", "region", "drena",
                    "responsable", "active")
    list_filter = ("type", "rattachement", "active", "perimetre", "region")
    search_fields = ("nom", "sigle")
    autocomplete_fields = ("parent", "region", "responsable", "drena")
    prepopulated_fields = {"slug": ("nom",)}


@admin.register(JournalAction)
class JournalActionAdmin(admin.ModelAdmin):
    list_display = ("horodatage", "agent", "perimetre", "action", "objet", "adresse_ip")
    list_filter = ("action", "perimetre")
    search_fields = ("action", "objet", "details")
    readonly_fields = [f.name for f in JournalAction._meta.fields]

    def has_add_permission(self, request):
        return False

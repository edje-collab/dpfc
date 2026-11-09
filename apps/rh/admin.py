from django.contrib import admin

from .models import Demande, JourFerie, RapportMission, SoldeConge, Validation


class ValidationInline(admin.TabularInline):
    model = Validation
    extra = 0
    autocomplete_fields = ("valideur",)
    readonly_fields = ("decide_le",)


@admin.register(Demande)
class DemandeAdmin(admin.ModelAdmin):
    list_display = ("numero", "type", "agent", "date_debut", "date_fin", "nb_jours",
                    "hors_perimetre_drena", "statut")
    list_filter = ("type", "statut", "hors_perimetre_drena", "agent__structure__rattachement",
                   "agent__structure")
    search_fields = ("numero", "agent__last_name", "agent__matricule", "motif", "destination")
    date_hierarchy = "date_debut"
    autocomplete_fields = ("agent", "interimaire", "structure", "region_mission", "depose_par")
    readonly_fields = ("numero", "nb_jours", "soumise_le", "cloturee_le", "solde_impacte")
    inlines = [ValidationInline]


@admin.register(SoldeConge)
class SoldeCongeAdmin(admin.ModelAdmin):
    list_display = ("agent", "annee", "droit_jours", "jours_reportes", "jours_consommes", "jours_restants")
    list_filter = ("annee",)
    search_fields = ("agent__last_name", "agent__matricule")
    autocomplete_fields = ("agent",)


@admin.register(JourFerie)
class JourFerieAdmin(admin.ModelAdmin):
    list_display = ("date", "libelle")


@admin.register(RapportMission)
class RapportMissionAdmin(admin.ModelAdmin):
    list_display = ("demande", "depose_le")
    search_fields = ("demande__numero", "resume")


@admin.register(Validation)
class ValidationAdmin(admin.ModelAdmin):
    list_display = ("demande", "ordre", "libelle", "valideur", "decision", "decide_le")
    list_filter = ("decision",)
    autocomplete_fields = ("demande", "valideur")

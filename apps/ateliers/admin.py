from django.contrib import admin

from .models import (
    Atelier,
    Bareme,
    CompteRendu,
    DoublonEmargement,
    Emargement,
    Participant,
    Session,
)


@admin.register(Bareme)
class BaremeAdmin(admin.ModelAdmin):
    list_display = ("code", "libelle", "montant_journalier", "actif")
    list_editable = ("montant_journalier", "actif")
    search_fields = ("code", "libelle")


class SessionInline(admin.TabularInline):
    model = Session
    extra = 0
    fields = ("date", "creneau", "libelle")


class ParticipantInline(admin.TabularInline):
    model = Participant
    extra = 0
    fields = ("nom", "prenoms", "fonction", "structure_origine", "categorie", "statut")
    show_change_link = True


@admin.register(Atelier)
class AtelierAdmin(admin.ModelAdmin):
    list_display = ("intitule", "type", "perimetre", "lieu", "date_debut", "date_fin",
                    "statut", "nb_participants", "nb_emarges")
    list_filter = ("statut", "type", "perimetre")
    search_fields = ("intitule", "lieu", "id_court")
    date_hierarchy = "date_debut"
    autocomplete_fields = ("perimetre", "activite", "structure_hote", "organisateur")
    filter_horizontal = ("controleurs",)
    readonly_fields = ("id_court",)
    exclude = ("cle",)
    inlines = [SessionInline, ParticipantInline]

    @admin.display(description="inscrits")
    def nb_participants(self, atelier):
        return atelier.nb_participants

    @admin.display(description="emarges")
    def nb_emarges(self, atelier):
        return atelier.nb_emarges


@admin.register(Participant)
class ParticipantAdmin(admin.ModelAdmin):
    list_display = ("nom_complet", "atelier", "structure_origine", "categorie",
                    "statut", "nb_sessions_emargees")
    list_filter = ("statut", "categorie", "atelier__perimetre")
    search_fields = ("nom", "prenoms", "structure_origine", "id_court")
    autocomplete_fields = ("atelier", "agent", "categorie")
    readonly_fields = ("id_court",)

    @admin.display(description="sessions emargees")
    def nb_sessions_emargees(self, participant):
        return participant.nb_sessions_emargees


@admin.register(Emargement)
class EmargementAdmin(admin.ModelAdmin):
    list_display = ("participant", "session", "horodatage", "mode", "saisi_par", "recu_le")
    list_filter = ("mode", "session__atelier__perimetre", "session__atelier")
    search_fields = ("participant__nom", "participant__prenoms", "motif")
    readonly_fields = ("id", "recu_le")


@admin.register(DoublonEmargement)
class DoublonEmargementAdmin(admin.ModelAdmin):
    list_display = ("participant", "session", "horodatage", "appareil", "recu_le")
    list_filter = ("session__atelier",)
    readonly_fields = [f.name for f in DoublonEmargement._meta.fields]

    def has_add_permission(self, request):
        return False


@admin.register(CompteRendu)
class CompteRenduAdmin(admin.ModelAdmin):
    list_display = ("atelier", "redige_par", "modifie_le")
    search_fields = ("contenu", "decisions", "recommandations")
    autocomplete_fields = ("atelier",)

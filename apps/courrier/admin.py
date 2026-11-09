from django.contrib import admin

from .models import (
    Courrier,
    Document,
    Imputation,
    ModeleDocument,
    PieceParapheur,
    VersionDocument,
    Visa,
)


class ImputationInline(admin.TabularInline):
    model = Imputation
    extra = 0
    fields = ("destinataire", "structure", "instructions", "delai", "pour_information", "traite_le")
    readonly_fields = ("traite_le",)
    autocomplete_fields = ("destinataire", "structure")


@admin.register(Courrier)
class CourrierAdmin(admin.ModelAdmin):
    list_display = ("numero", "sens", "objet", "correspondant", "perimetre",
                    "date_enregistrement", "statut", "en_retard")
    list_filter = ("sens", "statut", "nature", "confidentiel", "perimetre")
    search_fields = ("numero", "objet", "correspondant", "reference_expediteur", "resume")
    date_hierarchy = "date_enregistrement"
    autocomplete_fields = ("perimetre", "structure_correspondante", "activite", "courrier_lie")
    readonly_fields = ("numero", "classe_le")
    inlines = [ImputationInline]

    @admin.display(boolean=True, description="en retard")
    def en_retard(self, courrier):
        return courrier.est_en_retard


class VersionInline(admin.TabularInline):
    model = VersionDocument
    extra = 0
    fields = ("numero", "fichier", "commentaire", "empreinte", "taille", "deposee_par", "deposee_le")
    readonly_fields = ("numero", "empreinte", "taille", "deposee_le")


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ("titre", "type_document", "annee", "perimetre", "acces", "partage",
                    "nb_versions", "indexe_le")
    list_filter = ("type_document", "annee", "acces", "partage", "perimetre")
    search_fields = ("titre", "description", "texte_extrait")
    autocomplete_fields = ("perimetre", "courrier", "activite", "deposant")
    filter_horizontal = ("agents_autorises",)
    readonly_fields = ("indexe_le",)
    inlines = [VersionInline]

    @admin.display(description="versions")
    def nb_versions(self, document):
        return document.nb_versions


class VisaInline(admin.TabularInline):
    model = Visa
    extra = 0
    fields = ("ordre", "libelle", "viseur", "decision", "observation", "decide_le")
    readonly_fields = ("decide_le",)


@admin.register(PieceParapheur)
class PieceParapheurAdmin(admin.ModelAdmin):
    list_display = ("objet", "perimetre", "demandeur", "statut", "soumise_le", "close_le")
    list_filter = ("statut", "perimetre")
    search_fields = ("objet", "note")
    autocomplete_fields = ("perimetre", "document", "courrier", "demandeur")
    inlines = [VisaInline]


@admin.register(ModeleDocument)
class ModeleDocumentAdmin(admin.ModelAdmin):
    list_display = ("code", "titre", "nature", "actif")
    list_filter = ("nature", "actif")
    search_fields = ("code", "titre", "corps")
    prepopulated_fields = {"code": ("titre",)}

from django.contrib import admin

from .models import Circuit, Etape


class EtapeInline(admin.TabularInline):
    model = Etape
    extra = 1
    fields = ("ordre", "libelle", "designation", "role", "conditions",
              "seuil_montant", "facultative")


@admin.register(Circuit)
class CircuitAdmin(admin.ModelAdmin):
    list_display = ("type_acte", "perimetre", "type_perimetre", "nb_etapes", "actif")
    list_filter = ("type_perimetre", "type_acte", "actif")
    search_fields = ("type_acte", "libelle", "perimetre__code")
    autocomplete_fields = ("perimetre",)
    inlines = [EtapeInline]

    @admin.display(description="etapes")
    def nb_etapes(self, circuit):
        return circuit.etapes.count()

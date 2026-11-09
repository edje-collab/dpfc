from django.contrib import admin

from .models import Activite, Avancement, Axe, Indicateur, PlanAction


@admin.register(Axe)
class AxeAdmin(admin.ModelAdmin):
    list_display = ("code", "libelle", "ordre", "actif")
    list_editable = ("ordre", "actif")
    search_fields = ("code", "libelle")


class ActiviteInline(admin.TabularInline):
    model = Activite
    extra = 0
    fields = ("code", "intitule", "axe", "type", "date_debut_prevue", "date_fin_prevue",
              "budget_prevu", "statut", "avancement")
    readonly_fields = ("code",)
    show_change_link = True


@admin.register(PlanAction)
class PlanActionAdmin(admin.ModelAdmin):
    list_display = ("annee", "perimetre", "statut", "nb_activites", "taux_execution",
                    "taux_execution_budgetaire", "valide_le")
    list_filter = ("annee", "statut", "perimetre__type", "perimetre")
    search_fields = ("libelle", "perimetre__code", "perimetre__nom")
    autocomplete_fields = ("perimetre", "valide_par")
    readonly_fields = ("soumis_le", "valide_le", "clos_le")
    inlines = [ActiviteInline]

    @admin.display(description="activites")
    def nb_activites(self, plan):
        return plan.nb_activites

    @admin.display(description="execution")
    def taux_execution(self, plan):
        return f"{plan.taux_execution} %"

    @admin.display(description="budget")
    def taux_execution_budgetaire(self, plan):
        return f"{plan.taux_execution_budgetaire} %"


class AvancementInline(admin.TabularInline):
    model = Avancement
    extra = 0
    fields = ("date", "taux", "realisations", "effectif_touche", "montant_engage", "auteur")
    readonly_fields = ("auteur",)


class IndicateurInline(admin.TabularInline):
    model = Indicateur
    extra = 0


@admin.register(Activite)
class ActiviteAdmin(admin.ModelAdmin):
    list_display = ("code", "intitule", "plan", "axe", "type", "date_fin_prevue",
                    "statut", "avancement", "en_retard")
    list_filter = ("statut", "type", "plan__annee", "plan__perimetre", "axe")
    search_fields = ("code", "intitule", "description", "lieu")
    autocomplete_fields = ("plan", "axe", "structure", "responsable")
    date_hierarchy = "date_debut_prevue"
    inlines = [AvancementInline, IndicateurInline]

    @admin.display(boolean=True, description="en retard")
    def en_retard(self, activite):
        return activite.est_en_retard


@admin.register(Avancement)
class AvancementAdmin(admin.ModelAdmin):
    list_display = ("activite", "date", "taux", "effectif_touche", "montant_engage", "auteur")
    list_filter = ("date", "activite__plan__perimetre")
    search_fields = ("activite__code", "activite__intitule", "realisations")

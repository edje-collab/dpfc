from django.contrib import admin

from .models import (
    Article,
    BonCommande,
    Equipement,
    ExpressionBesoin,
    Fournisseur,
    LigneBesoin,
    MouvementStock,
    Offre,
    ValidationBesoin,
)


@admin.register(Fournisseur)
class FournisseurAdmin(admin.ModelAdmin):
    list_display = ("nom", "domaine", "contact", "telephone", "ncc", "actif")
    list_filter = ("actif", "domaine")
    search_fields = ("nom", "contact", "ncc")


class LigneInline(admin.TabularInline):
    model = LigneBesoin
    extra = 0
    fields = ("article", "designation", "quantite", "unite", "prix_unitaire")
    autocomplete_fields = ("article",)


class OffreInline(admin.TabularInline):
    model = Offre
    extra = 0
    fields = ("fournisseur", "montant", "delai_jours", "retenue")
    autocomplete_fields = ("fournisseur",)


class ValidationInline(admin.TabularInline):
    model = ValidationBesoin
    extra = 0
    fields = ("ordre", "libelle", "valideur", "decision", "commentaire", "decide_le")
    readonly_fields = ("decide_le",)


@admin.register(ExpressionBesoin)
class ExpressionBesoinAdmin(admin.ModelAdmin):
    list_display = ("numero", "objet", "perimetre", "demandeur", "montant", "statut")
    list_filter = ("statut", "perimetre")
    search_fields = ("numero", "objet", "justification")
    autocomplete_fields = ("perimetre", "activite", "structure", "demandeur")
    readonly_fields = ("numero", "soumis_le", "clos_le")
    inlines = [LigneInline, OffreInline, ValidationInline]

    @admin.display(description="montant estime")
    def montant(self, besoin):
        return f"{besoin.montant_estime:,.0f} FCFA".replace(",", " ")


@admin.register(BonCommande)
class BonCommandeAdmin(admin.ModelAdmin):
    list_display = ("numero", "fournisseur", "montant", "date_emission",
                    "date_reception", "statut")
    list_filter = ("statut", "fournisseur")
    search_fields = ("numero", "facture_numero", "besoin__objet")
    autocomplete_fields = ("besoin", "fournisseur")
    readonly_fields = ("numero",)


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ("code", "designation", "perimetre", "unite", "stock",
                    "seuil_alerte", "a_reapprovisionner", "actif")
    list_filter = ("perimetre", "actif")
    search_fields = ("code", "designation")
    autocomplete_fields = ("perimetre",)
    readonly_fields = ("stock",)

    @admin.display(boolean=True, description="sous seuil")
    def a_reapprovisionner(self, article):
        return article.sous_seuil


@admin.register(MouvementStock)
class MouvementStockAdmin(admin.ModelAdmin):
    list_display = ("date", "article", "type", "quantite", "stock_apres",
                    "beneficiaire", "saisi_par")
    list_filter = ("type", "article__perimetre", "date")
    search_fields = ("article__code", "article__designation", "motif", "beneficiaire")
    autocomplete_fields = ("article", "bon_commande")
    readonly_fields = ("stock_apres",)


@admin.register(Equipement)
class EquipementAdmin(admin.ModelAdmin):
    list_display = ("code_inventaire", "designation", "perimetre", "affecte_a",
                    "structure", "date_acquisition", "etat")
    list_filter = ("etat", "perimetre")
    search_fields = ("code_inventaire", "designation", "marque", "numero_serie")
    autocomplete_fields = ("perimetre", "structure", "affecte_a", "bon_commande")

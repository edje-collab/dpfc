from django import forms
from django.utils import timezone

from apps.core.models import Perimetre, Structure

from .models import (
    Article,
    Equipement,
    ExpressionBesoin,
    Fournisseur,
    LigneBesoin,
    MouvementStock,
    Offre,
)


class DateInput(forms.DateInput):
    input_type = "date"


class BesoinForm(forms.ModelForm):
    class Meta:
        model = ExpressionBesoin
        fields = ["objet", "justification", "activite", "structure", "date_souhaitee"]
        widgets = {
            "justification": forms.Textarea(attrs={"rows": 3}),
            "date_souhaitee": DateInput(),
            "objet": forms.TextInput(attrs={"placeholder": "Ex. Fournitures de bureau du trimestre"}),
        }
        help_texts = {
            "activite": "Rattache la depense au plan d'action : elle y sera reportee au paiement.",
            "justification": "Pourquoi cette depense est necessaire.",
        }

    def __init__(self, *args, perimetre=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.perimetre = perimetre or getattr(self.instance, "perimetre", None)
        for champ in ("activite", "structure", "date_souhaitee"):
            self.fields[champ].required = False
        if self.perimetre is not None:
            from apps.activites.models import Activite

            self.fields["activite"].queryset = Activite.objects.filter(
                plan__perimetre=self.perimetre
            )
            self.fields["structure"].queryset = Structure.objects.filter(
                perimetre=self.perimetre, active=True
            )

    def clean(self):
        donnees = super().clean()
        if self.perimetre is not None:
            self.instance.perimetre = self.perimetre
        return donnees


class LigneBesoinForm(forms.ModelForm):
    class Meta:
        model = LigneBesoin
        fields = ["article", "designation", "quantite", "unite", "prix_unitaire"]
        widgets = {
            "designation": forms.TextInput(attrs={"placeholder": "Designation de l'article"}),
        }
        help_texts = {
            "article": "Si l'article est tenu au magasin, la reception l'y fera entrer.",
            "prix_unitaire": "Prix estime, en francs CFA.",
        }

    def __init__(self, *args, besoin=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.besoin = besoin
        self.fields["article"].required = False
        self.fields["designation"].required = False
        if besoin is not None:
            self.fields["article"].queryset = Article.objects.filter(
                perimetre=besoin.perimetre, actif=True
            )

    def clean(self):
        donnees = super().clean()
        if self.besoin is not None:
            self.instance.besoin = self.besoin
        if not donnees.get("article") and not (donnees.get("designation") or "").strip():
            self.add_error("designation", "Indiquez la designation, ou choisissez un article.")
        return donnees


class OffreForm(forms.ModelForm):
    class Meta:
        model = Offre
        fields = ["fournisseur", "montant", "delai_jours", "fichier", "observations"]
        help_texts = {"montant": "Montant propose par le fournisseur, en francs CFA."}

    def __init__(self, *args, besoin=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.besoin = besoin
        for champ in ("delai_jours", "fichier", "observations"):
            self.fields[champ].required = False
        self.fields["fournisseur"].queryset = Fournisseur.objects.filter(actif=True)
        if besoin is not None:
            deja = besoin.offres.values_list("fournisseur_id", flat=True)
            self.fields["fournisseur"].queryset = self.fields["fournisseur"].queryset.exclude(
                pk__in=deja
            )

    def clean(self):
        donnees = super().clean()
        if self.besoin is not None:
            self.instance.besoin = self.besoin
        return donnees


class DecisionBesoinForm(forms.Form):
    commentaire = forms.CharField(
        label="Observation", required=False, widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Obligatoire en cas d'avis defavorable.",
    )


class ReceptionForm(forms.Form):
    observations = forms.CharField(
        label="Observations a la reception", required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
        help_text="Ecarts constates, etat des articles livres.",
    )


class FactureForm(forms.Form):
    numero = forms.CharField(label="Numero de facture", max_length=40)
    montant = forms.DecimalField(label="Montant facture (FCFA)", max_digits=14, decimal_places=0)
    fichier = forms.FileField(label="Facture", required=False)


class MotifForm(forms.Form):
    motif = forms.CharField(label="Motif", widget=forms.Textarea(attrs={"rows": 3}))


class ArticleForm(forms.ModelForm):
    class Meta:
        model = Article
        fields = ["code", "designation", "unite", "seuil_alerte"]
        widgets = {"code": forms.TextInput(attrs={"placeholder": "Ex. RAM-A4"})}
        help_texts = {
            "seuil_alerte": "En dessous ou a ce niveau, l'article est signale a reapprovisionner.",
        }

    def __init__(self, *args, perimetre=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.perimetre = perimetre or getattr(self.instance, "perimetre", None)

    def clean_code(self):
        code = self.cleaned_data["code"].strip().upper()
        existant = Article.objects.filter(perimetre=self.perimetre, code=code)
        if self.instance.pk:
            existant = existant.exclude(pk=self.instance.pk)
        if existant.exists():
            raise forms.ValidationError("Ce code est deja utilise dans votre magasin.")
        return code

    def clean(self):
        donnees = super().clean()
        if self.perimetre is not None:
            self.instance.perimetre = self.perimetre
        return donnees


class MouvementForm(forms.Form):
    """Entree, sortie ou inventaire sur un article."""

    type = forms.ChoiceField(label="Type de mouvement", choices=MouvementStock.Type.choices)
    quantite = forms.IntegerField(label="Quantite", min_value=1)
    date = forms.DateField(label="Date", widget=DateInput(), initial=timezone.localdate)
    motif = forms.CharField(label="Motif", required=False, max_length=200)
    beneficiaire = forms.CharField(
        label="Beneficiaire", required=False, max_length=150,
        help_text="Obligatoire pour une sortie : qui recoit les articles.",
    )

    def clean(self):
        donnees = super().clean()
        if donnees.get("type") == MouvementStock.Type.SORTIE:
            if not (donnees.get("beneficiaire") or "").strip():
                self.add_error("beneficiaire", "Indiquez le beneficiaire de la sortie.")
        if donnees.get("type") == MouvementStock.Type.INVENTAIRE:
            if not (donnees.get("motif") or "").strip():
                self.add_error("motif", "Indiquez les circonstances du comptage.")
        return donnees


class EquipementForm(forms.ModelForm):
    class Meta:
        model = Equipement
        fields = ["code_inventaire", "designation", "marque", "numero_serie",
                  "structure", "affecte_a", "date_acquisition", "valeur", "etat", "observations"]
        widgets = {
            "date_acquisition": DateInput(),
            "observations": forms.Textarea(attrs={"rows": 2}),
            "code_inventaire": forms.TextInput(attrs={"placeholder": "Ex. DPFC-ORD-001"}),
        }

    def __init__(self, *args, perimetre=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.perimetre = perimetre or getattr(self.instance, "perimetre", None)
        for champ in ("marque", "numero_serie", "structure", "affecte_a",
                      "date_acquisition", "observations"):
            self.fields[champ].required = False
        if self.perimetre is not None:
            self.fields["structure"].queryset = Structure.objects.filter(
                perimetre=self.perimetre, active=True
            )
            self.fields["affecte_a"].queryset = self.perimetre.agents()

    def clean(self):
        donnees = super().clean()
        if self.perimetre is not None:
            self.instance.perimetre = self.perimetre
        return donnees


class FiltreBesoinsForm(forms.Form):
    q = forms.CharField(
        label="Recherche", required=False,
        widget=forms.TextInput(attrs={"placeholder": "Numero, objet"}),
    )
    statut = forms.ChoiceField(
        label="Statut", required=False,
        choices=[("", "Tous les statuts")] + list(ExpressionBesoin.Statut.choices),
    )
    perimetre = forms.CharField(label="Perimetre", required=False, widget=forms.Select())

    def __init__(self, *args, agent=None, **kwargs):
        super().__init__(*args, **kwargs)
        if agent is not None and (agent.est_rh or agent.est_direction or agent.peut_administrer):
            self.fields["perimetre"].widget.choices = [("", "Tous les perimetres")] + [
                (p.code, p.nom) for p in Perimetre.objects.actifs()
            ]
        else:
            del self.fields["perimetre"]

from django import forms
from django.utils import timezone

from apps.accounts.models import Agent
from apps.core.models import Structure

from .models import Activite, Avancement, Indicateur, PlanAction


class DateInput(forms.DateInput):
    input_type = "date"


class PlanActionForm(forms.ModelForm):
    class Meta:
        model = PlanAction
        fields = ["annee", "libelle", "contexte"]
        widgets = {
            "contexte": forms.Textarea(attrs={"rows": 4}),
            "libelle": forms.TextInput(attrs={"placeholder": "Laisser vide pour un libelle automatique"}),
        }
        help_texts = {
            "contexte": "Orientations de l'exercice : priorites, cadrage budgetaire, consignes recues.",
        }

    def __init__(self, *args, perimetre=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.perimetre = perimetre
        self.fields["annee"].initial = timezone.localdate().year
        self.fields["libelle"].required = False

    def clean_annee(self):
        annee = self.cleaned_data["annee"]
        existant = PlanAction.objects.filter(perimetre=self.perimetre, annee=annee)
        if self.instance.pk:
            existant = existant.exclude(pk=self.instance.pk)
        if existant.exists():
            raise forms.ValidationError(
                f"Un plan d'action {annee} existe deja pour ce perimetre."
            )
        return annee


class ActiviteForm(forms.ModelForm):
    class Meta:
        model = Activite
        fields = [
            "intitule", "axe", "type", "description", "structure", "responsable",
            "date_debut_prevue", "date_fin_prevue", "lieu", "public_cible",
            "effectif_prevu", "budget_prevu", "source_financement",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "date_debut_prevue": DateInput(),
            "date_fin_prevue": DateInput(),
            "intitule": forms.TextInput(attrs={"placeholder": "Ex. Atelier de production des guides CM2"}),
            "public_cible": forms.TextInput(attrs={"placeholder": "Ex. Conseillers pedagogiques du primaire"}),
            "source_financement": forms.TextInput(attrs={"placeholder": "Ex. Budget de l'Etat, partenaire"}),
        }
        help_texts = {
            "effectif_prevu": "Nombre de beneficiaires attendus.",
            "budget_prevu": "En francs CFA. Laisser a zero si l'activite ne mobilise pas de credit.",
        }

    def __init__(self, *args, plan=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.plan = plan or getattr(self.instance, "plan", None)
        if self.plan is not None:
            perimetre = self.plan.perimetre
            self.fields["structure"].queryset = Structure.objects.filter(
                perimetre=perimetre, active=True
            )
            self.fields["responsable"].queryset = perimetre.agents()
            annee = self.plan.annee
            for champ in ("date_debut_prevue", "date_fin_prevue"):
                self.fields[champ].widget.attrs.update(
                    {"min": f"{annee}-01-01", "max": f"{annee}-12-31"}
                )
        self.fields["structure"].required = False
        self.fields["responsable"].required = False
        self.fields["axe"].required = False

    def clean(self):
        donnees = super().clean()
        if self.plan is not None:
            self.instance.plan = self.plan
        debut, fin = donnees.get("date_debut_prevue"), donnees.get("date_fin_prevue")
        if debut and fin and fin < debut:
            self.add_error("date_fin_prevue", "La fin prevue precede le debut prevu.")
        if debut and self.plan is not None and debut.year != self.plan.annee:
            self.add_error(
                "date_debut_prevue",
                f"L'activite doit demarrer dans l'annee du plan ({self.plan.annee}).",
            )
        return donnees


class AvancementForm(forms.ModelForm):
    class Meta:
        model = Avancement
        fields = ["date", "taux", "realisations", "difficultes", "effectif_touche",
                  "montant_engage", "piece_jointe"]
        widgets = {
            "date": DateInput(),
            "realisations": forms.Textarea(attrs={"rows": 3}),
            "difficultes": forms.Textarea(attrs={"rows": 2}),
            "taux": forms.NumberInput(attrs={"min": 0, "max": 100, "step": 5}),
        }
        labels = {"taux": "Avancement atteint (%)"}
        help_texts = {
            "taux": "Etat d'avancement de l'activite a ce jour, pas la progression de la periode.",
            "effectif_touche": "Beneficiaires touches sur cette periode seulement : le total se cumule.",
            "montant_engage": "Montant engage sur cette periode seulement : le total se cumule.",
        }

    def __init__(self, *args, activite=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.activite = activite
        self.fields["date"].initial = timezone.localdate()
        if activite is not None:
            self.fields["taux"].initial = activite.avancement

    def clean_taux(self):
        taux = self.cleaned_data["taux"]
        if taux > 100:
            raise forms.ValidationError("L'avancement ne peut depasser 100 %.")
        return taux


class DecisionPlanForm(forms.Form):
    """Validation ou renvoi d'un plan soumis."""

    motif = forms.CharField(
        label="Motif du renvoi",
        required=False,
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Obligatoire en cas de renvoi"}),
    )


class ReportForm(forms.Form):
    motif = forms.CharField(label="Motif", widget=forms.Textarea(attrs={"rows": 3}))
    nouvelle_fin = forms.DateField(
        label="Nouvelle echeance", required=False, widget=DateInput(),
        help_text="Laisser vide pour conserver l'echeance actuelle.",
    )


class IndicateurForm(forms.ModelForm):
    class Meta:
        model = Indicateur
        fields = ["libelle", "unite", "valeur_cible", "valeur_realisee", "commentaire"]
        widgets = {"commentaire": forms.Textarea(attrs={"rows": 2})}


class FiltreActivitesForm(forms.Form):
    """Filtres du registre des activites."""

    q = forms.CharField(label="Recherche", required=False,
                        widget=forms.TextInput(attrs={"placeholder": "Intitule, lieu, code"}))
    axe = forms.CharField(label="Axe", required=False, widget=forms.Select())
    statut = forms.ChoiceField(
        label="Statut", required=False,
        choices=[("", "Tous les statuts")] + list(Activite.Statut.choices),
    )
    perimetre = forms.CharField(label="Perimetre", required=False, widget=forms.Select())
    retard = forms.BooleanField(label="En retard uniquement", required=False)

    def __init__(self, *args, agent=None, **kwargs):
        super().__init__(*args, **kwargs)
        from .models import Axe

        self.fields["axe"].widget.choices = [("", "Tous les axes")] + [
            (a.code, f"{a.code} - {a.libelle}") for a in Axe.objects.filter(actif=True)
        ]
        voit_tout = agent is not None and (
            agent.est_rh or agent.est_direction or agent.peut_administrer
        )
        if voit_tout:
            from apps.core.models import Perimetre

            self.fields["perimetre"].widget.choices = [("", "Tous les perimetres")] + [
                (p.code, p.nom) for p in Perimetre.objects.actifs()
            ]
        else:
            del self.fields["perimetre"]


__all__ = [
    "ActiviteForm", "Agent", "AvancementForm", "DecisionPlanForm", "FiltreActivitesForm",
    "IndicateurForm", "PlanActionForm", "ReportForm",
]

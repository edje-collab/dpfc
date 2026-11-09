from django import forms
from django.utils import timezone

from apps.core.models import Perimetre, Structure

from .models import Courrier, Document, Imputation, ModeleDocument, PieceParapheur, TypeDocument


class DateInput(forms.DateInput):
    input_type = "date"


class CourrierForm(forms.ModelForm):
    class Meta:
        model = Courrier
        fields = [
            "sens", "nature", "correspondant", "structure_correspondante", "objet",
            "reference_expediteur", "date_courrier", "date_enregistrement", "resume",
            "courrier_lie", "activite", "confidentiel",
        ]
        widgets = {
            "date_courrier": DateInput(),
            "date_enregistrement": DateInput(),
            "resume": forms.Textarea(attrs={"rows": 3}),
            "correspondant": forms.TextInput(attrs={"placeholder": "Ex. Cabinet du Ministre, DRENA de Bouake"}),
            "objet": forms.TextInput(attrs={"placeholder": "Objet du courrier"}),
            "reference_expediteur": forms.TextInput(attrs={"placeholder": "Ex. 0245/MENAET/CAB"}),
        }
        help_texts = {
            "courrier_lie": "A renseigner lorsque ce courrier repond a un courrier deja enregistre.",
            "confidentiel": "Limite l'acces a l'enregistreur, aux imputataires et au responsable du perimetre.",
        }

    def __init__(self, *args, perimetre=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.perimetre = perimetre or getattr(self.instance, "perimetre", None)
        for champ in ("structure_correspondante", "courrier_lie", "activite"):
            self.fields[champ].required = False
        if self.perimetre is not None:
            self.fields["courrier_lie"].queryset = Courrier.objects.filter(
                perimetre=self.perimetre
            ).order_by("-date_enregistrement")[:200]
            from apps.activites.models import Activite

            self.fields["activite"].queryset = Activite.objects.filter(
                plan__perimetre=self.perimetre
            )
        self.fields["structure_correspondante"].queryset = Structure.objects.filter(active=True)
        self.fields["date_courrier"].initial = timezone.localdate()
        self.fields["date_enregistrement"].initial = timezone.localdate()

    def clean(self):
        donnees = super().clean()
        if self.perimetre is not None:
            self.instance.perimetre = self.perimetre
        courrier, enregistrement = donnees.get("date_courrier"), donnees.get("date_enregistrement")
        if courrier and enregistrement and enregistrement < courrier:
            self.add_error(
                "date_enregistrement", "Un courrier ne peut etre enregistre avant sa date."
            )
        return donnees


class ImputationForm(forms.Form):
    """Imputation d'un courrier a un ou plusieurs agents, avec instructions."""

    destinataires = forms.ModelMultipleChoiceField(
        label="Imputer a", queryset=None, widget=forms.CheckboxSelectMultiple
    )
    instructions = forms.CharField(
        label="Instructions", widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Suite a donner au courrier.",
    )
    delai = forms.DateField(label="Delai de traitement", widget=DateInput())
    pour_information = forms.BooleanField(
        label="Pour information seulement", required=False,
        help_text="L'imputation est close des sa creation : elle n'appelle pas de suite.",
    )

    def __init__(self, *args, courrier=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.courrier = courrier
        deja = (
            courrier.imputations.values_list("destinataire_id", flat=True) if courrier else []
        )
        candidats = courrier.perimetre.agents() if courrier else None
        self.fields["destinataires"].queryset = (
            candidats.exclude(pk__in=deja) if candidats is not None else None
        )
        self.fields["delai"].initial = timezone.localdate() + timezone.timedelta(days=7)

    def clean_delai(self):
        delai = self.cleaned_data["delai"]
        if delai < timezone.localdate():
            raise forms.ValidationError("Le delai de traitement est deja passe.")
        return delai


class CompteRenduForm(forms.ModelForm):
    class Meta:
        model = Imputation
        fields = ["compte_rendu"]
        widgets = {"compte_rendu": forms.Textarea(attrs={"rows": 4})}
        labels = {"compte_rendu": "Suite donnee"}
        help_texts = {"compte_rendu": "Ce que vous avez fait du courrier, et ce qu'il en resulte."}


class ClassementForm(forms.Form):
    motif = forms.CharField(label="Motif du classement", widget=forms.Textarea(attrs={"rows": 3}))


class DocumentForm(forms.ModelForm):
    fichier = forms.FileField(label="Fichier", required=True)
    commentaire_version = forms.CharField(
        label="Commentaire de version", required=False, max_length=200
    )

    class Meta:
        model = Document
        fields = ["titre", "type_document", "annee", "description", "courrier", "activite",
                  "acces", "partage"]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}
        help_texts = {
            "partage": "Rend le document consultable par les autres perimetres.",
            "acces": "« Acces restreint » limite la consultation au deposant et aux agents autorises.",
        }

    def __init__(self, *args, perimetre=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.perimetre = perimetre or getattr(self.instance, "perimetre", None)
        for champ in ("courrier", "activite"):
            self.fields[champ].required = False
        if self.perimetre is not None:
            self.fields["courrier"].queryset = Courrier.objects.filter(perimetre=self.perimetre)
            from apps.activites.models import Activite

            self.fields["activite"].queryset = Activite.objects.filter(
                plan__perimetre=self.perimetre
            )
        self.fields["annee"].initial = timezone.localdate().year
        if self.instance.pk:
            self.fields["fichier"].required = False
            self.fields["fichier"].label = "Nouvelle version (facultatif)"

    def clean(self):
        donnees = super().clean()
        if self.perimetre is not None:
            self.instance.perimetre = self.perimetre
        return donnees


class VersionForm(forms.Form):
    fichier = forms.FileField(label="Nouveau fichier")
    commentaire = forms.CharField(
        label="Commentaire de version", required=False, max_length=200,
        widget=forms.TextInput(attrs={"placeholder": "Ex. Corrections apres relecture"}),
    )


class PieceParapheurForm(forms.ModelForm):
    class Meta:
        model = PieceParapheur
        fields = ["objet", "document", "courrier", "note"]
        widgets = {
            "note": forms.Textarea(attrs={"rows": 3}),
            "objet": forms.TextInput(attrs={"placeholder": "Objet de la piece a viser"}),
        }
        help_texts = {"note": "Ce que les viseurs doivent savoir avant de se prononcer."}

    def __init__(self, *args, perimetre=None, agent=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.perimetre = perimetre
        self.fields["courrier"].required = False
        if perimetre is not None:
            self.fields["document"].queryset = Document.objects.filter(perimetre=perimetre)
            self.fields["courrier"].queryset = Courrier.objects.filter(perimetre=perimetre)

    def clean(self):
        donnees = super().clean()
        if self.perimetre is not None:
            self.instance.perimetre = self.perimetre
        return donnees


class VisaForm(forms.Form):
    observation = forms.CharField(
        label="Observation", required=False, widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Obligatoire en cas de refus.",
    )


class FiltreCourrierForm(forms.Form):
    q = forms.CharField(
        label="Recherche", required=False,
        widget=forms.TextInput(attrs={"placeholder": "Numero, objet, correspondant"}),
    )
    sens = forms.ChoiceField(
        label="Sens", required=False,
        choices=[("", "Arrivee et depart")] + list(Courrier.Sens.choices),
    )
    statut = forms.ChoiceField(
        label="Statut", required=False,
        choices=[("", "Tous les statuts")] + list(Courrier.Statut.choices),
    )
    annee = forms.IntegerField(label="Annee", required=False)
    retard = forms.BooleanField(label="En retard uniquement", required=False)
    perimetre = forms.CharField(label="Perimetre", required=False, widget=forms.Select())

    def __init__(self, *args, agent=None, **kwargs):
        super().__init__(*args, **kwargs)
        if agent is not None and (agent.est_rh or agent.est_direction or agent.peut_administrer):
            self.fields["perimetre"].widget.choices = [("", "Tous les perimetres")] + [
                (p.code, p.nom) for p in Perimetre.objects.actifs()
            ]
        else:
            del self.fields["perimetre"]


class FiltreDocumentForm(forms.Form):
    q = forms.CharField(
        label="Recherche plein texte", required=False,
        widget=forms.TextInput(attrs={"placeholder": "Mot du titre ou du contenu"}),
    )
    type_document = forms.ChoiceField(
        label="Type", required=False,
        choices=[("", "Tous les types")] + list(TypeDocument.choices),
    )
    annee = forms.IntegerField(label="Annee", required=False)
    perimetre = forms.CharField(label="Perimetre", required=False, widget=forms.Select())

    def __init__(self, *args, agent=None, **kwargs):
        super().__init__(*args, **kwargs)
        if agent is not None and (agent.est_rh or agent.est_direction or agent.peut_administrer):
            self.fields["perimetre"].widget.choices = [("", "Tous les perimetres")] + [
                (p.code, p.nom) for p in Perimetre.objects.actifs()
            ]
        else:
            del self.fields["perimetre"]


class ModeleForm(forms.Form):
    """Redaction d'un courrier depart a partir d'un modele."""

    modele = forms.ModelChoiceField(
        label="Modele", queryset=ModeleDocument.objects.filter(actif=True), required=True
    )

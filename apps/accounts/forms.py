from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from .models import Agent


class ConnexionForm(AuthenticationForm):
    username = forms.CharField(
        label="Matricule ou courriel",
        widget=forms.TextInput(attrs={"autofocus": True, "placeholder": "Ex. 334446X", "autocomplete": "username"}),
    )
    password = forms.CharField(
        label="Mot de passe",
        widget=forms.PasswordInput(attrs={"placeholder": "Votre mot de passe", "autocomplete": "current-password"}),
    )
    error_messages = {
        "invalid_login": "Matricule ou mot de passe incorrect. Verifiez vos identifiants.",
        "inactive": "Ce compte est desactive. Contactez le service du personnel de la DPFC.",
    }


class ProfilForm(forms.ModelForm):
    """Champs qu'un agent peut modifier lui-meme."""

    class Meta:
        model = Agent
        fields = ["first_name", "last_name", "email", "telephone", "photo", "date_naissance"]
        widgets = {
            "date_naissance": forms.DateInput(attrs={"type": "date"}),
            "telephone": forms.TextInput(attrs={"placeholder": "+225 07 00 00 00 00"}),
        }


class AgentForm(forms.ModelForm):
    """Creation / modification d'un compte agent par le service du personnel."""

    mot_de_passe_initial = forms.CharField(
        label="Mot de passe initial",
        required=False,
        widget=forms.PasswordInput(render_value=False),
        help_text="Laisser vide pour conserver le mot de passe actuel. A la creation, le matricule est utilise si le champ est vide.",
    )

    class Meta:
        model = Agent
        fields = [
            "matricule", "civilite", "last_name", "first_name", "email", "telephone",
            "structure", "fonction", "grade", "role", "superieur", "situation",
            "date_prise_service", "lieu_service", "is_active",
        ]
        widgets = {"date_prise_service": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["superieur"].queryset = Agent.objects.filter(is_active=True).exclude(
            pk=self.instance.pk or 0
        )
        self.fields["structure"].required = True

    def clean_matricule(self):
        return self.cleaned_data["matricule"].strip().upper()

    def save(self, commit=True):
        agent = super().save(commit=False)
        mdp = self.cleaned_data.get("mot_de_passe_initial")
        if mdp:
            agent.set_password(mdp)
            agent.doit_changer_mot_de_passe = True
        elif not agent.pk:
            agent.set_password(agent.matricule)
            agent.doit_changer_mot_de_passe = True
        if commit:
            agent.save()
        return agent


class AgentCreationAdminForm(UserCreationForm):
    class Meta:
        model = Agent
        fields = ("matricule", "last_name", "first_name", "email", "structure", "role")


class ImportAgentsForm(forms.Form):
    fichier = forms.FileField(
        label="Fichier des agents",
        help_text="Classeur Excel (.xlsx) ou fichier CSV. Utilisez le modele pour garantir l'en-tete.",
    )

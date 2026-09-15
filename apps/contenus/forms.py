from django import forms

from apps.core.models import Structure

from .models import MessageContact


class ContactForm(forms.ModelForm):
    # Champ piege anti-robot
    site_web = forms.CharField(required=False, widget=forms.HiddenInput)

    class Meta:
        model = MessageContact
        fields = ["nom", "email", "telephone", "structure_destinataire", "sujet", "message"]
        widgets = {
            "message": forms.Textarea(attrs={"rows": 6}),
            "nom": forms.TextInput(attrs={"placeholder": "Nom et prenoms"}),
            "email": forms.EmailInput(attrs={"placeholder": "vous@exemple.ci"}),
            "telephone": forms.TextInput(attrs={"placeholder": "+225 ..."}),
            "sujet": forms.TextInput(attrs={"placeholder": "Objet de votre message"}),
        }
        labels = {"structure_destinataire": "Service ou antenne concerne"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["structure_destinataire"].queryset = Structure.objects.filter(active=True)
        self.fields["structure_destinataire"].required = False
        self.fields["structure_destinataire"].empty_label = "Direction de la Pedagogie (general)"

    def clean_site_web(self):
        if self.cleaned_data.get("site_web"):
            raise forms.ValidationError("Envoi refuse.")
        return ""

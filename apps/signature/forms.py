from django import forms


class CreationCleForm(forms.Form):
    code = forms.CharField(
        label="Code de signature",
        widget=forms.PasswordInput,
        min_length=6,
        help_text="Au moins 6 caracteres. Ce code chiffre votre cle privee : il n'est jamais "
                  "conserve par le portail et ne peut pas etre retrouve.",
    )
    confirmation = forms.CharField(label="Confirmer le code", widget=forms.PasswordInput)
    engagement = forms.BooleanField(
        label="Je reconnais que ce code vaut signature et m'engage a ne pas le communiquer.",
    )

    def clean(self):
        donnees = super().clean()
        if donnees.get("code") and donnees.get("code") != donnees.get("confirmation"):
            self.add_error("confirmation", "Les deux codes ne correspondent pas.")
        return donnees


class RevocationForm(forms.Form):
    motif = forms.CharField(label="Motif de la revocation", max_length=200)


class VerificationForm(forms.Form):
    code = forms.CharField(
        label="Code de verification",
        max_length=24,
        widget=forms.TextInput(attrs={"placeholder": "DPFC-XXXX-XXXX-XXXX"}),
    )

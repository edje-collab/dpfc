from django import forms
from django.utils import timezone

from apps.core.models import Perimetre, Structure

from .models import Atelier, Bareme, CompteRendu, Participant, Session


class DateInput(forms.DateInput):
    input_type = "date"


class AtelierForm(forms.ModelForm):
    creneaux_par_jour = forms.ChoiceField(
        label="Decoupage des sessions",
        choices=[(1, "Une session par journee"), (2, "Matinee et apres-midi")],
        initial=1,
        help_text="Le decoupage par demi-journees permet de constater les presences partielles.",
    )

    class Meta:
        model = Atelier
        fields = ["intitule", "type", "activite", "lieu", "structure_hote",
                  "date_debut", "date_fin", "public_cible", "budget", "ordre_du_jour",
                  "organisateur", "controleurs"]
        widgets = {
            "date_debut": DateInput(),
            "date_fin": DateInput(),
            "ordre_du_jour": forms.Textarea(attrs={"rows": 4}),
            "controleurs": forms.CheckboxSelectMultiple,
            "intitule": forms.TextInput(attrs={"placeholder": "Ex. Atelier de production des guides CM2"}),
        }
        help_texts = {
            "activite": "Rattache l'atelier au plan d'action : les presences y seront reportees.",
            "controleurs": "Agents habilites a scanner les QR codes sur le terrain.",
        }

    def __init__(self, *args, perimetre=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.perimetre = perimetre or getattr(self.instance, "perimetre", None)
        for champ in ("activite", "structure_hote", "organisateur", "controleurs"):
            self.fields[champ].required = False
        if self.perimetre is not None:
            from apps.activites.models import Activite

            self.fields["activite"].queryset = Activite.objects.filter(
                plan__perimetre=self.perimetre
            )
            self.fields["organisateur"].queryset = self.perimetre.agents()
            self.fields["controleurs"].queryset = self.perimetre.agents()
            self.fields["structure_hote"].queryset = Structure.objects.filter(active=True)
        self.fields["date_debut"].initial = timezone.localdate()
        self.fields["date_fin"].initial = timezone.localdate()
        if self.instance.pk:
            del self.fields["creneaux_par_jour"]

    def clean(self):
        donnees = super().clean()
        if self.perimetre is not None:
            self.instance.perimetre = self.perimetre
        debut, fin = donnees.get("date_debut"), donnees.get("date_fin")
        if debut and fin and fin < debut:
            self.add_error("date_fin", "La fin precede le debut.")
        if debut and fin and (fin - debut).days > 30:
            self.add_error("date_fin", "Un atelier ne peut exceder trente jours.")
        return donnees


class ParticipantForm(forms.ModelForm):
    class Meta:
        model = Participant
        fields = ["agent", "nom", "prenoms", "fonction", "structure_origine",
                  "telephone", "email", "categorie", "provenance"]
        widgets = {
            "nom": forms.TextInput(attrs={"placeholder": "Nom de famille"}),
            "prenoms": forms.TextInput(attrs={"placeholder": "Prenoms"}),
            "telephone": forms.TextInput(attrs={"placeholder": "+225 ..."}),
        }
        help_texts = {
            "agent": "Pour un agent de la direction : l'identite est reprise automatiquement.",
            "categorie": "Determine le montant journalier de l'etat de paiement.",
        }

    def __init__(self, *args, atelier=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.atelier = atelier or getattr(self.instance, "atelier", None)
        for champ in ("agent", "prenoms", "fonction", "structure_origine",
                      "telephone", "email", "categorie", "provenance"):
            self.fields[champ].required = False
        self.fields["nom"].required = False
        self.fields["categorie"].queryset = Bareme.objects.filter(actif=True)

    def clean(self):
        donnees = super().clean()
        if self.atelier is not None:
            self.instance.atelier = self.atelier
        if not donnees.get("agent") and not (donnees.get("nom") or "").strip():
            self.add_error("nom", "Indiquez le nom, ou choisissez un agent du portail.")
        return donnees


class ImportParticipantsForm(forms.Form):
    """Inscription groupee des agents d'une structure."""

    structure = forms.ModelChoiceField(
        label="Inscrire tous les agents de", queryset=Structure.objects.none(),
    )
    categorie = forms.ModelChoiceField(
        label="Categorie de barème", queryset=Bareme.objects.none(), required=False,
    )

    def __init__(self, *args, perimetre=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["structure"].queryset = (
            Structure.objects.filter(perimetre=perimetre, active=True)
            if perimetre is not None
            else Structure.objects.filter(active=True)
        )
        self.fields["categorie"].queryset = Bareme.objects.filter(actif=True)


class SessionForm(forms.ModelForm):
    class Meta:
        model = Session
        fields = ["date", "creneau", "libelle"]
        widgets = {"date": DateInput()}

    def __init__(self, *args, atelier=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.atelier = atelier
        self.fields["libelle"].required = False
        if atelier is not None:
            self.fields["date"].widget.attrs.update(
                {"min": atelier.date_debut.isoformat(), "max": atelier.date_fin.isoformat()}
            )

    def clean(self):
        donnees = super().clean()
        if self.atelier is not None:
            self.instance.atelier = self.atelier
            date = donnees.get("date")
            if date and not (self.atelier.date_debut <= date <= self.atelier.date_fin):
                self.add_error("date", "La session doit tomber dans les dates de l'atelier.")
        return donnees


class ScanForm(forms.Form):
    """Saisie d'un jeton, au scanner ou au clavier."""

    jeton = forms.CharField(
        label="Jeton du participant",
        widget=forms.TextInput(attrs={"autofocus": "autofocus", "autocomplete": "off",
                                      "placeholder": "DPFC1.XXXX.YYYY.ZZZZ"}),
        help_text="Scannez le QR code, ou saisissez le jeton imprime sous le code.",
    )


class EmargementManuelForm(forms.Form):
    participant = forms.ModelChoiceField(label="Participant", queryset=Participant.objects.none())
    motif = forms.CharField(
        label="Motif de la saisie manuelle",
        widget=forms.Textarea(attrs={"rows": 2}),
        help_text="Pourquoi le QR code n'a-t-il pas pu etre scanne ?",
    )

    def __init__(self, *args, session=None, **kwargs):
        super().__init__(*args, **kwargs)
        if session is not None:
            deja = session.emargements.values_list("participant_id", flat=True)
            self.fields["participant"].queryset = (
                session.atelier.participants.exclude(pk__in=deja)
                .exclude(statut=Participant.Statut.REVOQUE)
            )


class MotifForm(forms.Form):
    motif = forms.CharField(label="Motif", widget=forms.Textarea(attrs={"rows": 3}))


class CompteRenduForm(forms.ModelForm):
    class Meta:
        model = CompteRendu
        fields = ["contenu", "decisions", "recommandations", "fichier"]
        widgets = {
            "contenu": forms.Textarea(attrs={"rows": 6}),
            "decisions": forms.Textarea(attrs={"rows": 4}),
            "recommandations": forms.Textarea(attrs={"rows": 3}),
        }


class FiltreAteliersForm(forms.Form):
    q = forms.CharField(
        label="Recherche", required=False,
        widget=forms.TextInput(attrs={"placeholder": "Intitule, lieu"}),
    )
    statut = forms.ChoiceField(
        label="Statut", required=False,
        choices=[("", "Tous les statuts")] + list(Atelier.Statut.choices),
    )
    type = forms.ChoiceField(
        label="Type", required=False,
        choices=[("", "Tous les types")] + list(Atelier.Type.choices),
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

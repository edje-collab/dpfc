from django import forms
from django.contrib.auth import get_user_model

from .models import Demande, JourFerie, RapportMission, SoldeConge, TypeDemande

Agent = get_user_model()

CHAMPS_COMMUNS = ["motif", "date_debut", "date_fin", "interimaire", "justificatif"]
CHAMPS_PAR_TYPE = {
    TypeDemande.CONGE_ANNUEL: ["lieu_jouissance", "contact_pendant_absence"],
    TypeDemande.CONGE_EXCEPTIONNEL: ["lieu_jouissance", "contact_pendant_absence"],
    TypeDemande.PERMISSION: ["heure_debut", "heure_fin", "contact_pendant_absence"],
    TypeDemande.ORDRE_MISSION: [
        "destination", "region_mission", "moyen_transport", "structures_visitees", "accompagnants",
        "hors_perimetre_drenaet", "termes_de_reference", "lettre_invitation",
    ],
    TypeDemande.ABSENCE: ["contact_pendant_absence"],
    TypeDemande.FORMATION: ["destination", "structures_visitees"],
}

AIDE_PAR_TYPE = {
    TypeDemande.CONGE_ANNUEL: "Conge decompte de votre solde annuel. Prevenez au moins 15 jours a l'avance.",
    TypeDemande.CONGE_EXCEPTIONNEL: "Evenement familial ou motif grave. Joignez la piece justificative.",
    TypeDemande.PERMISSION: "Absence courte, de quelques heures a cinq jours ouvrables.",
    TypeDemande.ORDRE_MISSION: (
        "Deplacement professionnel. Un rapport sera attendu au retour. Si la mission sort du "
        "perimetre de la DRENAET, joignez les termes de reference et la lettre d'invitation : "
        "l'ordre de mission est alors etabli par le DRENAET."
    ),
    TypeDemande.ABSENCE: "Declaration d'une absence deja survenue, avec justificatif.",
    TypeDemande.FORMATION: "Participation a une formation, un atelier ou un seminaire.",
}


class DemandeForm(forms.ModelForm):
    """
    Formulaire d'un acte. Le secretariat d'antenne peut deposer la demande au nom
    d'un agent de l'antenne : le champ « agent concerne » apparait alors.
    """

    agent_concerne = forms.ModelChoiceField(
        label="Agent concerne",
        queryset=Agent.objects.none(),
        required=False,
        help_text="Depot effectue au secretariat pour le compte de cet agent.",
    )

    class Meta:
        model = Demande
        fields = CHAMPS_COMMUNS + sorted({c for v in CHAMPS_PAR_TYPE.values() for c in v})
        widgets = {
            "date_debut": forms.DateInput(attrs={"type": "date"}),
            "date_fin": forms.DateInput(attrs={"type": "date"}),
            "heure_debut": forms.TimeInput(attrs={"type": "time"}),
            "heure_fin": forms.TimeInput(attrs={"type": "time"}),
            "motif": forms.Textarea(attrs={"rows": 4, "placeholder": "Exposez le motif de votre demande."}),
            "structures_visitees": forms.TextInput(attrs={"placeholder": "Ex. DRENA Bouake 1, IEPP Sakassou"}),
            "destination": forms.TextInput(attrs={"placeholder": "Ex. Korhogo"}),
            "moyen_transport": forms.TextInput(attrs={"placeholder": "Ex. Vehicule de service"}),
        }

    def __init__(self, *args, type_acte=None, agent=None, depot_pour_autrui=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.type_acte = type_acte or (self.instance.type if self.instance.pk else TypeDemande.CONGE_ANNUEL)
        self.agent = agent
        self.depot_pour_autrui = depot_pour_autrui
        autorises = CHAMPS_COMMUNS + CHAMPS_PAR_TYPE.get(self.type_acte, [])
        if depot_pour_autrui:
            autorises = ["agent_concerne"] + autorises
        for nom in list(self.fields):
            if nom not in autorises:
                self.fields.pop(nom)
        if depot_pour_autrui and agent is not None:
            self.fields["agent_concerne"].queryset = agent.agents_de_mon_antenne()
            self.fields["agent_concerne"].required = True
            self.fields["agent_concerne"].empty_label = "Choisir l'agent"
        if "interimaire" in self.fields and agent is not None:
            qs = Agent.objects.filter(is_active=True).exclude(pk=agent.pk)
            if agent.structure_id:
                qs = qs.filter(structure=agent.structure) | qs.filter(structure__parent=agent.structure)
            self.fields["interimaire"].queryset = qs.distinct()
            self.fields["interimaire"].required = False
            self.fields["interimaire"].empty_label = "Aucun interim designe"
        for nom in ("termes_de_reference", "lettre_invitation"):
            if nom in self.fields:
                self.fields[nom].required = False
        if "justificatif" in self.fields:
            from .models import REGLES_TYPE

            self.fields["justificatif"].required = False
            if REGLES_TYPE[self.type_acte]["justificatif"]:
                self.fields["justificatif"].help_text = "Piece obligatoire avant soumission."

    def clean(self):
        donnees = super().clean()
        self.instance.type = self.type_acte
        beneficiaire = donnees.get("agent_concerne") if self.depot_pour_autrui else None
        if beneficiaire is not None:
            self.instance.agent = beneficiaire
        elif self.agent is not None and not self.instance.agent_id:
            self.instance.agent = self.agent
        if self.type_acte == TypeDemande.ORDRE_MISSION and donnees.get("hors_perimetre_drenaet"):
            if not (donnees.get("termes_de_reference") or self.instance.termes_de_reference):
                self.add_error(
                    "termes_de_reference",
                    "Mission hors perimetre DRENAET : joignez les termes de reference.",
                )
            if not (donnees.get("lettre_invitation") or self.instance.lettre_invitation):
                self.add_error(
                    "lettre_invitation",
                    "Mission hors perimetre DRENAET : joignez la lettre d'invitation ou d'information.",
                )
        return donnees

    def save(self, commit=True):
        demande = super().save(commit=False)
        demande.type = self.type_acte
        beneficiaire = self.cleaned_data.get("agent_concerne") if self.depot_pour_autrui else None
        if beneficiaire is not None:
            demande.agent = beneficiaire
            demande.depose_par = self.agent
        elif self.agent is not None and not demande.agent_id:
            demande.agent = self.agent
        demande.structure = demande.agent.structure if demande.agent_id else demande.structure
        if commit:
            demande.save()
        return demande


class DecisionForm(forms.Form):
    DECISIONS = (("FAVORABLE", "Donner un avis favorable"), ("DEFAVORABLE", "Rejeter la demande"))
    decision = forms.ChoiceField(choices=DECISIONS, widget=forms.RadioSelect, label="Votre decision")
    commentaire = forms.CharField(
        label="Observation",
        required=False,
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Observation portee au dossier (obligatoire en cas de rejet)."}),
    )
    code_signature = forms.CharField(
        label="Code de signature electronique",
        required=False,
        widget=forms.PasswordInput(render_value=False),
        help_text="Saisissez votre code pour apposer votre signature electronique sur l'acte.",
    )

    def __init__(self, *args, signature_requise=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.signature_requise = signature_requise
        if signature_requise:
            self.fields["code_signature"].help_text = (
                "Etape de signature : votre code appose la signature electronique sur l'acte."
            )

    def clean(self):
        donnees = super().clean()
        if donnees.get("decision") == "DEFAVORABLE" and not donnees.get("commentaire", "").strip():
            self.add_error("commentaire", "Precisez le motif du rejet.")
        if (
            self.signature_requise
            and donnees.get("decision") == "FAVORABLE"
            and not donnees.get("code_signature")
        ):
            self.add_error("code_signature", "Le code de signature est requis pour signer cet acte.")
        return donnees


class RapportMissionForm(forms.ModelForm):
    class Meta:
        model = RapportMission
        fields = ["resume", "resultats", "difficultes", "recommandations", "fichier"]
        widgets = {
            "resume": forms.Textarea(attrs={"rows": 5}),
            "resultats": forms.Textarea(attrs={"rows": 4}),
            "difficultes": forms.Textarea(attrs={"rows": 3}),
            "recommandations": forms.Textarea(attrs={"rows": 3}),
        }


class SoldeForm(forms.ModelForm):
    class Meta:
        model = SoldeConge
        fields = ["agent", "annee", "droit_jours", "jours_reportes", "jours_consommes"]


class JourFerieForm(forms.ModelForm):
    class Meta:
        model = JourFerie
        fields = ["date", "libelle"]
        widgets = {"date": forms.DateInput(attrs={"type": "date"})}


class FiltreRegistreForm(forms.Form):
    q = forms.CharField(label="Recherche", required=False)
    type = forms.ChoiceField(
        label="Type d'acte", required=False, choices=[("", "Tous les actes")] + list(TypeDemande.choices)
    )
    statut = forms.ChoiceField(
        label="Statut", required=False, choices=[("", "Tous les statuts")] + list(Demande.Statut.choices)
    )
    rattachement = forms.ChoiceField(
        label="Affectation",
        required=False,
        choices=[("", "Toutes"), ("CENTRALE", "Direction centrale"), ("REGION", "Antennes regionales")],
    )
    du = forms.DateField(label="Du", required=False, widget=forms.DateInput(attrs={"type": "date"}))
    au = forms.DateField(label="Au", required=False, widget=forms.DateInput(attrs={"type": "date"}))

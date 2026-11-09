from django.contrib.auth import get_user_model
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from apps.accounts.models import Notification
from apps.activites.models import Activite, Avancement, PlanAction
from apps.core.models import Structure
from apps.courrier.models import Courrier, Document, Imputation
from apps.rh.models import Demande, RapportMission, SoldeConge, Validation
from apps.site_public.models import PageActualite, PageEvenement, PageProjet, Ressource

Agent = get_user_model()


class StructureSerializer(serializers.ModelSerializer):
    region = serializers.StringRelatedField()

    class Meta:
        model = Structure
        fields = ["id", "nom", "sigle", "slug", "type", "rattachement", "region", "telephone", "email"]


class AgentSerializer(serializers.ModelSerializer):
    nom_complet = serializers.CharField(read_only=True)
    structure = StructureSerializer(read_only=True)
    affectation = serializers.CharField(read_only=True)
    role_libelle = serializers.CharField(source="get_role_display", read_only=True)
    photo = serializers.ImageField(read_only=True)

    class Meta:
        model = Agent
        fields = [
            "id", "matricule", "civilite", "last_name", "first_name", "nom_complet", "email",
            "telephone", "photo", "fonction", "grade", "role", "role_libelle", "situation",
            "structure", "affectation", "doit_changer_mot_de_passe",
        ]
        read_only_fields = ["matricule", "role", "structure", "situation"]


class ConnexionSerializer(TokenObtainPairSerializer):
    """Ajoute le profil de l'agent a la reponse de connexion."""

    username_field = "matricule"

    def validate(self, attrs):
        donnees = super().validate(attrs)
        donnees["agent"] = AgentSerializer(self.user, context=self.context).data
        return donnees


class SoldeSerializer(serializers.ModelSerializer):
    jours_restants = serializers.IntegerField(read_only=True)
    total_droits = serializers.IntegerField(read_only=True)

    class Meta:
        model = SoldeConge
        fields = ["annee", "droit_jours", "jours_reportes", "jours_consommes", "jours_restants", "total_droits"]


class ValidationSerializer(serializers.ModelSerializer):
    valideur = serializers.CharField(source="valideur.nom_complet", read_only=True)
    fonction_valideur = serializers.CharField(source="valideur.fonction", read_only=True)
    decision_libelle = serializers.CharField(source="get_decision_display", read_only=True)

    class Meta:
        model = Validation
        fields = ["ordre", "libelle", "valideur", "fonction_valideur", "decision", "decision_libelle",
                  "commentaire", "decide_le"]


class DemandeSerializer(serializers.ModelSerializer):
    agent_nom = serializers.CharField(source="agent.nom_complet", read_only=True)
    agent_matricule = serializers.CharField(source="agent.matricule", read_only=True)
    type_libelle = serializers.CharField(source="get_type_display", read_only=True)
    statut_libelle = serializers.CharField(source="get_statut_display", read_only=True)
    validations = ValidationSerializer(many=True, read_only=True)
    progression = serializers.IntegerField(read_only=True)
    est_modifiable = serializers.BooleanField(read_only=True)
    autorite_signataire = serializers.CharField(read_only=True)
    signatures = serializers.SerializerMethodField()

    def get_signatures(self, demande) -> list[dict]:
        return [
            {
                "signataire": s.signataire.nom_complet,
                "qualite": s.qualite,
                "horodatage": s.horodatage,
                "code_verification": s.code_verification,
            }
            for s in demande.signatures.all()
        ]

    class Meta:
        model = Demande
        fields = [
            "id", "numero", "type", "type_libelle", "agent_nom", "agent_matricule", "motif",
            "date_debut", "date_fin", "heure_debut", "heure_fin", "nb_jours", "interimaire",
            "destination", "region_mission", "moyen_transport", "structures_visitees", "accompagnants",
            "hors_perimetre_drena", "termes_de_reference", "lettre_invitation",
            "lieu_jouissance", "contact_pendant_absence", "justificatif", "statut", "statut_libelle",
            "soumise_le", "cloturee_le", "motif_rejet", "validations", "progression", "est_modifiable",
            "autorite_signataire", "signatures", "cree_le",
        ]
        read_only_fields = ["numero", "nb_jours", "statut", "soumise_le", "cloturee_le", "motif_rejet"]

    def validate(self, attrs):
        debut = attrs.get("date_debut") or getattr(self.instance, "date_debut", None)
        fin = attrs.get("date_fin") or getattr(self.instance, "date_fin", None)
        if debut and fin and fin < debut:
            raise serializers.ValidationError({"date_fin": "La date de fin precede la date de debut."})
        return attrs


class RapportMissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = RapportMission
        fields = ["id", "demande", "resume", "resultats", "difficultes", "recommandations", "fichier", "depose_le"]
        read_only_fields = ["depose_le"]


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ["id", "titre", "message", "lien", "niveau", "lue", "creee_le"]


def _image_url(page, request, spec="width-800"):
    """URL absolue d'un rendu d'image Wagtail (ou None)."""
    if not page.image_id:
        return None
    url = page.image.get_rendition(spec).url
    return request.build_absolute_uri(url) if request else url


class ActualiteSerializer(serializers.ModelSerializer):
    titre = serializers.CharField(source="title", read_only=True)
    contenu = serializers.SerializerMethodField()
    image = serializers.SerializerMethodField()
    categorie = serializers.StringRelatedField()
    url = serializers.CharField(read_only=True)

    class Meta:
        model = PageActualite
        fields = ["id", "titre", "slug", "chapeau", "contenu", "image", "categorie", "date_publication", "url"]

    def get_contenu(self, page) -> str:
        return str(page.corps)

    def get_image(self, page) -> str | None:
        return _image_url(page, self.context.get("request"))


class RessourceSerializer(serializers.ModelSerializer):
    type_libelle = serializers.CharField(source="get_type_display", read_only=True)
    niveau_libelle = serializers.CharField(source="get_niveau_display", read_only=True)
    fichier = serializers.SerializerMethodField()

    class Meta:
        model = Ressource
        fields = ["id", "titre", "slug", "type", "type_libelle", "niveau", "niveau_libelle",
                  "discipline", "classe", "description", "fichier", "lien_externe", "annee"]

    def get_fichier(self, ressource) -> str | None:
        if not ressource.document_id:
            return None
        requete = self.context.get("request")
        url = ressource.document.url
        return requete.build_absolute_uri(url) if requete else url


class ProjetSerializer(serializers.ModelSerializer):
    nom = serializers.CharField(source="title", read_only=True)
    description = serializers.SerializerMethodField()
    image = serializers.SerializerMethodField()
    url = serializers.CharField(read_only=True)

    class Meta:
        model = PageProjet
        fields = ["id", "nom", "sigle", "slug", "accroche", "description", "couleur", "etat", "image", "url"]

    def get_description(self, page) -> str:
        return str(page.corps)

    def get_image(self, page) -> str | None:
        return _image_url(page, self.context.get("request"))


class EvenementSerializer(serializers.ModelSerializer):
    titre = serializers.CharField(source="title", read_only=True)
    type_libelle = serializers.CharField(source="get_type_display", read_only=True)
    description = serializers.SerializerMethodField()
    url = serializers.CharField(read_only=True)

    class Meta:
        model = PageEvenement
        fields = ["id", "titre", "slug", "type", "type_libelle", "description", "date_debut",
                  "date_fin", "heure_debut", "lieu", "public_cible", "url"]

    def get_description(self, page) -> str:
        return str(page.corps)


# --- Entrees et sorties des vues hors ModelViewSet ---------------------------
class ChangementMotDePasseSerializer(serializers.Serializer):
    ancien_mot_de_passe = serializers.CharField(write_only=True)
    nouveau_mot_de_passe = serializers.CharField(write_only=True, min_length=8)


class MessageSerializer(serializers.Serializer):
    detail = serializers.CharField(read_only=True)


class VerificationSerializer(serializers.Serializer):
    code_verification = serializers.CharField(read_only=True)
    acte = serializers.CharField(read_only=True)
    numero = serializers.CharField(read_only=True)
    beneficiaire = serializers.CharField(read_only=True)
    matricule = serializers.CharField(read_only=True)
    date_debut = serializers.DateField(read_only=True)
    date_fin = serializers.DateField(read_only=True)
    signataire = serializers.CharField(read_only=True)
    qualite = serializers.CharField(read_only=True)
    horodatage = serializers.DateTimeField(read_only=True)
    algorithme = serializers.CharField(read_only=True)
    empreinte = serializers.CharField(read_only=True)
    valide = serializers.BooleanField(read_only=True)


# --- Pilotage des activites --------------------------------------------------
class AvancementSerializer(serializers.ModelSerializer):
    """Lecture d'un point d'avancement."""

    auteur_nom = serializers.CharField(source="auteur.nom_complet", read_only=True)

    class Meta:
        model = Avancement
        fields = ["id", "activite", "date", "taux", "realisations", "difficultes",
                  "effectif_touche", "montant_engage", "piece_jointe", "auteur_nom", "saisi_le"]
        read_only_fields = ["auteur_nom", "saisi_le"]


class SaisieAvancementSerializer(serializers.ModelSerializer):
    """
    Depot d'un compte rendu depuis le terrain.

    L'activite est designee par l'URL et l'auteur par le jeton : ni l'une ni
    l'autre ne se declarent dans le corps de la requete.
    """

    class Meta:
        model = Avancement
        fields = ["date", "taux", "realisations", "difficultes",
                  "effectif_touche", "montant_engage", "piece_jointe"]
        extra_kwargs = {
            "date": {"required": False},
            "difficultes": {"required": False},
            "effectif_touche": {"required": False},
            "montant_engage": {"required": False},
            "piece_jointe": {"required": False},
        }

    def validate_taux(self, taux):
        if taux > 100:
            raise serializers.ValidationError("L'avancement ne peut depasser 100 %.")
        return taux


class ActiviteSerializer(serializers.ModelSerializer):
    axe_code = serializers.CharField(source="axe.code", read_only=True)
    type_libelle = serializers.CharField(source="get_type_display", read_only=True)
    statut_libelle = serializers.CharField(source="get_statut_display", read_only=True)
    responsable_nom = serializers.CharField(source="responsable.nom_complet", read_only=True)
    perimetre = serializers.CharField(source="plan.perimetre.code", read_only=True)
    annee = serializers.IntegerField(source="plan.annee", read_only=True)
    est_en_retard = serializers.BooleanField(read_only=True)
    jours_de_retard = serializers.IntegerField(read_only=True)

    class Meta:
        model = Activite
        fields = [
            "id", "code", "intitule", "description", "type", "type_libelle", "axe_code",
            "perimetre", "annee", "responsable_nom", "lieu", "public_cible",
            "date_debut_prevue", "date_fin_prevue", "date_debut_reelle", "date_fin_reelle",
            "statut", "statut_libelle", "avancement", "est_en_retard", "jours_de_retard",
            "budget_prevu", "budget_execute", "effectif_prevu", "effectif_realise",
        ]


class PlanActionSerializer(serializers.ModelSerializer):
    perimetre_code = serializers.CharField(source="perimetre.code", read_only=True)
    perimetre_nom = serializers.CharField(source="perimetre.nom", read_only=True)
    statut_libelle = serializers.CharField(source="get_statut_display", read_only=True)
    nb_activites = serializers.IntegerField(read_only=True)
    taux_execution = serializers.IntegerField(read_only=True)
    taux_execution_budgetaire = serializers.IntegerField(read_only=True)

    class Meta:
        model = PlanAction
        fields = ["id", "annee", "libelle", "contexte", "perimetre_code", "perimetre_nom",
                  "statut", "statut_libelle", "nb_activites", "taux_execution",
                  "taux_execution_budgetaire", "valide_le"]


class TableauPilotageSerializer(serializers.Serializer):
    annee = serializers.IntegerField(read_only=True)
    nb_activites = serializers.IntegerField(read_only=True)
    taux_execution = serializers.IntegerField(read_only=True)
    budget_prevu = serializers.DecimalField(max_digits=16, decimal_places=0, read_only=True)
    budget_execute = serializers.DecimalField(max_digits=16, decimal_places=0, read_only=True)
    beneficiaires = serializers.IntegerField(read_only=True)
    nb_en_retard = serializers.IntegerField(read_only=True)


# --- Courrier et documents ---------------------------------------------------
class CourrierSerializer(serializers.ModelSerializer):
    sens_libelle = serializers.CharField(source="get_sens_display", read_only=True)
    statut_libelle = serializers.CharField(source="get_statut_display", read_only=True)
    perimetre_code = serializers.CharField(source="perimetre.code", read_only=True)
    est_en_retard = serializers.BooleanField(read_only=True)
    nb_imputations = serializers.SerializerMethodField()

    class Meta:
        model = Courrier
        fields = ["id", "numero", "sens", "sens_libelle", "nature", "objet", "correspondant",
                  "reference_expediteur", "date_courrier", "date_enregistrement", "resume",
                  "statut", "statut_libelle", "perimetre_code", "confidentiel",
                  "est_en_retard", "nb_imputations"]

    def get_nb_imputations(self, courrier) -> int:
        return courrier.imputations.count()


class ImputationSerializer(serializers.ModelSerializer):
    courrier_numero = serializers.CharField(source="courrier.numero", read_only=True)
    courrier_objet = serializers.CharField(source="courrier.objet", read_only=True)
    destinataire_nom = serializers.CharField(source="destinataire.nom_complet", read_only=True)
    est_en_retard = serializers.BooleanField(read_only=True)
    jours_restants = serializers.IntegerField(read_only=True)

    class Meta:
        model = Imputation
        fields = ["id", "courrier", "courrier_numero", "courrier_objet", "destinataire_nom",
                  "instructions", "delai", "pour_information", "compte_rendu", "traite_le",
                  "est_en_retard", "jours_restants"]
        read_only_fields = ["traite_le"]


class CompteRenduSerializer(serializers.Serializer):
    """Suite donnee a une imputation, depuis le terrain."""

    compte_rendu = serializers.CharField()

    def validate_compte_rendu(self, valeur):
        if not valeur.strip():
            raise serializers.ValidationError("Indiquez la suite donnee au courrier.")
        return valeur


class DocumentSerializer(serializers.ModelSerializer):
    type_libelle = serializers.CharField(source="get_type_document_display", read_only=True)
    perimetre_code = serializers.CharField(source="perimetre.code", read_only=True)
    fichier = serializers.SerializerMethodField()
    nb_versions = serializers.IntegerField(read_only=True)

    class Meta:
        model = Document
        fields = ["id", "titre", "type_document", "type_libelle", "annee", "description",
                  "perimetre_code", "acces", "partage", "nb_versions", "fichier"]

    def get_fichier(self, document) -> str | None:
        version = document.version_courante
        if version is None or not version.fichier:
            return None
        requete = self.context.get("request")
        url = version.fichier.url
        return requete.build_absolute_uri(url) if requete else url

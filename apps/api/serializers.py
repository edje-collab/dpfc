from django.contrib.auth import get_user_model
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from apps.accounts.models import Notification
from apps.contenus.models import Actualite, Evenement, Projet, Ressource
from apps.core.models import Structure
from apps.rh.models import Demande, RapportMission, SoldeConge, Validation

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

    def get_signatures(self, demande):
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
            "hors_perimetre_drenaet", "termes_de_reference", "lettre_invitation",
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


class ActualiteSerializer(serializers.ModelSerializer):
    categorie = serializers.StringRelatedField()

    class Meta:
        model = Actualite
        fields = ["id", "titre", "slug", "chapeau", "contenu", "image", "categorie", "date_publication"]


class RessourceSerializer(serializers.ModelSerializer):
    type_libelle = serializers.CharField(source="get_type_display", read_only=True)
    niveau_libelle = serializers.CharField(source="get_niveau_display", read_only=True)

    class Meta:
        model = Ressource
        fields = ["id", "titre", "slug", "type", "type_libelle", "niveau", "niveau_libelle",
                  "discipline", "classe", "description", "fichier", "lien_externe", "annee"]


class ProjetSerializer(serializers.ModelSerializer):
    class Meta:
        model = Projet
        fields = ["id", "nom", "sigle", "slug", "accroche", "description", "couleur", "etat", "image"]


class EvenementSerializer(serializers.ModelSerializer):
    type_libelle = serializers.CharField(source="get_type_display", read_only=True)

    class Meta:
        model = Evenement
        fields = ["id", "titre", "slug", "type", "type_libelle", "description", "date_debut",
                  "date_fin", "heure_debut", "lieu", "public_cible"]

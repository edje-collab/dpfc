from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.generics import RetrieveUpdateAPIView
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from apps.accounts.models import Notification
from apps.contenus.models import Actualite, Evenement, Projet, Ressource
from apps.core.models import Structure
from apps.rh.models import Demande, RapportMission, SoldeConge, Validation
from apps.rh.services import annuler, decider, demandes_a_traiter, soumettre
from apps.signature.models import SignatureElectronique
from apps.signature.services import ErreurSignature, signer_demande, verifier_signature

from . import serializers as s

Agent = get_user_model()


class ConnexionView(TokenObtainPairView):
    serializer_class = s.ConnexionSerializer
    permission_classes = [permissions.AllowAny]


class MonProfilView(RetrieveUpdateAPIView):
    serializer_class = s.AgentSerializer

    def get_object(self):
        return self.request.user


class ChangerMotDePasseView(APIView):
    def post(self, request):
        ancien = request.data.get("ancien_mot_de_passe", "")
        nouveau = request.data.get("nouveau_mot_de_passe", "")
        if not request.user.check_password(ancien):
            return Response({"detail": "Mot de passe actuel incorrect."}, status=400)
        if len(nouveau) < 8:
            return Response({"detail": "Le nouveau mot de passe doit contenir au moins 8 caracteres."}, status=400)
        request.user.set_password(nouveau)
        request.user.doit_changer_mot_de_passe = False
        request.user.save(update_fields=["password", "doit_changer_mot_de_passe"])
        return Response({"detail": "Mot de passe modifie."})


class SoldeView(APIView):
    def get(self, request):
        annee = int(request.query_params.get("annee", timezone.localdate().year))
        solde = SoldeConge.pour(request.user, annee)
        return Response(s.SoldeSerializer(solde).data)


class DemandeViewSet(viewsets.ModelViewSet):
    """Actes administratifs de l'agent connecte."""

    serializer_class = s.DemandeSerializer

    def get_queryset(self):
        qs = Demande.objects.select_related("agent").prefetch_related("validations__valideur")
        portee = self.request.query_params.get("portee", "moi")
        if portee == "equipe":
            return qs.filter(agent__in=self.request.user.perimetre_agents()).order_by("-cree_le")
        return qs.filter(agent=self.request.user).order_by("-cree_le")

    def perform_create(self, serializer):
        serializer.save(agent=self.request.user, structure=self.request.user.structure)

    def perform_update(self, serializer):
        if not serializer.instance.est_modifiable:
            from rest_framework.exceptions import ValidationError

            raise ValidationError("Cette demande n'est plus modifiable.")
        serializer.save()

    @action(detail=True, methods=["post"])
    def soumettre(self, request, pk=None):
        demande = self.get_object()
        if demande.agent_id != request.user.pk:
            return Response({"detail": "Action reservee a l'auteur."}, status=403)
        try:
            soumettre(demande, requete=request)
        except ValueError as err:
            return Response({"detail": str(err)}, status=400)
        return Response(self.get_serializer(demande).data)

    @action(detail=True, methods=["post"])
    def annuler(self, request, pk=None):
        demande = self.get_object()
        if demande.agent_id != request.user.pk and not request.user.est_rh:
            return Response({"detail": "Action non autorisee."}, status=403)
        if not demande.est_annulable:
            return Response({"detail": "Demande non annulable a ce stade."}, status=400)
        annuler(demande, request.user, requete=request)
        return Response(self.get_serializer(demande).data)

    @action(detail=True, methods=["post"], url_path="decision")
    def decision(self, request, pk=None):
        """
        Avis favorable ou rejet. Si `code_signature` est fourni et que le valideur
        dispose d'une cle valide, la signature electronique est apposee dans la foulee.
        """
        demande = Demande.objects.filter(pk=pk).first()
        if demande is None:
            return Response(status=404)
        etape = demande.etape_courante()
        if etape is None or etape.valideur_id != request.user.pk:
            return Response({"detail": "Cette demande n'attend pas votre decision."}, status=403)

        favorable = str(request.data.get("favorable", "")).lower() in {"true", "1", "oui"}
        commentaire = request.data.get("commentaire", "")
        code = request.data.get("code_signature", "")
        derniere = not demande.validations.filter(ordre__gt=etape.ordre).exists()
        cle = getattr(request.user, "cle_signature", None)

        if not favorable and not commentaire.strip():
            return Response({"detail": "Le motif du rejet est obligatoire."}, status=400)
        if favorable and derniere and cle and cle.est_valide and not code:
            return Response(
                {"detail": "Etape de signature : transmettez votre code de signature."}, status=400
            )

        decider(etape, favorable, commentaire, requete=request)
        demande.refresh_from_db()

        donnees = s.DemandeSerializer(demande).data
        if favorable and code:
            try:
                signature = signer_demande(
                    demande, request.user, code, qualite=etape.libelle, validation=etape, requete=request
                )
            except ErreurSignature as err:
                donnees["avertissement_signature"] = str(err)
            else:
                donnees["code_verification"] = signature.code_verification
        return Response(donnees)

    @action(detail=True, methods=["post"], url_path="pieces",
            parser_classes=[MultiPartParser, FormParser])
    def pieces(self, request, pk=None):
        """
        Depot des pieces jointes depuis le terrain : termes de reference,
        lettre d'invitation, piece justificative.
        """
        demande = self.get_object()
        if demande.agent_id != request.user.pk and demande.depose_par_id != request.user.pk:
            return Response({"detail": "Action reservee a l'auteur du depot."}, status=403)
        if not demande.est_modifiable:
            return Response({"detail": "Cette demande n'est plus modifiable."}, status=400)

        champs = {
            "termes_de_reference": "termes_de_reference",
            "lettre_invitation": "lettre_invitation",
            "justificatif": "justificatif",
        }
        deposees = []
        for cle, champ in champs.items():
            fichier = request.FILES.get(cle)
            if fichier is not None:
                getattr(demande, champ).save(fichier.name, fichier, save=False)
                deposees.append(champ)
        if not deposees:
            return Response({"detail": "Aucun fichier transmis."}, status=400)
        demande.save()
        return Response({"pieces_enregistrees": deposees, **s.DemandeSerializer(demande).data})

    @action(detail=False, methods=["get"], url_path="a-valider")
    def a_valider(self, request):
        liste = demandes_a_traiter(request.user)
        return Response(s.DemandeSerializer(liste, many=True).data)


class VerificationView(APIView):
    """Verification publique d'un acte signe, a partir de son code."""

    permission_classes = [permissions.AllowAny]

    def get(self, request, code):
        signature = (
            SignatureElectronique.objects.filter(code_verification__iexact=code)
            .select_related("demande", "demande__agent", "signataire")
            .first()
        )
        if signature is None:
            return Response({"detail": "Code de verification inconnu."}, status=404)
        resultat = verifier_signature(signature)
        return Response({
            "code_verification": signature.code_verification,
            "acte": signature.demande.get_type_display(),
            "numero": signature.demande.numero,
            "beneficiaire": signature.demande.agent.nom_complet,
            "matricule": signature.demande.agent.matricule,
            "date_debut": signature.demande.date_debut,
            "date_fin": signature.demande.date_fin,
            "signataire": signature.signataire.nom_complet,
            "qualite": signature.qualite,
            "horodatage": signature.horodatage,
            "algorithme": signature.algorithme,
            "empreinte": signature.empreinte_document,
            **resultat,
        })


class RapportMissionViewSet(viewsets.ModelViewSet):
    serializer_class = s.RapportMissionSerializer

    def get_queryset(self):
        return RapportMission.objects.filter(demande__agent=self.request.user)


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = s.NotificationSerializer

    def get_queryset(self):
        return Notification.objects.filter(destinataire=self.request.user)

    @action(detail=False, methods=["post"], url_path="tout-lire")
    def tout_lire(self, request):
        n = Notification.objects.filter(destinataire=request.user, lue=False).update(lue=True)
        return Response({"marquees": n})


class AnnuaireViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = s.AgentSerializer

    def get_queryset(self):
        qs = Agent.objects.filter(is_active=True).select_related("structure")
        recherche = self.request.query_params.get("q")
        rattachement = self.request.query_params.get("rattachement")
        if recherche:
            qs = qs.filter(last_name__icontains=recherche)
        if rattachement:
            qs = qs.filter(structure__rattachement=rattachement)
        return qs


# --- Contenus publics (lecture libre) ---------------------------------------
class LectureLibre(viewsets.ReadOnlyModelViewSet):
    permission_classes = [permissions.AllowAny]


class ActualitePubliqueViewSet(LectureLibre):
    serializer_class = s.ActualiteSerializer
    lookup_field = "slug"

    def get_queryset(self):
        return Actualite.objects.publiees().select_related("categorie")


class RessourcePubliqueViewSet(LectureLibre):
    serializer_class = s.RessourceSerializer
    lookup_field = "slug"

    def get_queryset(self):
        qs = Ressource.objects.filter(publiee=True)
        for champ in ("type", "niveau"):
            valeur = self.request.query_params.get(champ)
            if valeur:
                qs = qs.filter(**{champ: valeur})
        return qs


class ProjetPubliqueViewSet(LectureLibre):
    serializer_class = s.ProjetSerializer
    lookup_field = "slug"
    queryset = Projet.objects.filter(publie=True)


class EvenementPubliqueViewSet(LectureLibre):
    serializer_class = s.EvenementSerializer
    lookup_field = "slug"

    def get_queryset(self):
        return Evenement.objects.filter(publie=True, date_debut__gte=timezone.localdate())


class AntennePubliqueViewSet(LectureLibre):
    serializer_class = s.StructureSerializer
    lookup_field = "slug"
    queryset = Structure.objects.filter(type=Structure.Type.ANTENNE, active=True).select_related("region")

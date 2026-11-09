"""Taches de fond de l'application RH."""
from celery import shared_task
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Notification

from .models import Demande, TypeDemande


@shared_task(name="apps.rh.tasks.rappels_quotidiens")
def rappels_quotidiens():
    """
    Relance les valideurs sur les actes en attente depuis plus de trois jours.

    Retourne le nombre de relances envoyees, pour le journal de Celery.
    """
    limite = timezone.now() - timezone.timedelta(days=3)
    en_attente = (
        Demande.objects.filter(
            statut__in=[Demande.Statut.SOUMISE, Demande.Statut.EN_COURS],
            soumise_le__lte=limite,
        )
        .select_related("agent")
        .prefetch_related("validations")
    )
    envoyees = 0
    for demande in en_attente:
        etape = demande.etape_courante()
        if etape is None:
            continue
        Notification.objects.create(
            destinataire=etape.valideur,
            titre=f"Acte en attente : {demande.numero}",
            message=(
                f"{demande.agent.nom_complet} attend votre decision depuis le "
                f"{demande.soumise_le:%d/%m/%Y} ({etape.libelle})."
            ),
            lien=reverse("rh:demande_detail", args=[demande.pk]),
            niveau=Notification.Niveau.ALERTE,
        )
        envoyees += 1
    return envoyees


@shared_task(name="apps.rh.tasks.rappeler_rapports_de_mission")
def rappeler_rapports_de_mission():
    """Rappelle aux agents de deposer le rapport des missions achevees."""
    aujourdhui = timezone.localdate()
    missions = Demande.objects.filter(
        type=TypeDemande.ORDRE_MISSION,
        statut=Demande.Statut.APPROUVEE,
        date_fin__lt=aujourdhui,
        rapport__isnull=True,
    ).select_related("agent")
    for mission in missions:
        Notification.objects.create(
            destinataire=mission.agent,
            titre=f"Rapport de mission attendu : {mission.numero}",
            message=f"La mission du {mission.date_debut:%d/%m/%Y} est achevee. Deposez votre rapport.",
            lien=reverse("rh:demande_detail", args=[mission.pk]),
            niveau=Notification.Niveau.ALERTE,
        )
    return missions.count()

"""Charge le jeu de demonstration du pilotage des activites."""
from django.core.management.base import BaseCommand

from apps.activites.demo import charger


class Command(BaseCommand):
    help = "Cree les plans d'action et les activites de demonstration."

    def handle(self, *args, **options):
        charger(stdout=self.stdout)
        self.stdout.write(self.style.SUCCESS("Jeu de demonstration du pilotage charge."))

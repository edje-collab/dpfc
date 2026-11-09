"""Charge le jeu de demonstration des ateliers et de l'emargement."""
from django.core.management.base import BaseCommand

from apps.ateliers.demo import charger


class Command(BaseCommand):
    help = "Cree les ateliers, participants et emargements de demonstration."

    def handle(self, *args, **options):
        charger(stdout=self.stdout)
        self.stdout.write(self.style.SUCCESS("Jeu de demonstration des ateliers charge."))

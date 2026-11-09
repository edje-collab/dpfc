"""Charge le jeu de demonstration des achats et du magasin."""
from django.core.management.base import BaseCommand

from apps.achats.demo import charger


class Command(BaseCommand):
    help = "Cree les besoins, commandes, articles et equipements de demonstration."

    def handle(self, *args, **options):
        charger(stdout=self.stdout)
        self.stdout.write(self.style.SUCCESS("Jeu de demonstration des achats charge."))

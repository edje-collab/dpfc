"""Charge le jeu de demonstration du courrier et des documents."""
from django.core.management.base import BaseCommand

from apps.courrier.demo import charger


class Command(BaseCommand):
    help = "Cree les courriers, documents et pieces au parapheur de demonstration."

    def handle(self, *args, **options):
        charger(stdout=self.stdout)
        self.stdout.write(self.style.SUCCESS("Jeu de demonstration du courrier charge."))

"""Installe ou reinstalle les circuits de validation modeles."""
from django.core.management.base import BaseCommand

from apps.circuits.modeles import installer_circuits_modeles


class Command(BaseCommand):
    help = "Cree les circuits de validation modeles des trois types de perimetre."

    def add_arguments(self, parseur):
        parseur.add_argument(
            "--remplacer",
            action="store_true",
            help="Reecrit les etapes des circuits modeles existants.",
        )

    def handle(self, *args, **options):
        crees, inchanges = installer_circuits_modeles(remplacer=options["remplacer"])
        self.stdout.write(self.style.SUCCESS(f"{crees} circuit(s) ecrit(s), {inchanges} inchange(s)."))

"""
Import des agents depuis un classeur Excel ou un CSV, en ligne de commande.

    python manage.py importer_agents agents.xlsx              # analyse seule
    python manage.py importer_agents agents.xlsx --appliquer  # ecriture
    python manage.py importer_agents --modele modele.xlsx     # genere le modele
"""
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.imports import analyser, appliquer, generer_modele, lire_fichier


class Command(BaseCommand):
    help = "Importe ou met a jour les comptes agents depuis un fichier Excel/CSV."

    def add_arguments(self, parseur):
        parseur.add_argument("fichier", nargs="?", help="Chemin du fichier .xlsx ou .csv")
        parseur.add_argument("--appliquer", action="store_true", help="Ecrit reellement en base.")
        parseur.add_argument("--modele", help="Genere le classeur modele au chemin indique.")

    def handle(self, *args, **options):
        if options["modele"]:
            with open(options["modele"], "wb") as sortie:
                sortie.write(generer_modele())
            self.stdout.write(self.style.SUCCESS(f"Modele ecrit dans {options['modele']}."))
            return

        chemin = options["fichier"]
        if not chemin:
            raise CommandError("Indiquez un fichier a importer ou utilisez --modele.")

        with open(chemin, "rb") as fichier:
            lignes, erreur = lire_fichier(fichier, chemin)
        if erreur:
            raise CommandError(erreur)

        resultats = analyser(lignes)
        for ligne in resultats:
            if ligne["action"] == "erreur":
                self.stdout.write(
                    self.style.ERROR(f"  ligne {ligne['ligne']} : {', '.join(ligne['erreurs'])}")
                )
        creations = sum(1 for r in resultats if r["action"] == "creation")
        maj = sum(1 for r in resultats if r["action"] == "mise_a_jour")
        erreurs = sum(1 for r in resultats if r["action"] == "erreur")
        self.stdout.write(f"{len(resultats)} ligne(s) : {creations} creation(s), {maj} mise(s) a jour, {erreurs} anomalie(s).")

        if not options["appliquer"]:
            self.stdout.write(self.style.WARNING("Analyse seule. Relancez avec --appliquer pour ecrire."))
            return

        compte = appliquer(resultats)
        self.stdout.write(self.style.SUCCESS(
            f"Import termine : {compte['crees']} cree(s), {compte['mis_a_jour']} mis a jour, "
            f"{compte['ignores']} ignore(s). Mot de passe initial = matricule."
        ))

"""
Retire de l'organigramme les structures centrales absentes du decret.

Decision de la direction : les sous-directions et services anterieurs au
decret n° 2026-509 sont supprimes, a l'exception du service du personnel et
des affaires administratives, qui subsiste.

    python manage.py nettoyer_organisation              # simulation
    python manage.py nettoyer_organisation --appliquer

Une structure porteuse d'historique — actes administratifs, courriers,
activites — n'est pas supprimee mais desactivee : effacer la structure
effacerait la provenance des actes deja pris, ce qu'une administration ne
peut pas se permettre. La commande dit a chaque fois lequel des deux cas
s'applique.
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import ProtectedError, RestrictedError

from apps.core.models import JournalAction, Structure

# Structures centrales prevues par le decret n° 2026-509 et par l'arrete
# d'organisation. Tout ce qui n'y figure pas releve de l'organigramme ancien.
SIGLES_CONFORMES = {
    "DGPCSP",  # direction generale de rattachement (article 27)
    "DPFC",    # la direction elle-meme
    "SDPPBS",  # sous-direction des programmes pedagogiques (article 28)
    "SDIP",    # sous-direction des innovations pedagogiques (article 28)
    "SDFPC",   # sous-direction de la formation pedagogique continue (article 28)
    "CNRPN",   # centre national, service rattache par arrete
}

# Conserve sur decision expresse de la direction : le service du personnel
# n'est pas une sous-direction du decret, mais il subsiste.
SIGLES_CONSERVES = {"SPAA"}


class Command(BaseCommand):
    help = (
        "Supprime les sous-directions et services centraux absents du decret "
        "n° 2026-509, en conservant le service du personnel."
    )

    def add_arguments(self, parseur):
        parseur.add_argument(
            "--appliquer",
            action="store_true",
            help="Execute reellement. Sans cette option, la commande se borne a simuler.",
        )
        parseur.add_argument(
            "--reaffecter",
            default="DPFC",
            help="Sigle de la structure qui accueille les agents des structures retirees "
                 "(par defaut : DPFC).",
        )

    def handle(self, *args, **options):
        appliquer = options["appliquer"]
        self._verifier_rattachement(appliquer)
        accueil = Structure.objects.filter(sigle=options["reaffecter"]).first()
        if accueil is None:
            self.stderr.write(
                self.style.ERROR(
                    f"Structure d'accueil « {options['reaffecter']} » introuvable."
                )
            )
            return

        # Une structure deja desactivee a ete traitee : la reprendre
        # n'apporterait rien et brouillerait le compte rendu.
        obsoletes = list(
            Structure.objects.filter(
                rattachement=Structure.Rattachement.CENTRALE, active=True
            )
            .exclude(sigle__in=SIGLES_CONFORMES | SIGLES_CONSERVES)
            .order_by("sigle")
        )
        deja_traitees = Structure.objects.filter(
            rattachement=Structure.Rattachement.CENTRALE, active=False
        ).exclude(sigle__in=SIGLES_CONFORMES | SIGLES_CONSERVES)

        if deja_traitees.exists():
            self.stdout.write(
                "Deja retirees lors d'un passage precedent : "
                + ", ".join(deja_traitees.values_list("sigle", flat=True))
                + " (desactivees, leur historique reste consultable)."
            )

        if not obsoletes:
            self.stdout.write(
                self.style.SUCCESS("L'organigramme central est conforme au decret.")
            )
            self._rappeler_conserves()
            return

        if not appliquer:
            self.stdout.write(
                self.style.WARNING("SIMULATION — rien n'est modifie. "
                                   "Ajoutez --appliquer pour executer.")
            )
        self.stdout.write(f"\n{len(obsoletes)} structure(s) absente(s) du decret :\n")

        supprimees, desactivees = [], []
        for structure in obsoletes:
            agents = list(structure.agents.all())
            enfants = list(structure.enfants.all())
            self.stdout.write(
                f"  {structure.sigle:12} {structure.nom[:52]}\n"
                f"               agents : {len(agents)}"
                f"{' (' + ', '.join(a.matricule for a in agents) + ')' if agents else ''}"
                f" | sous-structures : {len(enfants)}"
            )
            if not appliquer:
                continue

            etat = self._retirer(structure, accueil, agents, enfants)
            (supprimees if etat == "supprimee" else desactivees).append(structure.sigle)

        if not appliquer:
            self.stdout.write(
                "\nLes agents seraient rattaches a "
                f"{accueil.sigle}, les sous-structures egalement."
            )
            self._rappeler_conserves()
            return

        self.stdout.write("")
        if supprimees:
            self.stdout.write(self.style.SUCCESS(f"Supprimees : {', '.join(supprimees)}"))
        if desactivees:
            self.stdout.write(
                self.style.WARNING(
                    f"Desactivees (historique a preserver) : {', '.join(desactivees)}"
                )
            )
        self._rappeler_conserves()

    def _verifier_rattachement(self, appliquer):
        """
        La DPFC releve de la DGPCSP (article 27).

        Sur une base anterieure au decret, la direction existait deja sans
        rattachement : les valeurs par defaut de la creation ne s'appliquent
        pas a un enregistrement existant, et le lien reste donc a etablir.
        """
        direction = Structure.objects.filter(sigle="DPFC").first()
        generale = Structure.objects.filter(sigle="DGPCSP").first()
        if direction is None or generale is None:
            return
        if direction.parent_id == generale.pk:
            return

        self.stdout.write(
            self.style.WARNING(
                "La DPFC n'est pas rattachee a la DGPCSP (article 27 du decret)."
            )
        )
        if not appliquer:
            self.stdout.write("  Le rattachement serait etabli.\n")
            return
        direction.parent = generale
        direction.save(update_fields=["parent"])
        JournalAction.objects.create(
            action="Rattachement de la DPFC a la DGPCSP",
            objet="DPFC",
            details="Mise en conformite avec l'article 27 du decret n° 2026-509.",
        )
        self.stdout.write(self.style.SUCCESS("  Rattachement etabli.\n"))

    @transaction.atomic
    def _retirer(self, structure, accueil, agents, enfants):
        """
        Retire une structure.

        Les agents et les sous-structures sont d'abord rattaches a la structure
        d'accueil, puis la structure est supprimee. Si la base s'y oppose —
        des actes y font reference —, elle est desactivee a la place.
        """
        for agent in agents:
            agent.structure = accueil
            agent.save(update_fields=["structure"])
        for enfant in enfants:
            enfant.parent = accueil
            enfant.save(update_fields=["parent"])
        if structure.responsable_id:
            structure.responsable = None
            structure.save(update_fields=["responsable"])

        try:
            with transaction.atomic():
                structure.delete()
        except (ProtectedError, RestrictedError):
            structure.active = False
            structure.save(update_fields=["active"])
            JournalAction.objects.create(
                action="Desactivation d'une structure hors decret",
                objet=structure.sigle,
                details="Structure porteuse d'historique : desactivee plutot que supprimee.",
            )
            return "desactivee"

        JournalAction.objects.create(
            action="Suppression d'une structure hors decret",
            objet=structure.sigle,
            details=f"{len(agents)} agent(s) et {len(enfants)} sous-structure(s) "
                    f"rattache(s) a {accueil.sigle}.",
        )
        return "supprimee"

    def _rappeler_conserves(self):
        conserves = Structure.objects.filter(sigle__in=SIGLES_CONSERVES)
        for structure in conserves:
            self.stdout.write(
                f"\nConserve sur decision de la direction : "
                f"{structure.sigle} — {structure.nom}."
            )

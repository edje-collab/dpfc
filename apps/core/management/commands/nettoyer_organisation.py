"""
Retire de l'organigramme les structures centrales absentes du decret.

Decision de la direction : les sous-directions et services anterieurs au
decret n° 2026-509 sont supprimes, a l'exception du service du personnel et
des affaires administratives, qui subsiste.

    python manage.py nettoyer_organisation              # simulation
    python manage.py nettoyer_organisation --appliquer

Les agents suivent leur structure : chaque structure retiree designe la
sous-direction du decret qui reprend ses attributions (voir CORRESPONDANCES),
et ses agents y sont rattaches. A defaut de correspondance connue, ils vont a
la direction, qui decidera.

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

# Quelle sous-direction du decret reprend les attributions de chaque structure
# retiree. La repartition des agents suit celle des missions, non les personnes :
# c'est le seul critere qui se justifie sans arbitrer les carrieres.
CORRESPONDANCES = {
    # Formation continue -> Sous-direction de la Formation Pedagogique Continue
    "SDFC": "SDFPC",
    # Programmes et manuels scolaires -> Sous-direction des Programmes
    # Pedagogiques et des Bibliotheques Scolaires
    "SDPMS": "SDPPBS",
    # Ressources pedagogiques numeriques -> Sous-direction des Innovations
    # Pedagogiques, qui porte desormais le numerique educatif
    "SDPRPN": "SDIP",
}


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
            help="Structure d'accueil par defaut, pour les agents d'une structure "
                 "sans correspondance connue (par defaut : DPFC).",
        )
        parseur.add_argument(
            "--correspondance",
            action="append",
            default=[],
            metavar="ANCIEN=NOUVEAU",
            help="Ajoute ou remplace une correspondance, par exemple SDFC=SDFPC. "
                 "Repetable.",
        )

    def handle(self, *args, **options):
        appliquer = options["appliquer"]
        correspondances = dict(CORRESPONDANCES)
        for paire in options["correspondance"]:
            if "=" not in paire:
                self.stderr.write(self.style.ERROR(f"Correspondance mal formee : {paire}"))
                return
            ancien, nouveau = (p.strip().upper() for p in paire.split("=", 1))
            correspondances[ancien] = nouveau

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

        supprimees, desactivees, sans_correspondance = [], [], []
        for structure in obsoletes:
            agents = list(structure.agents.all())
            enfants = list(structure.enfants.all())
            reprise = self._reprise(structure, correspondances, accueil)
            if reprise.pk == accueil.pk and structure.sigle not in correspondances:
                sans_correspondance.append(structure.sigle)

            self.stdout.write(
                f"  {structure.sigle:12} {structure.nom[:52]}\n"
                f"               agents : {len(agents)}"
                f"{' (' + ', '.join(a.matricule for a in agents) + ')' if agents else ''}"
                f" | sous-structures : {len(enfants)}\n"
                f"               attributions reprises par : {reprise.sigle}"
            )
            if not appliquer:
                continue

            etat = self._retirer(structure, reprise, agents, enfants)
            (supprimees if etat == "supprimee" else desactivees).append(structure.sigle)

        if not appliquer:
            if sans_correspondance:
                self.stdout.write(
                    self.style.WARNING(
                        f"\nSans correspondance connue : {', '.join(sans_correspondance)}. "
                        f"Leurs agents iraient a {accueil.sigle}.\n"
                        "Precisez-la au besoin : --correspondance ANCIEN=NOUVEAU."
                    )
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

    def _reprise(self, structure, correspondances, accueil):
        """
        Structure qui reprend les attributions d'une structure retiree.

        A defaut de correspondance connue, ou si la structure designee est
        introuvable, les agents vont a la structure d'accueil : mieux vaut les
        remettre a la direction que de les placer au jugé.
        """
        sigle = correspondances.get(structure.sigle)
        if not sigle:
            return accueil
        reprise = Structure.objects.filter(sigle=sigle, active=True).first()
        if reprise is None:
            self.stdout.write(
                self.style.WARNING(
                    f"  Correspondance {structure.sigle} -> {sigle} : "
                    f"structure introuvable, repli sur {accueil.sigle}."
                )
            )
            return accueil
        return reprise

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

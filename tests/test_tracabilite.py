"""
Controle de la matrice de tracabilite du cahier des charges.

Une matrice qui se perime en silence est pire que pas de matrice : elle donne
l'illusion d'une preuve. Ce test verifie donc que chaque exigence du cahier des
charges renvoie a des tests qui existent reellement, et que les exigences
enoncees sont toutes tracees.
"""
import re
from pathlib import Path

from django.test import SimpleTestCase

RACINE = Path(__file__).resolve().parent.parent
CAHIER = RACINE / "docs" / "cahier-des-charges.md"

# Une reference de test : `apps/xxx/tests.py::test_yyy`
REFERENCE = re.compile(r"`(apps/[\w/]+\.py)::(test_\w+)`")
# Une reference a un fichier seul (migration, par exemple).
FICHIER_SEUL = re.compile(r"`(apps/[\w/]+\.py)`")
# Un identifiant d'exigence en debut de ligne de tableau : | ORG-01 | ...
EXIGENCE = re.compile(r"^\|\s*\*{0,2}([A-Z]{3}-\d{2})\*{0,2}\s*\|")


def _lire_cahier():
    return CAHIER.read_text(encoding="utf-8")


def _section_matrice(texte):
    """
    Partie du document qui porte la matrice et ses annexes.

    Elle va du titre de la section 15 a celui de la section 16 : la
    sous-section 15.1, qui recense les exigences verifiees autrement, en fait
    donc partie.
    """
    debut = texte.index("## 15. Matrice de traçabilité")
    fin = texte.index("## 16. Ce qui reste à trancher")
    return texte[debut:fin]


class CahierDesChargesTest(SimpleTestCase):
    def test_le_cahier_des_charges_existe(self):
        self.assertTrue(CAHIER.exists(), "docs/cahier-des-charges.md est introuvable.")

    def test_les_tests_references_existent(self):
        """Chaque test cite dans la matrice doit exister dans le code."""
        matrice = _section_matrice(_lire_cahier())
        manquants = []
        for chemin, nom_test in REFERENCE.findall(matrice):
            fichier = RACINE / chemin
            if not fichier.exists():
                manquants.append(f"{chemin} (fichier absent)")
                continue
            if f"def {nom_test}(" not in fichier.read_text(encoding="utf-8"):
                manquants.append(f"{chemin}::{nom_test}")
        self.assertEqual(
            manquants, [],
            "Le cahier des charges cite des tests qui n'existent plus :\n  "
            + "\n  ".join(manquants)
            + "\nMettez a jour docs/cahier-des-charges.md.",
        )

    def test_les_fichiers_references_existent(self):
        """Les references a un fichier seul — une migration, par exemple."""
        matrice = _section_matrice(_lire_cahier())
        sans_test = {
            chemin for chemin in FICHIER_SEUL.findall(matrice)
            if not any(chemin == c for c, _ in REFERENCE.findall(matrice))
        }
        manquants = [c for c in sans_test if not (RACINE / c).exists()]
        self.assertEqual(manquants, [], f"Fichiers cites mais absents : {manquants}")

    def test_chaque_exigence_enoncee_est_tracee(self):
        """
        Toute exigence du corps du document figure dans la matrice, ou dans la
        liste explicite de celles qui relevent de la configuration.
        """
        texte = _lire_cahier()
        matrice = _section_matrice(texte)
        corps = texte[: texte.index("## 15. Matrice de traçabilité")]

        enoncees = {m.group(1) for ligne in corps.splitlines()
                    if (m := EXIGENCE.match(ligne))}
        tracees = {m.group(1) for ligne in matrice.splitlines()
                   if (m := EXIGENCE.match(ligne))}
        # Exigences transverses, justifiees dans la section 15.1.
        hors_matrice = {
            m.group(1)
            for ligne in matrice[matrice.index("### 15.1"):].splitlines()
            if (m := EXIGENCE.match(ligne))
        }

        oubliees = sorted(enoncees - tracees - hors_matrice)
        self.assertEqual(
            oubliees, [],
            f"Exigences enoncees mais absentes de la matrice : {oubliees}",
        )

    def test_la_matrice_ne_cite_pas_d_exigence_inconnue(self):
        texte = _lire_cahier()
        corps = texte[: texte.index("## 15. Matrice de traçabilité")]
        matrice = _section_matrice(texte)

        enoncees = {m.group(1) for ligne in corps.splitlines()
                    if (m := EXIGENCE.match(ligne))}
        tracees = {m.group(1) for ligne in matrice.splitlines()
                   if (m := EXIGENCE.match(ligne))}
        inconnues = sorted(tracees - enoncees)
        self.assertEqual(
            inconnues, [],
            f"La matrice trace des exigences qui ne sont enoncees nulle part : {inconnues}",
        )

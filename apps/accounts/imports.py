"""
Import en masse des agents depuis un classeur Excel (.xlsx) ou un fichier CSV.

Le fichier est d'abord analyse (aucune ecriture), ce qui permet de corriger les
anomalies avant application. Les agents deja connus sont mis a jour, les autres
sont crees avec le matricule comme mot de passe initial, a changer a la premiere
connexion.
"""
import csv
import io
from datetime import date, datetime

from django.contrib.auth import get_user_model
from django.db import transaction

from apps.core.models import Structure
from apps.rh.models import SoldeConge

Agent = get_user_model()

# En-tete attendu : cle interne -> intitules acceptes (en minuscules, sans accent)
COLONNES = {
    "matricule": ["matricule"],
    "civilite": ["civilite", "civilité", "genre"],
    "nom": ["nom"],
    "prenoms": ["prenoms", "prénoms", "prenom", "prénom"],
    "email": ["email", "courriel", "mail"],
    "telephone": ["telephone", "téléphone", "tel", "contact"],
    "structure": ["structure", "sigle structure", "affectation", "antenne"],
    "fonction": ["fonction", "poste"],
    "grade": ["grade"],
    "role": ["role", "rôle", "profil"],
    "superieur": ["superieur", "supérieur", "matricule superieur", "responsable"],
    "date_prise_service": ["date_prise_service", "date de prise de service", "prise de service"],
    "lieu_service": ["lieu_service", "lieu de service"],
    "droit_conge": ["droit_conge", "droit conge", "droits a conge", "jours de conge"],
}

ENTETE_MODELE = [
    "matricule", "civilite", "nom", "prenoms", "email", "telephone", "structure",
    "fonction", "grade", "role", "superieur", "date_prise_service", "lieu_service", "droit_conge",
]

ROLES_VALIDES = {r[0] for r in Agent.Role.choices}
CIVILITES = {"M": "M", "MR": "M", "MONSIEUR": "M", "MME": "MME", "MADAME": "MME", "MLLE": "MME"}


def _normaliser(texte):
    remplacements = str.maketrans("àâäéèêëîïôöùûüç", "aaaeeeeiioouuuc")
    return str(texte or "").strip().lower().translate(remplacements)


def _valeur(brut):
    if brut is None:
        return ""
    if isinstance(brut, (datetime, date)):
        return brut.strftime("%Y-%m-%d")
    if isinstance(brut, float) and brut.is_integer():
        return str(int(brut))
    return str(brut).strip()


def lire_fichier(fichier, nom=""):
    """Retourne (lignes, erreur). Chaque ligne est un dictionnaire des colonnes reconnues."""
    nom = (nom or getattr(fichier, "name", "")).lower()
    if nom.endswith(".csv"):
        contenu = fichier.read()
        if isinstance(contenu, bytes):
            contenu = contenu.decode("utf-8-sig", errors="replace")
        lecteur = csv.reader(io.StringIO(contenu), delimiter=";" if ";" in contenu.split("\n")[0] else ",")
        grille = [list(ligne) for ligne in lecteur]
    elif nom.endswith((".xlsx", ".xlsm")):
        try:
            from openpyxl import load_workbook
        except ImportError:
            return [], "La bibliotheque openpyxl n'est pas installee sur le serveur."
        classeur = load_workbook(fichier, data_only=True, read_only=True)
        feuille = classeur[classeur.sheetnames[0]]
        grille = [[_valeur(c) for c in ligne] for ligne in feuille.iter_rows(values_only=True)]
    else:
        return [], "Format non reconnu : fournissez un fichier .xlsx ou .csv."

    grille = [ligne for ligne in grille if any(_valeur(c) for c in ligne)]
    if not grille:
        return [], "Le fichier est vide."

    entete = [_normaliser(c) for c in grille[0]]
    indices = {}
    for cle, intitules in COLONNES.items():
        for intitule in intitules:
            if _normaliser(intitule) in entete:
                indices[cle] = entete.index(_normaliser(intitule))
                break
    if "matricule" not in indices or "nom" not in indices:
        return [], "En-tete invalide : les colonnes « matricule » et « nom » sont obligatoires."

    lignes = []
    for numero, brut in enumerate(grille[1:], start=2):
        donnees = {
            cle: _valeur(brut[i]) if i < len(brut) else "" for cle, i in indices.items()
        }
        donnees["_ligne"] = numero
        lignes.append(donnees)
    return lignes, None


def analyser(lignes):
    """Controle chaque ligne sans rien ecrire. Retourne la liste des resultats."""
    structures = {s.sigle.upper(): s for s in Structure.objects.filter(active=True) if s.sigle}
    structures.update({_normaliser(s.nom): s for s in Structure.objects.filter(active=True)})
    matricules_connus = set(Agent.objects.values_list("matricule", flat=True))
    matricules_fichier = set()
    resultats = []

    for donnees in lignes:
        erreurs = []
        matricule = donnees.get("matricule", "").upper()
        if not matricule:
            erreurs.append("matricule manquant")
        elif matricule in matricules_fichier:
            erreurs.append("matricule en double dans le fichier")
        if not donnees.get("nom"):
            erreurs.append("nom manquant")

        cle_structure = donnees.get("structure", "")
        structure = structures.get(cle_structure.upper()) or structures.get(_normaliser(cle_structure))
        if cle_structure and structure is None:
            erreurs.append(f"structure inconnue : {cle_structure}")

        role = (donnees.get("role") or "AGENT").upper().replace(" ", "_")
        if role not in ROLES_VALIDES:
            erreurs.append(f"role inconnu : {donnees.get('role')}")
            role = "AGENT"

        date_service = donnees.get("date_prise_service", "")
        if date_service:
            valide = False
            for format_ in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
                try:
                    date_service = datetime.strptime(date_service[:10], format_).date().isoformat()
                    valide = True
                    break
                except ValueError:
                    continue
            if not valide:
                erreurs.append("date de prise de service illisible (attendu JJ/MM/AAAA)")
                date_service = ""

        droit = donnees.get("droit_conge", "")
        if droit and not droit.isdigit():
            erreurs.append("droit a conge non numerique")
            droit = ""

        matricules_fichier.add(matricule)
        resultats.append({
            "ligne": donnees.get("_ligne"),
            "matricule": matricule,
            "civilite": CIVILITES.get((donnees.get("civilite") or "M").upper(), "M"),
            "nom": donnees.get("nom", "").upper(),
            "prenoms": donnees.get("prenoms", ""),
            "email": donnees.get("email", ""),
            "telephone": donnees.get("telephone", ""),
            "structure_id": structure.pk if structure else None,
            "structure_libelle": structure.libelle_complet if structure else cle_structure,
            "fonction": donnees.get("fonction", ""),
            "grade": donnees.get("grade", ""),
            "role": role,
            "superieur": (donnees.get("superieur") or "").upper(),
            "date_prise_service": date_service,
            "lieu_service": donnees.get("lieu_service", ""),
            "droit_conge": droit,
            "erreurs": erreurs,
            "action": "erreur" if erreurs else ("mise_a_jour" if matricule in matricules_connus else "creation"),
        })
    return resultats


@transaction.atomic
def appliquer(resultats, auteur=None):
    """Cree ou met a jour les agents valides. Retourne un compte rendu."""
    compte = {"crees": 0, "mis_a_jour": 0, "ignores": 0}
    en_attente_superieur = []

    for ligne in resultats:
        if ligne["action"] == "erreur":
            compte["ignores"] += 1
            continue
        defauts = {
            "civilite": ligne["civilite"],
            "last_name": ligne["nom"],
            "first_name": ligne["prenoms"],
            "email": ligne["email"],
            "telephone": ligne["telephone"],
            "fonction": ligne["fonction"],
            "grade": ligne["grade"],
            "role": ligne["role"],
            "lieu_service": ligne["lieu_service"],
        }
        if ligne["structure_id"]:
            defauts["structure_id"] = ligne["structure_id"]
        if ligne["date_prise_service"]:
            defauts["date_prise_service"] = ligne["date_prise_service"]

        agent = Agent.objects.filter(matricule=ligne["matricule"]).first()
        if agent is None:
            agent = Agent(matricule=ligne["matricule"], **defauts)
            agent.set_password(ligne["matricule"])
            agent.doit_changer_mot_de_passe = True
            agent.save()
            compte["crees"] += 1
        else:
            for champ, valeur in defauts.items():
                if valeur:
                    setattr(agent, champ, valeur)
            agent.save()
            compte["mis_a_jour"] += 1

        if ligne["droit_conge"]:
            solde = SoldeConge.pour(agent)
            solde.droit_jours = int(ligne["droit_conge"])
            solde.save(update_fields=["droit_jours"])
        else:
            SoldeConge.pour(agent)

        if ligne["superieur"]:
            en_attente_superieur.append((agent.pk, ligne["superieur"]))

    for agent_id, matricule_superieur in en_attente_superieur:
        superieur = Agent.objects.filter(matricule=matricule_superieur).first()
        if superieur and superieur.pk != agent_id:
            Agent.objects.filter(pk=agent_id).update(superieur=superieur)

    return compte


def generer_modele():
    """Classeur Excel modele, avec une feuille d'aide listant structures et roles."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill

    classeur = Workbook()
    feuille = classeur.active
    feuille.title = "Agents"
    feuille.append(ENTETE_MODELE)
    for cellule in feuille[1]:
        cellule.font = Font(bold=True, color="FFFFFF")
        cellule.fill = PatternFill("solid", fgColor="14958A")
        cellule.alignment = Alignment(horizontal="center")
    feuille.append([
        "334446X", "M", "N'GORAN", "Koffi Evariste", "evariste.ngoran@dpfc.education.ci",
        "+225 07 00 00 00 00", "SDPRPN", "Chef de service", "Inspecteur", "CHEF_SERVICE",
        "100003S", "01/10/2019", "Abidjan", 30,
    ])
    for colonne, largeur in zip("ABCDEFGHIJKLMN", [14, 10, 18, 22, 32, 20, 16, 28, 18, 20, 16, 18, 16, 12]):
        feuille.column_dimensions[colonne].width = largeur

    aide = classeur.create_sheet("Aide")
    aide.append(["Structures disponibles (colonne « structure » : utilisez le sigle)"])
    aide["A1"].font = Font(bold=True)
    aide.append(["Sigle", "Libelle", "Rattachement"])
    for structure in Structure.objects.filter(active=True).order_by("rattachement", "nom"):
        aide.append([structure.sigle, structure.nom, structure.get_rattachement_display()])
    aide.append([])
    aide.append(["Roles acceptes (colonne « role »)"])
    for valeur, libelle in Agent.Role.choices:
        aide.append([valeur, libelle])
    aide.column_dimensions["A"].width = 22
    aide.column_dimensions["B"].width = 60
    aide.column_dimensions["C"].width = 28

    tampon = io.BytesIO()
    classeur.save(tampon)
    return tampon.getvalue()

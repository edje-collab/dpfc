"""
Extraction du texte des documents, pour la recherche plein texte.

Trois niveaux, du plus simple au plus couteux :

  1. fichier texte — lu directement ;
  2. PDF avec couche texte — lu par pypdf ;
  3. PDF scanne — necessite un moteur d'OCR, facultatif.

L'extraction ne doit jamais empecher le depot d'un document : toute erreur est
avalee et consignee, le document restant consultable, simplement non indexe.
"""
import logging

logger = logging.getLogger(__name__)

EXTENSIONS_TEXTE = {".txt", ".csv", ".md", ".json", ".xml", ".html", ".htm"}
TAILLE_MAX = 25 * 1024 * 1024  # au-dela, on n'indexe pas
LONGUEUR_MAX = 400_000  # caracteres conserves par document


def _extension(nom):
    point = nom.rfind(".")
    return nom[point:].lower() if point != -1 else ""


def _texte_brut(contenu):
    for encodage in ("utf-8", "latin-1"):
        try:
            return contenu.decode(encodage)
        except UnicodeDecodeError:
            continue
    return ""


def _texte_pdf(contenu):
    """Couche texte d'un PDF natif. Retourne une chaine vide pour un scan."""
    try:
        import io

        from pypdf import PdfReader

        lecteur = PdfReader(io.BytesIO(contenu))
        morceaux = []
        for page in lecteur.pages[:200]:
            try:
                morceaux.append(page.extract_text() or "")
            except Exception:  # une page illisible n'invalide pas les autres
                continue
        return "\n".join(morceaux)
    except ImportError:
        logger.info("pypdf absent : les PDF ne sont pas indexes.")
        return ""
    except Exception as erreur:
        logger.warning("PDF illisible a l'indexation : %s", erreur)
        return ""


def _texte_ocr(contenu):
    """
    Reconnaissance optique, pour les documents scannes.

    Le moteur est facultatif : s'il n'est pas installe, le document est
    simplement enregistre sans texte, sans que le depot echoue.
    """
    from importlib.util import find_spec

    if find_spec("pymupdf4llm") is None:
        logger.info("Aucun moteur d'OCR : les documents scannes ne sont pas indexes.")
        return ""
    try:
        import tempfile

        import pymupdf4llm

        with tempfile.NamedTemporaryFile(suffix=".pdf") as fichier:
            fichier.write(contenu)
            fichier.flush()
            # On borne a vingt pages : l'OCR est couteux et le but est d'indexer,
            # pas de restituer le document.
            return pymupdf4llm.to_markdown(fichier.name, pages=list(range(20)))
    except Exception as erreur:
        logger.warning("Echec de l'OCR a l'indexation : %s", erreur)
        return ""


def extraire_texte(nom, contenu, ocr=False):
    """
    Texte exploitable d'un fichier, ou chaine vide.

    `ocr` n'est tente que sur demande explicite : c'est une operation longue,
    reservee aux taches de fond.
    """
    if not contenu or len(contenu) > TAILLE_MAX:
        return ""
    extension = _extension(nom)

    if extension in EXTENSIONS_TEXTE:
        texte = _texte_brut(contenu)
    elif extension == ".pdf":
        texte = _texte_pdf(contenu)
        if not texte.strip() and ocr:
            texte = _texte_ocr(contenu)
    else:
        texte = ""

    return " ".join(texte.split())[:LONGUEUR_MAX]

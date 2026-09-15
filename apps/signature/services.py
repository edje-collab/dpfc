"""Operations cryptographiques : creation de bi-cles, signature et verification."""
import base64
import hashlib

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from django.utils import timezone

from .models import ALGORITHME, CleSignature, SignatureElectronique

TAILLE_CLE = 2048
DUREE_VALIDITE_ANS = 3


class ErreurSignature(Exception):
    """Code de signature invalide, cle absente ou revoquee."""


# --- Empreinte ---------------------------------------------------------------
def empreinte_document(demande) -> str:
    """SHA-256 du condense canonique de l'acte."""
    return hashlib.sha256(demande.condense().encode("utf-8")).hexdigest()


# --- Bi-cle ------------------------------------------------------------------
def creer_cle(agent, code_signature: str) -> CleSignature:
    """Genere (ou renouvelle) la bi-cle de l'agent. Le code chiffre la cle privee."""
    if len(code_signature or "") < 6:
        raise ErreurSignature("Le code de signature doit comporter au moins 6 caracteres.")

    privee = rsa.generate_private_key(public_exponent=65537, key_size=TAILLE_CLE)
    pem_privee = privee.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.BestAvailableEncryption(code_signature.encode()),
    ).decode()
    pem_publique = privee.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    empreinte = hashlib.sha256(pem_publique.encode()).hexdigest()

    aujourdhui = timezone.localdate()
    cle, _ = CleSignature.objects.update_or_create(
        agent=agent,
        defaults={
            "cle_publique": pem_publique,
            "cle_privee_chiffree": pem_privee,
            "empreinte": empreinte,
            "algorithme": ALGORITHME,
            "expire_le": aujourdhui.replace(year=aujourdhui.year + DUREE_VALIDITE_ANS),
            "revoquee": False,
            "motif_revocation": "",
        },
    )
    return cle


def revoquer_cle(agent, motif=""):
    cle = getattr(agent, "cle_signature", None)
    if cle is None:
        return None
    cle.revoquee = True
    cle.motif_revocation = motif
    cle.save(update_fields=["revoquee", "motif_revocation"])
    return cle


def _charger_cle_privee(cle: CleSignature, code_signature: str):
    try:
        return serialization.load_pem_private_key(
            cle.cle_privee_chiffree.encode(), password=code_signature.encode()
        )
    except (ValueError, TypeError) as err:
        raise ErreurSignature("Code de signature incorrect.") from err


# --- Signature ---------------------------------------------------------------
def signer_demande(demande, agent, code_signature, qualite="", validation=None, requete=None):
    """Appose la signature de l'agent sur l'acte et retourne la signature creee."""
    cle = getattr(agent, "cle_signature", None)
    if cle is None:
        raise ErreurSignature(
            "Aucune cle de signature n'est associee a votre compte. "
            "Creez-la depuis « Ma signature electronique »."
        )
    if not cle.est_valide:
        raise ErreurSignature("Votre cle de signature est revoquee ou expiree : renouvelez-la.")

    privee = _charger_cle_privee(cle, code_signature)
    empreinte = empreinte_document(demande)
    signature = privee.sign(
        empreinte.encode(),
        padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
        hashes.SHA256(),
    )
    ip = None
    if requete is not None:
        ip = requete.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip() or requete.META.get(
            "REMOTE_ADDR"
        )
    return SignatureElectronique.objects.create(
        demande=demande,
        validation=validation,
        signataire=agent,
        qualite=qualite or agent.fonction or agent.get_role_display(),
        empreinte_document=empreinte,
        valeur=base64.b64encode(signature).decode(),
        cle_publique=cle.cle_publique,
        algorithme=cle.algorithme,
        adresse_ip=ip or None,
    )


def verifier_signature(signature: SignatureElectronique) -> dict:
    """
    Verifie qu'une signature est cryptographiquement valide et que l'acte
    n'a pas ete modifie depuis son apposition.
    """
    resultat = {
        "signature_valide": False,
        "document_intact": False,
        "cle_revoquee": False,
        "message": "",
    }
    try:
        publique = serialization.load_pem_public_key(signature.cle_publique.encode())
        publique.verify(
            base64.b64decode(signature.valeur),
            signature.empreinte_document.encode(),
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
            hashes.SHA256(),
        )
        resultat["signature_valide"] = True
    except (InvalidSignature, ValueError):
        resultat["message"] = "La signature ne correspond pas a la cle publique du signataire."
        return resultat

    resultat["document_intact"] = empreinte_document(signature.demande) == signature.empreinte_document
    cle = getattr(signature.signataire, "cle_signature", None)
    resultat["cle_revoquee"] = bool(cle and cle.revoquee)

    if not resultat["document_intact"]:
        resultat["message"] = "L'acte a ete modifie apres signature : le document presente n'est pas authentique."
    elif resultat["cle_revoquee"]:
        resultat["message"] = "Signature valide, mais la cle du signataire a ete revoquee depuis."
    else:
        resultat["message"] = "Signature authentique : l'acte est conforme a l'original signe."
    return resultat


# --- Code a barres bidimensionnel -------------------------------------------
def qrcode_svg(donnees: str, taille=3):
    """QR code en SVG inline ; retourne None si la bibliotheque n'est pas installee."""
    try:
        import qrcode
        import qrcode.image.svg
    except ImportError:
        return None
    image = qrcode.make(
        donnees, box_size=taille, border=2, image_factory=qrcode.image.svg.SvgPathImage
    )
    from io import BytesIO

    tampon = BytesIO()
    image.save(tampon)
    return tampon.getvalue().decode()

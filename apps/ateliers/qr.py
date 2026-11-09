"""
Jetons de presence signes.

Le QR code ne porte aucune donnee personnelle : ni nom, ni matricule, ni
telephone. Il ne contient que deux identifiants courts et une signature, de
sorte qu'un code photographie ou perdu ne revele rien du participant.

    DPFC1.<atelier>.<participant>.<signature>
    signature = base32(HMAC-SHA256(cle de l'atelier, "DPFC1|atelier|participant"))[:16]

La cle est propre a chaque atelier : un jeton valable pour un atelier ne vaut
rien pour un autre.
"""
import base64
import hashlib
import hmac

PREFIXE = "DPFC1"
LONGUEUR_SIGNATURE = 16


def signer(cle, atelier, participant):
    message = f"{PREFIXE}|{atelier}|{participant}".encode()
    empreinte = hmac.new(cle.encode(), message, hashlib.sha256).digest()
    return base64.b32encode(empreinte).decode()[:LONGUEUR_SIGNATURE]


def jeton(atelier, participant):
    """Jeton a encoder dans le QR code du participant."""
    signature = signer(atelier.cle, atelier.id_court, participant.id_court)
    return f"{PREFIXE}.{atelier.id_court}.{participant.id_court}.{signature}"


def lire(valeur, cle, id_court_atelier):
    """
    Identifiant court du participant, ou None si le jeton est invalide.

    Un jeton d'un autre atelier, altere ou mal forme est rejete sans
    distinction : le controleur n'a pas a savoir laquelle des trois causes
    s'applique.
    """
    morceaux = (valeur or "").strip().split(".")
    if len(morceaux) != 4 or morceaux[0] != PREFIXE or morceaux[1] != id_court_atelier:
        return None
    attendue = signer(cle, morceaux[1], morceaux[2])
    return morceaux[2] if hmac.compare_digest(attendue, morceaux[3]) else None

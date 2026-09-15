"""
Signature electronique des actes administratifs.

Chaque signataire dispose d'une bi-cle RSA 2048 : la cle privee est conservee
chiffree par un code de signature que seul l'agent connait, le serveur ne
stocke jamais ce code. La signature porte sur l'empreinte SHA-256 du condense
canonique de l'acte : toute modification ulterieure de l'acte rend la
verification negative.
"""
import secrets

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone

ALGORITHME = "RSA-2048 / RSASSA-PSS / SHA-256"


def _code_verification():
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    bloc = lambda: "".join(secrets.choice(alphabet) for _ in range(4))  # noqa: E731
    return f"DPFC-{bloc()}-{bloc()}-{bloc()}"


class CleSignature(models.Model):
    """Bi-cle de signature d'un agent habilite a signer des actes."""

    agent = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="cle_signature"
    )
    cle_publique = models.TextField("cle publique (PEM)")
    cle_privee_chiffree = models.TextField("cle privee chiffree (PEM)")
    empreinte = models.CharField("empreinte de la cle publique", max_length=64, unique=True)
    algorithme = models.CharField(max_length=60, default=ALGORITHME)
    creee_le = models.DateTimeField(auto_now_add=True)
    expire_le = models.DateField("valable jusqu'au", null=True, blank=True)
    revoquee = models.BooleanField("revoquee", default=False)
    motif_revocation = models.CharField(max_length=200, blank=True)

    class Meta:
        verbose_name = "cle de signature"
        verbose_name_plural = "cles de signature"

    def __str__(self):
        return f"Cle de {self.agent} ({self.empreinte[:16]}...)"

    @property
    def est_valide(self):
        if self.revoquee:
            return False
        if self.expire_le and self.expire_le < timezone.localdate():
            return False
        return True

    @property
    def empreinte_lisible(self):
        brut = self.empreinte.upper()
        return " ".join(brut[i:i + 4] for i in range(0, 32, 4))


class SignatureElectronique(models.Model):
    """Signature apposee par une autorite sur un acte administratif."""

    demande = models.ForeignKey(
        "rh.Demande", on_delete=models.CASCADE, related_name="signatures", verbose_name="acte"
    )
    validation = models.OneToOneField(
        "rh.Validation", on_delete=models.SET_NULL, null=True, blank=True, related_name="signature"
    )
    signataire = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="signatures_apposees"
    )
    qualite = models.CharField("qualite du signataire", max_length=150)
    empreinte_document = models.CharField("empreinte de l'acte (SHA-256)", max_length=64)
    valeur = models.TextField("signature (base64)")
    cle_publique = models.TextField("cle publique au moment de la signature")
    algorithme = models.CharField(max_length=60, default=ALGORITHME)
    code_verification = models.CharField(max_length=24, unique=True, default=_code_verification)
    horodatage = models.DateTimeField(auto_now_add=True)
    adresse_ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        verbose_name = "signature electronique"
        verbose_name_plural = "signatures electroniques"
        ordering = ["horodatage"]

    def __str__(self):
        return f"{self.code_verification} - {self.signataire}"

    def get_absolute_url(self):
        return reverse("signature:verification", args=[self.code_verification])

    @property
    def empreinte_lisible(self):
        brut = self.empreinte_document.upper()
        return " ".join(brut[i:i + 8] for i in range(0, 64, 8))

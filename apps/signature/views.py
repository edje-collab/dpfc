from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from apps.core.models import JournalAction

from .forms import CreationCleForm, RevocationForm, VerificationForm
from .models import SignatureElectronique
from .services import ErreurSignature, creer_cle, qrcode_svg, revoquer_cle, verifier_signature


@login_required
def ma_cle(request):
    """Creation, renouvellement ou revocation de la bi-cle de signature."""
    cle = getattr(request.user, "cle_signature", None)
    form = CreationCleForm(request.POST or None)
    form_revocation = RevocationForm()

    if request.method == "POST" and request.POST.get("action") == "revoquer":
        form_revocation = RevocationForm(request.POST)
        if form_revocation.is_valid():
            revoquer_cle(request.user, form_revocation.cleaned_data["motif"])
            JournalAction.tracer(request.user, "Revocation de la cle de signature", requete=request)
            messages.warning(request, "Votre cle de signature est revoquee.")
            return redirect("signature:ma_cle")
    elif request.method == "POST" and form.is_valid():
        try:
            cle = creer_cle(request.user, form.cleaned_data["code"])
        except ErreurSignature as err:
            messages.error(request, str(err))
        else:
            JournalAction.tracer(
                request.user, "Creation d'une cle de signature", cle.empreinte[:16], requete=request
            )
            messages.success(
                request,
                "Cle de signature creee. Conservez votre code : il vous sera demande a chaque signature.",
            )
            return redirect("signature:ma_cle")

    return render(
        request,
        "intranet/signature_cle.html",
        {
            "cle": cle,
            "form": form,
            "form_revocation": form_revocation,
            "signatures": SignatureElectronique.objects.filter(signataire=request.user)
            .select_related("demande")[:20],
        },
    )


def verification(request, code=None):
    """Page publique de verification de l'authenticite d'un acte signe."""
    form = VerificationForm(request.GET or None)
    if code is None and form.is_valid():
        code = form.cleaned_data["code"].strip().upper()

    contexte = {"form": form, "code": code}
    if code:
        signature = SignatureElectronique.objects.filter(
            code_verification__iexact=code
        ).select_related("demande", "demande__agent", "signataire").first()
        if signature is None:
            contexte["introuvable"] = True
        else:
            contexte["signature"] = signature
            contexte["resultat"] = verifier_signature(signature)
    return render(request, "public/verification.html", contexte)


@login_required
def qr_acte(request, pk):
    """Fragment SVG du code de verification, insere dans le document imprimable."""
    signature = get_object_or_404(SignatureElectronique, pk=pk)
    url = request.build_absolute_uri(signature.get_absolute_url())
    return render(
        request, "intranet/_qr.html", {"svg": qrcode_svg(url), "url": url, "signature": signature}
    )

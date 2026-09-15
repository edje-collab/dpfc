from django.contrib import admin

from .models import CleSignature, SignatureElectronique


@admin.register(CleSignature)
class CleSignatureAdmin(admin.ModelAdmin):
    list_display = ("agent", "empreinte", "creee_le", "expire_le", "revoquee")
    list_filter = ("revoquee",)
    search_fields = ("agent__last_name", "agent__matricule", "empreinte")
    readonly_fields = ("cle_publique", "cle_privee_chiffree", "empreinte", "creee_le")


@admin.register(SignatureElectronique)
class SignatureElectroniqueAdmin(admin.ModelAdmin):
    list_display = ("code_verification", "demande", "signataire", "qualite", "horodatage")
    search_fields = ("code_verification", "demande__numero", "signataire__last_name")
    readonly_fields = [f.name for f in SignatureElectronique._meta.fields]

    def has_add_permission(self, request):
        return False

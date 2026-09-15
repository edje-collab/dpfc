from django.contrib import admin

from .models import ConfigurationSite, JournalAction, Region, Structure


@admin.register(Region)
class RegionAdmin(admin.ModelAdmin):
    list_display = ("nom", "code", "chef_lieu", "dren")
    search_fields = ("nom", "code", "chef_lieu")


@admin.register(Structure)
class StructureAdmin(admin.ModelAdmin):
    list_display = ("nom", "sigle", "type", "rattachement", "region", "drenaet", "responsable", "active")
    list_filter = ("type", "rattachement", "active", "region")
    search_fields = ("nom", "sigle")
    autocomplete_fields = ("parent", "region", "responsable", "drenaet")
    prepopulated_fields = {"slug": ("nom",)}


@admin.register(ConfigurationSite)
class ConfigurationSiteAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return not ConfigurationSite.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(JournalAction)
class JournalActionAdmin(admin.ModelAdmin):
    list_display = ("horodatage", "agent", "action", "objet", "adresse_ip")
    list_filter = ("action",)
    search_fields = ("action", "objet", "details")
    readonly_fields = [f.name for f in JournalAction._meta.fields]

    def has_add_permission(self, request):
        return False

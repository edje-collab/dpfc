from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from apps.contenus import views as vues_publiques

urlpatterns = [
    path("admin/", admin.site.urls),
    # --- Intranet agents (authentifie) ---
    path("intranet/", include("apps.accounts.urls")),
    path("intranet/rh/", include("apps.rh.urls")),
    # --- Signature electronique et verification publique ---
    path("", include("apps.signature.urls")),
    # --- API REST (application mobile Flutter) ---
    path("api/v1/", include("apps.api.urls")),
    # --- Site public (rendu serveur) ---
    path("", include("apps.contenus.urls")),
]

handler404 = vues_publiques.page_404
handler500 = vues_publiques.page_500

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.BASE_DIR / "static")

admin.site.site_header = "Administration du portail DPFC"
admin.site.site_title = "Portail DPFC"
admin.site.index_title = "Gestion des contenus et des agents"

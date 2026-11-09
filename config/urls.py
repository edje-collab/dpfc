from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from wagtail import urls as wagtail_urls
from wagtail.admin import urls as wagtailadmin_urls
from wagtail.documents import urls as wagtaildocs_urls

from apps.site_public import views as vues_publiques

urlpatterns = [
    # --- Administration Django : agents, RH, signature ---
    path("admin/", admin.site.urls),
    # --- Administration Wagtail : site public ---
    path("cms/", include(wagtailadmin_urls)),
    path("documents/", include(wagtaildocs_urls)),
    # --- Intranet agents (authentifie) ---
    path("intranet/", include("apps.accounts.urls")),
    path("intranet/rh/", include("apps.rh.urls")),
    path("intranet/pilotage/", include("apps.activites.urls")),
    # --- Signature electronique et verification publique ---
    path("", include("apps.signature.urls")),
    # --- API REST (application mobile Flutter) ---
    path("api/v1/", include("apps.api.urls")),
    path("api/v1/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/v1/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="documentation-api",
    ),
    # --- Site public : recherche (vue Django) puis pages Wagtail ---
    path("", include("apps.site_public.urls")),
]

handler404 = vues_publiques.page_404
handler500 = vues_publiques.page_500

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.BASE_DIR / "static")

# Les pages Wagtail repondent en dernier recours, sur toute URL restante.
urlpatterns += [path("", include(wagtail_urls))]

admin.site.site_header = "Administration du portail DPFC - espace agent"
admin.site.site_title = "Portail DPFC"
admin.site.index_title = "Agents, ressources humaines et signature"

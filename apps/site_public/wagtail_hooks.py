"""Integration a l'administration Wagtail : snippets, menu, comportements."""
from wagtail import hooks
from wagtail.snippets.models import register_snippet
from wagtail.snippets.views.snippets import SnippetViewSet, SnippetViewSetGroup

from .models import Categorie, MessageContact, PageActualite, Ressource


class RessourceViewSet(SnippetViewSet):
    model = Ressource
    icon = "doc-full-inverse"
    menu_label = "Ressources pedagogiques"
    list_display = ("titre", "type", "niveau", "discipline", "classe", "telechargements", "publiee")
    list_filter = ("type", "niveau", "publiee")
    search_fields = ("titre", "description", "discipline")
    ordering = ("type", "titre")


class CategorieViewSet(SnippetViewSet):
    model = Categorie
    icon = "tag"
    menu_label = "Categories d'actualites"
    list_display = ("nom", "couleur")
    search_fields = ("nom",)


class MessageContactViewSet(SnippetViewSet):
    model = MessageContact
    icon = "mail"
    menu_label = "Messages de contact"
    list_display = ("sujet", "nom", "email", "structure_destinataire", "etat", "recu_le")
    list_filter = ("etat", "structure_destinataire")
    search_fields = ("nom", "email", "sujet", "message")
    ordering = ("-recu_le",)


class SitePublicGroupe(SnippetViewSetGroup):
    menu_label = "Contenus"
    menu_icon = "folder-open-inverse"
    menu_order = 200
    items = (RessourceViewSet, CategorieViewSet, MessageContactViewSet)


register_snippet(SitePublicGroupe)


@hooks.register("after_create_page")
def renseigner_auteur(request, page):
    """L'agent qui cree une actualite en devient l'auteur par defaut."""
    if isinstance(page, PageActualite) and not page.auteur_id:
        PageActualite.objects.filter(pk=page.pk).update(auteur=request.user)

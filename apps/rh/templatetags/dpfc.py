from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter
def initiales(agent):
    return getattr(agent, "initiales", "?")


@register.filter
def pastille_statut(demande):
    """Pastille coloree representant l'etat d'une demande."""
    classe = getattr(demande, "couleur_statut", "neutre")
    return mark_safe(
        f'<span class="pastille pastille--{classe}">{demande.get_statut_display()}</span>'
    )


@register.filter
def classe_type(type_acte):
    return {
        "CONGE_ANNUEL": "conge",
        "CONGE_EXCEPTIONNEL": "conge",
        "PERMISSION": "permission",
        "ORDRE_MISSION": "mission",
        "ABSENCE": "absence",
        "FORMATION": "formation",
    }.get(type_acte, "autre")


@register.simple_tag(takes_context=True)
def url_avec(context, **kwargs):
    """Reconstruit l'URL courante en remplacant certains parametres GET."""
    params = context["request"].GET.copy()
    for cle, valeur in kwargs.items():
        if valeur in (None, ""):
            params.pop(cle, None)
        else:
            params[cle] = valeur
    return f"?{params.urlencode()}" if params else "?"

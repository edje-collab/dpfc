"""Reglages de generation du schema OpenAPI."""


def limiter_a_l_api_publique(endpoints, **kwargs):
    """
    Ne documente que l'API du portail.

    Les API internes de Wagtail (/cms/api/...) et l'administration Django ne
    font pas partie du contrat offert a l'application mobile.
    """
    return [
        (chemin, motif, methode, vue)
        for chemin, motif, methode, vue in endpoints
        if chemin.startswith("/api/v1/")
    ]

"""
Circuits modeles livres avec la plateforme.

Ils reprennent l'organisation de la direction : la direction centrale instruit
ses actes par la voie hierarchique, tandis qu'une antenne regionale et le CNRPN
sont autonomes — leur responsable decide seul, sauf lorsque l'acte sort de son
ressort ou le concerne personnellement.

Ces circuits sont modifiables dans l'administration ; un perimetre peut en
definir un qui lui est propre, qui prend alors le pas sur le modele.
"""
from apps.core.models import Perimetre

from .models import Circuit, Condition, Designation, Etape

# Types d'actes couverts : actes administratifs (apps.rh.models.TypeDemande)
# et pieces soumises au parapheur (apps.courrier.models).
TYPES_ACTES = [
    "CONGE_ANNUEL",
    "CONGE_EXCEPTIONNEL",
    "PERMISSION",
    "ORDRE_MISSION",
    "ABSENCE",
    "FORMATION",
]
TYPE_PARAPHEUR = "PARAPHEUR"

ROLE_RH = "RH"
ROLE_DIRECTEUR = "DIRECTEUR"

# --- Direction centrale ------------------------------------------------------
# Voie hierarchique : superieur, sous-directeur, visa du personnel, signature.
ETAPES_CENTRALE = [
    {
        "libelle": "Avis du superieur hierarchique",
        "designation": Designation.SUPERIEUR,
        "conditions": [],
    },
    {
        "libelle": "Avis du sous-directeur",
        "designation": Designation.RESPONSABLE_SOUS_DIRECTION,
        "conditions": [],
    },
    {
        "libelle": "Visa du service du personnel",
        "designation": Designation.ROLE,
        "role": ROLE_RH,
        "conditions": [Condition.SI_VISA_RH],
    },
    {
        "libelle": "Signature du directeur",
        "designation": Designation.ROLE,
        "role": ROLE_DIRECTEUR,
        "conditions": [Condition.SI_SIGNATURE_DIRECTEUR],
    },
]


def _etapes_perimetre_autonome(libelle_responsable):
    """
    Circuit d'une antenne ou du CNRPN.

    Cas courant : le responsable du perimetre decide seul.
    Mission hors ressort : son avis, puis etablissement de l'acte par la DRENA.
    Acte du responsable lui-meme : avis de la DRENA puis, si l'acte l'exige,
    visa du service du personnel et signature du directeur.
    """
    return [
        {
            "libelle": f"Decision du {libelle_responsable}",
            "designation": Designation.RESPONSABLE_PERIMETRE,
            "conditions": [Condition.SI_AGENT_NEST_PAS_RESPONSABLE],
        },
        {
            "libelle": "Etablissement de l'acte par le directeur regional (DRENA)",
            "designation": Designation.DIRECTEUR_REGIONAL,
            "conditions": [Condition.SI_HORS_PERIMETRE],
        },
        {
            "libelle": "Avis du directeur regional (DRENA)",
            "designation": Designation.DIRECTEUR_REGIONAL,
            "conditions": [Condition.SI_AGENT_EST_RESPONSABLE],
        },
        {
            "libelle": "Visa du service du personnel",
            "designation": Designation.ROLE,
            "role": ROLE_RH,
            # Le visa du personnel et la signature du directeur sont exclusifs :
            # l'acte qui remonte au directeur n'est pas vise separement.
            "conditions": [
                Condition.SI_AGENT_EST_RESPONSABLE,
                Condition.SI_VISA_RH,
                Condition.SI_SANS_SIGNATURE_DIRECTEUR,
            ],
        },
        {
            "libelle": "Signature du directeur de la pedagogie",
            "designation": Designation.ROLE,
            "role": ROLE_DIRECTEUR,
            "conditions": [Condition.SI_AGENT_EST_RESPONSABLE, Condition.SI_SIGNATURE_DIRECTEUR],
        },
    ]


# Le CNRPN n'a pas de ressort regional : les actes de son chef remontent
# directement a la direction centrale.
ETAPES_CENTRE = [
    {
        "libelle": "Decision du chef de centre (CNRPN)",
        "designation": Designation.RESPONSABLE_PERIMETRE,
        "conditions": [Condition.SI_AGENT_NEST_PAS_RESPONSABLE],
    },
    {
        "libelle": "Visa du service du personnel",
        "designation": Designation.ROLE,
        "role": ROLE_RH,
        # Exclusif de la signature du directeur, comme dans les antennes.
        "conditions": [
            Condition.SI_AGENT_EST_RESPONSABLE,
            Condition.SI_VISA_RH,
            Condition.SI_SANS_SIGNATURE_DIRECTEUR,
        ],
    },
    {
        "libelle": "Signature du directeur de la pedagogie",
        "designation": Designation.ROLE,
        "role": ROLE_DIRECTEUR,
        "conditions": [Condition.SI_AGENT_EST_RESPONSABLE, Condition.SI_SIGNATURE_DIRECTEUR],
    },
]

MODELES = {
    Perimetre.Type.CENTRALE: ETAPES_CENTRALE,
    Perimetre.Type.ANTENNE: _etapes_perimetre_autonome("chef d'antenne (APFC)"),
    Perimetre.Type.CENTRE: ETAPES_CENTRE,
}


# --- Parapheur ---------------------------------------------------------------
# Une piece remonte la voie hierarchique jusqu'au responsable du perimetre,
# qui donne le dernier visa. La direction centrale intercale son sous-directeur.
def _etapes_parapheur(avec_sous_direction):
    etapes = [
        {
            "libelle": "Visa du superieur hierarchique",
            "designation": Designation.SUPERIEUR,
            "conditions": [],
        },
    ]
    if avec_sous_direction:
        etapes.append(
            {
                "libelle": "Visa du sous-directeur",
                "designation": Designation.RESPONSABLE_SOUS_DIRECTION,
                "conditions": [],
            }
        )
    etapes.append(
        {
            "libelle": "Visa du responsable du perimetre",
            "designation": Designation.RESPONSABLE_PERIMETRE,
            "conditions": [],
        }
    )
    return etapes


MODELES_PARAPHEUR = {
    Perimetre.Type.CENTRALE: _etapes_parapheur(avec_sous_direction=True),
    Perimetre.Type.ANTENNE: _etapes_parapheur(avec_sous_direction=False),
    Perimetre.Type.CENTRE: _etapes_parapheur(avec_sous_direction=False),
}


def installer_circuits_modeles(remplacer=False):
    """
    Cree les circuits modeles manquants.

    Idempotent : un circuit deja present n'est pas touche, sauf si `remplacer`
    est demande, auquel cas ses etapes sont reecrites.
    """
    crees, inchanges = 0, 0
    definitions = [
        (type_perimetre, type_acte, etapes)
        for type_perimetre, etapes in MODELES.items()
        for type_acte in TYPES_ACTES
    ] + [
        (type_perimetre, TYPE_PARAPHEUR, etapes)
        for type_perimetre, etapes in MODELES_PARAPHEUR.items()
    ]

    for type_perimetre, type_acte, etapes in definitions:
        circuit, nouveau_circuit = Circuit.objects.get_or_create(
            perimetre=None,
            type_perimetre=type_perimetre,
            type_acte=type_acte,
            defaults={"libelle": f"Circuit modele {type_perimetre} - {type_acte}"},
        )
        if not nouveau_circuit and not remplacer:
            inchanges += 1
            continue
        circuit.etapes.all().delete()
        for ordre, etape in enumerate(etapes, start=1):
            Etape.objects.create(
                circuit=circuit,
                ordre=ordre,
                libelle=etape["libelle"],
                designation=etape["designation"],
                role=etape.get("role", ""),
                conditions=list(etape["conditions"]),
            )
        crees += 1
    return crees, inchanges

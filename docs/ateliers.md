# Ateliers et émargement

Voir [l'ADR 0007](adr/0007-emargement-par-qr-code.md) pour les décisions de conception.

## Cycle d'un atelier

```
Planifié ──ouverture──▶ En cours ──clôture──▶ Clos
    │                       │
    └────── annulation (motif obligatoire) ──▶ Annulé
```

L'émargement n'est possible que sur un atelier planifié ou en cours. Un atelier sans session ne peut pas être ouvert.

| Action | Qui |
|---|---|
| Créer, modifier, ouvrir, clore, annuler | Organisateur, responsable **désigné** du périmètre, direction |
| Inscrire des participants, imprimer les badges | Idem |
| Émarger | Organisateur, contrôleurs désignés, responsable du périmètre, direction |

## Sessions

Une session est une **journée** ou une **demi-journée**. Au choix à la création :

| Découpage | Effet |
|---|---|
| Une session par journée | Présence constatée à la journée |
| Matinée et après-midi | Permet de constater une présence partielle |

Une demi-journée compte pour 0,5 jour dans l'état de paiement.

## Badges et QR codes

`/intranet/ateliers/<id>/badges/` imprime une planche de badges. Chaque badge porte le QR code du participant et, sous le code, le jeton en clair — utilisable au clavier si le scanner tombe en panne.

Le QR **ne contient aucune donnée personnelle** : deux identifiants courts et une signature. Un badge perdu ne révèle rien.

## Émargement

### Depuis l'intranet

`/intranet/ateliers/<id>/emargement/` ouvre l'écran de scan. Le champ reste actif après chaque validation : on enchaîne les scans sans toucher à la souris. Un second scan du même participant signale « déjà émargé » sans créer de doublon.

L'**émargement manuel** est possible quand le QR ne peut pas être lu. Le motif est obligatoire et conservé.

### Depuis le terrain, hors ligne

L'application mobile télécharge l'atelier et sa liste de participants avant de partir, scanne hors ligne, puis dépose son lot dès que le réseau revient.

```
GET  /api/v1/ateliers/<id>/                  atelier et ses sessions
GET  /api/v1/ateliers/<id>/participants/     liste à embarquer
POST /api/v1/ateliers/<id>/emargements/      dépôt du lot
```

Le lot porte, pour chaque présence, un `identifiant` UUID **produit par l'appareil**. C'est lui qui rend l'opération idempotente : rejouer le même lot après une coupure n'enregistre rien de plus et ne perd rien.

La réponse détaille ce qui a été retenu :

```json
{"enregistres": 48, "doublons": 2, "invalides": 1, "details": [...]}
```

## Ce qui découle de l'émargement

| Sortie | Règle |
|---|---|
| État de paiement | Seuls les participants ayant émargé ; montant = barème × journées constatées |
| Attestation | Réservée à qui a émargé au moins la moitié des sessions |
| Feuille de présence | Grille participants × sessions, exportable en CSV |
| Plan d'action | À la clôture, les présences sont reportées sur l'activité rattachée |

### Barèmes

`/admin/` → Barèmes de participation. Chaque catégorie porte un montant journalier ; un participant sans catégorie apparaît dans l'état à zéro.

## Écrans

| Écran | Adresse |
|---|---|
| Tableau des ateliers | `/intranet/ateliers/` |
| Liste et recherche | `/intranet/ateliers/liste/` |
| Fiche d'un atelier | `/intranet/ateliers/<id>/` |
| Participants | `/intranet/ateliers/<id>/participants/` |
| Badges à imprimer | `/intranet/ateliers/<id>/badges/` |
| Écran d'émargement | `/intranet/ateliers/<id>/emargement/` |
| État de paiement | `/intranet/ateliers/<id>/paiement/` |
| Attestation | `/intranet/ateliers/participants/<id>/attestation/` |

## Jeu de démonstration

```bash
python manage.py charger_ateliers
```

Couvre : un atelier clos entièrement émargé avec son compte rendu, un atelier en cours à présences partielles dont un émargement manuel motivé, un atelier planifié dont les badges restent à imprimer, une journée d'antenne découpée en demi-journées, et un atelier annulé.

# Pilotage des activités

Chaque périmètre de gestion établit son plan d'action annuel, le fait valider, puis rend compte de son exécution. Voir [l'ADR 0005](adr/0005-pilotage-par-plan-d-action.md) pour les décisions de conception.

## Cycle du plan d'action

```
En préparation ──soumission──▶ Soumis ──validation──▶ Validé ──clôture──▶ Clos
       ▲                          │
       └──────── renvoi ──────────┘
```

| Étape | Qui | Conditions |
|---|---|---|
| Établir le plan | Responsable du périmètre (directeur, chef d'antenne, chef de centre) | Un seul plan par périmètre et par année |
| Inscrire des activités | Responsable du périmètre | Tant que le plan n'est pas validé |
| Soumettre | Responsable du périmètre | Au moins une activité inscrite |
| Valider ou renvoyer | Direction centrale | Le renvoi exige un motif |
| Rendre compte | Responsable de l'activité, chef du périmètre, direction | Plan validé, activité non close |
| Clore l'exercice | Direction centrale | Plan validé ; les activités ouvertes sont reportées |

## Rendre compte d'une activité

On ne modifie pas directement l'avancement : on dépose un **point d'avancement** qui indique le taux atteint à ce jour — non la progression de la période —, les réalisations, les difficultés, les bénéficiaires touchés et le montant engagé sur la période.

L'activité en découle :

- son avancement suit le dernier compte rendu ;
- les bénéficiaires et les montants se cumulent sur l'ensemble des comptes rendus ;
- elle passe **en cours** à la première déclaration, **réalisée** à 100 % ;
- les dates réelles de début et de fin sont renseignées automatiquement.

## Ce que mesure chaque taux

| Taux | Calcul | Remarque |
|---|---|---|
| Exécution physique d'une activité | Dernier point d'avancement | |
| Exécution physique d'un plan | Moyenne des avancements | Les activités annulées sont exclues |
| Exécution budgétaire | Montants engagés / budget prévu | |
| Couverture des bénéficiaires | Bénéficiaires touchés / prévus | |
| Atteinte d'un indicateur | Valeur réalisée / cible, plafonnée à 100 % | |

## Écrans

| Écran | Adresse | Contenu |
|---|---|---|
| Tableau de bord | `/intranet/pilotage/` | Indicateurs de l'exercice, activités en retard, consolidation nationale pour la direction |
| Plans d'action | `/intranet/pilotage/plans/` | Liste et cycle de vie des plans |
| Chronogramme | `/intranet/pilotage/plans/<id>/chronogramme/` | Activités positionnées sur les douze mois |
| Registre des activités | `/intranet/pilotage/activites/` | Recherche, filtres par axe, statut, périmètre et retard ; export CSV |
| Axes et périmètres | `/intranet/pilotage/axes/` | Référentiel des axes, liste des périmètres et de leurs responsables |

## Application mobile

| Méthode | Chemin | Rôle |
|---|---|---|
| GET | `/api/v1/pilotage/` | Synthèse pour l'écran d'accueil |
| GET | `/api/v1/plans/` | Plans visibles par l'agent |
| GET | `/api/v1/activites/` | Activités du périmètre — filtres `annee`, `statut`, `retard`, `mes_activites` |
| POST | `/api/v1/activites/<id>/avancement/` | Compte rendu depuis le terrain, pièce jointe comprise |

Toutes ces routes sont cloisonnées par périmètre : un chef d'antenne ne voit que son antenne.

## Jeu de démonstration

`python manage.py initialiser_dpfc --demo` charge un jeu couvrant tous les cas de gestion :

- un plan **en préparation**, un plan **soumis**, trois plans **validés** et un plan **clos** de l'exercice précédent ;
- des activités **planifiées**, **en cours**, **réalisées**, **en retard**, **reportées** et **annulées** ;
- les trois types de périmètre, chacun avec son responsable ;
- des indicateurs atteints, partiellement atteints et dépassés.

Les dates sont relatives au jour du chargement : la démonstration montre le même équilibre quelle que soit la période de l'année.

```bash
python manage.py charger_pilotage
```

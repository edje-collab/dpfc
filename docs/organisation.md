# Organisation de la direction dans la plateforme

Référence : **décret n° 2026-509 du 05 août 2026** portant organisation du Ministère de l'Éducation Nationale, de l'Alphabétisation et de l'Enseignement Technique.

## Ce que dit le décret

**Article 27.** La Direction Générale de la Pédagogie, des Curricula et du Suivi des Programmes (DGPCSP) comprend trois directions centrales :

- la **Direction de la Pédagogie et de la Formation Continue (DPFC)** ;
- la Direction de la Veille et du Suivi des Programmes ;
- la Direction des Matériels Didactiques.

**Article 28.** La DPFC est chargée de gérer et suivre les activités pédagogiques du préscolaire, du primaire et du secondaire général ; de promouvoir la qualité de l'enseignement et l'usage des nouvelles technologies ; d'élaborer et promouvoir les programmes en langues nationales ; d'assurer la formation continue des personnels enseignants et d'encadrement pédagogique ; de produire les rapports stratégiques et outils d'aide à la décision.

Elle comprend **trois sous-directions** :

| Sigle | Sous-direction |
|---|---|
| SDPPBS | Sous-direction des Programmes Pédagogiques et des Bibliothèques Scolaires |
| SDIP | Sous-direction des Innovations Pédagogiques |
| SDFPC | Sous-direction de la Formation Pédagogique Continue |

**Article 41.** Les services extérieurs du ministère sont les **DRENA** (directions régionales), les **DDENA** (directions départementales) et les **DRETPI** (directions régionales de l'enseignement technique et professionnel initial).

> Le décret ne mentionne ni les antennes régionales ni le CNRPN : l'article 1 renvoie à un arrêté du ministre le soin d'organiser les services extérieurs et les structures rattachées. La plateforme les traite donc comme des structures créées par arrêté.

## Périmètres de gestion autonome

Trois familles de périmètres, au sens de [l'ADR 0002](adr/0002-perimetres-de-gestion-autonome.md) :

| Type | Périmètre | Dirigé par | Autonome |
|---|---|---|---|
| `CENTRALE` | DPFC (direction et sous-directions) | Directeur de la pédagogie et de la formation continue | non |
| `ANTENNE` | Une par APFC régionale | Chef d'antenne | oui |
| `CENTRE` | CNRPN | Chef de centre | oui |

Autonome signifie : le responsable instruit et décide seul les actes de ses agents, le périmètre tient sa propre série de numéros d'actes, et son responsable ne voit que ses propres agents.

## Circuits de validation livrés

### Direction centrale

1. Avis du supérieur hiérarchique
2. Avis du sous-directeur
3. Visa du service du personnel — *si le type d'acte l'exige*
4. Signature du directeur — *si le type d'acte l'exige*

### Antenne régionale (APFC)

- **Cas courant** : décision du chef d'antenne, et rien d'autre.
- **Mission hors du ressort de la DRENA** : avis du chef d'antenne, puis établissement de l'acte par le directeur régional, sur présentation des termes de référence et de la lettre d'invitation.
- **Acte du chef d'antenne lui-même** : avis du directeur régional (DRENA), puis visa du service du personnel *ou* signature du directeur selon le type d'acte.

### CNRPN

- **Cas courant** : décision du chef de centre.
- **Acte du chef de centre lui-même** : le CNRPN n'ayant pas de ressort régional, l'acte remonte directement au visa du service du personnel ou à la signature du directeur.

Ces circuits sont modifiables dans l'administration Django (`/admin/` → Circuits de validation). Un périmètre peut définir son propre circuit pour un type d'acte : il prime alors sur le modèle.

```bash
python manage.py installer_circuits --remplacer
```

## Reprise des données existantes

La migration `core.0006` convertit automatiquement une base antérieure :

- les structures de type `DRENAET` deviennent des `DRENA` ;
- un périmètre est créé pour la direction centrale, un par antenne et un par centre ;
- chaque structure est rattachée au périmètre correspondant.

### Point restant à trancher par la direction

L'organigramme antérieur comportait des sous-directions et services qui ne figurent pas dans le décret (par exemple « Sous-direction de la formation continue », « Sous-direction des programmes et manuels scolaires », « Service développement et production de ressources pédagogiques numériques »). La migration **les conserve en l'état** : décider de leur suppression, de leur fusion dans les trois nouvelles sous-directions, et du réaffectation des agents concernés relève de la direction, pas de la reprise technique.

Pour les lister :

```bash
python manage.py shell -c "from apps.core.models import Structure; print('\n'.join(f'{s.sigle} - {s.nom}' for s in Structure.objects.filter(rattachement='CENTRALE').exclude(sigle__in=['DGPCSP','DPFC','SDPPBS','SDIP','SDFPC','SPAA','CNRPN'])))"
```

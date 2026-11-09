# Portail de la Direction de la Pédagogie et de la Formation Continue (DPFC)

Plateforme de gestion de la direction, **monolithe Django modulaire** réunissant dans un seul dépôt :

| Brique | Description |
|---|---|
| **Site public** | Géré par **Wagtail** (CMS, administration sur `/cms/`), accessible sans compte : actualités, ressources pédagogiques, FOAD, projets, agenda, antennes régionales, contact. Contenu par blocs, médiathèque, brouillons/publication, prévisualisation. |
| **Plateforme de gestion** | Espace authentifié : plans d'action annuels, activités, chronogramme et tableaux de bord par périmètre, courrier arrivée/départ, imputations, bibliothèque documentaire et parapheur, **ateliers avec émargement par QR code utilisable hors ligne**, actes administratifs (congé, permission, ordre de mission, absence, formation), circuits de validation **paramétrables par périmètre**, planning, registre, annuaire. |
| **API REST** | `/api/v1/` avec jetons JWT, consommée par l'application mobile **Flutter** livrée dans `mobile/`. |
| **Signature électronique** | Bi-clés RSA 2048 par signataire, scellement SHA-256 des actes, page publique de vérification et QR code sur le document. |

L'organisation suit le **décret n° 2026-509 du 05 août 2026** : la DPFC relève de la Direction Générale de la Pédagogie, des Curricula et du Suivi des Programmes et comprend trois sous-directions. S'y ajoutent, par arrêté, des structures à **gestion autonome** — les antennes régionales (APFC), dirigées par un chef d'antenne, et le **CNRPN**, dirigé par un chef de centre.

Chaque agent relève d'un **périmètre de gestion** qui détermine son circuit de validation, la numérotation de ses actes et ce que son responsable peut voir. Voir [docs/organisation.md](docs/organisation.md).

---

## 1. Démarrage rapide

Avec Docker, voir [§ 12](#12-déploiement). En local, sans conteneur :

```bash
python -m venv .venv && source .venv/bin/activate
```

```bash
pip install -r requirements-dev.txt
```

```bash
cp .env.example .env
```

Laissez `POSTGRES_HOST` vide dans `.env` pour démarrer sur SQLite, puis :

```bash
python manage.py migrate
```

```bash
python manage.py initialiser_dpfc --demo
```

```bash
python manage.py runserver
```

- Site public : http://127.0.0.1:8000/
- Administration du site public (Wagtail) : http://127.0.0.1:8000/cms/ (`ADMIN01` / `dpfc2026!`)
- Espace agent : http://127.0.0.1:8000/intranet/connexion/
- Administration de la plateforme (Django) : http://127.0.0.1:8000/admin/ (`ADMIN01` / `dpfc2026!`)
- API : http://127.0.0.1:8000/api/v1/ — documentation : http://127.0.0.1:8000/api/v1/docs/

**Comptes de démonstration** (le mot de passe initial est le matricule) :

| Matricule | Profil | Rôle dans le circuit |
|---|---|---|
| `100001D` | Directrice | signature finale |
| `100002R` | Service du personnel | visa RH, gestion des comptes et des soldes |
| `100003S` | Sous-directrice | avis N2 pour le central |
| `100004C` | Chef de service | avis N1 pour le central |
| `100005A` | Agent (central) | dépôt de demandes |
| `200001B` | Chef d'antenne APFC (Bouaké) | décide seul des actes de son antenne |
| `200005B` | Secrétariat d'antenne (Bouaké) | dépose les demandes des agents de l'antenne |
| `200002B` | Agent (antenne de Bouaké) | dépôt de demandes |
| `300001B` | Directeur régional DRENA (Bouaké) | établit les ODM hors ressort |
| `400001N` | Chef de centre (CNRPN) | décide pour les agents du centre |

Les autorités signataires du jeu de démonstration disposent d'une clé de signature dont le code est `signature2026`.

## 2. Arborescence

```
dpfc/
├── config/              paramètres, URLs, WSGI/ASGI
├── apps/
│   ├── core/            régions, périmètres de gestion, structures (direction générale,
│   │                    direction, sous-directions, antennes, CNRPN, services extérieurs),
│   │                    configuration éditoriale, journal d'audit
│   ├── accounts/        modèle Agent (connexion par matricule), rôles, notifications,
│   │                    annuaire, organigramme, gestion des comptes
│   ├── circuits/        circuits de validation paramétrables par périmètre et type d'acte
│   ├── activites/       plans d'action annuels, activités, avancement, indicateurs,
│   │                    chronogramme et tableaux de bord
│   ├── courrier/        registre arrivée/départ, imputations, documents versionnés,
│   │                    recherche plein texte, parapheur, modèles de courrier
│   ├── ateliers/        ateliers, sessions, badges QR, émargement hors ligne,
│   │                    états de paiement et attestations
│   ├── site_public/     site public Wagtail : pages (accueil, éditoriales, actualités, projets,
│   │                    événements, antennes, contact), snippets (ressources, catégories, messages)
│   ├── rh/              actes administratifs, circuit de validation, soldes de congé,
│   │                    planning, registre, documents officiels imprimables
│   ├── signature/       bi-clés RSA, signature des actes, vérification publique
│   └── api/             sérialiseurs et points d'entrée REST (JWT) pour Flutter
├── templates/public/    gabarits du site public
├── templates/intranet/  gabarits de l'espace agent
├── static/              CSS, JS, images
├── mobile/              application Flutter (client de l'API)
├── infra/               Dockerfile, Docker Compose, Nginx
├── docs/                organisation, décisions d'architecture, schéma OpenAPI
└── deploiement/         systemd, Nginx (déploiement sans conteneur)
```

## 3. Modèle d'organisation

Conforme au décret n° 2026-509 du 05 août 2026 — détail dans [docs/organisation.md](docs/organisation.md).

- `Region` : région administrative et chef-lieu.
- `Perimetre` : **unité de gestion autonome**, de type `CENTRALE` (la DPFC), `ANTENNE` (une par APFC) ou `CENTRE` (le CNRPN). C'est dans le périmètre que les actes sont instruits, numérotés et pilotés. Sa structure de tête (`perimetre_racine`) désigne le responsable : directeur, chef d'antenne ou chef de centre.
- `Structure` : `DIRECTION_GENERALE`, `DIRECTION`, `SOUS_DIRECTION`, `SERVICE`, `CENTRE`, `ANTENNE`, `BUREAU`, `DRENA`, `DDENA`, `DRETPI`, avec un `parent`, un `rattachement` (`CENTRALE` ou `REGION`) et un `perimetre`. Chaque antenne porte une région et un champ `drena` : la direction régionale dans le ressort de laquelle elle exerce.
- `Agent` : compte de connexion (matricule ou courriel), affectation à une structure — dont il hérite son périmètre —, supérieur hiérarchique, rôle (`AGENT`, `SECRETARIAT`, `CHEF_SERVICE`, `SOUS_DIRECTEUR`, `CHEF_ANTENNE`, `CHEF_CENTRE`, `DIRECTEUR_REGIONAL`, `RH`, `DIRECTEUR`, `DIRECTEUR_GENERAL`, `ADMIN`) et situation administrative.

Organigramme livré par `initialiser_dpfc` :

```
DGPCSP  Direction Générale de la Pédagogie, des Curricula et du Suivi des Programmes
└── DPFC  Direction de la Pédagogie et de la Formation Continue      ← périmètre DPFC
    ├── SDPPBS  Sous-direction des Programmes Pédagogiques et des Bibliothèques Scolaires
    ├── SDIP    Sous-direction des Innovations Pédagogiques
    ├── SDFPC   Sous-direction de la Formation Pédagogique Continue
    ├── SPAA    Service du personnel et des affaires administratives
    ├── CNRPN   Centre National de Ressources Pédagogiques Numériques  ← périmètre CNRPN
    └── APFC-*  Antennes régionales de la pédagogie et de la formation continue
                                                                       ← un périmètre chacune
```

## 4. Actes administratifs et circuit de validation

Types gérés : congé annuel, congé exceptionnel, permission d'absence, ordre de mission, déclaration d'absence, demande de formation.

Les circuits ne sont plus codés : ils sont **paramétrés par périmètre et par type d'acte** dans l'administration (`/admin/` → Circuits de validation). Ce qui suit décrit les circuits livrés par défaut. Voir [ADR 0003](docs/adr/0003-circuits-parametrables.md).

### 4.1 Antennes (APFC) et CNRPN — autonomie de gestion

Chaque antenne gère son personnel sans remontée au niveau central :

```
Agent d'antenne → chef d'antenne (APFC)        [une seule étape, décision définitive]
   dépôt matériel assuré par le secrétariat de l'antenne
```

Le secrétariat (rôle `SECRETARIAT`) dépose la demande pour le compte de l'agent : tableau de bord → « Dépôt au secrétariat pour un agent ». La demande reste celle de l'agent ; le déposant est tracé dans le champ `depose_par`.

**Exception — mission hors du ressort de la DRENA :**

```
Agent d'antenne → chef d'antenne (avis) → DRENA (établissement et signature de l'ODM)
```

L'agent coche « mission hors du ressort de la DRENA » et joint obligatoirement :
- les **termes de référence** (TDR) ;
- la **lettre d'invitation ou d'information** de la structure d'accueil.

Sans ces deux pièces, la transmission est bloquée (validation côté formulaire et côté modèle). Le document produit porte alors « Directeur régional (DRENA) » comme autorité signataire.

Les actes du chef d'antenne lui-même remontent à la DRENA, puis à la direction centrale lorsque le type d'acte l'exige.

**Le CNRPN** suit le même principe : le chef de centre décide seul pour ses agents. N'ayant pas de ressort régional, ses propres actes remontent directement au service du personnel ou au directeur.

Les actes sont numérotés par périmètre, chacun tenant sa série annuelle : `PA-0001/2026/DPFC`, `PA-0001/2026/APFC-GBK`, `PA-0001/2026/CNRPN`.

### 4.2 Direction centrale

```
Agent au central : chef de service → sous-directeur → service du personnel → directeur
```

Les étapes « service du personnel » et « directeur » ne sont ajoutées que si le type d'acte l'exige (`REGLES_TYPE` dans `apps/rh/models.py`). Un même valideur n'apparaît jamais deux fois et ne valide jamais sa propre demande.

Règles appliquées :

- décompte en **jours ouvrables** (hors samedis, dimanches et jours fériés saisis dans l'intranet) ;
- numérotation automatique : `CG-0001/2026/DPFC`, `OM-0007/2026/DPFC`… ;
- décompte du solde de congé à l'approbation, restitué en cas d'annulation ;
- rejet à une étape : le circuit s'arrête, l'agent est notifié avec le motif ;
- notification interne + courriel à chaque étape ;
- après un ordre de mission, un **rapport de mission** est attendu au retour ;
- l'acte approuvé produit un **document officiel imprimable** (décision de congé, autorisation d'absence, ordre de mission) avec visas et référence de contrôle.

Réglages métier dans `config/settings.py` :

```python
RH = {
    "DROIT_CONGE_ANNUEL_JOURS": 30,
    "PERMISSION_MAX_JOURS": 5,
    "DELAI_PREAVIS_CONGE_JOURS": 15,
}
```

## 5. Pilotage des activités

Chaque périmètre établit son plan d'action annuel, le fait valider par la direction, puis rend compte de son exécution. Détail dans [docs/pilotage.md](docs/pilotage.md).

```
En préparation ──soumission──▶ Soumis ──validation──▶ Validé ──clôture──▶ Clos
       ▲                          │
       └──────── renvoi ──────────┘
```

- **L'avancement n'est pas saisi, il est rapporté** : on dépose un point d'avancement (taux atteint, réalisations, difficultés, bénéficiaires, montant engagé) dont l'activité découle. Les bénéficiaires et les montants se cumulent ; l'activité passe en cours à la première déclaration et réalisée à 100 %.
- **Les taux sont calculés** : l'exécution d'un plan est la moyenne des avancements de ses activités, les annulées exclues.
- **Clore un exercice** reporte les activités restées ouvertes, avec mention explicite.
- **Les axes stratégiques sont nationaux**, ce qui permet la consolidation : la direction compare l'exécution de tous les périmètres sur un même cadre.

| Écran | Adresse |
|---|---|
| Tableau de bord | `/intranet/pilotage/` |
| Plans d'action | `/intranet/pilotage/plans/` |
| Chronogramme | `/intranet/pilotage/plans/<id>/chronogramme/` |
| Registre des activités (export CSV) | `/intranet/pilotage/activites/` |

## 6. Courrier et gestion documentaire

Chaque périmètre tient son registre du courrier, avec sa série annuelle par sens : `ARR-0001/2026/APFC-GBK`, `DEP-0001/2026/DPFC`. Détail dans [docs/courrier.md](docs/courrier.md).

```
Enregistré ──imputation──▶ Imputé ──toutes les suites données──▶ Traité
     │
     └──────── classement sans suite (motif obligatoire) ──────▶ Classé
```

- **Le statut est déduit**, jamais saisi : le courrier passe à « traité » quand toutes ses imputations le sont. Une imputation « pour information » est close dès sa création.
- **Les droits tiennent à la désignation**, pas au rôle : porter le rôle de chef d'antenne ne suffit pas à imputer le courrier d'une antenne, il faut en être le responsable désigné.
- **Confidentialité** : un courrier confidentiel n'est visible que de son enregistreur, de ses imputataires, du responsable du périmètre et de la direction.
- **Documents versionnés** avec empreinte SHA-256 ; recherche plein texte sur le titre, la description et le texte extrait des fichiers. Un fichier illisible n'empêche jamais le dépôt.
- **Parapheur** : les visas réutilisent le moteur de circuits (type d'acte `PARAPHEUR`) et remontent jusqu'au responsable du périmètre.

| Écran | Adresse |
|---|---|
| Tableau du courrier | `/intranet/courrier/` |
| Registre (export CSV) | `/intranet/courrier/registre/` |
| Bibliothèque documentaire | `/intranet/courrier/documents/` |
| Parapheur | `/intranet/courrier/parapheur/` |
| Modèles de courrier | `/intranet/courrier/modeles/` |

## 7. Ateliers et émargement

Les ateliers se tiennent souvent loin d'Abidjan, dans des salles sans réseau fiable. Le dispositif d'émargement en tient compte. Détail dans [docs/ateliers.md](docs/ateliers.md).

```
Planifié ──ouverture──▶ En cours ──clôture──▶ Clos
    │                       │
    └────── annulation (motif obligatoire) ──▶ Annulé
```

- **Le QR code ne porte aucune donnée personnelle** : deux identifiants courts aléatoires et une signature HMAC-SHA256, avec une clé propre à chaque atelier. Un badge perdu ne révèle rien.
- **L'émargement est idempotent** : l'identifiant vient de l'appareil, si bien qu'un téléphone peut accumuler ses scans hors ligne puis rejouer sa file autant de fois qu'il le faut sans créer de doublon.
- **Un doublon n'est jamais perdu**, il est journalisé — en cas de contestation, on reconstitue ce qui s'est passé.
- **L'émargement manuel est motivé**, et le motif conservé.
- **On émarge par session** (journée ou demi-journée), seule façon de constater une présence partielle.

Ce qui en découle : l'**état de paiement** ne retient que les participants ayant effectivement émargé (barème × journées constatées) ; l'**attestation** est réservée à qui a émargé au moins la moitié des sessions ; à la clôture, les présences sont **reportées sur le plan d'action**.

| Écran | Adresse |
|---|---|
| Tableau des ateliers | `/intranet/ateliers/` |
| Fiche d'un atelier | `/intranet/ateliers/<id>/` |
| Badges QR à imprimer | `/intranet/ateliers/<id>/badges/` |
| Écran d'émargement | `/intranet/ateliers/<id>/emargement/` |
| État de paiement (CSV) | `/intranet/ateliers/<id>/paiement/` |

## 8. Signature électronique

- **Clé personnelle** : espace agent → « Ma signature électronique ». Le portail génère une bi-clé RSA 2048 ; la clé privée est stockée chiffrée (PKCS#8) par un **code de signature** connu du seul agent, jamais conservé par le serveur.
- **Apposition** : au moment de la décision, le valideur saisit son code. La signature RSASSA-PSS/SHA-256 porte sur l'empreinte SHA-256 du condensé canonique de l'acte (numéro, agent, structure, type, dates, durée, destination, périmètre, motif). À la dernière étape du circuit, le code est exigé si l'agent dispose d'une clé valide.
- **Document** : l'acte imprimable porte un cartouche de signature (signataire, qualité, horodatage, algorithme, empreinte), un **code de vérification** (`DPFC-XXXX-XXXX-XXXX`) et un **QR code**.
- **Vérification publique** : `/verification/<code>/`, accessible sans compte. Toute modification postérieure de l'acte rend la vérification négative ; la révocation d'une clé est signalée, les actes déjà signés restant vérifiables.
- **Révocation / renouvellement** : depuis la même page, avec motif journalisé.

Cette implémentation est autoportante (aucune autorité externe). Elle est compatible avec une montée vers un certificat qualifié : il suffit de remplacer la clé auto-générée par une clé adossée à un certificat X.509 délivré par un PSCE agréé, la chaîne de vérification restant identique.

## 9. Import Excel des agents

Espace agent → « Import Excel des agents » (réservé au service du personnel et à l'administrateur).

1. Télécharger le **modèle Excel** : il contient l'en-tête attendu et une feuille « Aide » listant les sigles de structures et les rôles acceptés.
2. Déposer le fichier rempli (`.xlsx` ou `.csv`) : le portail **analyse sans rien écrire** et affiche ligne par ligne l'action prévue (création, mise à jour) ou l'anomalie (structure inconnue, rôle invalide, matricule manquant ou en double, date illisible).
3. Confirmer : les lignes valides sont appliquées, les autres ignorées.

Colonnes : `matricule`*, `civilite`, `nom`*, `prenoms`, `email`, `telephone`, `structure` (sigle), `fonction`, `grade`, `role`, `superieur` (matricule), `date_prise_service`, `lieu_service`, `droit_conge` (\* obligatoires). Les variantes d'intitulés courantes sont reconnues (accents, « prénoms », « téléphone », « affectation »…).

Les nouveaux comptes reçoivent le matricule comme mot de passe initial, à changer à la première connexion ; les liens hiérarchiques sont rattachés après création. En ligne de commande :

```bash
python manage.py importer_agents --modele modele.xlsx   # génère le modèle
python manage.py importer_agents agents.xlsx            # analyse seule
python manage.py importer_agents agents.xlsx --appliquer
```

## 10. API REST (application Flutter)

Schéma OpenAPI : [docs/api/openapi.yml](docs/api/openapi.yml), exploré en ligne sur `/api/v1/docs/`. Pour le régénérer :

```bash
python manage.py spectacular --file docs/api/openapi.yml
```

| Méthode | Chemin | Rôle |
|---|---|---|
| POST | `/api/v1/auth/connexion/` | jeton JWT + profil de l'agent |
| POST | `/api/v1/auth/rafraichir/` | renouvellement du jeton |
| GET/PATCH | `/api/v1/moi/` | profil |
| GET | `/api/v1/moi/solde/` | solde de congé |
| GET | `/api/v1/pilotage/` | synthèse du pilotage pour l'écran d'accueil |
| GET | `/api/v1/plans/` | plans d'action visibles |
| GET | `/api/v1/activites/` | activités du périmètre (`annee`, `statut`, `retard`, `mes_activites`) |
| POST | `/api/v1/activites/<id>/avancement/` | compte rendu d'exécution depuis le terrain |
| GET | `/api/v1/courriers/` | registre du périmètre (`sens`, `statut`, `retard`) |
| GET | `/api/v1/imputations/?en_attente=1` | mes imputations à traiter |
| POST | `/api/v1/imputations/<id>/traiter/` | suite donnée à une imputation |
| GET | `/api/v1/documents/?q=...` | recherche plein texte dans la bibliothèque |
| GET | `/api/v1/ateliers/` | ateliers du périmètre, avec leurs sessions |
| GET | `/api/v1/ateliers/<id>/participants/` | liste à embarquer pour le terrain |
| POST | `/api/v1/ateliers/<id>/emargements/` | dépôt d'un lot collecté hors ligne (idempotent) |
| GET/POST | `/api/v1/demandes/` | mes demandes, création |
| POST | `/api/v1/demandes/{id}/soumettre/` | transmission au circuit |
| POST | `/api/v1/demandes/{id}/decision/` | avis favorable ou rejet ; `code_signature` appose la signature |
| POST | `/api/v1/demandes/{id}/pieces/` | dépôt des TDR, lettre d'invitation ou justificatif (multipart) |
| GET | `/api/v1/verification/{code}/` | vérification publique d'un acte signé |
| GET | `/api/v1/demandes/a-valider/` | dossiers en attente de ma décision |
| GET | `/api/v1/notifications/` | notifications |
| GET | `/api/v1/public/...` | actualités, ressources, projets, événements, antennes (accès libre) |

Application mobile :

```bash
cd mobile
flutter pub get
flutter run          # adapter baseUrl dans lib/services/api.dart
```

Elle couvre le parcours de terrain complet : dépôt d'un acte, bascule « mission hors du ressort de la DRENA » avec envoi des TDR et de la lettre d'invitation depuis le téléphone, suivi du circuit, décision du chef d'antenne ou du directeur régional avec saisie du code de signature à la dernière étape, et vérification d'un acte par son code.

## 11. Tests et qualité

```bash
python manage.py test --settings=config.settings.test
```

```bash
pytest
```

```bash
ruff check apps config
```

217 tests couvrent les ateliers (jetons sans donnée personnelle, rejet des jetons altérés ou d'un autre atelier, idempotence de l'émargement, journalisation des doublons, émargement manuel motivé, état de paiement limité aux émargés, attestations, report sur le plan d'action), le courrier (numérotation par périmètre, cycle d'imputation, retards, confidentialité, droits liés à la désignation), les documents (versions, empreintes, extraction du texte, recherche, accès restreint), le parapheur (circuit, refus, corbeille), le pilotage (cycle du plan, avancement cumulé, retards, consolidation, chronogramme, indicateurs, cloisonnement), les périmètres de gestion (héritage par l'agent, cloisonnement de la visibilité, numérotation par périmètre), les circuits paramétrables (circuit central, autonomie de l'antenne et du CNRPN, mission hors ressort, acte du responsable, circuit propre à un périmètre, étape sans titulaire), le calcul des jours ouvrables, le dépôt par le secrétariat, le parcours complet d'une demande, le rejet, les droits d'accès, la signature électronique, l'import Excel/CSV, les pages publiques et l'API.

## 12. Déploiement

La pile est alignée sur celle d'e-PECU : PostgreSQL, Celery et Redis, stockage objet S3/MinIO, Nginx devant gunicorn ([ADR 0004](docs/adr/0004-pile-alignee-sur-e-pecu.md)).

### En conteneurs

```bash
cp .env.example .env
```

```bash
docker compose -f infra/compose/docker-compose.dev.yml up -d --build
```

```bash
docker compose -f infra/compose/docker-compose.dev.yml exec web python manage.py migrate
```

```bash
docker compose -f infra/compose/docker-compose.dev.yml exec web python manage.py initialiser_dpfc --demo
```

| Service | Adresse |
|---|---|
| Application | http://localhost:8000 |
| Documentation de l'API | http://localhost:8000/api/v1/docs/ |
| Courriels capturés (mailpit) | http://localhost:8026 |
| Console MinIO | http://localhost:9001 |

### Sans conteneur

```bash
export DJANGO_SETTINGS_MODULE=config.settings.prod
export DJANGO_SECRET_KEY="..."
export DJANGO_ALLOWED_HOSTS="dpfc.education.ci"
export POSTGRES_HOST=... POSTGRES_DB=dpfc POSTGRES_USER=dpfc POSTGRES_PASSWORD=...
python manage.py migrate
python manage.py collectstatic --noinput
gunicorn config.wsgi:application --workers 3 --bind unix:/run/dpfc.sock
```

Les tâches de fond (relances sur les actes en attente, rappels de rapport de mission) tournent dans un worker Celery et son ordonnanceur :

```bash
celery -A config worker -l info
```

```bash
celery -A config beat -l info
```

Avec `config.settings.prod`, HTTPS, cookies sécurisés, HSTS, `X-Frame-Options` et le verrouillage après échecs de connexion (`django-axes`) sont actifs.

## 13. Exploitation courante

- **Créer un agent** : espace agent → Comptes des agents → Créer un compte. Le mot de passe initial est le matricule et son changement est imposé à la première connexion.
- **Affecter en région** : rattacher l'agent à une structure de type `ANTENNE` ; le circuit d'antenne s'applique alors automatiquement. Renseigner le champ `drenaet` de l'antenne dans l'administration pour que l'exception « mission hors périmètre » désigne le bon directeur régional.
- **Créer des agents en masse** : Import Excel des agents (voir § 9).
- **Activer la signature d'une autorité** : l'intéressé génère lui-même sa clé depuis « Ma signature électronique ».
- **Publier une actualité, un projet, un événement ou une page** : Wagtail (`/cms/`) → Pages → Accueil → rubrique concernée → « Ajouter une page enfant ». Enregistrer en brouillon, prévisualiser, puis « Publier ». La case « Afficher dans les menus » (onglet Promotion) fait apparaître une page de premier niveau dans la barre de navigation.
- **Ressources pédagogiques, catégories, messages de contact** : Wagtail → menu Contenus. Les fichiers sont pris dans la médiathèque Documents.
- **Slogan et image de la bannière** : Wagtail → Pages → Accueil (modifier).
- **Identité, coordonnées, pied de page, bouton « Espace agent »** : Wagtail → Paramètres → Configuration du site.
- **Comptes des rédacteurs du site** : ce sont des agents (même modèle) ; leur donner l'accès à Wagtail via Paramètres → Groupes (groupes « Editors » / « Moderators » créés par Wagtail).
- **Jours fériés** : espace agent → Jours fériés (réservé au service du personnel).
- **Modifier un circuit de validation** : `/admin/` → Circuits de validation. Choisir le type d'acte et le périmètre, puis ordonner les étapes. Pour revenir aux circuits livrés : `python manage.py installer_circuits --remplacer`.
- **Créer une antenne ou un service autonome** : `/admin/` → Périmètres de gestion (code, type, région), puis la structure de tête correspondante en cochant « structure de tête du périmètre » et en désignant son responsable.
- **Ouvrir un exercice** : chaque responsable de périmètre établit son plan d'action (`/intranet/pilotage/plans/`), y inscrit ses activités, puis le transmet à la direction.
- **Définir les axes stratégiques** : `/admin/` → Axes stratégiques. Ils sont communs à tous les périmètres et conditionnent la consolidation.
- **Suivre l'exécution** : `/intranet/pilotage/` pour la synthèse, le chronogramme pour le calendrier, le registre pour la recherche et l'export CSV.
- **Enregistrer et imputer du courrier** : `/intranet/courrier/`. Le secrétariat enregistre, le responsable du périmètre impute avec instructions et délai, l'imputataire rend compte.
- **Modifier le circuit du parapheur** : `/admin/` → Circuits de validation, type d'acte `PARAPHEUR`.
- **Organiser un atelier** : `/intranet/ateliers/nouveau/`. Les sessions sont générées automatiquement ; imprimez les badges, désignez les contrôleurs, puis ouvrez l'atelier pour permettre l'émargement.
- **Définir les barèmes de participation** : `/admin/` → Barèmes de participation. Ils déterminent les montants de l'état de paiement.
- **Activer l'OCR des documents scannés** : installer `pymupdf4llm` et `rapidocr-onnxruntime`. Sans eux, les PDF natifs restent indexés et les scans sont archivés sans texte.

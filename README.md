# Portail de la Direction de la Pédagogie et de la Formation Continue (DPFC)

Projet **monolithique Django** réunissant dans un seul dépôt :

| Brique | Description |
|---|---|
| **Site public** | Rendu serveur (templates Django), accessible sans compte : actualités, ressources pédagogiques, FOAD, projets, agenda, antennes régionales, contact. |
| **Intranet agents** | Espace authentifié : consignation des actes administratifs (congé, permission, ordre de mission, absence, formation), circuit de validation hiérarchique, planning, registre, annuaire. |
| **API REST** | `/api/v1/` avec jetons JWT, consommée par l'application mobile **Flutter** livrée dans `mobile/`. |
| **Signature électronique** | Bi-clés RSA 2048 par signataire, scellement SHA-256 des actes, page publique de vérification et QR code sur le document. |

L'organisation reflète la réalité de la direction : une **direction centrale (nationale)** avec ses sous-directions et services, et des **antennes de la pédagogie et de la formation continue** en région. Chaque agent est rattaché à l'une ou l'autre, ce qui détermine automatiquement son circuit de validation.

---

## 1. Démarrage rapide

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                 # ajuster la clé secrète
python manage.py migrate
python manage.py initialiser_dpfc --demo
python manage.py runserver
```

- Site public : http://127.0.0.1:8000/
- Espace agent : http://127.0.0.1:8000/intranet/connexion/
- Administration : http://127.0.0.1:8000/admin/ (`ADMIN01` / `dpfc2026!`)
- API : http://127.0.0.1:8000/api/v1/

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
| `300001B` | Directeur régional DRENAET (Bouaké) | établit les ODM hors périmètre |

Les autorités signataires du jeu de démonstration disposent d'une clé de signature dont le code est `signature2026`.

## 2. Arborescence

```
dpfc/
├── config/              paramètres, URLs, WSGI/ASGI
├── apps/
│   ├── core/            régions, structures (direction, sous-directions, services, antennes),
│   │                    configuration éditoriale, journal d'audit
│   ├── accounts/        modèle Agent (connexion par matricule), rôles, notifications,
│   │                    annuaire, organigramme, gestion des comptes
│   ├── contenus/        site public : actualités, ressources, projets, événements, pages, contact
│   ├── rh/              actes administratifs, circuit de validation, soldes de congé,
│   │                    planning, registre, documents officiels imprimables
│   ├── signature/       bi-clés RSA, signature des actes, vérification publique
│   └── api/             sérialiseurs et points d'entrée REST (JWT) pour Flutter
├── templates/public/    gabarits du site public
├── templates/intranet/  gabarits de l'espace agent
├── static/              CSS, JS, images
├── mobile/              application Flutter (client de l'API)
└── deploiement/         systemd, Nginx, Docker
```

## 3. Modèle d'organisation

- `Region` : région administrative et chef-lieu.
- `Structure` : `DIRECTION`, `SOUS_DIRECTION`, `SERVICE`, `DRENAET`, `ANTENNE`, `BUREAU`, avec un `parent` et un `rattachement` (`CENTRALE` ou `REGION`). Chaque antenne (APFC) porte une région et un champ `drenaet` : la direction régionale dans le périmètre de laquelle elle exerce.
- `Agent` : compte de connexion (matricule ou courriel), affectation à une structure, supérieur hiérarchique, rôle (`AGENT`, `SECRETARIAT`, `CHEF_SERVICE`, `SOUS_DIRECTEUR`, `CHEF_ANTENNE`, `DIRECTEUR_REGIONAL`, `RH`, `DIRECTEUR`, `ADMIN`) et situation administrative (en poste, en congé, en mission…).

## 4. Actes administratifs et circuit de validation

Types gérés : congé annuel, congé exceptionnel, permission d'absence, ordre de mission, déclaration d'absence, demande de formation.

### 4.1 Antennes (APFC) — autonomie de gestion

Chaque antenne gère son personnel sans remontée au niveau central :

```
Agent d'antenne → chef d'antenne (APFC)        [une seule étape, décision définitive]
   dépôt matériel assuré par le secrétariat de l'antenne
```

Le secrétariat (rôle `SECRETARIAT`) dépose la demande pour le compte de l'agent : tableau de bord → « Dépôt au secrétariat pour un agent ». La demande reste celle de l'agent ; le déposant est tracé dans le champ `depose_par`.

**Exception — mission hors du périmètre de la DRENAET :**

```
Agent d'antenne → chef d'antenne (avis) → DRENAET (établissement et signature de l'ODM)
```

L'agent coche « mission hors du périmètre de la DRENAET » et joint obligatoirement :
- les **termes de référence** (TDR) ;
- la **lettre d'invitation ou d'information** de la structure d'accueil.

Sans ces deux pièces, la transmission est bloquée (validation côté formulaire et côté modèle). Le document produit porte alors la mention « établi par le DRENAET » comme autorité signataire.

Les actes du chef d'antenne lui-même remontent au DRENAET, puis à la direction centrale lorsque le type d'acte l'exige.

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

## 5. Signature électronique

- **Clé personnelle** : espace agent → « Ma signature électronique ». Le portail génère une bi-clé RSA 2048 ; la clé privée est stockée chiffrée (PKCS#8) par un **code de signature** connu du seul agent, jamais conservé par le serveur.
- **Apposition** : au moment de la décision, le valideur saisit son code. La signature RSASSA-PSS/SHA-256 porte sur l'empreinte SHA-256 du condensé canonique de l'acte (numéro, agent, structure, type, dates, durée, destination, périmètre, motif). À la dernière étape du circuit, le code est exigé si l'agent dispose d'une clé valide.
- **Document** : l'acte imprimable porte un cartouche de signature (signataire, qualité, horodatage, algorithme, empreinte), un **code de vérification** (`DPFC-XXXX-XXXX-XXXX`) et un **QR code**.
- **Vérification publique** : `/verification/<code>/`, accessible sans compte. Toute modification postérieure de l'acte rend la vérification négative ; la révocation d'une clé est signalée, les actes déjà signés restant vérifiables.
- **Révocation / renouvellement** : depuis la même page, avec motif journalisé.

Cette implémentation est autoportante (aucune autorité externe). Elle est compatible avec une montée vers un certificat qualifié : il suffit de remplacer la clé auto-générée par une clé adossée à un certificat X.509 délivré par un PSCE agréé, la chaîne de vérification restant identique.

## 6. Import Excel des agents

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

## 7. API REST (application Flutter)

| Méthode | Chemin | Rôle |
|---|---|---|
| POST | `/api/v1/auth/connexion/` | jeton JWT + profil de l'agent |
| POST | `/api/v1/auth/rafraichir/` | renouvellement du jeton |
| GET/PATCH | `/api/v1/moi/` | profil |
| GET | `/api/v1/moi/solde/` | solde de congé |
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

Elle couvre le parcours de terrain complet : dépôt d'un acte, bascule « mission hors périmètre DRENAET » avec envoi des TDR et de la lettre d'invitation depuis le téléphone, suivi du circuit, décision du chef d'antenne ou du DRENAET avec saisie du code de signature à la dernière étape, et vérification d'un acte par son code.

## 8. Tests

```bash
python manage.py test
```

56 tests couvrent le calcul des jours ouvrables, les deux régimes de validation (autonomie des antennes, exception DRENAET, circuit central), le dépôt par le secrétariat, le parcours complet d'une demande, le rejet, les droits d'accès, la signature électronique (création de clé, signature, détection de modification, révocation, vérification publique), l'import Excel/CSV, les pages publiques et l'API (dépôt de pièces, signature mobile, vérification).

## 9. Mise en production

```bash
export DJANGO_DEBUG=False
export DJANGO_SECRET_KEY="..."
export DJANGO_ALLOWED_HOSTS="dpfc.education.ci"
export DATABASE_URL="postgres://utilisateur:motdepasse@hote:5432/dpfc"
python manage.py migrate
python manage.py collectstatic --noinput
gunicorn config.wsgi:application --workers 3 --bind unix:/run/dpfc.sock
```

Modèles fournis dans `deploiement/` : service systemd, configuration Nginx (TLS, `/static/`, `/media/`), `Dockerfile` et `docker-compose.yml` avec PostgreSQL.

En production, HTTPS obligatoire, cookies sécurisés, HSTS et `X-Frame-Options` sont activés automatiquement dès que `DJANGO_DEBUG=False`.

## 10. Exploitation courante

- **Créer un agent** : espace agent → Comptes des agents → Créer un compte. Le mot de passe initial est le matricule et son changement est imposé à la première connexion.
- **Affecter en région** : rattacher l'agent à une structure de type `ANTENNE` ; le circuit d'antenne s'applique alors automatiquement. Renseigner le champ `drenaet` de l'antenne dans l'administration pour que l'exception « mission hors périmètre » désigne le bon directeur régional.
- **Créer des agents en masse** : Import Excel des agents (voir § 6).
- **Activer la signature d'une autorité** : l'intéressé génère lui-même sa clé depuis « Ma signature électronique ».
- **Publier une actualité ou une ressource** : administration Django (`/admin/`), rubriques Actualités et Ressources pédagogiques.
- **Bannière et coordonnées du site** : administration → Configuration du site.
- **Jours fériés** : espace agent → Jours fériés (réservé au service du personnel).

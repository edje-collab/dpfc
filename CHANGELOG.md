# Journal des versions

## 3.1.0 — Pilotage des activités (phase 2)

**Plans d'action annuels.** Nouvelle application `activites` : chaque périmètre — direction centrale, antenne régionale, CNRPN — établit son plan annuel, le transmet à la direction, puis rend compte de son exécution. Cycle complet : préparation, soumission, validation ou renvoi motivé, clôture avec report automatique des activités restées ouvertes.

**L'avancement est rapporté, pas saisi.** Un point d'avancement porte le taux atteint, les réalisations, les difficultés, les bénéficiaires touchés et le montant engagé sur la période. L'activité en découle : le taux suit le dernier compte rendu, les bénéficiaires et les montants se cumulent, les changements d'état et les dates réelles sont automatiques.

**Consolidation.** Taux d'exécution physique et budgétaire par activité, par axe stratégique et par plan, les activités annulées étant exclues du calcul. Tableau de bord par périmètre, consolidation nationale pour la direction, chronogramme sur douze mois, registre filtrable et export CSV. Les axes stratégiques sont un référentiel national, ce qui rend la comparaison entre périmètres possible.

**Application mobile.** `/api/v1/pilotage/`, `/api/v1/plans/`, `/api/v1/activites/` et le dépôt d'un compte rendu avec pièce jointe depuis le terrain, cloisonnés par périmètre.

**Correction.** La direction centrale est elle aussi un périmètre autonome, dirigé par un directeur central : `Perimetre.est_autonome` vaut désormais pour les trois types, et `est_deconcentre` distingue l'implantation (antenne ou centre rattaché) de l'autonomie de gestion.

**Jeu de démonstration.** Chaque antenne a son chef, son secrétariat et son conseiller : plus aucun périmètre sans responsable. Les plans couvrent tous les cas de gestion — en préparation, soumis, validés, clos — et les activités tous les statuts, y compris le retard, le report et l'annulation. Les dates sont relatives au jour du chargement, pour une démonstration stable toute l'année.

## 3.0.0 — Plateforme de gestion de la direction (phase 1 : socle)

Mise en conformité avec le **décret n° 2026-509 du 05 août 2026** et passage à une plateforme de gestion, sur la pile technique d'e-PECU.

**Organisation.** La DPFC est rattachée à la Direction Générale de la Pédagogie, des Curricula et du Suivi des Programmes et comprend les trois sous-directions du décret (SDPPBS, SDIP, SDFPC). Les services extérieurs suivent l'article 41 : DRENA, DDENA, DRETPI — l'ancien type `DRENAET` est renommé `DRENA`.

**Périmètres de gestion autonome.** Nouveau modèle `core.Perimetre` : la direction centrale, chaque antenne régionale (APFC) et le **CNRPN** — service rattaché dirigé par un chef de centre — forment chacun une unité de gestion. Un agent hérite du périmètre de sa structure ; les actes y sont instruits et numérotés par série annuelle propre (`PA-0001/2026/APFC-GBK`) ; un chef d'antenne ou de centre ne voit que ses agents.

**Circuits paramétrables.** Nouvelle application `circuits` : le trajet des actes n'est plus codé mais décrit en données, par type de périmètre et type d'acte, modifiable dans l'administration. Les étapes désignent une fonction (supérieur, sous-directeur, responsable du périmètre, directeur régional, rôle) résolue à la soumission, sous conditions combinables. Un périmètre peut définir son propre circuit. Un agent désactivé ne porte plus aucune étape.

**Pile technique.** Réglages découpés (`base`/`dev`/`recette`/`prod`/`test`), PostgreSQL, Docker Compose (application, worker et ordonnanceur Celery, PostgreSQL, Redis, MinIO, mailpit), stockage objet S3, Argon2 et `django-axes`, schéma OpenAPI (`/api/v1/docs/`), pytest et ruff.

**Nouveaux rôles.** `CHEF_CENTRE` (CNRPN) et `DIRECTEUR_GENERAL` (DGPCSP).

**Reprise des données.** La migration `core.0006` convertit une base existante sans perte : renommage des DRENAET, création des périmètres et rattachement des structures. Les sous-directions antérieures absentes du décret sont conservées : leur sort relève de la direction (voir `docs/organisation.md`).

## 2.0.0
- **Site public géré par Wagtail** (administration sur `/cms/`) : l'app `contenus` est remplacée par `site_public`. Accueil, pages éditoriales, actualités, projets et événements sont des pages Wagtail (contenu par blocs, images de la médiathèque, prévisualisation, brouillons/publication, historique des révisions). Ressources pédagogiques, catégories et messages de contact sont des snippets Wagtail. Le menu est déduit de l'arborescence (« Afficher dans les menus »).
- L'espace agent (intranet Django, administration `/admin/`, API et application Flutter) est inchangé ; l'API publique conserve ses routes (`/api/v1/public/...`) et ses champs, plus `url`.
- Configuration du site (identité, coordonnées, pied de page, bouton « Espace agent ») éditée dans Wagtail → Paramètres. Le slogan et l'image de bannière sont désormais portés par la page d'accueil.
- Commandes `initialiser_dpfc` et `initialiser_donnees` : construisent l'arborescence Wagtail et les contenus de démonstration.
- Option « Afficher le bouton Espace agent » qui masque ou affiche l'accès à l'espace agent (menu et pied de page) sur le portail public.
- Accueil : page réorganisée pour limiter le défilement — bannière compacte avec les chiffres clés intégrés, accès rapides aux ressources, puis actualités (une + liste) à gauche et agenda + projets stratégiques en colonne latérale.

## 1.1.1
- API : signature à la décision (`code_signature`), dépôt des pièces jointes en multipart, endpoint public de vérification.
- Application Flutter : bascule « mission hors périmètre DRENAET » avec envoi des TDR et de la lettre d'invitation, saisie du code de signature à la dernière étape, écran de vérification d'un acte.

## 1.1.0
- Autonomie des antennes : la demande d'un agent d'antenne est adressée directement au chef APFC, le dépôt étant assuré par le secrétariat (rôle `SECRETARIAT`, champ `depose_par`).
- Exception « mission hors périmètre DRENAET » : structures `DRENAET`, rôle `DIRECTEUR_REGIONAL`, pièces obligatoires (TDR + lettre d'invitation), ordre de mission établi et signé par le DRENAET.
- Signature électronique : bi-clés RSA 2048 par signataire, scellement SHA-256 des actes, code et QR code de vérification, page publique de vérification, révocation et renouvellement.
- Import Excel/CSV des agents : modèle généré, analyse préalable ligne à ligne, application des lignes valides, commande `importer_agents`.

## 1.0.0
- Site public rendu serveur : accueil, présentation, actualités, ressources, FOAD, projets, agenda, antennes, contact, recherche.
- Espace agent : dépôt et suivi des congés, permissions, ordres de mission, absences et formations.
- Circuit de validation automatique selon l'affectation (direction centrale ou antenne régionale).
- Soldes de congé, jours fériés, planning des absences, registre avec export CSV.
- Documents officiels imprimables avec visas.
- API REST JWT et application mobile Flutter.

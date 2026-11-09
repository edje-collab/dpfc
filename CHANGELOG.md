# Journal des versions

## 3.4.4 — Cloisonnement des services extérieurs

**Correction de cloisonnement.** Un agent des services extérieurs du ministère — directeur régional DRENA, par exemple — héritait du périmètre central faute d'en avoir un propre, et voyait donc le courrier, les documents, les achats et les ateliers de la direction. Or il est extérieur à la DPFC : il intervient dans les circuits de validation sans relever de sa gestion.

`Agent.perimetre` vaut désormais `None` lorsque la structure n'appartient à aucun périmètre, et les filtrages ne renvoient alors rien. Le directeur régional conserve ce qui lui revient : les agents de son ressort et son rôle dans l'établissement des ordres de mission hors ressort.

Nouvelle exigence **SEC-07**, avec ses tests.

## 3.4.3 — Répartition des agents selon les attributions

Les agents d'une structure retirée ne sont plus déposés à la direction : ils **suivent les attributions de leur structure**. Chaque structure retirée désigne la sous-direction du décret qui les reprend.

| Structure retirée | Attributions reprises par |
|---|---|
| Sous-direction de la formation continue | SDFPC — Formation Pédagogique Continue |
| Sous-direction des programmes et manuels scolaires | SDPPBS — Programmes Pédagogiques et Bibliothèques Scolaires |
| Service des ressources pédagogiques numériques | SDIP — Innovations Pédagogiques |

La répartition suit les **missions**, non les personnes : c'est le seul critère qui se justifie sans arbitrer les carrières. Une correspondance se précise au besoin par `--correspondance ANCIEN=NOUVEAU` ; à défaut de correspondance connue, les agents vont à la direction plutôt que d'être placés au jugé.

La simulation annonce désormais, pour chaque structure, qui reprend ses attributions.

## 3.4.2 — Mise en conformité de l'organigramme

**Décision de la direction appliquée.** Les sous-directions et services centraux antérieurs au décret n° 2026-509 sont retirés de l'organigramme, **à l'exception du service du personnel et des affaires administratives**, conservé. Nouvelle commande `manage.py nettoyer_organisation`, qui simule par défaut et n'exécute qu'avec `--appliquer`.

**Une structure porteuse d'historique est désactivée, pas supprimée** : effacer la structure effacerait la provenance des actes déjà pris. Le compte rendu indique à chaque fois lequel des deux cas s'applique. Les agents et sous-structures sont rattachés à la direction avant retrait.

**Correction.** Sur une base antérieure au décret, la DPFC n'était pas rattachée à la DGPCSP — les valeurs par défaut de `get_or_create` ne s'appliquent pas à un enregistrement existant. La commande établit ce lien (article 27).

Nouvelles exigences **ORG-09** à **ORG-11** au cahier des charges, avec leurs tests. Le point correspondant de la section « ce qui reste à trancher » passe en « points tranchés ».

## 3.4.1 — Cahier des charges

**Cahier des charges** ([docs/cahier-des-charges.md](docs/cahier-des-charges.md)) : objet, contexte réglementaire, organisation cible, et une centaine d'exigences numérotées couvrant l'organisation, les circuits, les actes administratifs, la signature, le pilotage, le courrier, les documents, le parapheur, les ateliers, les achats, les stocks, le site public, la sécurité et la technique.

**Matrice de traçabilité vérifiée.** Chaque exigence renvoie aux tests qui la prouvent, et `tests/test_tracabilite.py` contrôle que la matrice reste vraie : un test cité qui n'existe plus, une exigence énoncée mais non tracée, ou une référence à une exigence inconnue font échouer la suite. Une matrice qui se périme en silence donne l'illusion d'une preuve ; celle-ci ne le peut pas.

Les exigences transverses — sécurité, architecture, qualités attendues — sont recensées à part, avec leur mode de vérification propre.

**Points laissés à la direction** consignés : devenir des sous-directions antérieures au décret, seuils d'engagement, barèmes de participation, règle d'attestation, OCR, chiffrement des données personnelles.

## 3.4.0 — Achats et stocks (phase 5)

**Procédure d'achat.** Nouvelle application `achats`. Chaque périmètre exprime ses besoins, les fait valider, consulte les fournisseurs, commande, réceptionne puis solde. Séries annuelles propres au périmètre pour les besoins (`EB-0001/2026/APFC-GBK`) comme pour les bons de commande.

**Le circuit de validation dépend du montant.** Le moteur de circuits accepte désormais un seuil de montant par étape : une fourniture de bureau s'arrête au supérieur hiérarchique, un engagement de plus de deux millions remonte au directeur. Le seuil est paramétré dans l'administration, pas codé. L'objet qui circule expose `montant_circuit` ; ceux qui n'en portent pas valent zéro, de sorte que le moteur reste ignorant de ce qu'il fait circuler.

**Garde-fous de la commande.** Retenir une offre exige au moins deux consultations — un choix entre une seule option n'en est pas un. Commander à un fournisseur dont le compte contribuable manque est refusé. Une facture s'écartant de plus de 10 % du bon de commande demande une justification.

**Le stock dérive du journal.** Toute quantité s'explique par une entrée, une sortie ou un inventaire ; chaque mouvement conserve le stock résultant. On ne corrige jamais un compteur : un écart au comptage se solde par un mouvement d'inventaire motivé, qui fixe la quantité comptée. Une sortie ne peut pas dépasser le stock et exige un bénéficiaire.

**Liens avec le reste de la plateforme.** La réception fait entrer au magasin les articles qui y sont tenus, avec le bon de commande en référence ; la facture vient grossir le budget exécuté de l'activité rattachée au besoin.

**Équipements.** Inventaire des biens durables : code, marque, numéro de série, affectation, valeur et état.

**Application mobile.** `/api/v1/besoins/` et `/api/v1/articles/`, avec dépôt d'un mouvement depuis le terrain — le relevé d'inventaire se fait rayon par rayon.

## 3.3.0 — Ateliers et émargement par QR code (phase 4)

**Ateliers.** Nouvelle application `ateliers`. Chaque périmètre organise ses ateliers, formations et séminaires : sessions à la journée ou à la demi-journée, inscription individuelle ou groupée par structure, désignation de contrôleurs d'émargement, compte rendu et décisions. Cycle planifié → en cours → clos, l'annulation exigeant un motif.

**QR code sans donnée personnelle.** Le jeton de présence ne porte ni nom, ni matricule, ni téléphone : deux identifiants courts aléatoires et une signature HMAC-SHA256, la clé étant propre à chaque atelier. Un badge perdu ne révèle rien, et un jeton d'un autre atelier ou altéré est rejeté.

**Émargement utilisable hors ligne.** L'identifiant de l'émargement est produit par l'appareil au moment du scan : un téléphone accumule ses relevés sans réseau, puis rejoue sa file autant de fois qu'il le faut sans créer de doublon. Un second scan portant un identifiant différent est journalisé plutôt que perdu. L'émargement manuel est possible mais motivé.

**Ce qui en découle.** L'état de paiement ne retient que les participants ayant effectivement émargé — barème de la catégorie × journées constatées, les demi-journées comptant pour moitié. L'attestation est réservée à qui a émargé au moins la moitié des sessions. À la clôture, les présences constatées sont reportées sur l'activité du plan d'action : le pilotage se nourrit du terrain.

**Sorties.** Planche de badges à imprimer, feuille de présence et état de paiement exportables en CSV, attestation de participation à l'en-tête de la direction.

**Application mobile.** `/api/v1/ateliers/` pour embarquer l'atelier et sa liste de participants, `/api/v1/ateliers/<id>/emargements/` pour déposer un lot collecté hors ligne.

## 3.2.0 — Courrier et gestion documentaire (phase 3)

**Registre du courrier par périmètre.** Nouvelle application `courrier`. Chaque périmètre tient sa série annuelle par sens (`ARR-0001/2026/APFC-GBK`, `DEP-0001/2026/DPFC`). Un courrier arrivé est imputé à un ou plusieurs agents, avec instructions et délai ; son statut est déduit de l'état de ses imputations, jamais saisi. Imputation « pour information » close d'emblée, classement sans suite motivé, calcul du retard sur l'imputation la plus ancienne.

**Confidentialité et droits.** Un courrier confidentiel reste visible de son seul enregistreur, de ses imputataires, du responsable du périmètre et de la direction — filtrage appliqué en liste comme à l'accès direct. Les droits d'enregistrement, d'imputation et de pilotage tiennent désormais à la **désignation effective** (`dirige_son_perimetre`) et non au rôle porté : porter le rôle de chef d'antenne sans diriger l'antenne ne donne plus la main sur son courrier ni sur son plan d'action.

**Bibliothèque documentaire.** Documents versionnés avec empreinte SHA-256 et taille, versions antérieures conservées, partage entre périmètres et accès restreint par agent. Recherche plein texte portable : moteur français de PostgreSQL en production, recherche par sous-chaîne ailleurs. L'extraction du texte (fichiers texte, PDF natifs via pypdf, OCR facultatif pour les scans) ne bloque jamais le dépôt.

**Parapheur.** Les visas internes réutilisent le moteur de circuits : `PieceParapheur` expose l'interface attendue par `circuits.services`, qui reste ignorant du courrier. Nouveau type d'acte `PARAPHEUR` dans les circuits livrés, remontant jusqu'au responsable du périmètre — une note d'antenne ne traverse pas la direction centrale.

**Modèles de courrier** à l'en-tête de la direction, avec substitution de variables.

**Application mobile.** `/api/v1/courriers/`, `/api/v1/imputations/` avec compte rendu depuis le terrain, et `/api/v1/documents/` avec recherche plein texte — tous cloisonnés par périmètre.

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

# Cahier des charges — Plateforme de gestion de la DPFC

| | |
|---|---|
| **Maître d'ouvrage** | Direction de la Pédagogie et de la Formation Continue (DPFC) |
| **Tutelle** | Direction Générale de la Pédagogie, des Curricula et du Suivi des Programmes (DGPCSP) |
| **Ministère** | Éducation Nationale, de l'Alphabétisation et de l'Enseignement Technique |
| **Version** | 3.4.3 |
| **Référence réglementaire** | Décret n° 2026-509 du 05 août 2026 portant organisation du MENAET |

> Ce document est tenu à jour avec le code. Chaque exigence porte un identifiant et renvoie aux tests automatisés qui la vérifient : la [matrice de traçabilité](#15-matrice-de-traçabilité) est contrôlée à chaque exécution de la suite de tests, de sorte qu'une exigence ne peut pas être invoquée sans preuve.

---

## 1. Objet

La direction demande une plateforme unique pour conduire son activité : piloter son plan d'action, instruire les actes administratifs de ses agents, traiter son courrier, organiser ses ateliers et tenir ses achats — pour elle-même comme pour ses structures déconcentrées.

La plateforme remplace un fonctionnement fondé sur le papier, le tableur et le courriel, qui ne permet ni de savoir où en est un dossier, ni de consolider l'activité nationale.

## 2. Contexte réglementaire

Le **décret n° 2026-509 du 05 août 2026** fixe l'organisation de référence.

- **Article 27** — La DGPCSP comprend trois directions centrales, dont la DPFC.
- **Article 28** — La DPFC gère les activités pédagogiques du préscolaire, du primaire et du secondaire général, promeut la qualité de l'enseignement et l'usage des nouvelles technologies, élabore les programmes en langues nationales, assure la formation continue des personnels enseignants et d'encadrement, et produit les rapports stratégiques. Elle comprend trois sous-directions : **SDPPBS**, **SDIP**, **SDFPC**.
- **Article 41** — Les services extérieurs du ministère sont les **DRENA**, les **DDENA** et les **DRETPI**.

Le décret ne mentionne ni les antennes régionales ni le CNRPN : l'article 1 renvoie à un arrêté du ministre le soin d'organiser les services rattachés. La plateforme les traite donc comme des structures créées par arrêté, dotées d'une **gestion autonome**.

## 3. Organisation cible

### 3.1 Le périmètre de gestion

L'unité structurante de la plateforme n'est pas la structure administrative mais le **périmètre de gestion** : l'unité dans laquelle les actes sont instruits, numérotés et pilotés.

| Type | Périmètre | Dirigé par |
|---|---|---|
| `CENTRALE` | La DPFC et ses sous-directions | Directeur central |
| `ANTENNE` | Une par APFC régionale | Chef d'antenne |
| `CENTRE` | Le CNRPN | Chef de centre |

Les trois sont autonomes dans leur gestion. Ce qui les distingue est l'implantation, non l'autonomie : la direction centrale est au niveau national, les autres sont déconcentrées ou rattachées.

### 3.2 Exigences

| Réf. | Exigence |
|---|---|
| **ORG-01** | Un agent relève d'un seul périmètre, déduit de sa structure d'affectation. |
| **ORG-02** | Chaque périmètre a une structure de tête, dont le responsable est le responsable du périmètre. |
| **ORG-03** | Les trois types de périmètre sont autonomes ; `est_deconcentre` distingue l'implantation. |
| **ORG-04** | Chaque périmètre tient ses propres séries annuelles de numéros, pour chaque type de document. |
| **ORG-05** | Un responsable de périmètre déconcentré ne voit que les agents et les dossiers de son périmètre. |
| **ORG-06** | Le service du personnel, la direction et l'administration voient tous les périmètres. |
| **ORG-07** | Les droits tiennent à la **désignation effective** du responsable, non au rôle porté. |
| **ORG-08** | La reprise d'une base antérieure convertit sans perte : renommage DRENAET → DRENA, création des périmètres, rattachement des structures. |
| **ORG-09** | Les structures centrales absentes du décret sont retirées de l'organigramme, à l'exception du service du personnel et des affaires administratives, conservé sur décision de la direction. |
| **ORG-10** | Une structure porteuse d'historique est désactivée plutôt que supprimée : effacer la structure effacerait la provenance des actes déjà pris. |
| **ORG-11** | Les agents d'une structure retirée suivent ses attributions : chaque structure retirée désigne la sous-direction du décret qui les reprend. À défaut de correspondance connue, ils vont à la direction. |

## 4. Circuits de validation

Le trajet d'un dossier n'est pas codé : il est décrit en données, par type de périmètre et type d'acte, modifiable dans l'administration.

| Réf. | Exigence |
|---|---|
| **CIR-01** | Une étape désigne une **fonction** (supérieur, sous-directeur, responsable du périmètre, directeur régional, rôle), résolue au moment de la soumission. |
| **CIR-02** | Une étape porte zéro, une ou plusieurs conditions, toutes requises pour qu'elle s'applique. |
| **CIR-03** | Une étape peut porter un **seuil de montant** : elle ne s'applique qu'au-delà. |
| **CIR-04** | Un même agent ne valide qu'une fois et ne valide jamais son propre dossier. |
| **CIR-05** | Un agent désactivé ne porte aucune étape de validation. |
| **CIR-06** | Une étape facultative sans titulaire est ignorée ; une étape obligatoire sans titulaire bloque la soumission avec un message nommant le circuit à compléter. |
| **CIR-07** | Un périmètre peut définir son propre circuit, qui prime sur le modèle de son type. |
| **CIR-08** | Les circuits modèles sont des données de référence, réinstallées après chaque migration. |
| **CIR-09** | Le moteur ignore ce qu'il fait circuler : tout objet exposant `agent`, `type`, `regles` et `montant_circuit` peut l'emprunter. |

### 4.1 Circuits livrés

**Direction centrale** — supérieur hiérarchique → sous-directeur → visa du service du personnel → signature du directeur, les deux dernières selon le type d'acte.

**Antenne régionale** — le chef d'antenne décide seul. Exception : une mission hors du ressort de la DRENA appelle son avis puis l'établissement de l'acte par le directeur régional. Les actes du chef d'antenne lui-même remontent à la DRENA.

**CNRPN** — le chef de centre décide seul. N'ayant pas de ressort régional, ses propres actes remontent directement à la direction centrale.

## 5. Actes administratifs

| Réf. | Exigence |
|---|---|
| **ACT-01** | Types gérés : congé annuel, congé exceptionnel, permission d'absence, ordre de mission, déclaration d'absence, demande de formation. |
| **ACT-02** | Le décompte des jours exclut samedis, dimanches et jours fériés. |
| **ACT-03** | Une permission ne peut excéder le plafond paramétré ; au-delà, un congé est exigé. |
| **ACT-04** | Une mission hors du ressort de la DRENA exige les termes de référence et la lettre d'invitation ; sans elles, la transmission est bloquée. |
| **ACT-05** | Le secrétariat dépose pour le compte d'un agent ; le déposant est tracé. |
| **ACT-06** | Le solde de congé est décompté à l'approbation, pour les seuls types d'acte concernés. |
| **ACT-07** | Un rejet ferme le dossier et rend les étapes suivantes sans objet. |

## 6. Signature électronique

| Réf. | Exigence |
|---|---|
| **SIG-01** | Chaque signataire dispose d'un bi-clé RSA 2048, généré par lui-même et protégé par un code personnel. |
| **SIG-02** | La signature RSASSA-PSS/SHA-256 porte sur l'empreinte d'un condensé canonique de l'acte. |
| **SIG-03** | Toute modification de l'acte après signature est détectée à la vérification. |
| **SIG-04** | Une clé révoquée invalide les vérifications ultérieures. |
| **SIG-05** | Un acte signé est vérifiable publiquement par son code, sans authentification. |

## 7. Pilotage des activités

| Réf. | Exigence |
|---|---|
| **PIL-01** | Un plan d'action par périmètre et par année, suivant le cycle préparation → soumission → validation → clôture. |
| **PIL-02** | Un plan sans activité ne peut être soumis ; un renvoi exige un motif. |
| **PIL-03** | Les plans des périmètres déconcentrés sont validés par la direction centrale. |
| **PIL-04** | L'avancement n'est pas saisi : il découle d'un compte rendu portant le taux atteint, les réalisations, les difficultés, les bénéficiaires et le montant engagé. |
| **PIL-05** | Les bénéficiaires et les montants se cumulent ; le taux suit le dernier compte rendu. |
| **PIL-06** | L'activité passe en cours à la première déclaration, réalisée à 100 %, avec dates réelles renseignées automatiquement. |
| **PIL-07** | Le taux d'exécution d'un plan est la moyenne des avancements, les activités annulées exclues du calcul. |
| **PIL-08** | Une activité échue et non achevée est signalée en retard. |
| **PIL-09** | Clore un exercice reporte les activités restées ouvertes, avec mention explicite. |
| **PIL-10** | Les axes stratégiques sont un référentiel national, ce qui permet la consolidation entre périmètres. |
| **PIL-11** | Le chronogramme positionne les activités sur les douze mois de l'exercice. |
| **PIL-12** | Un indicateur a une cible et une valeur réalisée ; le taux d'atteinte est plafonné à 100 %. |

## 8. Courrier

| Réf. | Exigence |
|---|---|
| **COU-01** | Chaque périmètre tient son registre, avec une série annuelle par sens (`ARR-0001/2026/APFC-GBK`, `DEP-0001/...`). |
| **COU-02** | Un courrier ne peut être enregistré avant sa date. |
| **COU-03** | Un courrier arrivé est imputé à un ou plusieurs agents, avec instructions et délai. |
| **COU-04** | Une imputation « pour information » est close dès sa création : elle n'appelle pas de suite. |
| **COU-05** | Le statut du courrier est **déduit** de l'état de ses imputations, jamais saisi. |
| **COU-06** | Seul l'imputataire rend compte de son imputation ; un compte rendu vide est refusé. |
| **COU-07** | Le retard est calculé sur l'imputation ouverte la plus ancienne. |
| **COU-08** | Le classement sans suite exige un motif. |
| **COU-09** | Un courrier confidentiel n'est visible que de son enregistreur, de ses imputataires, du responsable du périmètre et de la direction. |
| **COU-10** | Le secrétariat enregistre ; l'imputation relève du responsable désigné du périmètre ou de la direction. |

## 9. Documents

| Réf. | Exigence |
|---|---|
| **GED-01** | Chaque dépôt crée une version numérotée, avec empreinte SHA-256 et taille ; les versions antérieures restent consultables. |
| **GED-02** | Le texte des fichiers est extrait pour la recherche plein texte. |
| **GED-03** | Un fichier illisible **n'empêche jamais le dépôt** : le document est enregistré sans texte. |
| **GED-04** | La recherche est portable : moteur français de PostgreSQL en production, recherche par sous-chaîne ailleurs. |
| **GED-05** | Un document reste au périmètre, sauf partage explicite ; l'accès restreint le limite au déposant et aux agents autorisés. |
| **GED-06** | Des modèles de courrier à l'en-tête de la direction, avec substitution de variables. |

## 10. Parapheur

| Réf. | Exigence |
|---|---|
| **PAR-01** | Une pièce versée à la bibliothèque est soumise aux visas internes, en réutilisant le moteur de circuits. |
| **PAR-02** | Le visa remonte la voie hiérarchique jusqu'au responsable du périmètre : une note d'antenne ne traverse pas la direction centrale. |
| **PAR-03** | Un refus ferme la pièce et rend les étapes suivantes sans objet. |
| **PAR-04** | La corbeille d'un viseur ne montre que les pièces à son étape courante. |

## 11. Ateliers et émargement

| Réf. | Exigence |
|---|---|
| **ATE-01** | Le QR code ne porte **aucune donnée personnelle** : deux identifiants courts aléatoires et une signature HMAC-SHA256. |
| **ATE-02** | La clé de signature est propre à chaque atelier ; un jeton d'un autre atelier est rejeté. |
| **ATE-03** | Un jeton altéré ou mal formé est rejeté sans distinction de cause. |
| **ATE-04** | L'émargement se fait par session — journée ou demi-journée —, seule façon de constater une présence partielle. |
| **ATE-05** | L'émargement est **idempotent** : son identifiant est produit par l'appareil, de sorte qu'une file rejouée après une coupure ne crée pas de doublon. |
| **ATE-06** | Un second scan portant un identifiant différent est **journalisé**, jamais perdu. |
| **ATE-07** | L'émargement manuel est possible mais exige un motif, conservé. |
| **ATE-08** | Un atelier clos ou annulé n'accepte plus d'émargement ; un participant révoqué n'émarge pas. |
| **ATE-09** | Un jeton invalide dans un lot n'interrompt pas le traitement des autres. |
| **ATE-10** | L'état de paiement ne retient que les participants ayant émargé ; le montant suit le barème au prorata des journées, les demi-journées comptant pour moitié. |
| **ATE-11** | L'attestation est réservée à qui a émargé au moins la moitié des sessions. |
| **ATE-12** | À la clôture, les présences constatées sont reportées sur l'activité du plan d'action. |
| **ATE-13** | L'émargement est réservé à l'organisateur, aux contrôleurs désignés, au responsable du périmètre et à la direction. |

### 11.1 Capacité hors ligne

Les ateliers se tiennent souvent dans des salles sans réseau fiable. L'application mobile télécharge l'atelier et sa liste de participants avant le départ, scanne hors ligne, puis dépose son lot au retour du réseau. **ATE-05** est la propriété qui rend ce mode possible : sans elle, le terrain devrait savoir ce qui a été transmis.

Cas de référence vérifié : un atelier de cinquante participants, collecté intégralement hors ligne et déposé en une fois.

## 12. Achats et stocks

| Réf. | Exigence |
|---|---|
| **ACH-01** | Expression de besoin numérotée par périmètre, portant des lignes d'articles et un montant estimé dérivé de celles-ci. |
| **ACH-02** | Le circuit de validation dépend du montant engagé : seuils paramétrés, non codés. |
| **ACH-03** | Retenir une offre exige au moins deux consultations. |
| **ACH-04** | Commander à un fournisseur dont le compte contribuable manque est refusé. |
| **ACH-05** | La réception peut être partielle, avec observations. |
| **ACH-06** | Une facture s'écartant de plus de 10 % du bon de commande demande une justification. |
| **ACH-07** | La facture solde le besoin et vient grossir le budget exécuté de l'activité rattachée. |
| **STO-01** | Le stock **dérive du journal** : toute quantité s'explique par une entrée, une sortie ou un inventaire. |
| **STO-02** | Chaque mouvement conserve le stock résultant ; le journal est confrontable au stock affiché. |
| **STO-03** | Une sortie ne peut pas dépasser le stock disponible. |
| **STO-04** | Une sortie exige un bénéficiaire. |
| **STO-05** | Un inventaire **fixe** la quantité comptée, quelle qu'elle soit ; son motif est exigé. |
| **STO-06** | La réception d'une commande fait entrer au magasin les articles qui y sont tenus ; ce qui n'est pas stockable est réceptionné sans mouvement. |
| **STO-07** | Un article sous son seuil d'alerte est signalé. |
| **STO-08** | Inventaire des équipements durables : code, marque, numéro de série, affectation, valeur, état. |

### 12.1 Seuils d'engagement livrés

| Montant estimé | Circuit |
|---|---|
| Jusqu'à 100 000 FCFA | Supérieur hiérarchique |
| 100 000 à 2 000 000 FCFA | + sous-directeur et responsable du périmètre |
| Au-delà de 2 000 000 FCFA | + engagement du directeur |

Ces seuils relèvent de la direction et se modifient dans l'administration sans livraison de code.

## 13. Site public

| Réf. | Exigence |
|---|---|
| **PUB-01** | Le site public est géré par un CMS : les rédacteurs publient sans intervention technique. |
| **PUB-02** | Brouillons, prévisualisation et historique des révisions. |
| **PUB-03** | Les contenus non publiés restent invisibles du public. |
| **PUB-04** | Le menu est déduit de l'arborescence éditoriale. |
| **PUB-05** | L'accès à l'espace agent est masquable depuis l'administration. |
| **PUB-06** | Vérification publique d'un acte signé par son code, sans authentification. |

## 14. Exigences transverses

### 14.1 Droits et cloisonnement

| Réf. | Exigence |
|---|---|
| **SEC-01** | Authentification par matricule ou courriel ; changement de mot de passe imposé à la première connexion. |
| **SEC-02** | Mots de passe hachés en Argon2. |
| **SEC-03** | Verrouillage après échecs répétés de connexion. |
| **SEC-04** | Journal d'audit des actions sensibles, horodaté et porteur de l'adresse IP. |
| **SEC-05** | Cloisonnement par périmètre appliqué en liste **et** à l'accès direct. |
| **SEC-06** | En production : HTTPS imposé, cookies sécurisés, HSTS, `X-Frame-Options`. |

### 14.2 Technique

| Réf. | Exigence |
|---|---|
| **TEC-01** | Monolithe Django modulaire : une application par domaine, socle indépendant des applications métier. |
| **TEC-02** | PostgreSQL en production ; démarrage possible sur SQLite en développement. |
| **TEC-03** | Déploiement en conteneurs : application, worker et ordonnanceur Celery, PostgreSQL, Redis, stockage objet, capture des courriels. |
| **TEC-04** | API REST documentée par un schéma OpenAPI, consommée par l'application mobile Flutter. |
| **TEC-05** | Authentification mobile par jeton JWT. |
| **TEC-06** | Suite de tests automatisés exécutable sans dépendance externe. |
| **TEC-07** | Analyse statique du code sans avertissement. |

### 14.3 Qualités attendues

| Réf. | Exigence |
|---|---|
| **QUA-01** | Toute règle métier refusée s'accompagne d'un message expliquant ce qui manque. |
| **QUA-02** | Toute décision irréversible — rejet, classement, annulation, report — exige un motif, conservé. |
| **QUA-03** | Les états calculés (statuts, taux, stocks) ne sont jamais saisis directement. |
| **QUA-04** | Les référentiels — circuits, axes, barèmes, seuils, modèles — sont modifiables sans livraison de code. |

---

## 15. Matrice de traçabilité

Chaque exigence renvoie aux tests qui la vérifient. Cette matrice est contrôlée par `tests/test_tracabilite.py` : un test référencé qui n'existe plus fait échouer la suite.

| Réf. | Tests |
|---|---|
| ORG-01 | `apps/circuits/tests.py::test_l_agent_herite_du_perimetre_de_sa_structure` |
| ORG-02 | `apps/circuits/tests.py::test_le_responsable_est_celui_de_la_structure_de_tete` |
| ORG-03 | `apps/circuits/tests.py::test_les_trois_perimetres_sont_autonomes` |
| ORG-04 | `apps/circuits/tests.py::test_les_actes_sont_numerotes_par_perimetre`<br>`apps/courrier/tests.py::test_series_distinctes_par_sens_et_par_perimetre`<br>`apps/achats/tests.py::test_serie_annuelle_par_perimetre` |
| ORG-05 | `apps/circuits/tests.py::test_un_responsable_ne_voit_que_son_perimetre`<br>`apps/courrier/tests.py::test_un_agent_ne_voit_que_le_courrier_de_son_perimetre`<br>`apps/ateliers/tests.py::test_visibilite_par_perimetre`<br>`apps/achats/tests.py::test_les_besoins_sont_cloisonnes` |
| ORG-06 | `apps/circuits/tests.py::test_le_service_du_personnel_voit_tous_les_perimetres` |
| ORG-07 | `apps/courrier/tests.py::test_porter_le_role_de_chef_ne_suffit_pas_a_imputer`<br>`apps/courrier/tests.py::test_meme_regle_pour_le_plan_d_action`<br>`apps/courrier/tests.py::test_le_secretariat_enregistre_mais_n_impute_pas` |
| ORG-08 | `apps/core/migrations/0006_reprise_organisation_decret_2026_509.py` |
| ORG-09 | `apps/circuits/tests.py::test_les_structures_hors_decret_sont_retirees`<br>`apps/circuits/tests.py::test_le_service_du_personnel_est_conserve`<br>`apps/circuits/tests.py::test_les_sous_directions_du_decret_sont_conservees` |
| ORG-10 | `apps/circuits/tests.py::test_une_structure_porteuse_d_historique_est_desactivee`<br>`apps/circuits/tests.py::test_un_second_passage_est_sans_effet` |
| ORG-11 | `apps/circuits/tests.py::test_les_agents_suivent_les_attributions_de_leur_structure`<br>`apps/circuits/tests.py::test_sans_correspondance_les_agents_vont_a_la_direction`<br>`apps/circuits/tests.py::test_une_correspondance_peut_etre_precisee_en_ligne_de_commande`<br>`apps/circuits/tests.py::test_la_dpfc_est_rattachee_a_la_direction_generale` |
| CIR-01 | `apps/circuits/tests.py::test_circuit_central_suit_la_voie_hierarchique` |
| CIR-02 | `apps/circuits/tests.py::test_l_acte_du_chef_d_antenne_remonte_a_la_drena` |
| CIR-03 | `apps/achats/tests.py::test_petite_depense_s_arrete_au_superieur`<br>`apps/achats/tests.py::test_depense_moyenne_remonte_au_responsable_du_perimetre`<br>`apps/achats/tests.py::test_engagement_important_remonte_a_la_direction` |
| CIR-04 | `apps/circuits/tests.py::test_un_agent_ne_valide_jamais_sa_propre_demande` |
| CIR-05 | `apps/circuits/tests.py::test_une_etape_sans_titulaire_est_ignoree_si_facultative` |
| CIR-06 | `apps/circuits/tests.py::test_une_etape_obligatoire_sans_titulaire_bloque` |
| CIR-07 | `apps/circuits/tests.py::test_un_perimetre_peut_avoir_son_propre_circuit` |
| CIR-08 | `apps/circuits/tests.py::test_les_circuits_modeles_couvrent_tous_les_types_d_actes` |
| CIR-09 | `apps/courrier/tests.py::test_le_circuit_remonte_la_voie_hierarchique`<br>`apps/achats/tests.py::test_parcours_favorable_complet` |
| ACT-01 | `apps/rh/tests.py::test_circuit_central_complet`<br>`apps/rh/tests.py::test_permission_centrale_sans_signature_directeur` |
| ACT-02 | `apps/rh/tests.py::test_weekend_exclu`<br>`apps/rh/tests.py::test_jour_ferie_exclu`<br>`apps/rh/tests.py::test_dates_inversees` |
| ACT-03 | `apps/rh/tests.py::test_ordre_de_mission_exige_une_destination` |
| ACT-04 | `apps/rh/tests.py::test_mission_hors_perimetre_exige_tdr_et_invitation`<br>`apps/rh/tests.py::test_mission_hors_ressort_etablie_par_la_drena` |
| ACT-05 | `apps/rh/tests.py::test_depot_par_le_secretariat_pour_un_agent`<br>`apps/rh/tests.py::test_depot_et_transmission` |
| ACT-06 | `apps/rh/tests.py::test_decision_du_chef_apfc_approuve_et_decompte_le_solde` |
| ACT-07 | `apps/rh/tests.py::test_rejet_stoppe_le_circuit`<br>`apps/rh/tests.py::test_file_de_validation_respecte_l_ordre` |
| SIG-01 | `apps/signature/tests.py::test_creation_de_la_bi_cle`<br>`apps/signature/tests.py::test_code_trop_court_refuse`<br>`apps/signature/tests.py::test_code_incorrect_refuse_la_signature` |
| SIG-02 | `apps/signature/tests.py::test_signature_et_verification`<br>`apps/signature/tests.py::test_empreinte_stable_et_sensible` |
| SIG-03 | `apps/signature/tests.py::test_modification_de_l_acte_invalide_la_signature` |
| SIG-04 | `apps/signature/tests.py::test_revocation_signalee_a_la_verification` |
| SIG-05 | `apps/signature/tests.py::test_page_publique_de_verification`<br>`apps/signature/tests.py::test_code_inconnu` |
| PIL-01 | `apps/activites/tests.py::test_cycle_soumission_validation`<br>`apps/activites/tests.py::test_un_seul_plan_par_perimetre_et_par_annee` |
| PIL-02 | `apps/activites/tests.py::test_un_plan_sans_activite_ne_peut_etre_soumis`<br>`apps/activites/tests.py::test_renvoi_exige_un_motif_et_ramene_en_preparation` |
| PIL-03 | `apps/activites/tests.py::test_le_plan_d_une_antenne_est_valide_par_le_directeur` |
| PIL-04 | `apps/activites/tests.py::test_le_premier_point_fait_passer_l_activite_en_cours` |
| PIL-05 | `apps/activites/tests.py::test_les_beneficiaires_et_les_montants_se_cumulent`<br>`apps/activites/tests.py::test_l_avancement_suit_le_dernier_point` |
| PIL-06 | `apps/activites/tests.py::test_cent_pour_cent_cloture_l_activite` |
| PIL-07 | `apps/activites/tests.py::test_taux_d_execution_du_plan_est_la_moyenne_des_activites`<br>`apps/activites/tests.py::test_les_activites_annulees_sortent_du_taux` |
| PIL-08 | `apps/activites/tests.py::test_une_activite_echue_et_non_achevee_est_en_retard` |
| PIL-09 | `apps/activites/tests.py::test_cloture_reporte_les_activites_restees_ouvertes` |
| PIL-10 | `apps/activites/tests.py::test_synthese_par_axe`<br>`apps/activites/tests.py::test_consolidation_nationale_liste_chaque_perimetre` |
| PIL-11 | `apps/activites/tests.py::test_le_chronogramme_positionne_les_activites_sur_les_mois` |
| PIL-12 | `apps/activites/tests.py::test_taux_d_atteinte_borne_a_cent`<br>`apps/activites/tests.py::test_cible_nulle_ne_divise_pas_par_zero` |
| COU-01 | `apps/courrier/tests.py::test_series_distinctes_par_sens_et_par_perimetre`<br>`apps/courrier/tests.py::test_la_serie_s_incremente` |
| COU-02 | `apps/courrier/tests.py::test_un_courrier_ne_peut_etre_enregistre_avant_sa_date` |
| COU-03 | `apps/courrier/tests.py::test_imputation_notifie_et_change_le_statut`<br>`apps/courrier/tests.py::test_un_courrier_depart_ne_s_impute_pas` |
| COU-04 | `apps/courrier/tests.py::test_imputation_pour_information_est_close_d_emblee` |
| COU-05 | `apps/courrier/tests.py::test_le_courrier_est_traite_quand_toutes_les_imputations_le_sont` |
| COU-06 | `apps/courrier/tests.py::test_seul_l_imputataire_rend_compte`<br>`apps/courrier/tests.py::test_compte_rendu_vide_refuse` |
| COU-07 | `apps/courrier/tests.py::test_retard_calcule_sur_l_imputation_la_plus_ancienne` |
| COU-08 | `apps/courrier/tests.py::test_classement_exige_un_motif_et_ferme_le_courrier` |
| COU-09 | `apps/courrier/tests.py::test_un_courrier_confidentiel_reste_invisible_aux_autres`<br>`apps/courrier/tests.py::test_l_imputataire_accede_au_courrier_confidentiel` |
| COU-10 | `apps/courrier/tests.py::test_la_direction_impute_dans_tous_les_perimetres` |
| GED-01 | `apps/courrier/tests.py::test_versions_numerotees_et_conservees`<br>`apps/courrier/tests.py::test_empreinte_et_taille_calculees` |
| GED-02 | `apps/courrier/tests.py::test_le_texte_est_extrait_et_rendu_cherchable`<br>`apps/courrier/tests.py::test_fichier_texte` |
| GED-03 | `apps/courrier/tests.py::test_un_fichier_illisible_n_empeche_pas_le_depot`<br>`apps/courrier/tests.py::test_type_non_gere_retourne_une_chaine_vide` |
| GED-04 | `apps/courrier/tests.py::test_filtres_de_recherche` |
| GED-05 | `apps/courrier/tests.py::test_recherche_limitee_au_perimetre`<br>`apps/courrier/tests.py::test_un_document_partage_traverse_les_perimetres`<br>`apps/courrier/tests.py::test_acces_restreint` |
| GED-06 | `apps/courrier/tests.py::test_substitution_des_variables`<br>`apps/courrier/tests.py::test_variable_absente_rendue_vide` |
| PAR-01 | `apps/courrier/tests.py::test_le_circuit_remonte_la_voie_hierarchique`<br>`apps/courrier/tests.py::test_visa_complet_cloture_la_piece` |
| PAR-02 | `apps/courrier/tests.py::test_une_piece_d_antenne_s_arrete_au_chef_d_antenne` |
| PAR-03 | `apps/courrier/tests.py::test_refus_ferme_la_piece_et_ignore_les_etapes_suivantes` |
| PAR-04 | `apps/courrier/tests.py::test_la_corbeille_ne_montre_que_l_etape_courante` |
| ATE-01 | `apps/ateliers/tests.py::test_le_jeton_ne_contient_aucune_donnee_personnelle` |
| ATE-02 | `apps/ateliers/tests.py::test_un_jeton_d_un_autre_atelier_est_rejete`<br>`apps/ateliers/tests.py::test_les_cles_sont_propres_a_chaque_atelier` |
| ATE-03 | `apps/ateliers/tests.py::test_un_jeton_altere_est_rejete`<br>`apps/ateliers/tests.py::test_un_jeton_mal_forme_est_rejete_sans_exception` |
| ATE-04 | `apps/ateliers/tests.py::test_generation_par_demi_journees`<br>`apps/ateliers/tests.py::test_le_matin_precede_l_apres_midi` |
| ATE-05 | `apps/ateliers/tests.py::test_renvoyer_le_meme_emargement_ne_cree_pas_de_doublon`<br>`apps/ateliers/tests.py::test_renvoyer_le_meme_lot_ne_cree_rien`<br>`apps/ateliers/tests.py::test_atelier_de_cinquante_participants_hors_ligne` |
| ATE-06 | `apps/ateliers/tests.py::test_un_second_scan_distinct_est_journalise_comme_doublon` |
| ATE-07 | `apps/ateliers/tests.py::test_emargement_manuel_exige_un_motif` |
| ATE-08 | `apps/ateliers/tests.py::test_on_n_emarge_pas_un_atelier_clos`<br>`apps/ateliers/tests.py::test_un_participant_revoque_n_emarge_pas` |
| ATE-09 | `apps/ateliers/tests.py::test_un_jeton_invalide_n_interrompt_pas_le_lot` |
| ATE-10 | `apps/ateliers/tests.py::test_l_etat_ne_retient_que_les_emarges`<br>`apps/ateliers/tests.py::test_le_montant_suit_le_bareme_et_les_jours_constates`<br>`apps/ateliers/tests.py::test_les_demi_journees_comptent_pour_moitie` |
| ATE-11 | `apps/ateliers/tests.py::test_attestation_reservee_a_qui_a_suffisamment_participe`<br>`apps/ateliers/tests.py::test_moins_de_la_moitie_des_sessions_ne_donne_pas_droit` |
| ATE-12 | `apps/ateliers/tests.py::test_la_cloture_reporte_les_presences_sur_le_plan_d_action` |
| ATE-13 | `apps/ateliers/tests.py::test_qui_peut_controler_l_emargement` |
| ACH-01 | `apps/achats/tests.py::test_le_montant_estime_derive_des_lignes`<br>`apps/achats/tests.py::test_un_besoin_sans_ligne_ne_se_soumet_pas` |
| ACH-02 | `apps/achats/tests.py::test_le_seuil_s_applique_aussi_en_antenne` |
| ACH-03 | `apps/achats/tests.py::test_une_seule_offre_ne_fait_pas_une_consultation`<br>`apps/achats/tests.py::test_retenir_une_offre_ecarte_les_autres` |
| ACH-04 | `apps/achats/tests.py::test_commande_refusee_si_le_compte_contribuable_manque` |
| ACH-05 | `apps/achats/tests.py::test_reception_partielle` |
| ACH-06 | `apps/achats/tests.py::test_un_ecart_de_plus_de_dix_pour_cent_est_signale`<br>`apps/achats/tests.py::test_un_ecart_raisonnable_passe` |
| ACH-07 | `apps/achats/tests.py::test_la_facture_solde_le_besoin`<br>`apps/achats/tests.py::test_la_depense_rejoint_le_plan_d_action` |
| STO-01 | `apps/achats/tests.py::test_le_stock_s_explique_par_le_journal` |
| STO-02 | `apps/achats/tests.py::test_chaque_mouvement_conserve_le_stock_resultant`<br>`apps/achats/tests.py::test_recalcul_apres_suppression_d_un_mouvement` |
| STO-03 | `apps/achats/tests.py::test_une_sortie_superieure_au_stock_est_refusee` |
| STO-04 | `apps/achats/tests.py::test_une_sortie_exige_un_beneficiaire` |
| STO-05 | `apps/achats/tests.py::test_l_inventaire_fixe_la_quantite_comptee` |
| STO-06 | `apps/achats/tests.py::test_la_reception_alimente_le_magasin` |
| STO-07 | `apps/achats/tests.py::test_articles_sous_seuil_limites_au_perimetre` |
| STO-08 | `apps/achats/tests.py::test_inventaire_des_equipements` |
| PUB-01 | `apps/site_public/tests.py::test_pages_principales`<br>`apps/site_public/tests.py::test_pages_de_detail`<br>`apps/site_public/tests.py::test_administration_wagtail_protegee` |
| PUB-02 | `apps/site_public/tests.py::test_les_brouillons_restent_invisibles` |
| PUB-03 | `apps/site_public/tests.py::test_les_brouillons_restent_invisibles` |
| PUB-04 | `apps/site_public/tests.py::test_accueil_affiche_les_contenus`<br>`apps/site_public/tests.py::test_recherche` |
| PUB-05 | `apps/site_public/tests.py::test_bouton_espace_agent_pilotable` |
| PUB-06 | `apps/signature/tests.py::test_page_publique_de_verification` |
| SEC-01 | `apps/rh/tests.py::test_connexion_requise`<br>`apps/accounts/tests.py::test_parcours_complet_depuis_l_intranet` |
| SEC-05 | `apps/api/tests.py::test_le_courrier_est_cloisonne_par_perimetre`<br>`apps/api/tests.py::test_le_magasin_est_cloisonne_par_perimetre`<br>`apps/courrier/tests.py::test_un_courrier_confidentiel_reste_invisible_aux_autres` |
| TEC-04 | `apps/api/tests.py::test_le_terrain_ne_voit_que_les_activites_de_son_perimetre` |
| TEC-05 | `apps/api/tests.py::test_connexion_retourne_le_profil`<br>`apps/api/tests.py::test_acces_refuse_sans_jeton` |

### 15.1 Exigences vérifiées autrement

Les exigences suivantes relèvent de la configuration, de l'architecture ou de pratiques transverses : aucun test unitaire ne les porte, mais chacune a son mode de contrôle.

| Réf. | Mode de vérification |
|---|---|
| SEC-02 | `manage.py check --deploy` ; `PASSWORD_HASHERS` place Argon2 en tête |
| SEC-03 | Configuration `django-axes`, active en production |
| SEC-04 | `JournalAction.tracer()` appelé à chaque opération sensible ; revue |
| SEC-06 | `manage.py check --deploy --settings=config.settings.prod` |
| TEC-01 | Revue d'architecture ; le socle n'importe aucune application métier |
| TEC-02 | Démarrage effectif sur les deux moteurs |
| TEC-03 | `docker compose -f infra/compose/docker-compose.dev.yml up` |
| TEC-06 | `manage.py test --settings=config.settings.test`, sans service externe |
| TEC-07 | `ruff check apps config` sans avertissement |
| QUA-01 | Revue des messages d'erreur ; chaque exception métier porte son explication |
| QUA-02 | Revue : rejet, classement, annulation et report exigent un motif |
| QUA-03 | Revue : les champs calculés sont `editable=False` ou dérivés en service |
| QUA-04 | Référentiels éditables dans `/admin/` : circuits, axes, barèmes, seuils, modèles |

---

## 16. Ce qui reste à trancher

Points qui relèvent de la direction, et non de la réalisation technique.

| Point | Nature de la décision |
|---|---|
| **Seuils d'engagement** | Les montants livrés (100 000 et 2 000 000 FCFA) sont des valeurs de travail, à confronter aux règles de la comptabilité publique applicables à la direction. |
| **Barèmes de participation** | Les montants journaliers des ateliers sont à aligner sur les barèmes officiels en vigueur. |
| **Règle d'attestation** | Le seuil retenu — la moitié des sessions — est un choix par défaut. |
| **OCR des documents scannés** | Facultatif. Son installation suppose une décision sur la charge serveur acceptable. |
| **Données personnelles** | Les coordonnées des participants extérieurs aux ateliers sont stockées en clair. Un chiffrement au repos est techniquement possible ; la décision dépend du niveau d'exigence retenu. |

---

### 16.1 Points tranchés

| Point | Décision | Date |
|---|---|---|
| **Sous-directions antérieures au décret** | Supprimées de l'organigramme, **à l'exception du service du personnel et des affaires administratives**, conservé. Appliqué par `manage.py nettoyer_organisation`. Une structure porteuse d'historique est désactivée plutôt que supprimée. | Version 3.4.2 |
| **Répartition des agents** | Les agents suivent les attributions de leur structure : formation continue → SDFPC, programmes et manuels → SDPPBS, ressources numériques → SDIP. | Version 3.4.3 |

---

## 17. Historique du document

| Version | Objet |
|---|---|
| 3.0.0 | Socle : organisation du décret, périmètres de gestion, circuits paramétrables, pile technique |
| 3.1.0 | Pilotage des activités |
| 3.2.0 | Courrier, documents et parapheur |
| 3.3.0 | Ateliers et émargement par QR code |
| 3.4.0 | Achats, bons de commande, magasin et équipements |
| 3.4.1 | Cahier des charges et matrice de traçabilité |
| 3.4.2 | Décision sur les sous-directions antérieures au décret (ORG-09 à ORG-11) |
| 3.4.3 | Répartition des agents selon les attributions reprises |

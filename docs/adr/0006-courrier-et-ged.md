# ADR 0006 — Courrier, documents et parapheur

**Registre par périmètre.** Chaque périmètre tient son propre registre du courrier, avec une série annuelle par sens : `ARR-0001/2026/APFC-GBK`, `DEP-0001/2026/DPFC`. C'est la même règle que pour les actes administratifs et les plans d'action — l'autonomie de gestion vaut aussi pour la correspondance.

**Le statut du courrier est déduit, pas saisi.** Un courrier arrivé est *enregistré* tant qu'il n'est pas imputé, *imputé* tant qu'une imputation reste ouverte, *traité* quand toutes le sont. Une imputation « pour information » est close dès sa création : elle n'appelle pas de suite et ne doit donc pas retenir le courrier. Le classement sans suite exige un motif.

**Confidentialité.** Un courrier confidentiel n'est visible que de son enregistreur, de ses imputataires et du responsable du périmètre — la direction et le service du personnel gardant leur vue d'ensemble. Le filtrage est implémenté deux fois, dans le queryset (`visibles_par`) et unitairement (`peut_etre_vu_par`), parce que les listes et les accès directs empruntent des chemins différents.

**Les droits tiennent à la désignation, pas au rôle.** Porter le rôle de chef d'antenne ne suffit pas à imputer le courrier d'une antenne : il faut en être le responsable désigné (`dirige_son_perimetre`). La distinction compte après une mutation mal soldée, où deux agents peuvent porter le même rôle.

**Documents versionnés.** Chaque dépôt crée une version numérotée, avec son empreinte SHA-256 et sa taille ; les versions antérieures restent consultables. Un document reste au périmètre sauf s'il est explicitement partagé ; l'accès restreint le limite au déposant et aux agents autorisés.

**Extraction du texte dégradée, jamais bloquante.** Trois niveaux : fichier texte lu directement, PDF natif lu par pypdf, PDF scanné confié à un moteur d'OCR facultatif. Un fichier illisible est enregistré sans texte — donc absent de la recherche plein texte — mais le dépôt aboutit. Indexer ne doit jamais empêcher d'archiver.

**Recherche portable.** PostgreSQL utilise son moteur de recherche français (`SearchVector` pondéré, titre en A, contenu en B) ; les autres bases retombent sur une recherche par sous-chaîne. Le modèle ne porte pas de colonne spécifique à PostgreSQL, ce qui laisse le projet démarrable sur SQLite.

**Le parapheur réutilise le moteur de circuits.** `PieceParapheur` expose la même interface qu'une demande administrative — `agent`, `type`, `regles`, `est_mission_hors_perimetre` — de sorte que `circuits.services` n'a rien à connaître du courrier. C'est la vérification concrète de la règle posée en [ADR 0001](0001-monolithe-modulaire.md) : le socle ne dépend d'aucune application métier, et les applications métier s'y branchent par une interface, pas par un couplage.

**Le visa s'arrête au responsable du périmètre.** Une note d'antenne n'a pas à traverser la direction centrale : le circuit remonte la voie hiérarchique jusqu'au chef d'antenne ou de centre. La direction centrale intercale son sous-directeur.

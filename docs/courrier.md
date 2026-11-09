# Courrier et gestion documentaire

Voir [l'ADR 0006](adr/0006-courrier-et-ged.md) pour les décisions de conception.

## Registre du courrier

Chaque périmètre tient sa propre série annuelle, par sens :

| Sens | Forme du numéro |
|---|---|
| Arrivée | `ARR-0001/2026/DPFC`, `ARR-0001/2026/APFC-GBK` |
| Départ | `DEP-0001/2026/DPFC` |

Le numéro est attribué automatiquement à l'enregistrement.

### Cycle d'un courrier arrivé

```
Enregistré ──imputation──▶ Imputé ──toutes les suites données──▶ Traité
     │
     └──────── classement sans suite (motif obligatoire) ──────▶ Classé
```

| Action | Qui |
|---|---|
| Enregistrer | Secrétariat, responsable du périmètre, direction |
| Imputer, classer | Responsable **désigné** du périmètre, direction |
| Rendre compte d'une imputation | L'imputataire lui-même |

Une imputation **pour information** est close dès sa création : elle ne retient pas le courrier.

Un courrier est **en retard** dès qu'une de ses imputations dépasse son délai sans être traitée ; le retard affiché est celui de l'imputation la plus ancienne.

### Confidentialité

Un courrier marqué confidentiel n'est visible que de :

- l'agent qui l'a enregistré ;
- ses imputataires ;
- le responsable du périmètre ;
- la direction, le service du personnel et l'administration.

## Bibliothèque documentaire

- **Versions** : chaque dépôt crée une version numérotée, avec empreinte SHA-256 et taille. Les versions antérieures restent téléchargeables.
- **Portée** : un document reste au périmètre, sauf s'il est coché « partagé avec tous les périmètres ».
- **Accès restreint** : limite la consultation au déposant et aux agents expressément autorisés.
- **Recherche plein texte** : porte sur le titre, la description et le texte extrait du fichier.

### Extraction du texte

| Type de fichier | Traitement |
|---|---|
| `.txt`, `.csv`, `.md`, `.json`, `.xml`, `.html` | lu directement |
| PDF avec couche texte | extrait par pypdf |
| PDF scanné | nécessite un moteur d'OCR (facultatif) |
| Autres | non indexé |

Un fichier illisible **n'empêche jamais le dépôt** : le document est enregistré, simplement absent de la recherche plein texte. Pour activer l'OCR des documents scannés, installer `pymupdf4llm` et `rapidocr-onnxruntime` ; sans eux, le reste fonctionne à l'identique.

## Parapheur

Une pièce déjà versée à la bibliothèque est soumise aux visas internes. Le circuit est paramétré dans `circuits` sous le type d'acte `PARAPHEUR` :

| Périmètre | Circuit livré |
|---|---|
| Direction centrale | Supérieur hiérarchique → sous-directeur → directeur |
| Antenne | Supérieur hiérarchique → chef d'antenne |
| CNRPN | Supérieur hiérarchique → chef de centre |

Un refus ferme la pièce et rend les étapes suivantes sans objet ; le motif est obligatoire. Comme pour les actes, un même agent ne vise qu'une fois et ne vise jamais sa propre pièce.

Le circuit se modifie dans `/admin/` → Circuits de validation, type d'acte `PARAPHEUR`.

## Modèles de courrier

`/intranet/courrier/modeles/` propose des modèles à l'en-tête de la direction. Variables substituées : `{{ objet }}`, `{{ correspondant }}`, `{{ date }}`, `{{ perimetre }}`, `{{ signataire }}`. Ils se créent dans `/admin/` → Modèles de documents.

## Écrans

| Écran | Adresse |
|---|---|
| Tableau du courrier | `/intranet/courrier/` |
| Registre (filtres, export CSV) | `/intranet/courrier/registre/` |
| Bibliothèque documentaire | `/intranet/courrier/documents/` |
| Parapheur | `/intranet/courrier/parapheur/` |
| Modèles | `/intranet/courrier/modeles/` |

## Application mobile

| Méthode | Chemin | Rôle |
|---|---|---|
| GET | `/api/v1/courriers/` | registre du périmètre — filtres `sens`, `statut`, `retard` |
| GET | `/api/v1/imputations/?en_attente=1` | mes imputations à traiter |
| POST | `/api/v1/imputations/<id>/traiter/` | suite donnée, depuis le terrain |
| GET | `/api/v1/documents/?q=...` | recherche plein texte dans la bibliothèque |

## Jeu de démonstration

```bash
python manage.py charger_courrier
```

Couvre : courrier en attente d'imputation, imputé en cours, traité avec sa réponse au départ, classé sans suite, en retard, confidentiel ; une série propre d'antenne ; documents versionnés, partagés et à accès restreint ; une pièce visée et une pièce en cours de visa.

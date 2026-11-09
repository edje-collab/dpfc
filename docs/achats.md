# Achats et stocks

Voir [l'ADR 0008](adr/0008-achats-et-stocks.md) pour les décisions de conception.

## La procédure, en cinq temps

```
Brouillon ──transmission──▶ En validation ──▶ Validé ──commande──▶ Commandé ──facture──▶ Soldé
                                  │
                                  └──── avis défavorable (motif) ──▶ Rejeté
```

1. **Exprimer le besoin** — objet, justification, articles et quantités. Le numéro suit la série annuelle du périmètre : `EB-0001/2026/APFC-GBK`.
2. **Faire valider** — le circuit s'allonge avec le montant (voir ci-dessous).
3. **Consulter les fournisseurs** — au moins deux offres sont exigées pour en retenir une.
4. **Commander** — bon de commande `BC-0001/2026/DPFC`, refusé si le compte contribuable du fournisseur manque.
5. **Réceptionner, puis facturer** — la réception alimente le magasin, la facture solde le besoin.

## Le circuit dépend du montant

| Montant estimé | Qui valide |
|---|---|
| Jusqu'à 100 000 FCFA | Supérieur hiérarchique |
| 100 000 à 2 000 000 FCFA | + sous-directeur (au central) et responsable du périmètre |
| Au-delà de 2 000 000 FCFA | + engagement du directeur |

Les seuils se modifient dans `/admin/` → Circuits de validation, type d'acte `BESOIN`, champ **seuil de montant** de chaque étape.

## Le magasin

Le stock **dérive du journal des mouvements**. Trois types d'écriture :

| Type | Effet |
|---|---|
| Entrée | Ajoute au stock |
| Sortie | Retranche — refusée si elle dépasse le stock, bénéficiaire obligatoire |
| Inventaire | **Fixe** la quantité comptée, quelle qu'elle soit ; le motif est exigé |

Chaque mouvement conserve le stock résultant. La fiche d'un article affiche un contrôle de cohérence entre le journal et le stock affiché — il doit toujours indiquer « conforme ».

Un article dont le stock passe sous son seuil d'alerte est signalé sur le tableau de bord et filtrable au magasin.

## Équipements

Inventaire des biens durables : code d'inventaire, marque, numéro de série, agent affectataire, valeur d'acquisition et état (bon, passable, en panne, réformé). Un équipement peut être rattaché au bon de commande qui l'a acquis.

## Écrans

| Écran | Adresse |
|---|---|
| Tableau des achats | `/intranet/achats/` |
| Expressions de besoin | `/intranet/achats/besoins/` |
| Bons de commande | `/intranet/achats/commandes/` |
| Magasin (export CSV) | `/intranet/achats/magasin/` |
| Fiche d'un article et son journal | `/intranet/achats/magasin/<id>/` |
| Équipements | `/intranet/achats/equipements/` |

Les fournisseurs se gèrent dans `/admin/` → Fournisseurs.

## Application mobile

| Méthode | Chemin | Rôle |
|---|---|---|
| GET | `/api/v1/besoins/` | besoins du périmètre (`statut`, `mes_besoins`) |
| GET | `/api/v1/articles/?alerte=1` | état du magasin, articles à réapprovisionner |
| GET | `/api/v1/articles/<id>/mouvements/` | journal d'un article |
| POST | `/api/v1/articles/<id>/mouvement/` | entrée, sortie ou inventaire depuis le terrain |

Le relevé d'inventaire se fait ainsi rayon par rayon, le téléphone à la main.

## Jeu de démonstration

```bash
python manage.py charger_achats
```

Couvre : un dossier complet de la consultation à la facture, un besoin validé en attente d'offres, un besoin en cours de validation, un besoin rejeté avec son motif, un brouillon, un besoin d'antenne ; un magasin dont deux articles passent sous le seuil ; un inventaire corrigeant un écart constaté ; six équipements dont un en panne.

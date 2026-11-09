# ADR 0008 — Achats et tenue du magasin

## Le stock dérive du journal, il ne se saisit pas

Un article porte un champ `stock`, mais ce n'est qu'une **vue mise en cache** du journal des mouvements. Toute quantité s'explique par une entrée, une sortie ou un inventaire ; chaque mouvement conserve le stock résultant (`stock_apres`), et `stock_reel` recalcule la valeur depuis le journal pour la confronter au cache.

Conséquence pratique : on ne corrige jamais un stock en modifiant un compteur. Un écart constaté au comptage se solde par un **mouvement d'inventaire**, qui fixe la quantité comptée et laisse trace du motif. L'historique reste vérifiable, ce qui est le minimum pour un magasin public.

`recalculer_stock()` répare le cache après une reprise de données ou la suppression d'un mouvement, et retourne l'écart — normalement nul.

## Deux garde-fous au magasin

- **Une sortie ne peut pas dépasser le stock.** Le magasin ne distribue pas ce qu'il n'a pas ; l'écriture est refusée avec le stock disponible en clair.
- **Une sortie exige un bénéficiaire.** Une quantité qui disparaît sans destinataire n'est pas traçable.

L'inventaire échappe à la première règle : fixer la quantité comptée, quelle qu'elle soit, est précisément son objet.

## Le circuit de validation dépend du montant

Une rame de papier n'engage pas la direction ; un photocopieur si. Plutôt que de coder ce seuil, on l'a porté dans le moteur de circuits : chaque étape a un `seuil_montant`, et ne s'applique qu'au-delà. Les circuits livrés distinguent trois niveaux.

| Montant | Circuit |
|---|---|
| Jusqu'à 100 000 FCFA | Supérieur hiérarchique |
| De 100 000 à 2 000 000 FCFA | + sous-directeur et responsable du périmètre |
| Au-delà de 2 000 000 FCFA | + engagement du directeur |

L'objet qui circule expose `montant_circuit` ; les actes administratifs, qui n'en portent pas, valent zéro et ne déclenchent aucune étape à seuil. Le moteur reste ainsi ignorant de ce qu'il fait circuler — la règle posée en [ADR 0001](0001-monolithe-modulaire.md).

## Deux offres font une consultation

Retenir une offre exige qu'il y en ait au moins deux : un choix entre une seule option n'en est pas un. De même, commander à un fournisseur dont le compte contribuable manque est refusé — c'est une pièce exigible pour toute commande publique.

## Les écarts sont signalés, pas bloqués

Une facture qui s'écarte de plus de 10 % du bon de commande déclenche une erreur de validation invitant à justifier l'écart. Le seuil n'interdit pas la dépense : il force à l'expliquer.

## Ce qui relie les achats au reste

- **Réception → magasin** : les articles tenus au magasin y entrent automatiquement, avec le bon de commande en référence. Ce qui n'est pas stockable — une prestation — est réceptionné sans mouvement.
- **Facture → plan d'action** : si le besoin était rattaché à une activité, le montant facturé vient grossir son budget exécuté. Le pilotage se nourrit de la dépense réelle, sans double saisie.

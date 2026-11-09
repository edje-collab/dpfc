# ADR 0007 — Émargement par QR code, utilisable hors ligne

**Contexte.** Les ateliers se tiennent souvent loin d'Abidjan, dans des salles sans réseau fiable. L'émargement conditionne l'état de paiement et les attestations : il doit être fiable, traçable, et ne pas dépendre de la connexion.

## Le QR code ne porte aucune donnée personnelle

```
DPFC1.<atelier>.<participant>.<signature>
signature = base32(HMAC-SHA256(clé de l'atelier, "DPFC1|atelier|participant"))[:16]
```

Ni nom, ni matricule, ni téléphone : seulement deux identifiants courts aléatoires — distincts des clés primaires — et une signature. Un badge photographié, perdu ou ramassé ne révèle rien de son porteur, et ne permet pas non plus de dénombrer les participants.

**La clé est propre à chaque atelier.** Un jeton valable pour un atelier ne vaut rien pour un autre, et un jeton altéré est rejeté. Le contrôleur voit « jeton invalide » sans distinction de cause : il n'a pas à savoir laquelle des trois s'applique.

## L'émargement est idempotent

L'identifiant primaire de l'émargement est un UUID **produit par l'appareil au moment du scan**, pas par le serveur. Conséquence : un téléphone qui perd le réseau accumule ses scans, puis renvoie sa file entière dès que la connexion revient — plusieurs fois s'il le faut — sans jamais créer de doublon.

C'est la propriété qui rend le travail hors ligne possible. Sans elle, le terrain devrait savoir ce qui a été transmis et ce qui ne l'a pas été.

## Un doublon n'est jamais perdu

Un second scan portant un identifiant différent — deux appareils, deux contrôleurs — ne remplace pas le premier et n'est pas rejeté en silence : il est journalisé dans `DoublonEmargement`. En cas de contestation, on peut reconstituer ce qui s'est réellement passé.

## L'émargement manuel est motivé

Quand le QR ne peut pas être lu, le contrôleur émarge à la main — mais le motif est obligatoire et conservé. C'est la contrepartie d'une procédure qui contourne le contrôle automatique.

## L'émargement se fait par session, pas par atelier

Une session est une journée ou une demi-journée. C'est la seule façon de constater une présence partielle — un participant reparti après le déjeuner —, ce qui conditionne directement le montant dû.

## Ce qui découle de l'émargement

- **État de paiement** : ne retient que les participants ayant effectivement émargé. Nul n'est payé pour une présence non constatée. Le montant suit le barème de la catégorie, au prorata des journées, les demi-journées comptant pour moitié.
- **Attestation** : délivrée à qui a émargé au moins la moitié des sessions. Une présence symbolique ne vaut pas participation.
- **Plan d'action** : à la clôture, les présences constatées sont reportées sur l'activité rattachée. Le pilotage se nourrit de ce qui a été fait sur le terrain, au lieu d'une saisie déclarative séparée.

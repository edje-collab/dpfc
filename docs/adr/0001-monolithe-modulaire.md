# ADR 0001 — Monolithe Django par applications

**Décision.** Un dépôt, un déploiement, une application Django par domaine. Le socle (`core`, `accounts`, `circuits`) ne dépend d'aucune application métier ; les applications métier s'appuient sur le socle et communiquent par `services.py`.

**Pourquoi.** Équipe réduite et exploitation par un seul administrateur, comme pour la plateforme e-PECU dont ce projet reprend la pile. Un découpage en services séparés coûterait plus qu'il ne rapporterait à cette échelle.

**Conséquence.** `apps/circuits/services.py` ne connaît de l'application `rh` que trois attributs de la demande (`agent`, `regles`, `est_mission_hors_perimetre`). Toute nouvelle application métier (courrier, activités, achats) se branchera sur le même socle sans le modifier.

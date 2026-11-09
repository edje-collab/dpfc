# ADR 0002 — Le périmètre de gestion comme unité d'autonomie

**Contexte.** Le décret n° 2026-509 du 05 août 2026 place la DPFC sous la Direction Générale de la Pédagogie, des Curricula et du Suivi des Programmes et lui donne trois sous-directions. S'y ajoutent, par arrêté d'organisation, des structures dont **la gestion est autonome** : les antennes régionales (APFC), dirigées par un chef d'antenne, et le Centre National de Ressources Pédagogiques Numériques (CNRPN), dirigé par un chef de centre.

**Décision.** Introduire `core.Perimetre` : l'unité dans laquelle les actes sont instruits, numérotés et pilotés. Trois types — `CENTRALE`, `ANTENNE`, `CENTRE`. Chaque structure appartient à un périmètre ; une seule structure par périmètre en est la tête (`perimetre_racine`), et son responsable est le responsable du périmètre.

**Ce que cela produit.**

- Un agent hérite du périmètre de sa structure : `agent.perimetre`.
- Les actes sont numérotés par périmètre (`PA-0001/2026/APFC-GBK`, `PA-0001/2026/CNRPN`), chaque périmètre tenant sa propre série annuelle.
- Un chef d'antenne ou un chef de centre ne voit que les agents de son périmètre (`perimetre_agents`) ; le service du personnel et la direction voient l'ensemble.
- Les circuits de validation sont définis par type de périmètre, et peuvent être spécialisés périmètre par périmètre.

**Alternative écartée.** Déduire l'autonomie du seul champ `rattachement` (CENTRALE / REGION), comme auparavant. Cela marchait pour les antennes mais pas pour le CNRPN, rattaché à la direction centrale tout en étant autonome : l'autonomie de gestion et l'implantation géographique sont deux choses distinctes.

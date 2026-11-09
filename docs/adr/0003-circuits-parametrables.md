# ADR 0003 — Circuits de validation paramétrables plutôt que codés

**Contexte.** Le trajet d'un acte était écrit en Python dans `apps/rh/services.py` : une suite de `if` mêlant le type d'acte, l'affectation de l'agent et le cas particulier de la mission hors ressort. Toute évolution de l'organisation imposait une livraison de code.

**Décision.** Décrire les circuits en données (`circuits.Circuit` et `circuits.Etape`). Une étape ne nomme pas un agent mais une **fonction** (`Designation`) : supérieur hiérarchique, responsable de la structure, sous-directeur, responsable du périmètre, directeur régional, ou premier agent portant un rôle. Le valideur réel est résolu à la soumission.

**Conditions.** Une étape porte zéro, une ou plusieurs conditions, toutes requises : visa du personnel exigé, signature du directeur exigée (ou non), mission hors ressort, agent dirigeant lui-même le périmètre. C'est ce qui permet d'exprimer, par exemple, « l'acte du chef d'antenne remonte à la DRENA puis au directeur ».

**Résolution.** Un même agent ne valide qu'une fois ; nul ne valide sa propre demande ; un agent désactivé ne porte aucune étape. Une étape facultative sans titulaire est ignorée, une étape obligatoire sans titulaire bloque la soumission avec un message nommant le circuit à compléter.

**Repli.** Si un périmètre ne définit pas de circuit pour un type d'acte, le circuit modèle de son type de périmètre s'applique. Les modèles sont réinstallés après chaque migration : ce sont des données de référence, pas du contenu éditable à perdre.

**Règle conservée.** Pour l'acte d'un responsable de périmètre, le visa du service du personnel et la signature du directeur restent exclusifs, comme dans le code d'origine — la condition `SI_SANS_SIGNATURE_DIRECTEUR` l'exprime explicitement.

# ADR 0005 — Le plan d'action annuel comme cadre du pilotage

**Contexte.** La direction demande une plateforme de gestion, pas seulement un registre d'actes administratifs. Chaque périmètre — la direction centrale, chaque antenne régionale, le CNRPN — conduit un programme d'activités dont il doit rendre compte.

**Décision.** Un `PlanAction` par périmètre et par année, cadre de toutes les activités de l'exercice. Il suit un cycle court : préparation → soumission → validation → clôture. L'`Activite` est le pivot : elle porte une période prévue, un budget, des bénéficiaires, un responsable et un axe stratégique.

**Qui valide quoi.** Les plans des périmètres déconcentrés sont validés par le directeur central ; la direction centrale valide le sien. Cela reflète l'autonomie de gestion de chaque périmètre, assortie de la responsabilité d'ensemble du directeur.

**L'avancement n'est pas saisi, il est rapporté.** On n'édite jamais directement le pourcentage d'une activité : on dépose un compte rendu (`Avancement`) qui porte le taux atteint, les réalisations, les difficultés, les bénéficiaires touchés et le montant engagé sur la période. L'activité en dérive : le taux suit le dernier compte rendu, les bénéficiaires et les montants se cumulent, et les changements d'état (en cours à la première déclaration, réalisée à 100 %) sont automatiques. L'historique reste ainsi vérifiable.

**Les taux sont calculés, jamais stockés.** Le taux d'un plan est la moyenne des avancements de ses activités, les annulées exclues du dénominateur — une activité abandonnée ne doit ni pénaliser ni flatter l'exécution. Le taux budgétaire et la couverture des bénéficiaires suivent la même logique.

**Clôture.** Clore un exercice reporte les activités restées ouvertes, avec mention explicite. Un plan clos ne laisse jamais d'activité dans un état indéterminé.

**Axes communs.** Le référentiel des axes stratégiques est national, pas propre à chaque périmètre : c'est ce qui rend la consolidation possible. Une antenne décline les mêmes axes que la direction centrale.

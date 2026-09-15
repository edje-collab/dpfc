# Journal des versions

## 1.1.1
- API : signature à la décision (`code_signature`), dépôt des pièces jointes en multipart, endpoint public de vérification.
- Application Flutter : bascule « mission hors périmètre DRENAET » avec envoi des TDR et de la lettre d'invitation, saisie du code de signature à la dernière étape, écran de vérification d'un acte.

## 1.1.0
- Autonomie des antennes : la demande d'un agent d'antenne est adressée directement au chef APFC, le dépôt étant assuré par le secrétariat (rôle `SECRETARIAT`, champ `depose_par`).
- Exception « mission hors périmètre DRENAET » : structures `DRENAET`, rôle `DIRECTEUR_REGIONAL`, pièces obligatoires (TDR + lettre d'invitation), ordre de mission établi et signé par le DRENAET.
- Signature électronique : bi-clés RSA 2048 par signataire, scellement SHA-256 des actes, code et QR code de vérification, page publique de vérification, révocation et renouvellement.
- Import Excel/CSV des agents : modèle généré, analyse préalable ligne à ligne, application des lignes valides, commande `importer_agents`.

## 1.0.0
- Site public rendu serveur : accueil, présentation, actualités, ressources, FOAD, projets, agenda, antennes, contact, recherche.
- Espace agent : dépôt et suivi des congés, permissions, ordres de mission, absences et formations.
- Circuit de validation automatique selon l'affectation (direction centrale ou antenne régionale).
- Soldes de congé, jours fériés, planning des absences, registre avec export CSV.
- Documents officiels imprimables avec visas.
- API REST JWT et application mobile Flutter.

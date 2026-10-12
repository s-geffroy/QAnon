# Vérification des prédictions de Q

Un fichier `part-N.yaml` par tranche chronologique ; une entrée par prédiction
(`key` = `<drop>-<rang>`, voir `predictions_all.json`).

## Protocole

- **Sélection** : prédictions extraites automatiquement qui sont `specific` ou
  ont une échéance (290).
- **Horizon** : l'échéance énoncée, sinon la date du drop + 12 mois.
- **Verdicts** : `fulfilled` (réalisée pour l'essentiel dans l'horizon),
  `partial` (en partie, ou sous une forme sensiblement différente),
  `not_fulfilled`, `unverifiable` (pas d'objet vérifiable, ou faits non
  publics), `not_a_prediction` (erreur d'extraction).
- **Sources** : au moins une, obligatoire pour `fulfilled`, `partial`,
  `not_fulfilled`.
- **`trivial: true`** : l'événement était déjà annoncé ou programmé
  publiquement au moment du drop ; « prédire » ne portait alors aucune
  information.

## Citations (règle harmonisée le 12 octobre 2026)

1. Q reprend à son compte une annonce d'autrui (article, tweet, déclaration
   d'un allié) → c'est une prédiction de Q ; `trivial: true` si l'annonce
   était déjà publique.
2. Q cite pour dénoncer ou tourner en dérision (ex. 609-0, John Kerry) → pas
   une prédiction.
3. Le texte cité ne porte pas sur l'avenir (proclamation, durée d'un décret,
   explication d'un fait présent) → pas une prédiction.

## Historique

- Verdicts établis par cinq agents de recherche (une tranche chacun), puis
  relus en entier : liens testés, verdicts « réalisée » et « partielle »
  contrôlés un à un, puis « non réalisée » et « invérifiable ».
- Corrections de la relecture : départ de Rosenstein et « zéro risque de
  destitution » alignés sur l'horizon de 12 mois ; drop 228 requalifié (constats
  passés et questions) ; 2358 et 2368 partiels ; citations harmonisées
  (1287, 1553, 1608, 1927, 2552, 4220).

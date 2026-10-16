# Rapport de revue editoriale

**Statut :** PARTIAL

## Portee

Ce rapport evalue la qualite editoriale (discours, argumentation, conformite aux consignes). Il ne dit pas si le texte a ete ecrit par un humain ou une IA.

## Synthese

Cette revue de synthèse porte sur un document de travail académique à destination d'un public spécialiste. Trois relecteurs ont été mobilisés (éditorial, argumentation, adversarial), ainsi qu'un audit mécanique dont l'étape a échoué ; les métriques de l'audit ne sont donc pas exploitables comme éléments de preuve dans cette synthèse. Les points de consensus partiel concernent la répétition de formes et de formules. Trois problèmes sont signalés à gravité élevée, et tous sont non résolus. Premier point : la divergence entre modèles est décrite dans les résultats comme une limite de mesure qui interdit d'y voir une anticipation reconnaissable, puis dans la conclusion comme un élément qui conforte la conclusion ; les relecteurs argumentation et adversarial signalent cette incompatibilité, qui n'est pas résolue dans le dossier. Deuxième point : la conclusion qualifie de presque jamais la réalisation des prédictions hors événements programmés, alors que le taux rapporté est de 16 % (IC 95 % : 10–24 %) ; le relecteur argumentation et le relecteur adversarial sont d'accord sur ce point, mais leurs interprétations de l'écart diffèrent. Troisième point : l'exclusion d'une coordination est présentée à partir de tests sur des fenêtres temporelles précises, sans que la portée exacte du terme « coordination » soit fixée ; l'adversarial note en outre un résultat de Hawkes (p = 0,035) présenté comme lien ténu. Un quatrième problème, de gravité moyenne, concerne l'attribution à Q de la création de formules reprises ensuite par Reddit, alors que les résultats présentent les délais comme des bornes et mentionnent une circulation possible sur d'autres plateformes. Les problèmes de forme (sous-sections au gabarit répété, ouvertures d'étiquettes du type « Intitulé. », redondances entre résumé, résultats et conclusion, formules sentencieuses, densité de ponctuation et de chiffres) sont signalés par le relecteur éditorial et partiellement repris par l'adversarial, avec une confiance modérée à faible. Le relecteur éditorial note lui-même que la régularité de structure peut relever de la convention du genre. Limites de la revue : les tableaux, figures et documents liés n'ont pas été fournis ; la cohérence des chiffres entre sections n'a pas été vérifiée ; l'étape mécanique a échoué ; les niveaux de confiance des relecteurs sont des estimations internes et ne constituent pas des mesures validées ; les catégories et gravités ont été reprises telles quelles du dossier, sans nouvelle hiérarchisation de ma part.

### Limites de la revue
- L'étape d'audit mécanique a échoué ; ses métriques (longueur des phrases, répétitions d'ouvertures, ponctuation, diversité lexicale) figurent dans le dossier mais ne sont pas validées par cette synthèse.
- Les tableaux, figures, annexes et documents liés ne sont pas fournis ; certaines inférences ne peuvent être vérifiées sur pièces.
- La cohérence des chiffres entre sections n'a pas été vérifiée par les relecteurs.
- Les niveaux de confiance et de sévérité sont ceux produits par les relecteurs ; ils ne sont pas calibrés et ne constituent pas une mesure indépendante.
- Les trois relecteurs ont des périmètres différents ; le relecteur adversarial couvre des points que les deux autres ne traitent pas, et inversement, sans que le dossier permette de trancher leur recouvrement exact.
- Certaines citations du dossier ont été reprises telles quelles ; leur contexte complet n'est pas accessible, ce qui limite l'évaluation de leur portée.
- Les désaccords entre relecteurs sur la lecture de certaines formules (par exemple la divergence entre modèles) sont conservés et non arbitrés.
- La synthèse ne qualifie pas l'authorship du texte et ne porte aucun jugement sur son origine.

## Audit deterministe

- Mots : 4635
- Phrases : 234
- Paragraphes : 69
- `sentence.mean_words` : 19.81 mots (percentile du genre : 20, n=44)
- `sentence.length_cv` : 0.687 (percentile du genre : 95, n=44)
- `paragraph.mean_words` : 67.17 mots (percentile du genre : 5, n=44)
- `paragraph.length_cv` : 0.953 (percentile du genre : 100, n=44)
- `lexical.type_token_ratio` : 0.29 (percentile du genre : 0, n=44)
- `lexical.mattr` : 0.829 (percentile du genre : 75, n=44)
- `lexical.trigram_repetition` : 0.0689 (percentile du genre : 91, n=44)
- `discourse.transition_density_per_1000_words` : 3.02 (percentile du genre : 32, n=44)
- `structure.repeated_paragraph_openings` : 0.362 (percentile du genre : 100, n=44)
- `punctuation.colons_per_1000_words` : 9.49 (percentile du genre : 84, n=44)
- `punctuation.semicolons_per_1000_words` : 5.39 (percentile du genre : 98, n=44)
- `punctuation.em_dashes_per_1000_words` : 0.0 (percentile du genre : 0, n=44)

## Appels aux modeles et cout

- editorial — `anthropic/claude-sonnet-5.5` — ok — 0.067086 $
- argumentation — `openai/gpt-6.1-sol` — ok — 0.054391 $
- mechanical — `deepseek/deepseek-v4.1-flash` — echec — 0.006421 $
- adversarial — `google/gemini-3.8-flash` — ok — 0.022573 $
- synthesis — `anthropic/claude-haiku-5.5` — ok — 0.002735 $
- **Total :** 0.153206 $

## Problemes consolides

### ISSUE-0001 — contradiction

- Statut : **UNRESOLVED**
- Gravite : **high**
- Confiance : 0.83
- Observation : La divergence entre modèles reçoit deux interprétations incompatibles : limite de mesure dans les résultats, puis élément confortant la conclusion dans la discussion. Aucun argument supplémentaire ne justifie ce changement de statut probatoire.
- Objectif de revision : Donner à la divergence entre modèles un statut épistémique stable dans les résultats, la discussion et la conclusion.
- Citations :
  - « C'est une limite de la mesure plus qu'une preuve supplémentaire, et elle interdit d'y voir une anticipation reconnaissable. »
  - « ce qui conforte la conclusion mais interdit d'interpréter finement les cas où un lien est vu. »
- Contre-arguments / limites :
  - Le contradicteur a releve une explication alternative plausible ou une limite de portee pour cette categorie.
- A preserver :
  - La comparaison entre modèles.
  - La reconnaissance explicite des limites du test.
- Actions permises (sans texte de remplacement) :
  - Préciser quelle conclusion est affectée par le désaccord.
  - Distinguer fragilité de la mesure et résultat défavorable à une hypothèse.
  - Harmoniser les interprétations entre sections.

### ISSUE-0002 — causal_link

- Statut : **UNRESOLVED**
- Gravite : **high**
- Confiance : 0.80
- Observation : Les écarts dans les deux sens sous le modèle « jours » sont présentés comme établissant la co-activité et excluant une coordination. Le texte ne montre pas que cette configuration permette de départager exhaustivement ces explications.
- Objectif de revision : Limiter l'inférence aux formes de synchronie effectivement testées et distinguer explication compatible et cause établie.
- Citations :
  - « ce qui signe la co-activité des jours chargés et non une coordination »
  - « Aucune fenêtre ne montre d'excès dans le sens « tweet après le drop ». »
- Contre-arguments / limites :
  - Le contradicteur a releve une explication alternative plausible ou une limite de portee pour cette categorie.
- A preserver :
  - La priorité donnée au modèle nul local.
  - La comparaison des deux sens temporels.
- Actions permises (sans texte de remplacement) :
  - Expliciter la portée du terme « coordination ».
  - Séparer constat statistique et interprétation causale.
  - Ne pas présenter les explications envisagées comme exhaustives.

### ISSUE-0003 — claim_scope

- Statut : **UNRESOLVED**
- Gravite : **medium**
- Confiance : 0.81
- Gravites rapportees : medium, medium, high (consolidee a la mediane)
- Observation : La conclusion qualifie de quasi inexistantes les réussites hors événements programmés, alors que le taux rapporté est de 16 %, avec un intervalle de 10 à 24 %. Elle assimile aussi programmation et annonce préalable, regroupées dans le calcul.
- Objectif de revision : Calibrer la synthèse sur la fréquence observée et sur la définition exacte des événements exclus.
- Citations :
  - « Hors événements déjà annoncés ou programmés, le taux tombe à 16 % (IC 95 % : 10–24 %). »
  - « Les prédictions vérifiables se réalisent rarement, et presque jamais quand elles n'étaient pas déjà programmées. »
  - « et forge à son tour des formules que Reddit reprend en quelques jours ou semaines. »
  - « Ces délais restent des bornes. »
  - « une formule absente de Reddit pendant quelques semaines pouvait circuler ailleurs, notamment sur /pol/ et 8chan. »
  - « Q n'apparaît ni comme l'inventeur de la scène complotiste américaine ni comme son écho »
  - « aucune précédence n'est détectée entre ses thèmes et les siens, dans les sources et aux échelles testées. »
- Contre-arguments / limites :
  - Le contradicteur a releve une explication alternative plausible ou une limite de portee pour cette categorie.
- A preserver :
  - La distinction entre réussites globales et réussites hors annonces préalables.
  - Les intervalles de confiance.
  - Les délais mesurés.
  - La comparaison entre plateformes.
  - La réserve sur les circulations non observées.
  - La restriction aux échelles testées.
  - La distinction entre répertoire sélectionné et scène dans son ensemble.
- Actions permises (sans texte de remplacement) :
  - Réexaminer les qualificatifs de fréquence.
  - Conserver dans la synthèse les catégories utilisées pour le calcul.
  - Éviter d'assimiler faible fréquence et fréquence négligeable sans critère explicite.
  - Restreindre l'attribution aux occurrences documentées.
  - Distinguer chronologie et transmission.
  - Reporter les limites décisives dans la synthèse.
  - Associer chaque caractérisation à son type de preuve.
  - Ne pas convertir une absence de significativité en exclusion d'un rôle.

### ISSUE-0004 — redundant_restatement

- Statut : **PROBABLE**
- Gravite : **medium**
- Confiance : 0.55
- Observation : Le résumé, les résultats et la conclusion répètent plusieurs fois les mêmes constats, et des phrases reformulent un point déjà clair ou renvoient à une section précédente.
- Objectif de revision : Dire chaque réserve une fois, à l'endroit où elle sert la démonstration.
- Citations :
  - « Aucune précédence n'est donc détectée, dans un sens ou dans l'autre, aux échelles testées. »
  - « ce qui conforte la conclusion mais interdit d'interpréter finement les cas où un lien est vu »
  - « Les rares « correspondances » dépendent donc du lecteur. »
- A preserver :
  - Les limites explicitement signalées
- Actions permises (sans texte de remplacement) :
  - Fusionner les réserves de 4.6 avec la discussion
  - Alléger la conclusion qui répète les résultats

### ISSUE-0005 — repeated_openings

- Statut : **PROBABLE**
- Gravite : **medium**
- Confiance : 0.50
- Observation : Les sections Données et Méthodes enchaînent des paragraphes ouverts par un intitulé nominal suivi d'un point (« Le corpus. », « Rythme. », « Discours. »), et plusieurs paragraphes partagent des amorces proches (métrique : 36 % d'ouvertures répétées).
- Objectif de revision : Réduire la monotonie des ouvertures là où le contenu n'exige pas l'étiquette.
- Citations :
  - « Tweets de Donald Trump. Les tweets jusqu'au 8 janvier 2021 »
  - « Intérêt public. Les pages vues de 15 articles de Wikipédia »
- A preserver :
  - La lisibilité de repérage des sources de données
- Actions permises (sans texte de remplacement) :
  - Fusionner les sous-blocs courts apparentés
  - Varier les points d'entrée syntaxiques des paragraphes

### ISSUE-0006 — structural_uniformity

- Statut : **UNRESOLVED**
- Gravite : **medium**
- Confiance : 0.40
- Observation : Les sous-sections de résultats suivent un même gabarit : titre-thèse, série de chiffres, puis phrase d'interprétation ou de rattachement à une autre section. La régularité tient en partie au genre, mais devient mécanique.
- Objectif de revision : Laisser certains blocs de résultats s'achever sur le chiffre sans commentaire de rattachement.
- Citations :
  - « Q ne reprend pas l'ensemble du complotisme américain, il en retient quelques récits. »
  - « Q réagit donc à Trump de manière marginale, ce qui rejoint les 59 citations de tweets de la section 4.3. »
- Contre-arguments / limites :
  - Le contradicteur a releve une explication alternative plausible ou une limite de portee pour cette categorie.
- A preserver :
  - La précision chiffrée et les intervalles de confiance
- Actions permises (sans texte de remplacement) :
  - Supprimer les conclusions de paragraphe qui ne font que relier ou reformuler
  - Varier l'ordre chiffre/interprétation selon l'importance du résultat

### ISSUE-0007 — voice_and_register

- Statut : **PROBABLE**
- Gravite : **low**
- Confiance : 0.40
- Observation : Quelques formules sentencieuses ou imagées tranchent avec le registre précis demandé et valent surtout par leur effet de chute.
- Objectif de revision : Remplacer les chutes par des énoncés calibrés sur ce que les données établissent.
- Citations :
  - « Q choisit ses personnages, pas sa géographie »
  - « Le principal enseignement est méthodologique : chaque « preuve » avancée par le mouvement peut être transformée en hypothèse testable »
  - « /pol/, le berceau de Q »
- A preserver :
  - Le ton globalement sobre et impersonnel
- Actions permises (sans texte de remplacement) :
  - Reformuler les chutes en constats directs
  - Nuancer la généralisation finale sur toute « preuve » du mouvement

### ISSUE-0008 — rhythm_and_sentence_variety

- Statut : **PROBABLE**
- Gravite : **low**
- Confiance : 0.40
- Observation : Les paragraphes de résultats et de méthodes sont denses : accumulation de nombres, parenthèses, points-virgules et deux-points, avec des phrases très chargées en incises statistiques.
- Objectif de revision : Alléger les phrases les plus encombrées sans perdre de données.
- Citations :
  - « Le modèle de Markov caché retient 3 régimes : un silence, une veille (0,42 drop par jour) et un régime actif (9,9 drops par jour) »
- A preserver :
  - Les valeurs et intervalles
- Actions permises (sans texte de remplacement) :
  - Déporter certains chiffres vers les tableaux
  - Scinder les phrases à plus de trois incises

## Etapes en echec

### mechanical
- `deepseek/deepseek-v4.1-flash`
- Cause : `OUTPUT_TRUNCATED` — reponse vide (finish_reason=length, tokens=6486, raisonnement=6486, effort=minimal)

# Editorial Review Report

**Status:** COMPLETE

## Scope

This report evaluates editorial naturalness, discourse, argumentation, and compliance signals. It does not estimate whether the text was written by a human or an AI.

## Deterministic audit

- Words: 3675
- Sentences: 201
- Paragraphs: 7
- `sentence.mean_words`: 18.28 words
- `sentence.length_cv`: 0.607
- `paragraph.mean_words`: 525 words
- `paragraph.length_cv`: 0.359
- `lexical.type_token_ratio`: 0.329
- `lexical.trigram_repetition`: 0.0422
- `discourse.transition_density_per_1000_words`: 1.63
- `structure.repeated_paragraph_openings`: 0.286
- `punctuation.colons_per_1000_words`: 26.67
- `punctuation.semicolons_per_1000_words`: 6.8

## LLM executions and estimated cost

- `anthropic/claude-sonnet-5` — success=True — input=15427 — output=21360 — estimated_cost_usd=0.244454
- `openai/gpt-5.6-terra` — success=True — input=8779 — output=3684 — estimated_cost_usd=0.061766
- `mistralai/mistral-large-2512` — success=True — input=8704 — output=3960 — estimated_cost_usd=0.010292
- `google/gemini-3.6-flash` — success=True — input=20502 — output=5427 — estimated_cost_usd=0.035728
- `anthropic/claude-sonnet-5` — success=True — input=29429 — output=1448 — estimated_cost_usd=0.073338
- **Estimated total:** $0.425578
- Cost is estimated from the repository's dated OpenRouter price catalog; OpenRouter billing is authoritative.

## Consolidated issues

### ISSUE-0003 — claim_scope

- Status: **PROBABLE**
- Severity: **high**
- Confidence: 0.58
- Observation: La première activité demande de calculer puis de comparer un « taux de la classe », alors que le corpus distribué est délibérément composé pour contenir plusieurs catégories de verdict. Ce taux provient donc d’un échantillon pédagogique construit, non d’un échantillon permettant d’estimer ou de comparer directement un taux global de réussite des prédictions.
- Revision goal: Distinguer explicitement la fonction pédagogique du taux calculé en classe de tout taux interprétable pour décrire l’ensemble du corpus.
- Evidence:
  - les études relient le soutien à QAnon à l'antisémitisme ( Levin et al., 2022 ) , et la page Acteurs le rappelle : « Être nommé par Q ne dit rien des personnes : Q accuse sans preuve. »
  - La figure de George Soros est un ressort récurrent de récits antisémites : si la question surgit, traitez-la comme telle plutôt que de la laisser en suspens.
  - « choisir dans verification.csv six à huit prédictions de types variés, dont au moins une “réalisée”, une “non réalisée”, une “invérifiable” et une “pas une prédiction” »
  - « calculer le taux de la classe [...] puis le comparer aux résultats du site sur l'ensemble des prédictions vérifiées »
  - « les mots-outils comme empreinte de style »
  - « Pourquoi ces petits mots, peu contrôlés par l'auteur, trahissent-ils un style ? »
  - « leur fréquence varie peu chez un même auteur et distingue mieux deux plumes que le vocabulaire »
  - « changement de plume et changement de plateforme sont ici indiscernables »
  - « il peut repérer une rupture, pas désigner une personne »
- Counterarguments / limits:
  - Adversarial reviewer identified a plausible alternative explanation or scope limitation.
- Preserve:
  - La rigueur générale de sourçage qui caractérise le reste de cette fiche et du document.
  - La progression utile qui va de la formulation d’une annonce à sa vérification puis à l’interprétation d’un taux.
  - L’explication de l’exclusion des annonces invérifiables du dénominateur.
  - La mise en évidence utile de la confusion possible entre changement de style et changement d’auteur.
  - Les garde-fous éthiques concernant la désignation de personnes et l’usage de textes d’élèves.
- Allowed revision actions (no replacement prose):
  - Vérifier si une référence distincte accompagne cette affirmation ailleurs dans le document source, et sinon l'indiquer explicitement ou la reformuler comme une mise en garde pédagogique plutôt que comme un fait établi.
  - Indiquer le statut de l’échantillon distribué et les conséquences de sa sélection sur le taux obtenu.
  - Séparer la comparaison méthodologique des dénominateurs et catégories d’une comparaison chiffrée susceptible d’être lue comme représentative.
  - Prévoir que toute comparaison numérique avec le site soit accompagnée de la limite d’échantillonnage pertinente.
  - Examiner les verbes et métaphores qui attribuent aux mots-outils une capacité d’identification directe.
  - Présenter dès l’entrée de l’exercice les fréquences de mots-outils comme des indices comparatifs soumis à des facteurs de confusion.
  - Maintenir les explications alternatives au même niveau de visibilité que la méthode de calcul.

### ISSUE-0001 — structural_uniformity

- Status: **PROBABLE**
- Severity: **medium**
- Confidence: 0.72
- Observation: Les fiches suivent un schéma rhétorique quasi identique : présentation de la question de méthode, déroulement de l'activité en étapes chronométrées, questions de réflexion, et enfin 'Éléments de correction'. Cette architecture répétitive est renforcée par des sous-structures similaires (ex. : 'Pourquoi... ?' pour les questions de réflexion).
- Revision goal: Diversifier l'architecture interne des fiches pour refléter les spécificités de chaque activité, tout en conservant une cohérence globale adaptée au public enseignant.
- Evidence:
  - Éléments de correction.
  - Préparation (enseignant) :
  - Pourquoi une annonce invérifiable ne peut-elle compter ni comme un succès ni comme un échec ?
  - Vérifier une prédiction soi-même [...] Préparation (enseignant) [...] Reformuler (15 min) [...] Enquêter (30 min) [...] Trancher (15 min) [...] Confronter (20 min) [...] Généraliser (10 min) [...] Pourquoi... ? [...] Éléments de correction.
  - Une coïncidence n'est pas une preuve [...] Accroche (10 min) [...] Construire le hasard (20 min) [...] Comparer (15 min) [...] Changer de référence (15 min) [...] Retourner la question (10 min) [...] Pourquoi... ? [...] Éléments de correction.
  - Une écriture qui fait travailler le lecteur [...] Tri (15 min) [...] Analyse (15 min) [...] Mesure (15 min) [...] Réécriture (15 min) [...] Pourquoi... ? [...] Éléments de correction.
- Preserve:
  - La clarté didactique et la facilité de repérage pour l'enseignant que procure une structure récurrente.
  - La variété réelle du contenu méthodologique d'une fiche à l'autre.
  - La clarté des consignes pour les enseignants.
  - La progression logique des activités.
  - La distinction entre les étapes pratiques et les éléments de réflexion.
- Allowed revision actions (no replacement prose):
  - Réexaminer si l'ordre ou la présence de chaque bloc (objectifs/activités/questions/correction/mise en garde) découle de la logique propre à chaque méthode plutôt que d'un calque systématique.
  - Envisager de faire varier la forme de clôture d'au moins une fiche si le raisonnement propre à cette méthode ne requiert pas de mise en garde finale de même ampleur.
  - Varier l'ordre des étapes dans certaines fiches lorsque le contenu le permet (ex. : commencer par une question de réflexion avant de présenter l'activité).
  - Adapter la longueur et la complexité des sections en fonction du contenu, plutôt que de suivre un modèle fixe.
  - Éviter de systématiser les questions de type 'Pourquoi... ?' en fin de section ; les intégrer de manière plus organique dans le déroulement.

### ISSUE-0002 — repeated_openings

- Status: **PROBABLE**
- Severity: **medium**
- Confidence: 0.72
- Observation: Les paragraphes des sections 'Éléments de correction' commencent systématiquement par une phrase déclarative courte, souvent sous la forme d'un chiffre ou d'une statistique suivie d'une explication. Par exemple : '13 % des drops (598) contiennent au moins une prédiction...', 'Un tweet de Trump suit un drop en moins de 5 minutes dans 4,2 % des cas...', 'Acteurs les plus cités (nombre de drops) : Donald Trump (386)...'. Cette formule est répétée à l'identique dans les quatre fiches.
- Revision goal: Varier les points d'entrée syntaxiques et rhétoriques dans les paragraphes d'ouverture des sections 'Éléments de correction' pour éviter l'effet de template mécanique, tout en préservant la clarté et la fonction instructive.
- Evidence:
  - Éléments de correction.
  - Comprendre qu'une coïncidence ne s'évalue qu'en la comparant à ce que le hasard produit.
  - Comprendre qu'un nombre brut de mentions ne dit rien sans point de comparaison.
  - Comprendre qu'un chiffre d'enquête dépend de la question posée.
  - 13 % des drops (598) contiennent au moins une prédiction, soit 846 prédictions dont 203 précises.
  - Un tweet de Trump suit un drop en moins de 5 minutes dans 4,2 % des cas, contre 4,0 % attendus par hasard (modèle nul local, p = 0,227) : pas de synchronie démontrée.
  - Acteurs les plus cités (nombre de drops) : Donald Trump (386), Mainstream media (241), Barack Obama (166) ; 33 % des drops nomment au moins un acteur du dictionnaire.
- Preserve:
  - La fonction de repère que cette formule offre à l'enseignant qui navigue dans le document.
  - La variété déjà présente dans les verbes d'objectifs des fiches qui ne commencent pas par « Comprendre ».
  - La précision des chiffres et des références.
  - La fonction pédagogique des éléments de correction.
  - La distinction claire entre fait, estimation et interprétation.
- Allowed revision actions (no replacement prose):
  - Si l'on souhaite atténuer l'effet de gabarit, envisager de reformuler l'intitulé de correction pour certaines fiches selon la nature de la réponse apportée (ex. mention explicite du résultat plutôt qu'un intitulé générique).
  - Introduire des variations syntaxiques (questions rhétoriques, phrases complexes, subordonnées) pour les ouvertures de paragraphes dans les sections 'Éléments de correction'.
  - Éviter de systématiser la présentation des statistiques en début de paragraphe.
  - Utiliser des connecteurs logiques uniquement lorsque la relation entre les idées le justifie, et non par réflexe.

### ISSUE-0004 — causal_link

- Status: **UNRESOLVED**
- Severity: **medium**
- Confidence: 0.71
- Observation: Dans l’activité sur l’écriture cryptique, plusieurs mesures ou propriétés textuelles sont suivies d’effets psychologiques ou stratégiques formulés comme des conséquences établies. Le texte fournit des interprétations et des références, mais ne distingue pas toujours clairement ce que les chiffres mesurent de ce qu’ils permettent d’inférer sur l’attente des lecteurs, l’absorption de l’échec ou la fonction de l’autocitation.
- Revision goal: Marquer plus nettement la frontière entre les indicateurs observés, les mécanismes interprétés et les conclusions que les sources permettent d’appuyer.
- Evidence:
  - « L'autocitation sert à faire “confirmer” une annonce passée par l'actualité. »
  - « L'urgence entretient l'attente ; la formule qui diffère la preuve absorbe l'échec quand l'échéance passe. »
  - « Une écriture simple, en phrases courtes et en questions, laisse au lecteur le soin de conclure. »
- Counterarguments / limits:
  - Adversarial reviewer identified a plausible alternative explanation or scope limitation.
- Preserve:
  - Le choix pertinent de faire relier des caractéristiques formelles à des questions de vérifiabilité.
  - Les précautions contre la transformation de la séance en jeu de décodage.
- Allowed revision actions (no replacement prose):
  - Identifier les passages qui passent d’une mesure à une fonction supposée du discours.
  - Attribuer ou qualifier les interprétations lorsque plusieurs mécanismes restent possibles.
  - Inviter à justifier le lien entre l’indicateur et l’effet avancé plutôt que de le présenter systématiquement comme automatique.

### ISSUE-0005 — instruction_compliance

- Status: **PROBABLE**
- Severity: **medium**
- Confidence: 0.67
- Observation: Le texte utilise systématiquement des deux-points pour introduire des explications ou des listes, même lorsque la ponctuation n'est pas nécessaire pour la clarté. Par exemple : 'Règle du site : l'horizon est l'échéance énoncée...', 'Pourquoi une annonce invérifiable ne peut-elle compter ni comme un succès ni comme un échec : Où la place-t-on dans le calcul du taux ?'. Cette habitude est confirmée par la métrique 'punctuation.colons_per_1000_words' (26,67), qui est élevée.
- Revision goal: Réduire l'usage systématique des deux-points et privilégier une ponctuation plus variée, adaptée à la syntaxe et au rythme du texte.
- Evidence:
  - « Les éléments de correction renvoient aux chiffres clés, recalculés à chaque version du site : citez la version consultée ( Citer ). »
  - « 39 des 140 prédictions vérifiables se sont réalisées »
  - « Un tweet de Trump suit un drop en moins de 5 minutes dans 4,2 % des cas »
  - Règle du site : l'horizon est l'échéance énoncée, sinon douze mois après le drop.
  - Pourquoi une annonce invérifiable ne peut-elle compter ni comme un succès ni comme un échec : Où la place-t-on dans le calcul du taux ?
  - Éléments de correction. 13 % des drops (598) contiennent au moins une prédiction : soit 846 prédictions dont 203 précises.
- Counterarguments / limits:
  - Adversarial reviewer identified a plausible alternative explanation or scope limitation.
- Preserve:
  - L’avertissement utile selon lequel les données sont recalculées.
  - Le renvoi aux fichiers, pages et références qui structurent les activités.
  - La clarté des explications et des consignes.
  - La précision des références et des chiffres.
- Allowed revision actions (no replacement prose):
  - Vérifier que l’identifiant de version, sa date et son accès sont visibles dans le support effectivement remis.
  - Rattacher les ensembles de chiffres évolutifs à la version consultée dans les consignes ou dans un appareil de référence stable.
  - Si les données sont susceptibles de varier, signaler quels résultats de correction doivent être mis à jour avant utilisation.
  - Remplacer les deux-points par des points ou des virgules lorsque la relation logique est évidente.
  - Varier la ponctuation en fonction du rythme souhaité (ex. : utiliser des tirets pour des incises, des parenthèses pour des précisions).
  - Éviter d'utiliser les deux-points comme une signature stylistique systématique.

### ISSUE-0006 — transition_habits

- Status: **PROBABLE**
- Severity: **low**
- Confidence: 0.85
- Observation: Les transitions entre les étapes des activités sont souvent assurées par des connecteurs temporels ('puis', 'ensuite', 'enfin') ou des formulations réflexes ('se demander aussi', 'faire chercher pourquoi'). Ces transitions sont utilisées de manière systématique, même lorsque la logique du contenu ne les justifie pas pleinement.
- Revision goal: Réduire l'usage de transitions réflexes et privilégier des liens logiques implicites lorsque le contenu le permet, afin de renforcer la fluidité naturelle du texte.
- Evidence:
  - Chercher, recouper et citer des sources pour établir un verdict. Comprendre pourquoi une annonce vague ou déjà programmée ne compte pas comme une prédiction réussie. Lire un taux et son intervalle de confiance.
  - Enquêter (30 min) : chercher au moins une source fiable par annonce [...] Se demander aussi si l'événement était déjà annoncé ou programmé [...]
  - Comparer (15 min) : lire la ligne « 5 min, tweet après le drop » du témoin local [...] Changer de référence (15 min) : lire les mêmes lignes avec le témoin « jours ». Faire chercher pourquoi [...]
- Preserve:
  - La clarté des consignes pour les étapes pratiques.
  - La progression chronologique des activités.
- Allowed revision actions (no replacement prose):
  - Supprimer les connecteurs temporels lorsque la succession des étapes est évidente.
  - Remplacer les formulations réflexes ('se demander aussi', 'faire chercher pourquoi') par des questions ou des consignes plus intégrées au contenu.
  - Utiliser des transitions uniquement lorsque la relation entre les idées n'est pas immédiatement perceptible.

### ISSUE-0007 — list_like_prose

- Status: **PROBABLE**
- Severity: **low**
- Confidence: 0.80
- Observation: Certaines sections, notamment les consignes pratiques, prennent la forme d'énumérations additives plutôt que d'une prose développée. Par exemple, les étapes des activités sont présentées sous forme de listes chronométrées, et les questions de réflexion sont alignées sans développement intermédiaire.
- Revision goal: Transformer les énumérations additives en prose développée lorsque cela sert la progression pédagogique, tout en conservant la clarté des consignes.
- Evidence:
  - Reformuler (15 min) : pour chaque annonce, les groupes écrivent l'énoncé vérifiable correspondant (qui, quoi, pour quand). [...] Enquêter (30 min) : chercher au moins une source fiable par annonce [...] Trancher (15 min) : attribuer un verdict [...] Confronter (20 min) : dévoiler les verdicts [...] Généraliser (10 min) : calculer le taux de la classe [...]
  - Pourquoi une annonce invérifiable ne peut-elle compter ni comme un succès ni comme un échec ? Où la place-t-on dans le calcul du taux ? Pourquoi le site calcule-t-il un second taux « hors triviales » ? [...]
- Preserve:
  - La lisibilité des étapes pratiques pour les enseignants.
  - La distinction entre les différentes phases des activités.
- Allowed revision actions (no replacement prose):
  - Regrouper certaines étapes ou questions sous des sous-titres thématiques pour éviter l'effet de liste.
  - Développer des transitions logiques entre les questions de réflexion pour montrer leur articulation.
  - Varier la présentation des consignes (ex. : intégrer certaines étapes dans des phrases complexes plutôt que sous forme de listes).

### ISSUE-0008 — redundant_restatement

- Status: **PROBABLE**
- Severity: **low**
- Confidence: 0.80
- Observation: Certaines idées sont reformulées ou répétées sans ajout significatif, notamment dans les 'Éléments de correction'. Par exemple, l'explication de la p-value est reprise presque à l'identique dans deux sections différentes, et la notion de 'taux de réalisation' est réexpliquée plusieurs fois.
- Revision goal: Éliminer les reformulations redondantes et privilégier un développement progressif des idées, en évitant de réexpliquer des concepts déjà clairs.
- Evidence:
  - Une p-value n'est pas la probabilité qu'une hypothèse soit vraie : c'est la fréquence, parmi les tirages au hasard, d'un résultat au moins aussi frappant que l'observation ; elle n'est jamais nulle quand on l'estime par tirages ( Phipson & Smyth, 2010 ).
  - Une p-value est la part des tirages au hasard qui produisent au moins autant de coïncidences que la réalité. Plus elle est grande, plus la réalité ressemble au hasard.
- Preserve:
  - La clarté des explications pour les concepts complexes.
  - La cohérence des éléments de correction.
- Allowed revision actions (no replacement prose):
  - Supprimer les répétitions d'explications déjà fournies, sauf si une nouvelle nuance est introduite.
  - Regrouper les explications similaires dans une seule section pour éviter les redites.
  - Utiliser des renvois internes (ex. : 'voir la section X pour plus de détails') lorsque cela est pertinent.

# Rapport de revue editoriale

**Statut :** PARTIAL

## Portee

Ce rapport evalue la qualite editoriale (discours, argumentation, conformite aux consignes). Il ne dit pas si le texte a ete ecrit par un humain ou une IA.

## Synthese

Synthèse éditoriale du dossier d'évaluation, rédigée à partir des sorties de trois relecteurs (éditorial, argumentation, contradicteur) et d'un audit mécanique. Le dossier fait apparaître un accord partiel sur plusieurs points. Le premier concerne la portée des conclusions : l'absence de corrélation significative après correction pour comparaisons multiples est reformulée, dans la conclusion, comme une absence générale de relation (« ni meneur ni suiveur », « Q n'invente pas la scène complotiste américaine et ne la suit pas non plus »). Les relecteurs argumentation et contradicteur jugent cette généralisation non établie, les tests ne portant que sur les thèmes admissibles, les sources retenues et certaines échelles temporelles ; l'absence de détection n'est pas assimilée ici à une absence de relation. Le second point concerne le désaccord entre les deux modèles de langage (kappa de Cohen publié, 0,23 selon le contradicteur), que la conclusion utiliserait comme renforcement de l'hypothèse d'absence d'anticipation reconnaissable. Les relecteurs le lisent comme une limite de robustesse de la mesure plutôt que comme une confirmation indépendante ; le contradicteur signale une alternative possible sans la trancher. Le troisième point concerne le vocabulaire causal : le résumé et les résultats emploient « déclenchés » pour des drops, alors que la discussion précise qu'un processus de Hawkes décrit une structure temporelle et non une cause. Le relecteur argumentation juge la réserve tardive insuffisante, surtout dans le résumé autonome. Concernant la prédiction, la comparaison passé-avenir ne détecte pas de différence significative (test exact de Fisher, p = 0,44), mais la conclusion affirme que les correspondances futures n'excèdent pas les passées ; les relecteurs estiment cette équivalence non établie. Le taux de 16 % hors événements programmés (IC 95 % : 10–24 %) est jugé par deux relecteurs qualifié de manière excessive (« presque jamais »). Les points de forme (résumé surchargé, clôtures récapitulatives, section 4.10 dense, registre des titres, ouvertures répétées) sont signalés principalement par le relecteur éditorial, avec un niveau de confiance modéré. Une incohérence de dénombrement est relevée : 290 annonces vérifiées dans la méthode, 250 dans le résumé, 203 précises selon la section 4.5 ; le relecteur éditorial propose l'explication 290 − 40 = 250, que la section 4.5 explicite. Les éléments ci-dessus restent non résolus ou probables selon les statuts attribués ; ils ne constituent pas un consensus entre relecteurs sur la gravité de chaque point, notamment pour la sévérité des points de forme. Limites de cette revue : l'étape mécanique a échoué et n'a fourni aucun résultat exploitable ; les tableaux, figures, verdicts et ressources externes annoncés n'ont pas été fournis et n'ont pu être vérifiés ; la véracité des références et des dénominations de modèles n'a pas été évaluée de l'extérieur ; les mesures d'audit (densité de connecteurs, ouvertures répétées) ne sont pas localisées précisément dans le texte. Le relecteur adversarial et les relecteurs éditoriaux ont des niveaux de confiance différents, et certaines observations de l'audit ne sont pas confirmées par une localisation.

### Limites de la revue
- L'étape mécanique a échoué ; aucun résultat mécanique exploitable n'est disponible dans ce dossier.
- Les tableaux, figures, verdicts et ressources externes mentionnés dans le texte ne sont pas fournis et n'ont pas pu être vérifiés.
- La véracité des références, des dénominations de modèles et des chiffres n'a pas été évaluée de manière indépendante au-delà de la cohérence interne du dossier.
- Les ouvertures de paragraphes répétées signalées par l'audit (38 %) ne sont pas localisables précisément dans le texte fourni ; le relecteur adversarial note que cette répétition relève en partie d'un format fonctionnel dans les sections techniques.
- Les mesures d'audit de transition et de densité ponctuelle ne sont pas interprétées de manière uniforme par les relecteurs.
- Les niveaux de confiance des relecteurs sont hétérogènes (de 0,5 à 0,95 pour les arguments, de 0,4 à 0,6 pour les observations éditoriales) et ne sont pas harmonisés dans la synthèse.
- Le relecteur adversarial signale une dépendance à des stades de relecture dont le statut n'est pas documenté au-delà de son propre résumé.
- La synthèse ne tranche pas la gravité relative des points de forme par rapport aux points de portée des conclusions, les relecteurs n'étant pas d'accord sur ce classement.

## Audit deterministe

- Mots : 4615
- Phrases : 234
- Paragraphes : 65
- `sentence.mean_words` : 19.72 mots (percentile du genre : 18, n=44)
- `sentence.length_cv` : 0.723 (percentile du genre : 95, n=44)
- `paragraph.mean_words` : 71.0 mots (percentile du genre : 5, n=44)
- `paragraph.length_cv` : 1.104 (percentile du genre : 100, n=44)
- `lexical.type_token_ratio` : 0.29 (percentile du genre : 0, n=44)
- `lexical.mattr` : 0.827 (percentile du genre : 75, n=44)
- `lexical.trigram_repetition` : 0.0689 (percentile du genre : 91, n=44)
- `discourse.transition_density_per_1000_words` : 2.82 (percentile du genre : 32, n=44)
- `structure.repeated_paragraph_openings` : 0.385 (percentile du genre : 100, n=44)
- `punctuation.colons_per_1000_words` : 9.75 (percentile du genre : 84, n=44)
- `punctuation.semicolons_per_1000_words` : 5.42 (percentile du genre : 98, n=44)
- `punctuation.em_dashes_per_1000_words` : 0.0 (percentile du genre : 0, n=44)

## Appels aux modeles et cout

- editorial — `anthropic/claude-sonnet-5.5` — ok — 0.074314 $
- mechanical — `deepseek/deepseek-v4.1-flash` — echec — 0.006421 $
- argumentation — `openai/gpt-6.1-sol` — ok — 0.059644 $
- adversarial — `google/gemini-3.8-flash` — ok — 0.023330 $
- synthesis — `anthropic/claude-haiku-5.5` — ok — 0.003145 $
- **Total :** 0.166854 $

## Problemes consolides

### ISSUE-0001 — claim_scope

- Statut : **UNRESOLVED**
- Gravite : **high**
- Confiance : 0.82
- Gravites rapportees : medium, high, high (consolidee a la mediane)
- Observation : L’absence de corrélations significatives après correction devient une affirmation générale selon laquelle Q ne mène ni ne suit la scène. Les tests ne portent pourtant que sur les thèmes admissibles, les sources retenues et certaines échelles temporelles.
- Objectif de revision : Limiter les conclusions aux relations effectivement testées et distinguer absence de détection et absence de relation.
- Citations :
  - « Pour les 15 comparaisons hebdomadaires possibles, aucune corrélation ne résiste à la correction pour comparaisons multiples : ni meneur ni suiveur. »
  - « Replacé dans son milieu, Q n'invente pas la scène complotiste américaine et ne la suit pas non plus. »
  - « Les deux taux ne diffèrent pas significativement (test exact de Fisher, p = 0,44). »
  - « Les « correspondances » avec l'avenir, rares, varient d'un modèle à l'autre et n'excèdent pas celles qu'on observe avec le passé. »
  - « Hors événements déjà annoncés ou programmés, le taux tombe à 16 % (IC 95 % : 10–24 %). »
  - « Les prédictions vérifiables se réalisent rarement, et presque jamais quand elles n'étaient pas déjà programmées. »
- Contre-arguments / limites :
  - Le contradicteur a releve une explication alternative plausible ou une limite de portee pour cette categorie.
- A preserver :
  - La correction pour comparaisons multiples.
  - Le constat descriptif d’un répertoire thématique restreint.
  - Les intervalles de confiance et les résultats contre le hasard.
  - La réserve sur la continuité thématique.
  - La distinction entre événements programmés et autres annonces.
  - Les intervalles de Wilson.
- Actions permises (sans texte de remplacement) :
  - Rattacher chaque synthèse au périmètre des comparaisons.
  - Préciser les limites de puissance ou signaler qu’elles ne sont pas évaluées.
  - Retirer les inférences sur l’invention des récits non directement testées.
  - Aligner la synthèse sur la portée exacte du test.
  - Justifier l’asymétrie des fenêtres pour leur comparaison.
  - Ne pas considérer la continuité thématique comme une explication démontrée.
  - Supprimer l’intensification non justifiée.
  - Maintenir le périmètre des prédictions vérifiables dans la synthèse.

### ISSUE-0002 — causal_link

- Statut : **UNRESOLVED**
- Gravite : **high**
- Confiance : 0.82
- Gravites rapportees : medium, high, high (consolidee a la mediane)
- Observation : Le résumé et les résultats décrivent des drops comme déclenchés par d’autres drops ou par Trump, alors que la discussion précise qu’un processus de Hawkes décrit une structure temporelle et non sa cause.
- Objectif de revision : Maintenir partout le statut modélisé, et non causalement identifié, des parts d’excitation.
- Citations :
  - « Les rares « correspondances » dépendent donc du lecteur, ce qui renforce la conclusion que les drops n'annoncent pas l'actualité de façon reconnaissable. »
  - « La comparaison avec un second modèle montre que les rares liens trouvés varient d'un modèle à l'autre (accord modeste), ce qui conforte la conclusion »
  - « La plupart des drops sont déclenchés par des drops antérieurs, avec une mémoire longue mais sans signature de système critique »
  - « Les tweets de Trump ne déclenchent que 0,5 % des drops »
  - « un processus de Hawkes décrit la structure temporelle des drops, pas leur cause »
  - « et forge à son tour des formules que Reddit reprend en quelques jours ou semaines. »
  - « Ces délais restent des bornes. »
  - « une formule absente de Reddit pendant quelques semaines pouvait circuler ailleurs, notamment sur /pol/ et 8chan. »
- Contre-arguments / limites :
  - Le contradicteur a releve une explication alternative plausible ou une limite de portee pour cette categorie.
- A preserver :
  - La réplication sur les mêmes drops.
  - Les résultats distincts des deux modèles.
  - La comparaison avec Poisson.
  - Les diagnostics d’adéquation et les mécanismes alternatifs.
  - Les délais observés.
  - La distinction entre formules antérieures et postérieures aux drops.
- Actions permises (sans texte de remplacement) :
  - Séparer la conclusion sur la stabilité de la mesure de celle sur l’anticipation.
  - Indiquer quelle validation permettrait de départager les jugements des modèles.
  - Maintenir l’incertitude dans la discussion et le résumé.
  - Qualifier les attributions au moment de leur présentation.
  - Harmoniser résumé, résultats et discussion sur le statut causal.
  - Distinguer dépendance temporelle et mécanisme de production.
  - Reporter les réserves d’échantillonnage dans la synthèse.
  - Réserver les attributions de création aux cas directement documentés.

### ISSUE-0003 — structural_uniformity

- Statut : **PROBABLE**
- Gravite : **medium**
- Confiance : 0.60
- Observation : Le résumé tient en un bloc unique qui condense méthodes, résultats et sous-résultats ; la première moitié est une énumération de méthodes en une seule phrase très longue.
- Objectif de revision : Hiérarchiser le résumé en isolant les résultats principaux de l'inventaire des méthodes.
- Citations :
  - « Il combine statistiques descriptives, analyse textuelle (thèmes NMF, termes distinctifs, stylométrie exploratoire), un test de la synchronie revendiquée »
- A preserver :
  - Les chiffres avec IC
  - La mention de la publication des données
- Actions permises (sans texte de remplacement) :
  - Scinder la liste des méthodes
  - Réserver au résumé les résultats centraux

### ISSUE-0004 — rhetorical_goal_alignment

- Statut : **PROBABLE**
- Gravite : **medium**
- Confiance : 0.50
- Observation : La conclusion adopte une formule nette (« commentaire de l'actualité habillé en prophétie », « Q n'invente pas ») alors que la discussion souligne que les modèles sont des analogies et que les tests ne tranchent pas la causalité.
- Objectif de revision : Aligner la portée de la conclusion sur les limites énoncées et éviter l'image.
- Citations :
  - « les drops de Q apparaissent comme un commentaire de l'actualité habillé en prophétie »
  - « Le principal enseignement est méthodologique : chaque « preuve » avancée par le mouvement peut être transformée en hypothèse testable »
- A preserver :
  - La section Limites détaillée
- Actions permises (sans texte de remplacement) :
  - Qualifier la conclusion
  - Remplacer la métaphore par un énoncé de résultat
  - Généraliser moins l'enseignement final

### ISSUE-0005 — argumentative_progression

- Statut : **PROBABLE**
- Gravite : **medium**
- Confiance : 0.45
- Observation : La section 4.10 empile de nombreux chiffres de toxicité et de vocabulaire en un paragraphe dense, avec un « paradoxe apparent » résolu par une série de ventilations difficiles à suivre.
- Objectif de revision : Scinder et ordonner la section selon une question centrale unique par paragraphe.
- Citations :
  - « La ventilation par groupe (tableau 5) lève ce paradoxe apparent. »
  - « Les codes de haine, surtout antisémites, touchent 5,0 % des posts de /pol/ avant Q et 6,5 % après »
- A preserver :
  - Le constat sur le caractère plus calme des fils Q
- Actions permises (sans texte de remplacement) :
  - Découper le bloc en paragraphes thématiques
  - Déporter les chiffres secondaires vers les tableaux

### ISSUE-0006 — redundant_restatement

- Statut : **UNRESOLVED**
- Gravite : **medium**
- Confiance : 0.40
- Observation : Plusieurs paragraphes se terminent par une phrase de synthèse ou de renvoi qui répète ce qui vient d'être établi, et la conclusion réénumère presque tous les résultats.
- Objectif de revision : Supprimer les clôtures récapitulatives qui n'ajoutent pas d'inférence et resserrer la conclusion.
- Citations :
  - « Les rares « correspondances » dépendent donc du lecteur, ce qui renforce la conclusion que les drops n'annoncent pas l'actualité de façon reconnaissable. »
  - « Cette sélectivité prolonge celle des acteurs (section 4.4) : Q ne reprend pas l'ensemble du complotisme américain, il en retient quelques récits. »
- Contre-arguments / limites :
  - Le contradicteur a releve une explication alternative plausible ou une limite de portee pour cette categorie.
- A preserver :
  - Les renvois croisés qui apportent un recoupement de méthodes
- Actions permises (sans texte de remplacement) :
  - Retirer les phrases de clôture redondantes
  - Réduire la conclusion à l'apport propre

### ISSUE-0007 — contradiction

- Statut : **PROBABLE**
- Gravite : **medium**
- Confiance : 0.40
- Observation : Certains chiffres de vérification semblent incohérents : la méthode annonce 290 annonces vérifiées, le résumé parle de 250 prédictions précises ou datées, et 4.5 donne 203 précises.
- Objectif de revision : Clarifier le périmètre de chaque effectif dans le résumé et la méthode.
- Citations :
  - « la vérification sourcée, une à une, de 250 prédictions précises ou datées »
  - « Les 290 annonces précises ou datées ont été vérifiées une à une. »
- A preserver :
  - Le décompte détaillé en 4.5
- Actions permises (sans texte de remplacement) :
  - Harmoniser la désignation des 250 et 290
  - Expliquer le lien avec les 203 précises

### ISSUE-0008 — voice_and_register

- Statut : **PROBABLE**
- Gravite : **low**
- Confiance : 0.40
- Observation : Le registre bascule par moments : titre « Un écriture qui délègue l'interprétation », titres de sections journalistiques, formules imagées (« berceau »), abréviations (« avr. », « oct. ») dans le corps du texte.
- Objectif de revision : Uniformiser le registre des titres et des dates.
- Citations :
  - « 4.10 /pol/, le berceau de Q »
  - « Un choix d'acteurs très sélectif »
  - « l'heure de publication bascule le 21 avr. 2018 »
- A preserver :
  - Les titres porteurs de résultat
- Actions permises (sans texte de remplacement) :
  - Neutraliser les titres imagés
  - Harmoniser l'écriture des dates

### ISSUE-0009 — repeated_openings

- Statut : **PROBABLE**
- Gravite : **low**
- Confiance : 0.40
- Observation : Les paragraphes de Données et Méthodes commencent par un intitulé court suivi d'un point (« Rythme. », « Discours. »), pattern systématique ; l'audit signale par ailleurs 38 % d'ouvertures répétées.
- Objectif de revision : Maintenir la structure fonctionnelle mais varier les ouvertures dans les résultats.
- Citations :
  - « Tweets de Donald Trump. »
  - « Actualité mondiale. »
- A preserver :
  - Les intitulés de sources et méthodes
- Actions permises (sans texte de remplacement) :
  - Varier les ouvertures des paragraphes de résultats

## Etapes en echec

### mechanical
- `deepseek/deepseek-v4.1-flash`
- Cause : `OUTPUT_TRUNCATED` — reponse vide (finish_reason=length, tokens=6492, raisonnement=6492, effort=minimal)

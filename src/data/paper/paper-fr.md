---
title: "Les drops de Q à l'épreuve des faits"
subtitle: "Étude statistique des messages de « Q » (2017-2022) confrontés à l'actualité"
author: "Sylvain Geffroy"
date: "16 octobre 2026"
version: "Document de travail, version 1.2"
abstract_en: |
  Between October 2017 and November 2022, an anonymous author signing "Q" posted 4,966 messages ("drops") on 4chan, 8chan and 8kun, the founding texts of the QAnon conspiracy theory. Most research studies QAnon's followers and platforms. We study the drops themselves. We check what they say against what actually happened.

  Nothing suggests that Q anticipated the news. Trump's tweets do not follow the drops more often than chance once local activity is taken into account (4.2% vs 4.0%, p = 0.23). Of the checkable predictions, 28% came true (95% CI 21–36%), but only 16% once scheduled events are set aside. None of the announced arrests or indictments happened. In a blind "horoscope test", a language model must say which of two news lists goes with a drop. Three times out of four it finds no specific link. When it does, it favours the real period for the past and the future alike, and a second model sees a specific link in only 5 of 100 "future" comparisons. The timing of the drops is better described by a model of earthquake aftershocks than by a news feed. That model attributes most drops to earlier drops and almost none to Trump's tweets. Against the wider scene (six subreddits sampled every active day from 2016 to 2023, Wikipedia, Google Trends, 4chan's /pol/), Q draws on a small number of the scene's themes, and we detect no precedence either way at the scales we tested. Its own forums, though, react within hours. On /pol/, which we read in full (134.5 million posts), Q moved into threads already opened by Trump's "calm before the storm". It kept their conspiracies but not their explicit hate vocabulary, and its threads are calmer than the rest of the board.

  The study combines descriptive statistics, text analysis, permutation tests, GDELT news data and a sourced check of 250 predictions. All data, code and verdicts are public.
---

## Résumé

Entre octobre 2017 et novembre 2022, un auteur anonyme signant « Q » a publié 4 966 messages (« drops ») sur 4chan, 8chan puis 8kun, les textes fondateurs de la théorie du complot QAnon. La plupart des travaux étudient les adeptes de QAnon et ses plateformes. Nous étudions les drops eux-mêmes. Nous confrontons ce qu'ils disent à ce qui s'est réellement passé.

Rien n'indique que Q ait anticipé l'actualité. Les tweets de Trump ne suivent pas les drops plus souvent que le hasard une fois l'activité locale prise en compte (4,2 % contre 4,0 %, p = 0,23). Sur les prédictions vérifiables, 28 % se sont réalisées (IC 95 % 21–36 %), mais seulement 16 % une fois écartés les événements déjà programmés. Aucune des arrestations ou inculpations annoncées n'a eu lieu. Dans un « test de l'horoscope » à l'aveugle, un modèle de langage doit dire laquelle de deux listes d'actualité va avec un drop. Trois fois sur quatre, il ne trouve aucun lien précis. Quand il en trouve un, il préfère la vraie période pour le passé comme pour l'avenir, et un second modèle ne voit de lien précis que dans 5 comparaisons « avenir » sur 100. Le rythme des drops est mieux décrit par un modèle de répliques sismiques que par un fil d'actualité. Ce modèle attribue la plupart des drops à des drops antérieurs et presque aucun aux tweets de Trump. Face à la scène complotiste (six subreddits échantillonnés chaque jour actif de 2016 à 2023, Wikipédia, Google Trends, /pol/ de 4chan), Q ne reprend qu'un petit nombre des thèmes de la scène, et nous ne détectons aucune précédence, dans un sens ou dans l'autre, aux échelles testées. Ses propres forums, eux, réagissent dans les heures qui suivent. Sur /pol/, que nous avons lu en entier (134,5 millions de posts), Q s'installe dans des fils déjà ouverts par le « calme avant la tempête » de Trump. Il en garde les complots, mais pas le vocabulaire de haine explicite, et ses fils sont plus calmes que le reste du forum.

L'étude combine statistiques descriptives, analyse textuelle, tests par permutation, données d'actualité de GDELT et vérification sourcée de 250 prédictions. Données, code et verdicts sont publiés.

**Mots-clés** : QAnon, théories du complot, prophéties, analyse textuelle, GDELT, modèles de langage, vérification des faits, processus de Hawkes, chaînes de Markov.

## 1. Introduction

QAnon est né le 28 octobre 2017 sur le forum /pol/ de 4chan, dans un milieu qui avait déjà produit collectivement la théorie du « Pizzagate » [@tuters2018posttruth]. Un auteur anonyme, se présentant comme un initié du gouvernement américain détenteur d'une habilitation « Q », y annonçait qu'une cabale d'élites pédocriminelles serait bientôt démantelée par Donald Trump. Le mouvement s'est diffusé d'une plateforme à l'autre [@dezeeuw2020tracing], a gagné une partie de l'électorat républicain [@sommer2023trust] et a été associé à l'assaut du Capitole du 6 janvier 2021 [@jensen2024qanon].

La recherche a beaucoup étudié les adeptes – leur nombre [@enders2022who; @prri2024rise], leur psychologie [@bloom2021pastels], leurs pratiques de « recherche » [@marwick2024constructing] – et les plateformes. Les drops eux-mêmes ont été analysés surtout qualitativement [@linvill2021mapping; @mcintosh2022sinister] ou sous l'angle de l'attribution d'auteur [@papasavva2022gospel; @cafiero2023who]. À notre connaissance, il manque une confrontation systématique, sur tout le corpus, entre ce que Q a écrit et annoncé et ce qui s'est réellement passé.

Ce document de travail propose cette confrontation, avec trois exigences : mesurer plutôt qu'illustrer, comparer chaque observation à une référence explicite (un modèle nul, l'actualité mondiale, une période tirée au hasard), et publier toutes les données et tous les verdicts pour qu'ils puissent être discutés. Il accompagne un site bilingue où chaque chiffre est recalculé, sourcé et citable (https://s-geffroy.github.io/QAnon/).

## 2. Données

**Le corpus.** Il n'existe pas de collection officielle des drops, et les sites d'agrégation divergent à la marge [@papasavva2022gospel]. Nous utilisons le corpus JSON-QAnon [@kingsman2021qanon] : 4 966 messages du 28 octobre 2017 au 27 novembre 2022 (heure de New York), avec leur forum, leurs images et les messages auxquels ils renvoient. Q a publié sur 533 jours distincts, avec un silence de 563 jours entre le 8 décembre 2020 et le 24 juin 2022.

**Tweets de Donald Trump.** Les tweets jusqu'au 8 janvier 2021 [@codebreaker2021donald], horodatés en UTC, soit environ 12,7 tweets par jour sur la période.

**Actualité mondiale.** Les fichiers quotidiens de GDELT 1.0 [@gdeltproject] du 1er octobre 2017 au 31 janvier 2021 : 1 219 jours, 181 749 399 événements, agrégés par acteur et par pays. Pour le test de l'horoscope, nous utilisons aussi le portail « Current events » de Wikipédia, résumé éditorial quotidien de l'actualité avec sources : 17 701 items sur la même période.

**Intérêt public.** Les pages vues de 15 articles de Wikipédia (dont « QAnon » en onze langues) via l'API Wikimedia [@wikimediapageviews].

**La scène complotiste américaine.** Six subreddits (r/conspiracy, r/conspiracytheories, r/The_Donald, r/greatawakening, r/CBTS_Stream, r/QAnonCasualties), y compris ceux qui ont été bannis, via l'archive Arctic Shift : volumes quotidiens exacts de 2016 à 2023, activité horaire des deux forums de Q, et un échantillon quotidien systématique de messages, sans nom d'auteur ({val:reddit_sample}). Les pages vues de 25 articles de Wikipédia sur les grands thèmes de la scène (redirections comprises). L'intérêt de recherche Google (États-Unis) pour ces thèmes. Le forum /pol/ de 4chan de juin 2016 à novembre 2019 [@papasavva2020raiders], lu une seule fois et réduit à des agrégats. Un lexique versionné de 459 motifs (formules de Q, grands récits complotistes, codes de haine, culture de /pol/, milices, élections, santé) sert aux mêmes comptages dans toutes ces sources. Sur /pol/, les 34 motifs ajoutés après sa lecture sont mesurés dans les fils Q, dans un échantillon de 1 % des posts et, pour les mots isolés, dans les comptes mensuels de mots de tout le forum.

**Données éditoriales.** Une chronologie de 31 événements datés et sourcés, un dictionnaire de 199 acteurs (motifs de reconnaissance, codes pays), un glossaire de 47 formules et une bibliographie vérifiée, tous versionnés avec le code.

## 3. Méthodes

**Rythme.** Intervalles entre drops consécutifs, coefficient de rafale B et coefficient de mémoire M [@goh2008burstiness] ; sessions de drops séparés de moins de 30 minutes ; régimes d'activité par partition optimale des comptes hebdomadaires [@jackson2005optimal; @killick2012pelt], avec un coût de Poisson corrigé de la surdispersion et une pénalité BIC.

**Discours.** Thèmes par factorisation en matrices non négatives [@lee1999nmf] des poids TF-IDF ; termes distinctifs de chaque année par log-odds avec a priori de Dirichlet informatif [@monroe2008fightin] ; stylométrie exploratoire par le Delta de Burrows [@burrows2002delta] sur des blocs d'environ 1 500 mots ; lisibilité de Flesch [@flesch1948readability] et richesse lexicale MATTR [@covington2010mattr].

**Q et les tweets de Trump.** Q affirmait que des tweets publiés quelques minutes après un drop en confirmaient l'authenticité (les « deltas »). Pour chaque fenêtre (1, 5, 10 et 60 minutes) et chaque sens, nous comparons la part de drops suivis (ou précédés) d'un tweet à sa distribution sous deux modèles nuls, par 1 000 permutations [@phipson2010permutation] : un modèle « jours », qui déplace chaque drop à la même heure d'un autre jour, et un modèle « local », qui le déplace de quelques heures et conserve donc l'activité du moment. Le premier surestime la synchronie, car Q et Trump publient tous deux davantage les jours de forte actualité. C'est le second qui juge la revendication.

**Acteurs et actualité.** Pour chaque acteur du dictionnaire, la sur-représentation est le rapport entre sa part dans les mentions de Q et sa part dans les événements GDELT. Nous calculons aussi des corrélations hebdomadaires décalées et des tests de causalité de Granger [@granger1969causal], sans correction pour comparaisons multiples (ils sont exploratoires).

**Prédictions.** Chaque drop non vide est soumis à un modèle de langage, avec une consigne et un schéma de réponse stricts, qui doit dire s'il contient une prédiction et laquelle (paraphrase, type d'événement, sujets, échéance, précision). Le modèle a été choisi parmi sept, sur un jeu de référence de 150 drops annotés à la main selon des consignes publiées (36 positifs), avec un intervalle bootstrap [@efron1979bootstrap] sur le F1. Nous avons retenu gpt-5.6-luna (F1 = 0,86 ; IC 0,78–0,94), pour un coût de 0,59 $ sur le corpus, contre 0,90 et 4,34 $ pour le meilleur modèle, l'écart n'étant pas significatif.

**Vérification.** Le modèle classe chaque prédiction extraite en précise ou vague. Les 290 annonces précises, ou vagues mais assorties d'une échéance datée, ont été vérifiées une à une, et celles qui se révèlent ne pas être des prédictions sont écartées. L'horizon est l'échéance énoncée, sinon douze mois après le drop. Chaque verdict (réalisée, partielle, non réalisée, invérifiable, pas une prédiction) est justifié et sourcé. Une prédiction est « triviale » si l'événement était déjà annoncé ou programmé quand Q l'a écrite. Les taux sont donnés avec des intervalles de Wilson [@wilson1927probable].

**Test de l'horoscope.** Si les drops anticipaient l'actualité, un lecteur devrait reconnaître, parmi deux périodes, celle qui suit réellement le drop. Pour 300 drops tirés au sort (au moins 15 mots, stratifiés par année), un modèle de langage reçoit, sans aucune date, le texte du drop et deux listes d'items d'actualité liés aux États-Unis, de même longueur et dans un ordre tiré au sort : la vraie période et une période tirée au hasard à plus de six mois du drop. Deux comparaisons sont faites : les 7 jours qui précèdent le drop (le drop commente-t-il l'actualité ?) et les 30 jours qui suivent (l'annonce-t-il ?). La consigne est sceptique : une formulation vague ne compte pas. Le modèle note chaque liste de 0 à 10 et choisit l'une d'elles, ou aucune. Nous testons la part de bons choix parmi les cas tranchés contre 50 %. Un second modèle repose les mêmes questions pour un tiers des drops.

**Modèles stochastiques.** Les comptes quotidiens de drops sont décrits par un modèle de Markov caché à émissions binomiales négatives [@rabiner1989tutorial], dont le nombre d'états est choisi par le BIC. Les thèmes NMF successifs d'une même session forment une chaîne de Markov, dont la persistance est comparée à 1 000 permutations des thèmes au sein des sessions. La dérive du style est l'entropie croisée d'un modèle de caractères d'ordre 3 entraîné sur un semestre et évalué sur le suivant, complétée par une distance de compression [@benedetto2002language]. Les horodatages des drops sont ensuite traités comme une séquence sismique : un processus de Hawkes [@hawkes1971spectra] à noyau exponentiel ou d'Omori [@ogata1988statistical], sur un fond propre à chaque régime avec cycle quotidien, estimé par l'algorithme EM [@veen2008estimation] et jugé par l'AIC et par l'adéquation des résidus après changement de temps. Un terme croisé mesure la part des drops que le modèle attribue aux tweets de Trump, comparée à 28 décalages témoins de –14 à +14 jours. Nous estimons aussi la mémoire longue par analyse des fluctuations redressées [@peng1994mosaic], la loi des tailles de sessions [@clauset2009powerlaw; @vuong1989likelihood] et la phase du cycle quotidien de publication.

**Q dans la scène.** Pour chaque thème de la scène que Q emploie dans au moins dix drops, la part hebdomadaire de drops qui le mentionnent est comparée à l'attention de la scène (Reddit, Wikipédia, Google Trends) par corrélation croisée de –8 à +8 semaines après pré-blanchiment, avec 300 substituts IAAFT [@schreiber2000surrogate] et correction de Benjamini–Hochberg [@benjamini1995controlling] : Q précède, suit, évolue en même temps, ou rien de significatif. L'entropie de transfert [@schreiber2000measuring] cherche des flux d'information entre séries quotidiennes, une fois retirés les cycles hebdomadaires. La réponse des forums de Q à ses drops est mesurée heure par heure par analyse d'époque superposée, contre des instants tirés au hasard. Les plus grands pics d'attention de la scène sont classés en chocs extérieurs ou cascades internes selon la forme de leur montée et de leur retombée [@crane2008robust]. Sur /pol/, une formule « apparaît » la première semaine où son nombre de posts dépasse durablement le quantile 0,999 d'une loi de Poisson au taux d'avant Q. La toute première occurrence, souvent fortuite, n'est pas retenue. La toxicité est celle des scores Perspective fournis avec le jeu de données ; le vocabulaire propre aux fils Q est mesuré par log-rapport de cotes à prior de Dirichlet informatif [@monroe2008fightin].

**Prophéties recyclées et autocitations.** Les prédictions sont regroupées par sujet (même type d'événement, même acteur) ; un sujet annoncé sur au moins trois mois distincts est « recyclé ». Nous mesurons enfin le délai des renvois de Q vers ses propres drops, qui sous-tendent la formule « Future proves past ».

## 4. Résultats

### 4.1 Un rythme de rafales, des régimes liés aux plateformes

Q ne publie pas au fil de l'eau mais par rafales : le coefficient B vaut 0,91 (0 pour un processus de Poisson). L'intervalle médian entre deux drops est de 14 minutes, et 26 % des drops suivent le précédent de moins de 5 minutes, 75 % de moins d'une heure. Les drops se regroupent en 1 743 sessions, et 85 % d'entre eux appartiennent à une session de plusieurs messages. Le record est de 64 drops le 28 mars 2019. Le volume hebdomadaire se découpe en six régimes (figure 1). Une phase intense dure jusqu'à l'automne 2018 (47 drops par semaine en moyenne). Après un creux vient un pic en février et mars 2019 (89 par semaine). Suit une phase faible d'avril 2019 au printemps 2020 (11 par semaine), qui couvre la fermeture de 8chan en août 2019 et le retour sur 8kun en novembre. L'activité reprend au printemps 2020 avec la pandémie (35 par semaine), puis s'éteint après l'élection de novembre 2020.

{figure:weekly}

### 4.2 Une écriture qui délègue l'interprétation

Un drop contient en moyenne 1,39 point d'interrogation, et 38 % en contiennent au moins un. Les phrases sont courtes (7 mots en moyenne, indice de Flesch 65). Le thème dominant de la factorisation (43 % du poids) mêle le président (« POTUS »), le contrôle et le public. D'autres thèmes regroupent les formules rituelles (« fake news », « news unlocks », « future proves past », « God bless », « do you believe in coincidences? »). Q renvoie à un message d'anonyme dans 23 % des drops et à l'un de ses propres drops dans 8 %, signe d'une écriture en dialogue avec des lecteurs chargés de « faire leurs recherches », conformément à ce que décrivent les analyses qualitatives [@mcintosh2022sinister; @marwick2024constructing]. Le vocabulaire religieux ou moral reste minoritaire (6,3 % des drops) et ne progresse pas : il culmine dans les premières semaines.

La stylométrie exploratoire place la rupture de style la plus nette autour du 25 novembre 2017, c'est-à-dire au premier drop sur 8chan. Cela rejoint les études qui concluent à au moins deux plumes successives [@orphanalytics2020style; @cafiero2023who], mais notre analyse ne permet pas de distinguer un changement d'auteur d'un changement de plateforme, et elle n'identifie personne.

### 4.3 Pas de synchronie avec les tweets de Trump

Avec le modèle nul local, un tweet de Trump suit un drop en moins de 5 minutes dans 4,2 % des cas, contre 4,0 % attendus (p = 0,23). Aucune fenêtre ne montre d'excès dans le sens « tweet après le drop ». Le modèle « jours » produit des écarts significatifs, mais dans les deux sens, y compris quand le tweet précède le drop, ce qui correspond à la co-activité des jours chargés plutôt qu'à une coordination (tableau 1).

{table:trump} Dans l'autre sens, Q réagissait à Trump : 59 drops citent un tweet présidentiel, en médiane 1 h 54 après sa publication.

### 4.4 Un choix d'acteurs très sélectif

Les acteurs les plus nommés sont Donald Trump (386 drops), les « médias » (241) et Barack Obama (166) ; 33 % des drops nomment au moins un acteur du dictionnaire. Rapportée à leur place dans l'actualité mondiale, la sur-représentation est massive pour George Soros (×15,8), Hillary Clinton (×8,0) et le Parti démocrate (×3,1), tandis que le Congrès (×0,2) ou l'Union européenne (×0,45) sont sous-représentés. Les pays cités par Q suivent pourtant l'actualité (corrélation de rang 0,61) : Q sélectionne donc ses acteurs bien plus que les pays dont il parle (figure 3).

{figure:overrep} Les tests de Granger ne montrent pas que l'actualité d'un acteur précède les mentions de Q (une seule p-valeur sur quinze sous 0,05, ce qu'on attend du hasard).

### 4.5 Des prédictions rares, proches et rarement réalisées

Le modèle trouve au moins une prédiction dans 13 % des drops (598), soit 846 prédictions, dont 203 précises et 643 vagues. Les échéances datées sont proches : médiane de 7 jours, la moitié à moins d'une semaine. Sur les 290 annonces vérifiées, 40 se révèlent ne pas être des prédictions, et 110 des 250 restantes sont invérifiables. Des 140 prédictions vérifiables, 39 se sont réalisées, soit 28 % (IC 95 % : 21–36 %), et 22 en partie. Hors événements déjà annoncés ou programmés, le taux tombe à 16 % (IC 95 % : 10–24 %). Aucune des 8 arrestations ou inculpations vérifiables ne s'est produite, ni aucune des 10 déclassifications annoncées. Les réussites portent surtout sur des démissions (7 sur 14) et des décisions de justice déjà attendues (3 sur 3) (tableau 2).

{table:verif_types}
 Dix-sept sujets sont annoncés sur au moins trois mois différents, et dans sept d'entre eux l'annonce revient après un échec déjà vérifié – un comportement attendu des groupes prophétiques [@festinger1956when; @westmark2022identifying].

### 4.6 Le test de l'horoscope

Dans environ trois quarts des comparaisons, le modèle ne trouve aucun lien précis entre le drop et l'une ou l'autre période. Quand il tranche, il reconnaît la vraie période dans 75 % des cas pour les 7 jours qui précèdent le drop (IC 95 % : 63–84 %, p < 0,001) et dans 68 % pour les 30 jours qui suivent (IC 95 % : 56–77 %, p = 0,004). Les deux taux ne diffèrent pas significativement (test exact de Fisher, p = 0,44). Le signal « avenir » ne suffit pas à conclure à une anticipation : il ne concerne qu'une minorité de comparaisons, des périodes tirées au hasard « correspondent » elles aussi, et il est compatible avec la simple continuité des sujets d'une semaine à l'autre, hypothèse que ce test ne mesure pas. Une période tirée au hasard obtient une note d'au moins 5 sur 10 dans 6 % des cas (figure 2). Des drops assez vagues « collent » à des événements survenus des années plus tard, comme une allusion à la Cour suprême rattachée à la mort de Ruth Bader Ginsburg en 2020. {val:horo_robust_sentence}

{figure:horoscope}

### 4.7 L'intérêt public suit les événements, pas les drops

Les pages vues de l'article « QAnon » suivent à peine l'activité de Q : les corrélations hebdomadaires, avec des décalages de –4 à +4 semaines, restent faibles (0,17 au plus). Elles bondissent avec la visibilité du mouvement hors d'internet : ×13,3 la semaine du meeting de Trump à Tampa (août 2018), où apparaissent les premières pancartes « Q » très médiatisées, et ×11,2 après l'assaut du Capitole.

### 4.8 Un processus auto-excité, à mémoire longue, sans criticité

Le modèle de Markov caché retient {val:hmm_k} régimes, un silence, une veille et un régime actif (figure 4a). La veille compte {val:hmm_mid} drop par jour, le régime actif {val:hmm_rate}. Ce dernier ne couvre que {val:hmm_days} des jours, mais réunit {val:hmm_drops} des drops. Un séjour dure {val:hmm_dwell} jours en moyenne, pour {val:hmm_switches} bascules en tout. Sur les {val:hmm_ncp} ruptures de la section 4.1, {val:hmm_agree} tombent à moins d'une semaine d'une bascule du modèle, que rien ne contraint pourtant à les retrouver. Au sein des sessions, Q reste sur le même thème dans {val:chain_diag} des enchaînements, contre {val:chain_null} si les thèmes étaient permutés dans chaque session (p = {val:chain_p}). L'ordre des drops n'est donc pas aléatoire, mais l'effet est faible (taux d'entropie de {val:chain_h1} bits contre {val:chain_h0} sans mémoire). Les deux plus fortes dérives du style tombent aux passages {val:drift_a} (+{val:drift_da} bit par caractère) et {val:drift_b} (+{val:drift_db}), ce qui rejoint, avec une autre méthode, la rupture stylistique de la section 4.2.

Le processus de Hawkes décrit les horodatages bien mieux qu'un processus de Poisson, même doté du même fond par régime et du même cycle quotidien (écart d'AIC : {val:hk_daic}). Le meilleur modèle attribue {val:hk_n} des drops à l'excitation par des drops antérieurs ({val:hk_n_exp} avec un noyau exponentiel). Le délai médian de déclenchement est de {val:hk_med} minutes, et la retombée suit une loi d'Omori d'exposant {val:hk_p}, plus raide que celle des répliques sismiques. L'adéquation reste imparfaite (distance de Kolmogorov–Smirnov {val:hk_ks}, contre {val:hk_ks0} pour Poisson ; figure 4b). Le modèle n'attribue aux tweets de Trump que {val:ht_share} des drops, une part faible mais supérieure à celle de chacun des {val:ht_nshift} décalages témoins (p = {val:ht_p}). Le lien avec Trump reste donc marginal dans ce modèle, ce qui rejoint les 59 citations de tweets de la section 4.3.

L'activité quotidienne a une mémoire longue (exposant de Hurst {val:dfa_q}, contre {val:dfa_sh} une fois les jours mélangés), du même ordre que celle des tweets de Trump ({val:dfa_t}). En revanche, rien n'indique une criticité auto-organisée : la queue des tailles de sessions (exposant {val:av_alpha} au-delà de {val:av_xmin} drops, {val:av_tail} sessions sur {val:av_n}) n'est pas distinguable d'une loi lognormale (p = {val:av_pln}) ni d'une exponentielle (p = {val:av_pexp}). Enfin, l'heure de publication bascule le {val:ph_date}, et le pic de publication passe de {val:ph_before} à {val:ph_after} (heure de New York ; p = {val:ph_p} par permutation de la date de rupture). Mois après mois, la phase du cycle quotidien de Q reste accrochée à celle de Trump, environ {val:ph_lag} heures plus tard (valeur de verrouillage de phase {val:ph_plv}). Ce changement d'horaire est compatible avec un changement de main ou de rythme de vie, sans que ces données permettent de trancher.

{figure:models}

### 4.9 Q dans la scène complotiste américaine

{val:scene_status}

{val:scene_sync} {val:scene_absorption} Cette sélectivité prolonge celle des acteurs (section 4.4) : Q ne reprend pas l'ensemble du complotisme américain, il en retient quelques récits.

{val:scene_te} {val:scene_response} {val:scene_peaks}

{val:scene_diffusion} Ces délais restent des bornes. L'échantillon couvre tous les jours actifs, mais pas tous les messages, et une formule absente de Reddit pendant quelques semaines pouvait circuler ailleurs, notamment sur /pol/ et 8chan.

{table:diffusion}

### 4.10 /pol/, le berceau de Q

{val:scene_pol}

{table:pol_births}

{val:scene_pol2}

{table:pol_tox_groups}

{val:scene_pol3}

## 5. Discussion et limites

Ces résultats dessinent un auteur qui réagit à l'actualité, par rafales et sous forme de questions, choisit ses personnages et recycle ses annonces. Aucun de ces résultats ne désigne un initié qui l'anticiperait. Ils confirment, sur tout le corpus et avec des références explicites, ce que les études qualitatives et journalistiques avaient décrit [@rothschild2021storm; @tian2021qanon], et précisent les ordres de grandeur.

Plusieurs limites s'imposent. Le corpus n'est pas canonique. L'annotation des prédictions est automatique, et sa qualité, mesurée (F1 = 0,86), n'est pas parfaite. La frontière entre question rhétorique, formule et annonce reste discutable. La vérification est éditoriale : chaque verdict est sourcé et publié pour être contesté. Le test de l'horoscope dépend du jugement d'un modèle de langage. La comparaison avec un second modèle montre que les rares liens trouvés varient d'un modèle à l'autre (accord modeste). C'est une limite de la mesure, qui interdit d'interpréter finement les cas où un lien est vu. Ce test mesure en outre des liens précis, pas l'impression subjective de « confirmation » que recherchaient les lecteurs de Q. Les modèles de la section 4.8 sont des analogies : un processus de Hawkes décrit la structure temporelle des drops, pas leur cause, et une part « endogène » élevée est compatible avec un auteur qui écrit en série comme avec des réponses à des lecteurs. Les sources de la scène ont leurs propres biais : l'échantillon Reddit couvre chaque jour actif mais non chaque message, les bannissements de subreddits sont des censures et non des silences, Google Trends est un indice échantillonné et arrondi, et /pol/ s'arrête en novembre 2019. Les scores de toxicité de /pol/, calculés par Perspective, lisent mal l'ironie et l'argot de 4chan, et la date d'apparition d'une formule dépend d'un seuil (quantile 0,999, confirmation sur quatre semaines). Les 34 motifs ajoutés au lexique après la lecture de /pol/ n'y sont mesurés que dans les fils Q, un échantillon de 1 % et les comptes mensuels de mots, et la répartition des posts entre groupes de toxicité suit le premier terme reconnu. Enfin, les corrélations avec GDELT, Wikipédia, Reddit ou Google ne disent rien de la causalité.

## 6. Conclusion

Confrontés systématiquement aux faits, les drops de Q apparaissent comme un commentaire de l'actualité habillé en prophétie. La synchronie revendiquée avec Trump disparaît dès qu'on la compare au hasard. Les prédictions vérifiables se réalisent rarement (28 %), et nettement moins quand l'événement n'était pas déjà annoncé ou programmé (16 %, IC 95 % 10–24 %). Les « correspondances » avec l'avenir, rares, varient d'un modèle à l'autre et n'excèdent pas celles qu'on observe avec le passé. Replacé dans son milieu, Q n'apparaît ni comme l'inventeur de la scène complotiste américaine ni comme son écho : aucune précédence n'est détectée entre ses thèmes et les siens, dans les sources et aux échelles testées. Il s'installe sur /pol/ dans des fils et un vocabulaire qui existaient avant lui, n'en retient que quelques récits, et forge à son tour des formules que Reddit reprend en quelques jours ou semaines. Ses forums, eux, réagissent à ses drops dans les heures qui suivent. Le principal enseignement est méthodologique : chaque « preuve » avancée par le mouvement peut être transformée en hypothèse testable, à condition de lui donner une référence.

## Données et code

Toutes les données dérivées, les verdicts de vérification, le jeu de référence et ses consignes, le code (licence MIT) et le site (licence CC BY 4.0) sont disponibles : https://s-geffroy.github.io/QAnon/ et doi:10.5281/zenodo.23338131. Les chiffres de ce document sont ceux du site à la date de cette version (16 octobre 2026). Le site est recalculé à chaque évolution, et chaque version est archivée.

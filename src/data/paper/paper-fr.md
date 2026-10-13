---
title: "Les drops de Q à l'épreuve des faits"
subtitle: "Étude statistique des messages de « Q » (2017-2022) confrontés à l'actualité"
author: "Sylvain Geffroy"
date: "13 octobre 2026"
version: "Document de travail, version 1.0"
abstract_en: |
  Between October 2017 and November 2022, an anonymous author signing "Q" posted 4,966 messages ("drops") on 4chan, 8chan and 8kun, the founding texts of the QAnon conspiracy theory. Most research on QAnon studies its followers and platforms; this working paper measures the drops themselves and confronts them systematically with real-world events. It combines descriptive statistics, text analysis (NMF themes, distinctive terms, exploratory stylometry), a test of the claimed synchrony with Donald Trump's tweets against two null models, a comparison of the actors Q names with world news coverage (GDELT, 182 million events), the extraction of all predictions by a language model chosen after evaluation on a hand-annotated reference set, a sourced one-by-one verification of 250 specific or dated predictions, and a blind "horoscope test" of whether the drops fit the news better than chance. Q posts in bursts and nothing indicates that it anticipated the news: no excess of Trump tweets follows the drops once local activity is controlled for (4.2% vs 4.0% expected, p = 0.23); 28% of checkable predictions came true (95% CI 21–36%), 16% excluding already scheduled events, and none of the announced arrests or indictments; in the horoscope test the model finds no specific link in three quarters of comparisons; when it finds one it favours the real period for the past and the future alike (no significant difference), and a second model sees a specific link in only 5 of 100 "future" comparisons. All data, code and verdicts are published.
---

## Résumé

Entre octobre 2017 et novembre 2022, un auteur anonyme signant « Q » a publié 4 966 messages (« drops ») sur 4chan, 8chan puis 8kun : les textes fondateurs de la théorie du complot QAnon. La plupart des travaux sur QAnon étudient ses adeptes et ses plateformes ; ce document de travail mesure les drops eux-mêmes et les confronte systématiquement à l'actualité réelle. Il combine statistiques descriptives, analyse textuelle (thèmes NMF, termes distinctifs, stylométrie exploratoire), un test de la synchronie revendiquée avec les tweets de Donald Trump contre deux modèles nuls, une comparaison des acteurs nommés par Q avec la couverture médiatique mondiale (GDELT, 182 millions d'événements), l'extraction de toutes les prédictions par un modèle de langage choisi après évaluation sur un jeu de référence annoté à la main, la vérification sourcée, une à une, de 250 prédictions précises ou datées, et un « test de l'horoscope » à l'aveugle qui mesure si les drops collent à l'actualité plus que par hasard. Q publie par rafales, et rien n'indique qu'il ait anticipé l'actualité : aucun excès de tweets de Trump ne suit les drops une fois l'activité locale prise en compte (4,2 % contre 4,0 % attendus, p = 0,23) ; 28 % des prédictions vérifiables se sont réalisées (IC 95 % : 21–36 %), 16 % hors événements déjà programmés, et aucune des arrestations ou inculpations annoncées ; dans le test de l'horoscope, le modèle ne trouve aucun lien précis dans les trois quarts des comparaisons ; quand il en trouve un, il préfère la vraie période pour le passé comme pour l'avenir, sans différence significative, et un second modèle ne voit de lien précis que dans 5 comparaisons « avenir » sur 100. Données, code et verdicts sont publiés.

**Mots-clés** : QAnon, théories du complot, prophéties, analyse textuelle, GDELT, modèles de langage, vérification des faits.

## 1. Introduction

QAnon est né le 28 octobre 2017 sur le forum /pol/ de 4chan, dans un milieu qui avait déjà produit collectivement la théorie du « Pizzagate » [@tuters2018posttruth]. Un auteur anonyme, se présentant comme un initié du gouvernement américain détenteur d'une habilitation « Q », y annonçait qu'une cabale d'élites pédocriminelles serait bientôt démantelée par Donald Trump. Le mouvement s'est diffusé d'une plateforme à l'autre [@dezeeuw2020tracing], a gagné une partie de l'électorat républicain [@sommer2023trust] et a été associé à l'assaut du Capitole du 6 janvier 2021 [@jensen2024qanon].

La recherche a beaucoup étudié les adeptes – leur nombre [@enders2022who; @prri2024rise], leur psychologie [@bloom2021pastels], leurs pratiques de « recherche » [@marwick2024constructing] – et les plateformes. Les drops eux-mêmes ont été analysés surtout qualitativement [@linvill2021mapping; @mcintosh2022sinister] ou sous l'angle de l'attribution d'auteur [@papasavva2022gospel; @cafiero2023who]. À notre connaissance, il manque une confrontation systématique, sur tout le corpus, entre ce que Q a écrit et annoncé et ce qui s'est réellement passé.

Ce document de travail propose cette confrontation, avec trois exigences : mesurer plutôt qu'illustrer, comparer chaque observation à une référence explicite (un modèle nul, l'actualité mondiale, une période tirée au hasard), et publier toutes les données et tous les verdicts pour qu'ils puissent être discutés. Il accompagne un site bilingue où chaque chiffre est recalculé, sourcé et citable (https://s-geffroy.github.io/QAnon/).

## 2. Données

**Le corpus.** Il n'existe pas de collection officielle des drops ; les sites d'agrégation divergent à la marge [@papasavva2022gospel]. Nous utilisons le corpus JSON-QAnon [@kingsman2021qanon] : 4 966 messages du 28 octobre 2017 au 27 novembre 2022 (heure de New York), avec leur forum, leurs images et les messages auxquels ils renvoient. Q a publié sur 533 jours distincts, avec un silence de 563 jours entre le 8 décembre 2020 et le 24 juin 2022.

**Tweets de Donald Trump.** Les tweets jusqu'au 8 janvier 2021 [@codebreaker2021donald], horodatés en UTC, soit environ 12,7 tweets par jour sur la période.

**Actualité mondiale.** Les fichiers quotidiens de GDELT 1.0 [@gdeltproject] du 1er octobre 2017 au 31 janvier 2021 : 1 219 jours, 181 749 399 événements, agrégés par acteur et par pays. Pour le test de l'horoscope, nous utilisons aussi le portail « Current events » de Wikipédia, résumé éditorial quotidien de l'actualité avec sources : 17 701 items sur la même période.

**Intérêt public.** Les pages vues de 15 articles de Wikipédia (dont « QAnon » en onze langues) via l'API Wikimedia [@wikimediapageviews].

**Données éditoriales.** Une chronologie de 31 événements datés et sourcés, un dictionnaire de 199 acteurs (motifs de reconnaissance, codes pays), un glossaire de 47 formules et une bibliographie vérifiée, tous versionnés avec le code.

## 3. Méthodes

**Rythme.** Intervalles entre drops consécutifs, coefficient de rafale B et coefficient de mémoire M [@goh2008burstiness] ; sessions de drops séparés de moins de 30 minutes ; régimes d'activité par partition optimale des comptes hebdomadaires [@jackson2005optimal; @killick2012pelt], avec un coût de Poisson corrigé de la surdispersion et une pénalité BIC.

**Discours.** Thèmes par factorisation en matrices non négatives [@lee1999nmf] des poids TF-IDF ; termes distinctifs de chaque année par log-odds avec a priori de Dirichlet informatif [@monroe2008fightin] ; stylométrie exploratoire par le Delta de Burrows [@burrows2002delta] sur des blocs d'environ 1 500 mots ; lisibilité de Flesch [@flesch1948readability] et richesse lexicale MATTR [@covington2010mattr].

**Q et les tweets de Trump.** Q affirmait que des tweets publiés quelques minutes après un drop en confirmaient l'authenticité (les « deltas »). Pour chaque fenêtre (1, 5, 10 et 60 minutes) et chaque sens, nous comparons la part de drops suivis (ou précédés) d'un tweet à sa distribution sous deux modèles nuls, par 1 000 permutations [@phipson2010permutation] : un modèle « jours », qui déplace chaque drop à la même heure d'un autre jour, et un modèle « local », qui le déplace de quelques heures et conserve donc l'activité du moment. Le premier surestime la synchronie, car Q et Trump publient tous deux davantage les jours de forte actualité ; le second juge la revendication.

**Acteurs et actualité.** Pour chaque acteur du dictionnaire, la sur-représentation est le rapport entre sa part dans les mentions de Q et sa part dans les événements GDELT ; nous calculons aussi des corrélations hebdomadaires décalées et des tests de causalité de Granger [@granger1969causal], sans correction pour comparaisons multiples (ils sont exploratoires).

**Prédictions.** Chaque drop non vide est soumis à un modèle de langage avec une consigne et un schéma de réponse stricts : contient-il une prédiction, et laquelle (paraphrase, type d'événement, sujets, échéance, précision) ? Le modèle a été choisi parmi sept, sur un jeu de référence de 150 drops annotés à la main selon des consignes publiées (36 positifs), avec un intervalle bootstrap [@efron1979bootstrap] sur le F1 : gpt-5.6-luna (F1 = 0,86 ; IC 0,78–0,94) a été retenu, pour un coût de 0,59 $ sur le corpus, contre 0,90 et 4,34 $ pour le meilleur modèle, l'écart n'étant pas significatif.

**Vérification.** Les 290 annonces précises ou datées ont été vérifiées une à une. L'horizon est l'échéance énoncée, sinon douze mois après le drop ; chaque verdict (réalisée, partielle, non réalisée, invérifiable, pas une prédiction) est justifié et sourcé ; une prédiction est « triviale » si l'événement était déjà annoncé ou programmé quand Q l'a écrite. Les taux sont donnés avec des intervalles de Wilson [@wilson1927probable].

**Test de l'horoscope.** Si les drops anticipaient l'actualité, un lecteur devrait reconnaître, parmi deux périodes, celle qui suit réellement le drop. Pour 300 drops tirés au sort (au moins 15 mots, stratifiés par année), un modèle de langage reçoit, sans aucune date, le texte du drop et deux listes d'items d'actualité liés aux États-Unis, de même longueur et dans un ordre tiré au sort : la vraie période et une période tirée au hasard à plus de six mois du drop. Deux comparaisons sont faites : les 7 jours qui précèdent le drop (le drop commente-t-il l'actualité ?) et les 30 jours qui suivent (l'annonce-t-il ?). La consigne est sceptique : une formulation vague ne compte pas. Le modèle note chaque liste de 0 à 10 et choisit l'une d'elles, ou aucune ; nous testons la part de bons choix parmi les cas tranchés contre 50 %. Un second modèle repose les mêmes questions pour un tiers des drops.

**Prophéties recyclées et autocitations.** Les prédictions sont regroupées par sujet (même type d'événement, même acteur) ; un sujet annoncé sur au moins trois mois distincts est « recyclé ». Nous mesurons enfin le délai des renvois de Q vers ses propres drops, qui sous-tendent la formule « Future proves past ».

## 4. Résultats

### 4.1 Un rythme de rafales, des régimes liés aux plateformes

Q ne publie pas au fil de l'eau mais par rafales : le coefficient B vaut 0,91 (0 pour un processus de Poisson). L'intervalle médian entre deux drops est de 14 minutes ; 26 % des drops suivent le précédent de moins de 5 minutes et 75 % de moins d'une heure. Les drops se regroupent en 1 743 sessions, et 85 % d'entre eux appartiennent à une session de plusieurs messages. Le record est de 64 drops le 28 mars 2019. Le volume hebdomadaire se découpe en six régimes : une phase intense jusqu'à l'automne 2018 (47 drops par semaine en moyenne), un creux, un pic de février-mars 2019 (89 par semaine), une phase faible d'avril 2019 au printemps 2020 (11 par semaine), qui couvre la fermeture de 8chan en août 2019 et le retour sur 8kun en novembre, une reprise au printemps 2020 avec la pandémie (35 par semaine), puis le silence après l'élection de novembre 2020 (figure 1).

{figure:weekly}

### 4.2 Une écriture qui délègue l'interprétation

Un drop contient en moyenne 1,39 point d'interrogation, et 38 % en contiennent au moins un. Les phrases sont courtes (7 mots en moyenne, indice de Flesch 65). Le thème dominant de la factorisation (43 % du poids) mêle le président (« POTUS »), le contrôle et le public ; d'autres thèmes regroupent les formules rituelles (« fake news », « news unlocks », « future proves past », « God bless », « do you believe in coincidences? »). Q renvoie à un message d'anonyme dans 23 % des drops et à l'un de ses propres drops dans 8 % : une écriture en dialogue avec des lecteurs chargés de « faire leurs recherches », conformément à ce que décrivent les analyses qualitatives [@mcintosh2022sinister; @marwick2024constructing]. Le vocabulaire religieux ou moral reste minoritaire (6,3 % des drops) et ne progresse pas : il culmine dans les premières semaines.

La stylométrie exploratoire place la rupture de style la plus nette autour du 25 novembre 2017, c'est-à-dire au premier drop sur 8chan. Cela rejoint les études qui concluent à au moins deux plumes successives [@orphanalytics2020style; @cafiero2023who], mais notre analyse ne permet pas de distinguer un changement d'auteur d'un changement de plateforme, et elle n'identifie personne.

### 4.3 Pas de synchronie avec les tweets de Trump

Avec le modèle nul local, un tweet de Trump suit un drop en moins de 5 minutes dans 4,2 % des cas, contre 4,0 % attendus (p = 0,23) ; aucune fenêtre ne montre d'excès dans le sens « tweet après le drop ». Le modèle « jours » produit des écarts significatifs, mais dans les deux sens, y compris quand le tweet précède le drop : c'est la signature de la co-activité des jours chargés, non d'une coordination (tableau 1).

{table:trump} Dans l'autre sens, Q réagissait à Trump : 59 drops citent un tweet présidentiel, en médiane 1 h 54 après sa publication.

### 4.4 Un choix d'acteurs très sélectif

Les acteurs les plus nommés sont Donald Trump (386 drops), les « médias » (241) et Barack Obama (166) ; 33 % des drops nomment au moins un acteur du dictionnaire. Rapportée à leur place dans l'actualité mondiale, la sur-représentation est massive pour George Soros (×15,8), Hillary Clinton (×8,0) et le Parti démocrate (×3,1), tandis que le Congrès (×0,2) ou l'Union européenne (×0,45) sont sous-représentés. Les pays cités par Q suivent pourtant l'actualité (corrélation de rang 0,61) : Q choisit ses personnages, pas sa géographie (figure 3).

{figure:overrep} Les tests de Granger ne montrent pas que l'actualité d'un acteur précède les mentions de Q (une seule p-valeur sur quinze sous 0,05, ce qu'on attend du hasard).

### 4.5 Des prédictions rares, proches et rarement réalisées

Le modèle trouve au moins une prédiction dans 13 % des drops (598), soit 846 prédictions, dont 203 précises. Les échéances datées sont proches : médiane de 7 jours, la moitié à moins d'une semaine. Sur les 290 annonces vérifiées, 40 se révèlent ne pas être des prédictions ; sur les 250 restantes, 110 sont invérifiables. Des 140 prédictions vérifiables, 39 se sont réalisées, soit 28 % (IC 95 % : 21–36 %), et 22 en partie. Hors événements déjà annoncés ou programmés, le taux tombe à 16 % (IC 95 % : 10–24 %). Aucune des 8 arrestations ou inculpations vérifiables ne s'est produite, ni aucune des 10 déclassifications annoncées ; les réussites portent surtout sur des démissions (7 sur 14) et des décisions de justice déjà attendues (3 sur 3) (tableau 2).

{table:verif_types}
 Dix-sept sujets sont annoncés sur au moins trois mois différents, et dans sept d'entre eux l'annonce revient après un échec déjà vérifié – un comportement attendu des groupes prophétiques [@festinger1956when; @westmark2022identifying].

### 4.6 Le test de l'horoscope

Dans environ trois quarts des comparaisons, le modèle ne trouve aucun lien précis entre le drop et l'une ou l'autre période. Quand il tranche, il reconnaît la vraie période dans 75 % des cas pour les 7 jours qui précèdent le drop (IC 95 % : 63–84 %, p < 0,001) et dans 68 % pour les 30 jours qui suivent (IC 95 % : 56–77 %, p = 0,004). Les deux taux ne diffèrent pas significativement (test exact de Fisher, p = 0,44). Le signal « avenir » ne suffit pas à conclure à une anticipation : il ne concerne qu'une minorité de comparaisons, des périodes tirées au hasard « correspondent » elles aussi, et il est compatible avec la simple continuité des sujets d'une semaine à l'autre, hypothèse que ce test ne mesure pas. Une période tirée au hasard obtient une note d'au moins 5 sur 10 dans 6 % des cas (figure 2) : des drops assez vagues « collent » à des événements survenus des années plus tard, comme une allusion à la Cour suprême rattachée à la mort de Ruth Bader Ginsburg en 2020. {val:horo_robust_sentence}

{figure:horoscope}

### 4.7 L'intérêt public suit les événements, pas les drops

Les pages vues de l'article « QAnon » suivent à peine l'activité de Q : les corrélations hebdomadaires, avec des décalages de –4 à +4 semaines, restent faibles (0,17 au plus). Elles bondissent avec la visibilité du mouvement hors d'internet : ×13,3 la semaine du meeting de Trump à Tampa (août 2018), où apparaissent les premières pancartes « Q » très médiatisées, et ×11,2 après l'assaut du Capitole.

## 5. Discussion et limites

Ces résultats dessinent un auteur qui réagit à l'actualité, par rafales et sous forme de questions, choisit ses personnages et recycle ses annonces ; aucun ne désigne un initié qui l'anticiperait. Ils confirment, sur tout le corpus et avec des références explicites, ce que les études qualitatives et journalistiques avaient décrit [@rothschild2021storm; @tian2021qanon], et précisent les ordres de grandeur.

Plusieurs limites s'imposent. Le corpus n'est pas canonique. L'annotation des prédictions est automatique : sa qualité est mesurée (F1 = 0,86), pas parfaite, et la frontière entre question rhétorique, formule et annonce reste discutable. La vérification est éditoriale : chaque verdict est sourcé et publié pour être contesté. Le test de l'horoscope dépend du jugement d'un modèle de langage : la comparaison avec un second modèle montre que les rares liens trouvés varient d'un modèle à l'autre (accord modeste), ce qui conforte la conclusion mais interdit d'interpréter finement les cas où un lien est vu ; et il mesure des liens précis, pas l'impression subjective de « confirmation » que recherchaient les lecteurs de Q. Enfin, les corrélations avec GDELT et Wikipédia ne disent rien de la causalité.

## 6. Conclusion

Confrontés systématiquement aux faits, les drops de Q apparaissent comme un commentaire de l'actualité habillé en prophétie : la synchronie revendiquée avec Trump disparaît dès qu'on la compare au hasard, les prédictions vérifiables se réalisent rarement et presque jamais quand elles n'étaient pas déjà programmées, et les « correspondances » avec l'avenir, rares, varient d'un modèle à l'autre et n'excèdent pas celles qu'on observe avec le passé. Le principal enseignement est méthodologique : chaque « preuve » avancée par le mouvement peut être transformée en hypothèse testable, à condition de lui donner une référence.

## Données et code

Toutes les données dérivées, les verdicts de vérification, le jeu de référence et ses consignes, le code (licence MIT) et le site (licence CC BY 4.0) sont disponibles : https://s-geffroy.github.io/QAnon/ et doi:10.5281/zenodo.23338131. Les chiffres de ce document correspondent à la version 1.0 du site (octobre 2026) ; le site est recalculé à chaque évolution.

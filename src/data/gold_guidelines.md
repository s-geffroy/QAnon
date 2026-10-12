# Gold set « prédictions » — guide d'annotation

Fichier : `src/data/gold.jsonl` (150 lignes, une par drop). Sert à évaluer les
LLM qui extraient des prédictions des drops Q.

**Annotateur** : Claude, annotation à relire par un humain. Une seule passe,
drop par drop, en lisant le texte et les posts référencés (`refs_json`).

## Définition

Une **prédiction** est une affirmation sur un état ou un événement futur (par
rapport à l'horodatage du drop) dans le monde réel, falsifiable en principe :
arrestation, inculpation, démission, déclassification, révélation, action
militaire, résultat électoral, événement daté…

Ne sont **pas** des prédictions : les questions rhétoriques seules, les slogans
vagues (« Nothing can stop what is coming », « Enjoy the show », « Judgement is
coming »), les affirmations sur le passé ou le présent, et ce que Q annonce de
sa propre activité de publication (« Future posts will be relayed here »).

Sont des prédictions : les prédictions implicites dont l'objet est clair
(« Goodbye, Mr. Rosenstein » posté avec un article sur son éviction), et les
annonces sans objet mais **ancrées dans le temps** (« Next week. BOOM. »),
marquées `vague`.

Champs : `event_type` dans la liste fermée ; `deadline` = date ISO si elle est
énoncée ou déductible (« next week » → dimanche de la semaine suivante ;
« this week » posté un dimanche → semaine qui commence ; « tomorrow » → J+1 en
UTC ; un mois → dernier jour du mois), sinon `null`. `deadline_type` vaut
`relative` aussi quand l'expression (« soon », « days ahead », « within the
next few months ») ne peut pas devenir une date : `deadline` reste `null`.
`specific` = qui + quoi vérifiables ; sinon `vague`. `claim` est une paraphrase
neutre en anglais (« Q claims that … will … »).

## Cas limites (exemples du jeu)

- **2252 / 2210** — « Goodbye, Mr. Rosenstein. » + lien de presse : prédiction
  implicite (resignation, specific).
- **854** — « Is the stage set for a drop of HRC … vid? » : question rhétorique,
  même si elle suggère fortement une publication → négatif. Même règle pour
  **1274** (« Ready for tomorrow? ») et **2686** (« Will action be taken by
  DOJ/FBI? 2019? »).
- **954 / 4924** — « Next week. BOOM. » / « BOOMS EN_ROUTE TOMORROW » : sans
  objet mais datés → positif, `other`, `vague`. À l'inverse, **3756**
  (« Something BIG is coming. ») n'est ancré ni dans le temps ni sur un objet → négatif.
- **4395** — Q cite un article Fox (« arrests … may be imminent ») avec
  « re_read again » : la prédiction est celle de la source, que Q reprend à son
  compte → positif.
- **780** — faux rapport DHS « future proves past », remis « as early as
  March [ ], 2018 » → positif, `disclosure`, échéance 2018-03-31 (`explicit`).
- **2416** — échéance non écrite mais déduite du contexte (midterms du
  2018-11-06) → `relative`.

## Échantillonnage (déterministe)

Base `/state/qanon.db`, table `drops`, textes vides exclus (`trim(text) != ''`).
Ids triés, regroupés par année UTC de `time`.

1. **random** (75) : `random.Random(42)`, puis pour chaque année dans l'ordre
   2017, 2018, 2019, 2020, 2022, `rng.sample(ids_de_l_annee, k)` avec
   k = 10, 30, 15, 18, 2.
2. **likely** (75) : on retire les drops déjà tirés, on garde ceux dont le texte
   correspond (insensible à la casse) à
   `\bwill\b|\bexpect\b|\bcoming\b|\bsoon\b|\bnext week\b|\b\d{1,2}/\d{1,2}\b|\bdays?\b|\bweeks?\b|\btomorrow\b|\btonight\b|\bboom\b|\barrest|\bindict|\bdeclas`,
   puis même tirage avec `random.Random(43)` et les mêmes quotas.

## Comptes

| | positifs | négatifs |
|---|---|---|
| random (75) | 6 | 69 |
| likely (75) | 21 | 54 |
| **total (150)** | **27** | **123** |

29 prédictions dans 27 drops (2416 et 4354 en ont deux chacun) : 23 `vague`,
6 `specific` ; échéance `none` 15, `relative` 13, `explicit` 1.

Par `event_type` (en nombre de prédictions) : other 11, resignation 4,
disclosure 4, indictment 3, arrest 2, declassification 2, military 1,
attack 1, election 1 ; death, legal_ruling, economic 0.

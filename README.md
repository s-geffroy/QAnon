# Les drops de Q à l'épreuve des faits / Q drops checked against the facts

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23338131.svg)](https://doi.org/10.5281/zenodo.23338131)

Étude statistique des 4 966 messages de « Q » (2017-2022), à l'origine de QAnon,
confrontés à l'actualité réelle : prédictions vérifiées une à une, tweets de Trump,
actualité mondiale (GDELT), intérêt du public, scène complotiste et /pol/.

*A statistical study of the 4,966 "Q" posts (2017–2022) behind QAnon, checked
against real-world events: predictions verified one by one, Trump's tweets, world
news (GDELT), public interest, the conspiracy scene and /pol/.*

- **Site (FR/EN)** : [s-geffroy.github.io/QAnon](https://s-geffroy.github.io/QAnon/)
  ([français](https://s-geffroy.github.io/QAnon/fr/index.html), [English](https://s-geffroy.github.io/QAnon/en/index.html))
- **Document de travail / working paper** : [en ligne](https://s-geffroy.github.io/QAnon/fr/paper.html),
  [PDF](https://s-geffroy.github.io/QAnon/data/geffroy-2026-qanon-drops-de-q-epreuve-des-faits.pdf)
- **Prédictions vérifiées / checked predictions** : [page](https://s-geffroy.github.io/QAnon/fr/predictions.html)
- **Données ouvertes / open data** : [page](https://s-geffroy.github.io/QAnon/fr/data.html)
- **Pour enseigner / teaching** : [séances prêtes](https://s-geffroy.github.io/QAnon/fr/teaching.html)
- **Citer / cite** : Geffroy, S. (2026). *Les drops de Q à l'épreuve des faits.*
  doi:[10.5281/zenodo.23338131](https://doi.org/10.5281/zenodo.23338131) (voir `CITATION.cff`) ;
  document de travail (PDF, v1.2) : doi:[10.5281/zenodo.23473751](https://doi.org/10.5281/zenodo.23473751)
- **Licences** : code MIT (`LICENSE`), contenus, données et site CC BY 4.0 (`LICENSE-CC-BY-4.0`)

La suite de ce fichier documente le worker qui calcule et publie le site.

## Le worker

Worker heberge sur le VPS multi-applications : du travail de fond, **aucune
surface HTTP**.

## Ce que fait le worker

Une etude statistique des drops de « Q » (2017-2022), confrontee a l'actualite,
publiee en site bilingue FR/EN sur GitHub Pages
(`https://s-geffroy.github.io/QAnon/`).

`cycle()` fait avancer un pipeline d'etapes reprenables (`src/qanon/stages.py`) :

| etape | role |
|---|---|
| `fetch_qdrops` | drops Kaggle `jkingsman/qanondrops` (public, sans jeton), relu chaque semaine |
| `fetch_tweets` | tweets de Trump, Kaggle `codebreaker619/donald-trump-tweets-dataset` (UTC) |
| `load_timeline` | chronologie curee `src/data/timeline.yaml` (sourcee, bilingue) |
| `analyze_descriptive` | volumes, plateformes, rythmes, silences |
| `fetch_pageviews` | pages vues Wikipedia (API Wikimedia), 15 articles, 2017-2023 |
| `analyze_trump` | test des « deltas » : coincidences drop/tweet contre deux modeles nuls |
| `analyze_discourse` | themes (NMF), mots distinctifs, formules du glossaire, style, stylometrie |
| `analyze_actors` | acteurs cites (`src/data/actors.yaml`), co-mentions, pays |
| `analyze_stats` | rythme et rafales, regimes d'activite, forums, sites cites, renvois, religion, lisibilite |
| `analyze_interest` | interet public, etude d'evenements, diffusion par langue |
| `llm_eval` | evaluation des modeles OpenAI sur `src/data/gold.jsonl` (secret `openai_api_key`) |
| `build_site` | site statique FR/EN dans `/state/site` (18 pages, donnees telechargeables) |
| `fetch_gdelt` | GDELT 1.0, un fichier par jour 2017-10 → 2021-01, agrege et reprenable (~1 h) |
| `publish_pages` | push de `gh-pages` apres chaque reconstruction (secret `github_token`) |
| `analyze_news` | Q contre l'actualite : surrepresentation, correlations decalees, Granger |

Publication : apres chaque reconstruction du site, l'etape `publish_pages`
pousse `/state/site` sur la branche `gh-pages` (un seul commit, force-push) en
HTTPS, avec un jeton GitHub « fine-grained » limite au depot (droit Contents:
Read and write) lu dans le secret `github_token`
(`/etc/app-secrets/qanon/github_token`, 0444). Le jeton n'apparait ni dans les
logs ni dans l'URL. A renouveler a son expiration ; en cas de fuite, le revoquer
sur GitHub. En secours, `scripts/publish-pages.sh` publie en SSH depuis l'hote.

Donnees editoriales versionnees dans `src/data/` : chronologie, acteurs,
glossaire, bibliographie, etat de la recherche (`research.yaml`), FAQ (`faq.yaml`),
jeu d'annotation de reference et ses consignes.

Bibliographie : la source est `src/data/bibliography.yaml` ; `src/data/bibliography.bib`
en est l'export BibTeX complet, tenu a jour (un test echoue s'il est en retard).
Le regenerer apres toute modification :
`sudo appctl run worker sh -c 'cd /app && python3 -m qanon.site.biblio' > src/data/bibliography.bib`.

Une etape est relancee quand ses entrees changent (donnees amont, code,
periode de rafraichissement) ; sinon le worker dort. Base : `/state/qanon.db`
(SQLite), resultats : `/state/results/*.json`. Une etape en echec garde son
avancement et reessaie avec un delai croissant (1 min a 1 h).

## Charpente

`src/worker.py` :

| element | role |
|---|---|
| boucle | rappelle `cycle()` toutes les `WORKER_INTERVAL` secondes |
| battement | `/tmp/heartbeat`, touche a chaque tour, lu par le healthcheck |
| arret propre | SIGTERM honore, sommeil fractionne, fin du cycle en cours |
| `/state` | volume `qanon_state`, ce qui doit survivre a un redemarrage |

## Cycle de developpement

```bash
sudo -iu qanon
cd /srv/apps/qanon
claude
```

Puis, apres modification :

```bash
tests/test_smoke.sh      # dans un conteneur jetable : cycle, battement, arret propre, pytest
tests/test_site.sh       # site genere depuis l'etat reel : graphes, JSON-LD, renvois, liens et ancres
sudo appctl validate
sudo appctl rebuild
sudo appctl status       # le conteneur doit passer 'healthy'
sudo appctl logs -f      # c'est ici qu'on voit si le travail se fait
scripts/publish-pages.sh # publie /state/site sur GitHub Pages
```

Un worker n'a pas d'URL a ouvrir : **les logs sont l'interface**. `status` dit
que la boucle tourne, `logs` dit que le travail se fait. Les deux sont
necessaires.

## Reglages

| variable | defaut | role |
|---|---|---|
| `WORKER_INTERVAL` | `60` | secondes entre deux cycles |
| `PIPELINE_CYCLE_BUDGET` | `45` | secondes de travail par cycle au plus |
| `PIPELINE_STAGES` | (toutes) | restreint les etapes executees (tests) |
| `WORKER_STATE` | `/state` | repertoire d'etat (volume persistant) |
| `WORKER_HEARTBEAT` | `/tmp/heartbeat` | fichier de battement |

Le seuil du healthcheck (180 s dans `compose.yaml`) doit rester superieur a
deux fois `WORKER_INTERVAL`.

## Exposition

`app.yaml` le declare en `none` : le conteneur ne parle qu'au reseau interne de
l'application. Pour ouvrir une page de metriques ou une sonde :

```bash
sudo /opt/infra/scripts/app-exposure.py qanon --set worker=tailnet --port worker=9100
```

`app.yaml` et les labels Traefik sont mis a jour ensemble.

## Secrets

| secret | usage |
|---|---|
| `openai_api_key` | evaluation des modeles (`llm_eval`) puis classification des predictions |

Les secrets reels vont dans `/etc/app-secrets/qanon/` (root uniquement),
jamais dans ce depot :

```bash
printf '%s\n' "<la cle>" | sudo tee /etc/app-secrets/qanon/api_key
sudo chmod 0444 /etc/app-secrets/qanon/api_key   # lisible dans le conteneur
```

et dans `compose.yaml` :

```yaml
    secrets:
      - api_key
    environment:
      API_KEY_FILE: /run/secrets/api_key

secrets:
  api_key:
    file: /etc/app-secrets/qanon/api_key
```

`0444` et non `0400` : le mode est reporte tel quel dans le conteneur, ou le
worker tourne en utilisateur non privilegie. Sur l'hote, c'est le repertoire
(0700 root) qui protege le secret.

## Licence et citation

- **Code** (`src/` hors `src/data/`, `scripts/`, `tests/`, `compose.yaml`,
  `app.yaml`) : licence MIT (`LICENSE`).
- **Contenu** (textes, donnees editoriales de `src/data/`, donnees derivees,
  graphiques, site genere) : CC BY 4.0 (`LICENSE-CC-BY-4.0`).
- **Polices** hebergees avec le site (`src/qanon/site/static/fonts/`, fichiers woff2
  variables de Google Fonts, sous-ensembles latin, latin etendu et grec) : Atkinson
  Hyperlegible Next et Source Serif 4, licence SIL OFL 1.1 (fichiers `OFL-*.txt` a cote).
- **Bibliotheques de graphiques** hebergees avec le site (`src/qanon/site/static/vendor/`) :
  vega 5.30.0, vega-lite 5.21.0 et vega-embed 6.26.0 (BSD-3-Clause), fond de carte
  world-atlas 2.0.2 (ISC), copies a l'identique de npm (empreintes verifiees) ; licences
  `LICENSE-*.txt` a cote. Le site ne fait plus aucune requete vers un tiers.

Auteur : Sylvain Geffroy. Archive Zenodo : doi:10.5281/zenodo.23338131 (toutes
versions ; v1.0.0 : doi:10.5281/zenodo.23338132) ; document de travail
(PDF, v1.2) : doi:10.5281/zenodo.23473751. `CITATION.cff` donne la reference ; chaque chiffre
cle du site a sa propre citation (page « Chiffres cles »). Les jeux de donnees
sources gardent leurs propres conditions.

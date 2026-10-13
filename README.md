# qanon

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23338131.svg)](https://doi.org/10.5281/zenodo.23338131)

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

Auteur : Sylvain Geffroy. Archive Zenodo : doi:10.5281/zenodo.23338131 (toutes
versions ; v1.0.0 : doi:10.5281/zenodo.23338132). `CITATION.cff` donne la reference ; chaque chiffre
cle du site a sa propre citation (page « Chiffres cles »). Les jeux de donnees
sources gardent leurs propres conditions.

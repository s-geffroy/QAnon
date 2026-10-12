# qanon

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
| `analyze_trump` | test des « deltas » : coincidences drop/tweet contre deux modeles nuls |
| `build_site` | site statique FR/EN dans `/state/site` |
| `publish_site` | force-push sur la branche `gh-pages` (secret `github_token`) |

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
sudo appctl validate
sudo appctl rebuild
sudo appctl status       # le conteneur doit passer 'healthy'
sudo appctl logs -f      # c'est ici qu'on voit si le travail se fait
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
| `PAGES_REPO` | `s-geffroy/QAnon` | depot cible de la publication |
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
| `github_token` | PAT fine-grained, depot `s-geffroy/QAnon` seul, *Contents: Read and write* |
| `openai_api_key` | classification des predictions (etape a venir) |

GitHub : apres le premier push de `gh-pages`, Settings → Pages → *Deploy from a
branch* → `gh-pages` / `(root)`.

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

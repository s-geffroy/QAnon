#!/usr/bin/env bash
# Test minimal, dans un conteneur jetable de l'image : le worker fait-il un
# cycle, pose-t-il son battement, et s'arrete-t-il sur SIGTERM ? Puis les tests
# unitaires. L'etat va dans /tmp du conteneur, jamais dans le volume reel.
set -euo pipefail
cd "$(dirname "$0")/.."

out=$(sudo appctl run worker sh -c '
  export WORKER_INTERVAL=1 WORKER_STATE=/tmp/state WORKER_HEARTBEAT=/tmp/beat PIPELINE_STAGES=load_timeline
  timeout --signal=TERM 4 python3 -u /app/worker.py || true
  test -f /tmp/beat         || { echo "ECHEC : pas de battement"; exit 1; }
  test -f /tmp/state/cycles || { echo "ECHEC : aucun cycle effectue"; exit 1; }
  python3 -c "import sqlite3; n = sqlite3.connect(\"/tmp/state/qanon.db\").execute(\"select count(*) from events\").fetchone()[0]; assert n > 0, n; print(\"evenements\", n)"
  cd /app && python3 -m pytest -q -p no:cacheprovider tests
' 2>&1) || { echo "$out"; echo "ECHEC"; exit 1; }
echo "$out" | grep -q "arrete"           || { echo "$out"; echo "ECHEC : arret non propre"; exit 1; }
echo "$out" | grep -qE "[0-9]+ passed"    || { echo "$out"; echo "ECHEC : tests unitaires"; exit 1; }
echo "$out" | grep -E "evenements|passed|failed"
echo "OK : cycle effectue, battement pose, arret propre, tests unitaires passes"

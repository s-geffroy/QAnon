#!/usr/bin/env bash
# Verification du site genere a partir de l'etat reel, dans un conteneur jetable :
# graphes et JSON-LD lisibles, aucun renvoi non resolu, liens internes et ancres valides.
# La base est ouverte en lecture seule ; rien n'est ecrit dans le volume.
set -euo pipefail
cd "$(dirname "$0")/.."
sudo appctl build >/dev/null
out=$(sudo appctl run worker sh -c 'cd /app && python3 tests/check_site.py' 2>&1 | grep -v "Container") \
  || { echo "$out"; echo "ECHEC : verification du site"; exit 1; }
echo "$out"
echo "OK : site verifie"

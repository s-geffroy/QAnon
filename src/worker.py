#!/usr/bin/env python3
"""
Squelette de worker : une boucle, un battement de coeur, un arret propre.

Remplacer le contenu de cycle(). Le reste est la charpente et merite d'etre
gardee : c'est elle qui rend le conteneur observable et arretable.
"""
import os
import signal
import time
from pathlib import Path

from qanon.log import log
from qanon.pipeline import Pipeline
from qanon.stages import STAGES

INTERVAL = int(os.environ.get("WORKER_INTERVAL", "30"))
HEARTBEAT = Path(os.environ.get("WORKER_HEARTBEAT", "/tmp/heartbeat"))
STATE = Path(os.environ.get("WORKER_STATE", "/state"))

# PIPELINE_STAGES : liste d'etapes a executer (toutes par defaut), pour les tests.
ONLY = {s for s in os.environ.get("PIPELINE_STAGES", "").split(",") if s}

stopping = False
pipeline = None


def on_stop(signum, _frame):
    global stopping
    stopping = True
    log(f"signal {signum} recu : arret a la fin du cycle en cours")


def cycle():
    """Le travail : un lot de chaque etape eligible du pipeline (voir qanon/stages.py)."""
    counter = STATE / "cycles"
    n = int(counter.read_text()) + 1 if counter.exists() else 1
    counter.write_text(str(n))
    r = pipeline.step(should_stop=lambda: stopping)
    if r["ran"] or r["failed"]:
        log(f"cycle {n} : {', '.join(r['ran']) or 'aucune etape terminee'}"
            f"{' ; en echec : ' + ', '.join(r['failed']) if r['failed'] else ''}"
            f" ; a jour {r['fresh']}/{r['total']}")
    elif n % 60 == 1:
        # Rien a faire : une ligne de temps en temps, pas a chaque tour.
        log(f"cycle {n} : a jour {r['fresh']}/{r['total']}"
            f"{' ; en attente : ' + ', '.join(r['waiting']) if r['waiting'] else ''}")


def main():
    signal.signal(signal.SIGTERM, on_stop)
    signal.signal(signal.SIGINT, on_stop)
    STATE.mkdir(parents=True, exist_ok=True)
    global pipeline
    pipeline = Pipeline(STAGES, STATE, only=ONLY)
    log(f"demarrage (intervalle {INTERVAL} s, etat dans {STATE})")

    while not stopping:
        try:
            cycle()
        except Exception as exc:
            # Un cycle qui echoue ne tue pas le worker : il rate son tour et
            # reessaie au suivant. Ce qui ne doit jamais etre avale, c'est le
            # message d'erreur.
            log(f"echec du cycle : {exc!r}")
        HEARTBEAT.touch()

        # Sommeil fractionne : un SIGTERM ne doit pas attendre l'intervalle
        # entier pour etre pris en compte.
        for _ in range(INTERVAL):
            if stopping:
                break
            time.sleep(1)

    log("arrete")


main()

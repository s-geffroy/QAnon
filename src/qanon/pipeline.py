"""Pipeline d'etapes reprenables.

Chaque etape est idempotente et avance par lots : un appel a `run(ctx)` fait un
lot borne, ecrit son avancement (curseur, donnees) et renvoie True quand
l'etape est terminee, False s'il reste du travail a enchainer, None si elle
attend un evenement exterieur (lot OpenAI en cours) : on repassera au
prochain cycle normal, sans enchainer. Une etape est "a jour" quand elle est terminee et que
l'empreinte de ses entrees n'a pas change depuis ; sinon elle est relancee.

L'empreinte combine : la version de l'etape, les sorties des etapes amont,
l'empreinte du code (etapes derivees) et une periode de rafraichissement
(sources distantes). Une etape dont un amont n'est pas a jour attend.
"""
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from . import db
from .log import log

APP_DIR = Path(__file__).resolve().parent.parent
CYCLE_BUDGET = int(os.environ.get("PIPELINE_CYCLE_BUDGET", "45"))


def code_fingerprint():
    files = sorted(
        p for p in APP_DIR.rglob("*")
        # .md : le document de travail (data/paper) ; sans lui, une correction du seul article ne
        # relancerait jamais la construction du site.
        if p.is_file() and p.suffix in {".py", ".html", ".css", ".js", ".yaml", ".jsonl", ".md"}
        and "__pycache__" not in p.parts and "tests" not in p.parts
    )
    return db.sha(*(f"{p.relative_to(APP_DIR)}:{db.sha(p.read_bytes())}" for p in files))


@dataclass
class Stage:
    name: str
    run: Callable
    inputs: tuple = ()
    version: str = "1"
    refresh: int = 0          # secondes ; 0 = jamais de rafraichissement periodique
    code: bool = False        # l'empreinte du code fait partie des entrees
    keep_cursor: bool = False  # une nouvelle empreinte reprend au curseur au lieu de repartir de zero
    optional: tuple = ()      # entrees prises en compte si elles existent, sans les attendre


class Ctx:
    def __init__(self, conn, state, stage, deadline, should_stop):
        self.conn = conn
        self.state = state
        self.stage = stage
        self.deadline = deadline
        self._should_stop = should_stop
        self.results = state / "results"
        self.results.mkdir(exist_ok=True)

    def time_left(self):
        return self.deadline - time.monotonic()

    def should_yield(self):
        """Vrai quand le lot doit s'arreter : budget du cycle epuise ou SIGTERM."""
        return self.time_left() <= 0 or self._should_stop()

    @property
    def cursor(self):
        row = self.conn.execute("SELECT cursor FROM stages WHERE name = ?", (self.stage.name,)).fetchone()
        return row["cursor"] if row else None

    def save_cursor(self, value):
        """Ecrit l'avancement et valide la transaction en cours avec lui."""
        self.conn.execute("UPDATE stages SET cursor = ?, updated_at = ? WHERE name = ?",
                          (value, int(time.time()), self.stage.name))
        self.conn.commit()

    def set_output(self, value):
        """Empreinte de la sortie de l'etape : c'est elle que voient les etapes aval."""
        db.set_meta(self.conn, f"out:{self.stage.name}", value)


class Pipeline:
    def __init__(self, stages, state, only=None):
        self.stages = [s for s in stages if not only or s.name in only]
        self.state = Path(state)
        self.state.mkdir(parents=True, exist_ok=True)
        self.code = code_fingerprint()
        # Un (re)demarrage est une nouvelle tentative deliberee (secret ajoute,
        # correctif deploye) : les delais d'attente apres echec sont remis a zero.
        conn = db.connect(self.state / "qanon.db")
        conn.execute("UPDATE stages SET retry_at = 0")
        conn.commit()
        conn.close()

    def fingerprint(self, conn, stage, now):
        parts = [stage.version]
        parts += [db.get_meta(conn, f"out:{name}", "") for name in stage.inputs + stage.optional]
        if stage.code:
            parts.append(self.code)
        if stage.refresh:
            parts.append(int(now // stage.refresh))
        return db.sha(*parts)

    def _done_elsewhere(self, conn, name):
        """Entree produite par une etape hors de la selection (PIPELINE_STAGES) :
        on se fie a son dernier etat enregistre."""
        if any(s.name == name for s in self.stages):
            return False
        row = conn.execute("SELECT done FROM stages WHERE name = ?", (name,)).fetchone()
        return bool(row and row["done"])

    def step(self, should_stop=lambda: False):
        """Un cycle : fait avancer d'un lot chaque etape eligible. Renvoie un resume."""
        conn = db.connect(self.state / "qanon.db")
        try:
            return self._step(conn, should_stop)
        finally:
            conn.close()

    def _step(self, conn, should_stop):
        now = time.time()
        deadline = time.monotonic() + CYCLE_BUDGET
        fresh, ran, waiting, failed = set(), [], [], []
        busy = False
        for stage in self.stages:
            if should_stop() or time.monotonic() >= deadline:
                waiting.append(stage.name)
                continue
            fp = self.fingerprint(conn, stage, now)
            row = conn.execute("SELECT * FROM stages WHERE name = ?", (stage.name,)).fetchone()
            if row and row["done"] and row["fingerprint"] == fp:
                fresh.add(stage.name)
                continue
            if any(name not in fresh and not self._done_elsewhere(conn, name) for name in stage.inputs):
                waiting.append(stage.name)
                continue
            if row and row["retry_at"] > now:
                waiting.append(stage.name)
                continue
            if not row:
                conn.execute("INSERT INTO stages(name, fingerprint, done) VALUES(?, ?, 0)", (stage.name, fp))
            elif row["fingerprint"] != fp:
                cursor = row["cursor"] if stage.keep_cursor else None
                conn.execute("UPDATE stages SET fingerprint = ?, done = 0, cursor = ? WHERE name = ?",
                             (fp, cursor, stage.name))
            conn.commit()

            ctx = Ctx(conn, self.state, stage, deadline, should_stop)
            t0 = time.monotonic()
            try:
                result = stage.run(ctx)
                finished = result is True
            except Exception as exc:
                conn.rollback()
                failures = (row["failures"] if row else 0) + 1
                delay = min(60 * 2 ** (failures - 1), 3600)
                conn.execute("UPDATE stages SET failures = ?, retry_at = ?, last_error = ?, updated_at = ? "
                             "WHERE name = ?", (failures, int(now + delay), repr(exc)[:500], int(now), stage.name))
                conn.commit()
                log(f"etape {stage.name} : echec ({failures}e, nouvel essai dans {delay} s) : {exc!r}")
                failed.append(stage.name)
                continue
            conn.execute("UPDATE stages SET done = ?, failures = 0, retry_at = 0, last_error = NULL, "
                         "updated_at = ? WHERE name = ?", (int(finished), int(time.time()), stage.name))
            conn.commit()
            ran.append(f"{stage.name}{'' if finished else '…'} {time.monotonic() - t0:.1f}s")
            if finished:
                fresh.add(stage.name)
            elif result is False:
                busy = True
        return {"busy": busy, "ran": ran, "waiting": waiting, "failed": failed,
                "fresh": len(fresh), "total": len(self.stages)}

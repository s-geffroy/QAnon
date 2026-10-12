import numpy as np

from qanon import db
from qanon.analysis.trump import within
from qanon.pipeline import Pipeline, Stage
from qanon.site import fmt


def make(calls, fail=None):
    def counter(ctx):
        n = int(ctx.cursor or 0) + 1
        ctx.save_cursor(str(n))
        calls.append(("counter", n))
        if fail and fail(n):
            raise RuntimeError("panne")
        if n >= 3:
            ctx.set_output("c3")
            return True
        return False

    def derived(ctx):
        calls.append(("derived",))
        ctx.set_output("d")
        return True

    return [Stage("counter", counter), Stage("derived", derived, inputs=("counter",))]


def test_batches_resume_and_dependencies(tmp_path):
    calls = []
    Pipeline(make(calls), tmp_path).step()
    assert calls == [("counter", 1)]          # l'aval attend que l'amont soit termine
    # Un nouveau Pipeline (= redemarrage du conteneur) reprend au curseur.
    Pipeline(make(calls), tmp_path).step()
    Pipeline(make(calls), tmp_path).step()
    assert calls[-2:] == [("counter", 3), ("derived",)]
    calls.clear()
    Pipeline(make(calls), tmp_path).step()
    assert calls == []                        # tout est a jour


def test_failure_keeps_progress_and_backs_off(tmp_path):
    calls = []
    p = Pipeline(make(calls, fail=lambda n: n == 1), tmp_path)
    r = p.step()
    assert r["failed"] == ["counter"]
    conn = db.connect(tmp_path / "qanon.db")
    row = conn.execute("SELECT * FROM stages WHERE name='counter'").fetchone()
    assert row["failures"] == 1 and row["retry_at"] > 0 and "panne" in row["last_error"]
    calls.clear()
    p.step()
    assert calls == []                        # meme processus : en attente du delai
    Pipeline(make(calls), tmp_path).step()
    assert calls == [("counter", 2)]          # redemarrage : nouvel essai immediat, curseur garde


def test_waiting_stage_is_not_busy(tmp_path):
    r = Pipeline([Stage("wait", lambda ctx: None)], tmp_path).step()
    assert r["busy"] is False and r["ran"] and r["fresh"] == 0


def test_within_windows():
    tweets = np.array([100, 1000])
    drops = np.array([40, 990, 5000])
    assert within(drops, tweets, 60) == 2 / 3     # 40 -> 100 et 990 -> 1000
    assert within(drops, tweets, 10) == 1 / 3     # seul 990 -> 1000
    assert within(drops, tweets, 10, after=False) == 0


def test_formats():
    assert fmt.num("fr", 12345.6, 1) == "12 345,6"
    assert fmt.pct("en", 0.123) == "12.3%"
    assert fmt.date("fr", "2017-10-28") == "28 oct. 2017"
    assert fmt.date("en", "2020-12-08T10:00:00+00:00") == "Dec 8, 2020"

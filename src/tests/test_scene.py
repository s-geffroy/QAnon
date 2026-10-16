"""Outils de l'analyse de la scene : chaque estimateur retrouve ce qu'on a mis
dans des donnees synthetiques."""
import numpy as np

from qanon.analysis import scene


def test_transfer_entropy_direction():
    rng = np.random.default_rng(1)
    x = rng.normal(size=3000)
    y = np.roll(x, 2) * 0.8 + rng.normal(size=3000) * 0.6
    xd, yd = scene.tercile(x), scene.tercile(y)
    assert scene.transfer_entropy(xd, yd, 2) > 0.1
    assert scene.transfer_entropy(yd, xd, 2) < 0.02
    te, lag = scene.te_max(x, yd)
    assert lag == 2


def test_iaaft_keeps_distribution_and_spectrum():
    rng = np.random.default_rng(2)
    x = np.cumsum(rng.normal(size=1024))
    s = scene.iaaft(x, rng)
    assert np.allclose(np.sort(s), np.sort(x))
    a, b = np.abs(np.fft.rfft(x)), np.abs(np.fft.rfft(s))
    assert np.corrcoef(a, b)[0, 1] > 0.95
    assert abs(np.corrcoef(x, s)[0, 1]) < 0.9


def test_bh():
    adj = scene.bh([0.01, 0.04, 0.03, 0.5])
    assert np.allclose(adj, [0.04, 0.0533333, 0.0533333, 0.5], atol=1e-4)


def test_ccf_sign_convention():
    rng = np.random.default_rng(3)
    a = rng.normal(size=400)
    b = np.roll(a, 3) + rng.normal(size=400) * 0.3     # a precede b de 3
    lags = list(range(-5, 6))
    c = scene.ccf(a, b, lags)
    assert lags[int(np.argmax(c))] == 3


def test_bass_fit_recovers_parameters():
    t = np.arange(61)
    y = 5000 * np.diff(scene.bass_F(t, 0.02, 0.35))
    r = scene.bass_fit(y)
    assert abs(r["p"] - 0.02) < 0.005 and abs(r["q"] - 0.35) < 0.05 and r["r2"] > 0.99


def test_endo_exo_classes():
    k = np.arange(1, 200)
    base = np.full(400, 100.0)
    exo = base.copy()
    exo[200] = 5100
    exo[201:400] += 5000 * k[:199] ** -0.8
    r = scene.endo_exo(exo, 200)
    assert r["class"] == "exogene" and abs(r["decay_exponent"] - 0.8) < 0.15
    endo = base.copy()
    d = np.abs(np.arange(400) - 200) + 1.0
    endo += 5000 * d ** -0.4
    r = scene.endo_exo(endo, 200)
    assert r["class"] == "endogene"


def test_weekly_rhythm_alone_gives_no_transfer():
    """Deux series independantes au meme rythme hebdomadaire : sans retrait de la
    saisonnalite, un faux lien apparaissait au retard 7."""
    import pandas as pd
    rng = np.random.default_rng(4)
    days = pd.date_range("2018-01-01", periods=1100).strftime("%Y-%m-%d")
    week = np.tile([5, 5, 5, 5, 5, 1, 1], 200)[:1100]
    x = rng.poisson(week * 20)
    y = rng.poisson(week * 30)
    xc, yc = scene.deseason(x, days), scene.deseason(y, days)
    te, _ = scene.te_max(xc, scene.tercile(yc))
    null = [scene.te_max(scene.iaaft(xc, rng), scene.tercile(yc))[0] for _ in range(100)]
    assert sum(v >= te for v in null) > 5


def test_endo_exo_level_shift():
    v = np.concatenate([np.full(200, 100.0), [3000.0], np.full(199, 2500.0)])
    assert scene.endo_exo(v, 200)["class"] == "palier"


def test_trends_stitching(tmp_path):
    import pandas as pd
    from qanon import db
    from qanon.sources.trends import ANCHOR, WINDOWS
    conn = db.connect(tmp_path / "t.db")
    w1 = pd.date_range("2016-01-03", "2020-12-27", freq="7D").strftime("%Y-%m-%d")
    w2 = pd.date_range("2018-12-30", "2023-12-31", freq="7D").strftime("%Y-%m-%d")
    mo = pd.date_range("2016-01-01", "2023-12-01", freq="MS").strftime("%Y-%m-%d")
    rows = [("solo:x", WINDOWS[0], "x", d, 50, 0) for d in w1]
    rows += [("solo:x", WINDOWS[1], "x", d, 100, 0) for d in w2]          # renormalise par Google
    rows += [("solo:x", WINDOWS[2], "x", d, 80, 0) for d in mo]
    rows += [("anchor:x", WINDOWS[2], q, d, v, 0) for d in mo for q, v in (("x", 5), (ANCHOR, 50))]
    rows += [("solo:rare", w, "rare", d, 100 if i == 3 else 0, 0)
             for w, ds in ((WINDOWS[0], w1), (WINDOWS[1], w2), (WINDOWS[2], mo)) for i, d in enumerate(ds)]
    rows += [("anchor:rare", WINDOWS[2], q, d, v, 0) for d in mo for q, v in (("rare", 0), (ANCHOR, 50))]
    conn.executemany("INSERT INTO trends_raw VALUES (?,?,?,?,?,?)", rows)
    weekly_s, monthly_s, no_level = scene.trends_series(conn)
    assert np.allclose(monthly_s["x"].to_numpy(), 0.1)          # 5 / 50 : niveau de l'ancre
    assert np.allclose(weekly_s["x"].to_numpy(), 0.1)           # recolle puis mis au meme niveau
    assert weekly_s["x"].index[0] == "2016-01-04"               # dimanche -> lundi
    assert no_level == {"rare"} and monthly_s["rare"].max() == 1.0


def test_trends_resumes_from_data_and_backs_off(tmp_path, monkeypatch):
    from qanon import db
    from qanon.sources import trends
    import pandas as pd
    conn = db.connect(tmp_path / "t.db")

    class Ctx:
        def __init__(self):
            self.conn, self.out = conn, None
        def should_yield(self):
            return False
        def set_output(self, v):
            self.out = v

    monkeypatch.setattr(trends, "queries", lambda: ["a", "b"])
    monkeypatch.setattr(trends, "PAUSE", 0)
    calls = []

    def fake(batch, window):
        calls.append((tuple(batch), window))
        if len(calls) == 3:
            raise RuntimeError("429")
        return pd.DataFrame({q: [10] for q in batch}, index=pd.to_datetime(["2018-01-07"]))
    monkeypatch.setattr(trends, "fetch", fake)
    assert trends.run(Ctx()) is None and len(calls) == 3          # 2 lots acquis, puis refus
    assert trends.run(Ctx()) is None and len(calls) == 3          # suspendu : aucune requete
    db.set_meta(conn, "trends_blocked_until", 0)
    assert trends.run(Ctx()) is True and len(calls) == 3 + 6      # 8 lots : reprend aux 6 manquants


def test_review_holds_while_publication_is_held(tmp_path, monkeypatch):
    """PUBLISH_HOLD : un texte modifie n'est soumis ni a l'audit ni a la revue payante."""
    from qanon import db, review
    from qanon.site import build
    conn = db.connect(tmp_path / "t.db")

    class Ctx:
        state, out = tmp_path, None
        def __init__(self):
            self.conn = conn
        def should_yield(self):
            return False
        def set_output(self, v):
            self.out = v

    class NoNetwork:
        def __getattr__(self, name):
            raise AssertionError(f"appel reseau pendant la suspension : {name}")

    monkeypatch.setattr(build, "Site", lambda state, conn: None)
    monkeypatch.setattr(review, "texts", lambda site: {"paper": "texte modifie"})
    monkeypatch.setattr(review.requests, "Session", NoNetwork)
    monkeypatch.setenv("PUBLISH_HOLD", "1")
    assert review.run(Ctx()) is None
    assert db.get_meta(conn, "review_hold_logged") == "1"
    assert conn.execute("SELECT count(*) FROM editorial_review").fetchone()[0] == 0


def test_review_waits_while_reviewer_is_stopped(tmp_path, monkeypatch):
    """Application Reviewer arretee : l'etape attend (None), sans echec ni soumission, journalise
    l'arret une fois et ne reinterroge /health qu'apres DOWN_RECHECK."""
    from qanon import db, review
    from qanon.site import build
    conn = db.connect(tmp_path / "t.db")
    calls = []

    class Ctx:
        state, out = tmp_path, None
        def __init__(self):
            self.conn = conn
        def should_yield(self):
            return False
        def set_output(self, v):
            self.out = v

    class Resp:
        status_code = 404

    class Down:
        def get(self, url, **kw):
            calls.append(url)
            return Resp()
        def post(self, url, **kw):
            raise AssertionError(f"soumission alors que l'API est arretee : {url}")

    monkeypatch.setattr(build, "Site", lambda state, conn: None)
    monkeypatch.setattr(review, "texts", lambda site: {"paper": "texte modifie"})
    monkeypatch.setattr(review.requests, "Session", Down)
    monkeypatch.delenv("PUBLISH_HOLD", raising=False)
    assert review.run(Ctx()) is None
    assert db.get_meta(conn, "review_api_down") == "1"
    assert calls == [f"{review.API}/health"]
    assert review.run(Ctx()) is None          # dans les 30 min : aucun appel
    assert len(calls) == 1
    assert conn.execute("SELECT count(*) FROM editorial_review").fetchone()[0] == 0

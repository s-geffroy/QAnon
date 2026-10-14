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
    from qanon import db
    from qanon.sources.trends import ANCHOR, WINDOWS
    conn = db.connect(tmp_path / "t.db")
    rows = []
    w1 = __import__("pandas").date_range("2016-01-03", "2020-12-27", freq="7D").strftime("%Y-%m-%d")
    w2 = __import__("pandas").date_range("2018-12-30", "2023-12-31", freq="7D").strftime("%Y-%m-%d")
    for d in w1:
        rows += [("b", WINDOWS[0], "x", d, 20, 0), ("b", WINDOWS[0], ANCHOR, d, 10, 0)]
    for d in w2:   # meme interet, mais Google a renormalise : tout est double
        rows += [("b", WINDOWS[1], "x", d, 40, 0), ("b", WINDOWS[1], ANCHOR, d, 20, 0)]
    conn.executemany("INSERT INTO trends_raw VALUES (?,?,?,?,?,?)", rows)
    weekly_s, monthly_s = scene.trends_series(conn)
    s = weekly_s["x"]
    assert np.allclose(s.to_numpy(), 2.0)          # 20 / 10, et 40 / 20 apres recollage
    assert s.index[0] == "2016-01-04"              # dimanche -> lundi

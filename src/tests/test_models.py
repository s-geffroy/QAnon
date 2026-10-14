"""Modeles de Markov et analogies physiques : chaque estimateur doit retrouver ce
qu'on a mis dans des donnees synthetiques."""
import numpy as np

from qanon.analysis import markov, physics


def test_hmm_recovers_two_regimes():
    rng = np.random.default_rng(1)
    states = np.repeat([0, 1, 0, 1, 0], 120)
    y = rng.poisson(np.where(states == 1, 12.0, 0.5))
    fits = [markov.hmm_fit(y, k) for k in (1, 2, 3)]
    assert markov.hmm_fit(y, 2, dist="poisson")["r"] is None
    best = min(fits, key=lambda f: f["bic"])
    assert best["K"] in (2, 3)
    two = fits[1]
    assert abs(two["lam"][0] - 0.5) < 0.2 and abs(two["lam"][1] - 12) < 1
    path = markov.viterbi(y, two["pi"], two["A"], two["lam"], two["r"])
    assert (path == states).mean() > 0.97


def test_nb_hmm_absorbs_overdispersion():
    """Comptes surdisperses en deux regimes : le HMM binomial negatif s'arrete a 2 etats,
    le HMM de Poisson en reclame davantage."""
    rng = np.random.default_rng(8)
    states = np.repeat([0, 1, 0, 1, 0, 1], 150)
    mean = np.where(states == 1, 15.0, 1.0)
    y = rng.negative_binomial(1.5, 1.5 / (1.5 + mean))
    nb = min((markov.hmm_fit(y, k) for k in (1, 2, 3, 4)), key=lambda f: f["bic"])
    po = min((markov.hmm_fit(y, k, dist="poisson") for k in (1, 2, 3, 4)), key=lambda f: f["bic"])
    assert nb["K"] == 2 and po["K"] > 2


def test_topic_chain_detects_persistence():
    rng = np.random.default_rng(2)
    sid, topic = [], []
    for s in range(400):
        t = rng.integers(4)
        for _ in range(4):
            # Meme theme que le precedent 70 % du temps, sinon tirage uniforme.
            t = t if rng.random() < 0.7 else rng.integers(4)
            sid.append(s)
            topic.append(t)
    r = markov.topic_chain(np.array(sid), np.array(topic), 4, list("abcd"), n_perm=99)
    assert r["diag_share"] > r["null_global"]["diag_mean"] + 0.2
    assert r["null_global"]["p_diag"] <= 0.01
    assert r["entropy_rate_bits"] < r["entropy_iid_bits"]


def test_char_markov_periodic_is_predictable():
    rng = np.random.default_rng(3)
    periodic = "abcdefg " * 400
    noise = "".join(rng.choice(list("abcdefgh "), 3200))
    assert markov.CharMarkov(periodic).bits_per_char(periodic[:500]) < 0.5
    assert markov.CharMarkov(noise[:2700]).bits_per_char(noise[2700:]) > 2.5


def _simulate_hawkes(mu, n, beta, T, rng):
    """Simulation par branchement : immigrants de Poisson, chacun ayant Poisson(n)
    descendants a des delais Exp(beta), recursivement."""
    gen = list(rng.uniform(0, T, rng.poisson(mu * T)))
    out = []
    while gen:
        out += gen
        kids = []
        for t in gen:
            kids += list(t + rng.exponential(1 / beta, rng.poisson(n)))
        gen = [k for k in kids if k < T]
    return np.sort(np.array(out))


def test_hawkes_em_recovers_branching_ratio():
    rng = np.random.default_rng(4)
    T = 4000.0
    t = _simulate_hawkes(0.2, 0.5, 2.0, T, rng)
    base = physics.Baseline(0.0, T, [], np.ones(24), lambda x: np.zeros_like(np.asarray(x, dtype=float)))
    fit = physics.hawkes_em(t, base, physics.Kernel("exp"))
    assert abs(fit["branching_ratio"] - 0.5) < 0.1
    assert abs(fit["kernel"]["decay_per_hour"] - 2.0) < 0.5
    poisson = physics.hawkes_em(t, base, physics.Kernel("exp"), fit_self=False)
    assert fit["aic"] < poisson["aic"]


def test_pairs_lags():
    t = np.array([0.0, 1.0, 2.5, 10.0])
    p = physics.Pairs(t, window=3.0)
    assert sorted(zip(p.rows.tolist(), np.round(p.lags, 6).tolist())) == [(1, 1.0), (2, 1.5), (2, 2.5)]
    assert p.older.tolist() == [0, 0, 0, 3]


def test_dfa_white_noise_and_walk():
    rng = np.random.default_rng(5)
    x = rng.normal(size=8000)
    assert abs(physics.dfa(x)[0] - 0.5) < 0.08
    assert abs(physics.dfa(np.cumsum(x))[0] - 1.5) < 0.1


def test_powerlaw_fit_recovers_alpha():
    rng = np.random.default_rng(6)
    x = np.floor(5 * (1 - rng.random(4000)) ** (-1 / 1.5) + 0.5)   # alpha = 2.5, xmin = 5
    xm, a, _ = physics.powerlaw_fit(x)
    assert abs(a - 2.5) < 0.2 and 3 <= xm <= 8
    xc = 2.0 * (1 - rng.random(4000)) ** (-1 / 1.2)
    xm, a, _ = physics.powerlaw_fit(xc, discrete=False)
    assert abs(a - 2.2) < 0.15


def test_phase_split_finds_shift():
    rng = np.random.default_rng(7)
    hours = np.concatenate([rng.normal(21, 2, 600), rng.normal(16, 2, 600)]) % 24
    days = np.repeat(np.arange(400), 3)
    r = physics.phase_split(hours, days, n_perm=50)
    assert abs(r["index"] - 600) <= 30 and r["p"] < 0.05
    assert abs(r["before_peak"] - 21) < 0.5 and abs(r["after_peak"] - 16) < 0.5


def test_run_parts_resumes(tmp_path):
    from qanon.analysis.common import run_parts

    class Ctx:
        results = tmp_path
        cursor = None
        calls = 0

        def save_cursor(self, v):
            self.cursor = v

        def should_yield(self):
            return True   # budget epuise : une partie par appel

    ctx, seen = Ctx(), []
    parts = [(k, (lambda k=k: seen.append(k) or k.upper())) for k in "abc"]
    assert run_parts(ctx, "x", parts) is None and seen == ["a"]
    assert run_parts(ctx, "x", parts) is None and seen == ["a", "b"]
    assert run_parts(ctx, "x", parts) == {"a": "A", "b": "B", "c": "C"} and seen == ["a", "b", "c"]
    assert not (tmp_path / ".x.parts.json").exists()

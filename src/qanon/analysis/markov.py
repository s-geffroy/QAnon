"""Chaines de Markov sur le corpus.

- Regimes caches de l'activite : HMM sur les comptes journaliers (Baum-Welch),
  emissions binomiales negatives (les comptes sont surdisperses : avec des
  emissions de Poisson, le BIC reclame toujours plus d'etats), nombre d'etats
  choisi par BIC, chemin de Viterbi.
- Enchainement des themes : le theme d'un drop predit-il celui du suivant dans
  la meme session ? Matrice de transition, taux d'entropie, deux modeles nuls
  par permutation (melange global, melange au sein de chaque session).
- Compression : entropie croisee par compression lzma (Benedetto, Caglioti &
  Loreto 2002) entre Q par semestre et les tweets de Trump, et derive du style
  mesuree par un modele de Markov de caracteres d'ordre 3.
"""
import lzma
from collections import Counter

import numpy as np
import pandas as pd
from scipy import optimize
from scipy import stats as sps
from scipy.cluster.hierarchy import leaves_list, linkage
from scipy.spatial.distance import squareform

from .. import db
from ..log import log
from .common import ET, clean, load_drops, load_tweets, run_parts, write
from .discourse import topic_model
from .stats import SESSION_GAP_MIN

SEED = 20171028      # premier drop
N_PERM = 1000
K_MAX = 5
END_TWEETS = 1610064000  # 2021-01-08 : suspension du compte @realDonaldTrump


# ------------------------------------------------------------------ HMM de Poisson
def daily_counts(ts):
    """Comptes par jour (heure de New York), jours sans drop compris."""
    day = ts.dt.tz_convert(ET).dt.tz_localize(None).dt.normalize()
    c = day.value_counts().sort_index()
    return c.reindex(pd.date_range(c.index.min(), c.index.max(), freq="D"), fill_value=0)


def _logpmf(y, lam, r=None):
    """log P(y | moyenne lam, dispersion r) : binomiale negative (variance lam + lam^2 / r),
    Poisson si r est None."""
    if r is None:
        return sps.poisson.logpmf(y, lam)
    return sps.nbinom.logpmf(y, r, r / (r + lam))


def _emissions(y, lam, r=None):
    """log P(y_t | etat k), puis exp normalise par ligne (evite le soupassement)."""
    logb = _logpmf(y[:, None], lam[None, :], None if r is None else r[None, :])
    m = logb.max(axis=1, keepdims=True)
    return np.exp(logb - m), m.ravel(), logb


def _forward_backward(y, pi, A, lam, r=None):
    B, m, _ = _emissions(y, lam, r)
    T, K = B.shape
    alpha, c = np.empty((T, K)), np.empty(T)
    a = pi * B[0]
    c[0] = a.sum()
    alpha[0] = a / c[0]
    for t in range(1, T):
        a = (alpha[t - 1] @ A) * B[t]
        c[t] = a.sum()
        alpha[t] = a / c[t]
    beta = np.empty((T, K))
    beta[-1] = 1.0
    for t in range(T - 2, -1, -1):
        beta[t] = A @ (B[t + 1] * beta[t + 1]) / c[t + 1]
    ll = float(np.log(c).sum() + m.sum())
    return alpha, beta, c, B, ll


def hmm_fit(y, K, n_iter=300, tol=1e-7, inits=3, dist="nb"):
    """Baum-Welch d'un HMM a K etats (emissions 'nb' ou 'poisson') ; meilleure de
    plusieurs initialisations."""
    y = np.asarray(y, dtype=float)
    best = None
    for r in range(inits):
        # Initialisations deterministes : quantiles des comptes, puis echelles log.
        if r == 0:
            lam = np.quantile(y, np.linspace(0.2, 0.97, K))
        elif r == 1:
            lam = np.geomspace(0.05, max(y.max(), 1.0) * 0.6, K)
        else:
            lam = np.linspace(0.05, max(y.mean() * 3, 1.0), K)
        lam = np.maximum(lam, 0.02) + np.arange(K) * 0.05
        A = np.full((K, K), 0.1 / max(K - 1, 1))
        np.fill_diagonal(A, 0.9)
        pi = np.full(K, 1 / K)
        r = np.full(K, 2.0) if dist == "nb" else None
        prev = -np.inf
        for _ in range(n_iter):
            alpha, beta, c, B, ll = _forward_backward(y, pi, A, lam, r)
            gamma = alpha * beta
            gamma /= gamma.sum(axis=1, keepdims=True)
            xi = A * (alpha[:-1].T @ (B[1:] * beta[1:] / c[1:, None]))
            pi = gamma[0] + 1e-12
            pi /= pi.sum()
            A = xi / xi.sum(axis=1, keepdims=True)
            lam = np.maximum((gamma * y[:, None]).sum(axis=0) / gamma.sum(axis=0), 1e-6)
            if r is not None:
                # Dispersion de chaque etat : vraisemblance ponderee, moyenne fixee (EM generalise).
                for k in range(K):
                    f = lambda lr: -(gamma[:, k] * _logpmf(y, lam[k], np.exp(lr))).sum()
                    r[k] = np.exp(optimize.minimize_scalar(f, bounds=(np.log(0.05), np.log(1e4)),
                                                           method="bounded").x)
            if ll - prev < tol * abs(ll):
                break
            prev = ll
        if best is None or ll > best["ll"]:
            best = {"ll": ll, "pi": pi, "A": A, "lam": lam, "r": r}
    # Etats ordonnes par intensite croissante.
    o = np.argsort(best["lam"])
    best = {"ll": best["ll"], "pi": best["pi"][o], "A": best["A"][np.ix_(o, o)], "lam": best["lam"][o],
            "r": None if best["r"] is None else best["r"][o], "dist": dist}
    n_par = K * (2 if dist == "nb" else 1) + K * (K - 1) + (K - 1)
    best["bic"] = -2 * best["ll"] + n_par * np.log(len(y))
    best["K"] = K
    return best


def viterbi(y, pi, A, lam, r=None):
    _, _, logb = _emissions(np.asarray(y, dtype=float), lam, r)
    T, K = logb.shape
    la = np.log(A + 1e-300)
    delta = np.log(pi + 1e-300) + logb[0]
    back = np.zeros((T, K), dtype=int)
    for t in range(1, T):
        s = delta[:, None] + la
        back[t] = s.argmax(axis=0)
        delta = s.max(axis=0) + logb[t]
    path = np.empty(T, dtype=int)
    path[-1] = delta.argmax()
    for t in range(T - 1, 0, -1):
        path[t - 1] = back[t, path[t]]
    return path


def runs(dates, path):
    """Segments consecutifs d'un meme etat."""
    out, start = [], 0
    for t in range(1, len(path) + 1):
        if t == len(path) or path[t] != path[start]:
            out.append({"start": dates[start].date().isoformat(), "end": dates[t - 1].date().isoformat(),
                        "days": t - start, "state": int(path[start])})
            start = t
    return out


def hmm_summary(c, fits, changepoints=None):
    best = min(fits, key=lambda f: f["bic"])
    y = c.to_numpy()
    path = viterbi(y, best["pi"], best["A"], best["lam"], best["r"])
    A = best["A"]
    w, v = np.linalg.eig(A.T)
    stat = np.real(v[:, np.argmin(np.abs(w - 1))])
    stat = stat / stat.sum()
    seg = runs(c.index, path)
    long_switches = [pd.Timestamp(s["start"]) for s in seg[1:] if s["days"] >= 14]
    near = []
    for cp in (changepoints or {}).get("segments", [])[1:]:
        start = pd.Timestamp(cp["start"])
        dist = min((abs((x - start).days) for x in long_switches), default=None)
        near.append({"changepoint": cp["start"], "nearest_hmm_switch_days": dist})
    states = []
    for k in range(best["K"]):
        mask = path == k
        disp = None if best["r"] is None else float(best["r"][k])
        states.append({"state": k, "rate_per_day": round(float(best["lam"][k]), 3),
                       "dispersion_r": None if disp is None else round(disp, 3),
                       "var_to_mean": round(1 + float(best["lam"][k]) / disp, 2) if disp else 1.0,
                       "stationary": round(float(stat[k]), 4),
                       "share_days": round(float(mask.mean()), 4),
                       "share_drops": round(float(y[mask].sum() / max(y.sum(), 1)), 4),
                       "mean_dwell_days": round(float(1 / max(1 - A[k, k], 1e-9)), 1)})
    return {
        "n_days": int(len(y)), "start": c.index[0].date().isoformat(), "end": c.index[-1].date().isoformat(),
        "K": best["K"], "emission": best["dist"],
        "bic": [{"K": f["K"], "bic": round(float(f["bic"]), 1), "ll": round(float(f["ll"]), 1)} for f in fits],
        "states": states, "transition": [[round(float(x), 4) for x in row] for row in A],
        "series": [{"date": d.date().isoformat(), "n": int(n), "state": int(s)}
                   for d, n, s in zip(c.index, y, path)],
        "runs": [r for r in seg if r["days"] >= 7],
        "n_switches": int(len(seg) - 1), "changepoint_agreement": near,
    }


# ------------------------------------------------------------------ chaine de themes
def sessions(t_sec, gap_min=SESSION_GAP_MIN):
    return np.cumsum(np.concatenate([[True], np.diff(t_sec) > gap_min * 60]))


def _transition_counts(a, b, K):
    return np.bincount(a * K + b, minlength=K * K).reshape(K, K)


def _entropy_rate(C):
    C = np.asarray(C, dtype=float)
    rows = C.sum(axis=1)
    P = C / np.maximum(rows[:, None], 1e-12)
    with np.errstate(divide="ignore", invalid="ignore"):
        h = -np.nansum(np.where(P > 0, P * np.log2(P), 0), axis=1)
    return float((rows / rows.sum() * h).sum())


def _shuffle_within(groups, rng):
    """Permutation des positions au sein de chaque groupe (vectorisee)."""
    return np.lexsort((rng.random(len(groups)), groups))


def topic_chain(sid, topic, K, labels, n_perm=N_PERM, seed=SEED):
    """sid, topic : drops ordonnes dans le temps (drops sans theme exclus)."""
    rng = np.random.default_rng(seed)
    same = sid[1:] == sid[:-1]
    ia, ib = np.nonzero(same)[0], np.nonzero(same)[0] + 1
    C = _transition_counts(topic[ia], topic[ib], K)
    n_pairs = int(C.sum())
    p = np.bincount(topic, minlength=K) / len(topic)
    h0 = float(-(p[p > 0] * np.log2(p[p > 0])).sum())
    h1 = _entropy_rate(C)
    diag = float(np.trace(C) / n_pairs)
    null = {"global": [], "session": []}
    acc_session = np.zeros((K, K))
    for _ in range(n_perm):
        g = topic[rng.permutation(len(topic))]
        Cg = _transition_counts(g[ia], g[ib], K)
        s = topic[_shuffle_within(sid, rng)]
        Cs = _transition_counts(s[ia], s[ib], K)
        acc_session += Cs
        null["global"].append((np.trace(Cg) / n_pairs, _entropy_rate(Cg)))
        null["session"].append((np.trace(Cs) / n_pairs, _entropy_rate(Cs)))
    E = acc_session / n_perm

    def test(key):
        arr = np.array(null[key])
        return {"diag_mean": round(float(arr[:, 0].mean()), 4),
                "p_diag": round(float((1 + (arr[:, 0] >= diag).sum()) / (n_perm + 1)), 4),
                "entropy_rate_mean": round(float(arr[:, 1].mean()), 4),
                "p_entropy": round(float((1 + (arr[:, 1] <= h1).sum()) / (n_perm + 1)), 4)}

    # G-test d'independance (indicatif : les paires d'une meme session ne sont pas independantes).
    with np.errstate(divide="ignore", invalid="ignore"):
        Eind = np.outer(C.sum(1), C.sum(0)) / n_pairs
        G = 2 * np.nansum(np.where(C > 0, C * np.log(C / Eind), 0))
    lift = []
    for i in range(K):
        for j in range(K):
            if C[i, j] >= 10 and E[i, j] > 0:
                lift.append({"from": i, "to": j, "n": int(C[i, j]), "expected": round(float(E[i, j]), 1),
                             "lift": round(float(C[i, j] / E[i, j]), 2)})
    lift.sort(key=lambda r: -r["lift"])
    rows = C.sum(axis=1)
    persistence = [{"topic": k, "label": labels[k], "share": round(float(p[k]), 4),
                    "stay": round(float(C[k, k] / rows[k]), 4) if rows[k] else None,
                    "stay_expected_session": round(float(E[k, k] / max(E[k].sum(), 1e-9)), 4),
                    "n_from": int(rows[k])} for k in range(K)]
    return {
        "n_drops": int(len(topic)), "n_pairs": n_pairs, "n_sessions_multi": int(len(np.unique(sid[ib]))),
        "K": K, "labels": labels, "counts": C.tolist(),
        "entropy_iid_bits": round(h0, 4), "entropy_rate_bits": round(h1, 4), "diag_share": round(diag, 4),
        "null_global": test("global"), "null_session": test("session"),
        "g_test": {"G": round(float(G), 1), "df": (K - 1) ** 2,
                   "p": float(sps.chi2.sf(G, (K - 1) ** 2))},
        "persistence": persistence, "lift": lift[:20], "n_perm": n_perm,
    }


# ------------------------------------------------------------------ compression
REF_CHARS = 30_000
PROBE_CHARS = 5_000
N_DRAWS = 3


def _L(text):
    return len(lzma.compress(text.encode("utf-8"), preset=6))


def _norm(t):
    return " ".join(t.split())


def _sample(docs, rng):
    """Reference (REF_CHARS) et sonde (PROBE_CHARS) disjointes, tirees au hasard parmi les documents."""
    order = rng.permutation(len(docs))
    ref, probe, n = [], [], 0
    for i in order:
        if n < REF_CHARS:
            ref.append(docs[i])
            n += len(docs[i]) + 1
        else:
            probe.append(docs[i])
            if sum(map(len, probe)) >= PROBE_CHARS:
                break
    return "\n".join(ref)[:REF_CHARS], "\n".join(probe)[:PROBE_CHARS]


def semester(et):
    return et.dt.year.astype(str) + "-S" + np.where(et.dt.month <= 6, "1", "2")


def corpora(d, tw):
    out = {}
    d = d.assign(sem=semester(d["et"]), txt=[_norm(clean(x)) for x in d["text"]])
    for s, g in d.groupby("sem"):
        out[f"Q {s}"] = [x for x in g["txt"] if x]
    tw = tw[(tw["is_retweet"] == 0) & (tw["time"] < END_TWEETS) & (tw["time"] >= d["time"].min() - 86400 * 183)]
    tw = tw.assign(sem=semester(tw["ts"].dt.tz_convert(ET)), txt=[_norm(clean(x)) for x in tw["text"]])
    for s, g in tw.groupby("sem"):
        out[f"Trump {s}"] = [x for x in g["txt"] if x]
    return out


def compression(docs_by, seed=SEED):
    """Entropie croisee par compression. cross[a][b] : bits/caractere pour coder une
    sonde de b apres avoir lu une reference de a. Distance (divergence symetrisee) :
    (cross[a][b] - cross[b][b] + cross[b][a] - cross[a][a]) / 2."""
    rng = np.random.default_rng(seed)
    names = [k for k, v in docs_by.items() if sum(map(len, v)) >= REF_CHARS + PROBE_CHARS]
    skipped = [k for k in docs_by if k not in names]
    n = len(names)
    cross = np.zeros((n, n))
    for _ in range(N_DRAWS):
        samples = [_sample(docs_by[k], rng) for k in names]
        Lref = [_L(r) for r, _ in samples]
        for i, (ref, _) in enumerate(samples):
            for j, (_, probe) in enumerate(samples):
                cross[i, j] += (_L(ref + "\n" + probe) - Lref[i]) * 8 / len(probe)
    cross /= N_DRAWS
    self_h = np.diag(cross).copy()
    D = (cross - self_h[None, :] + cross.T - self_h[:, None]) / 2
    np.fill_diagonal(D, 0)
    D = np.maximum(D, 0)
    order = leaves_list(linkage(squareform(D, checks=False), method="average")).tolist() if n > 2 else list(range(n))
    nearest = {}
    for i, a in enumerate(names):
        j = min((j for j in range(n) if j != i), key=lambda j: D[i, j])
        nearest[a] = {"name": names[j], "distance": round(float(D[i, j]), 4)}
    return {"names": names, "skipped_too_small": skipped, "ref_chars": REF_CHARS, "probe_chars": PROBE_CHARS,
            "draws": N_DRAWS, "self_bits_per_char": {a: round(float(h), 4) for a, h in zip(names, self_h)},
            "cross": [[round(float(x), 4) for x in row] for row in cross],
            "distance": [[round(float(x), 4) for x in row] for row in D],
            "order": [names[i] for i in order], "nearest": nearest}


class CharMarkov:
    """Modele de caracteres d'ordre k, lisse par interpolation avec le modele d'ordre inferieur."""

    def __init__(self, text, k=3, kappa=1.0):
        self.k, self.kappa = k, kappa
        self.alphabet = sorted(set(text)) + ["\x00"]
        self.counts = [Counter() for _ in range(k + 1)]
        self.ctx = [Counter() for _ in range(k + 1)]
        for o in range(k + 1):
            for i in range(o, len(text)):
                self.counts[o][text[i - o:i + 1]] += 1
                self.ctx[o][text[i - o:i]] += 1

    def prob(self, hist, c):
        p = 1 / len(self.alphabet)
        for o in range(self.k + 1):
            h = hist[len(hist) - o:] if o else ""
            n = self.ctx[o].get(h, 0)
            p = (self.counts[o].get(h + c, 0) + self.kappa * p) / (n + self.kappa)
        return p

    def bits_per_char(self, text):
        k = self.k
        return float(-np.mean([np.log2(self.prob(text[max(0, i - k):i], text[i])) for i in range(len(text))]))


def style_drift(docs_by, test_chars=20_000, seed=SEED):
    """Entropie croisee (bits/caractere) d'un modele d'ordre 3 appris sur un semestre de Q
    et evalue sur un echantillon tenu a l'ecart de chaque semestre."""
    rng = np.random.default_rng(seed)
    names = [k for k in docs_by if k.startswith("Q ") and sum(map(len, docs_by[k])) >= 2 * test_chars]
    train, test = {}, {}
    for k in names:
        docs = [x.lower() for x in docs_by[k]]
        order = rng.permutation(len(docs))
        held, rest, n = [], [], 0
        for i in order:
            if n < test_chars:
                held.append(docs[i])
                n += len(docs[i]) + 1
            else:
                rest.append(docs[i])
        test[k] = "\n".join(held)[:test_chars]
        train[k] = "\n".join(rest)
    models = {k: CharMarkov(train[k]) for k in names}
    M = [[round(models[a].bits_per_char(test[b]), 4) for b in names] for a in names]
    step = [{"from": a, "to": b, "bits": M[i][i + 1], "self": M[i + 1][i + 1],
             "drift": round(M[i][i + 1] - M[i + 1][i + 1], 4)}
            for i, (a, b) in enumerate(zip(names[:-1], names[1:]))]
    return {"names": names, "test_chars": test_chars, "order": 3, "matrix": M, "steps": step}


# ------------------------------------------------------------------ etape
def run(ctx):
    d = load_drops(ctx.conn)
    stats_path = ctx.results / "stats.json"
    cps = __import__("json").loads(stats_path.read_text())["changepoints"] if stats_path.exists() else None
    c = daily_counts(d["ts"])
    y = c.to_numpy()

    def chain():
        dd = d[d["text"].str.strip() != ""].reset_index(drop=True)
        W, comps, vocab = topic_model([clean(x) for x in dd["text"]])
        keep = W.sum(axis=1) > 0
        labels = [" · ".join(vocab[np.argsort(comps[k])[::-1][:4]]) for k in range(W.shape[1])]
        sid = sessions(dd["time"].to_numpy())[keep]
        return topic_chain(sid, W.argmax(axis=1)[keep], W.shape[1], labels)

    def text_parts():
        return corpora(d, load_tweets(ctx.conn))

    parts = [(f"hmm{k}", (lambda k=k: _jsonable(hmm_fit(y, k)))) for k in range(1, K_MAX + 1)]
    parts += [("chain", chain),
              ("compression", lambda: compression(text_parts())),
              ("drift", lambda: style_drift(text_parts()))]
    acc = run_parts(ctx, "markov", parts)
    if acc is None:
        return False
    fits = [_unjson(acc[f"hmm{k}"]) for k in range(1, K_MAX + 1)]
    out = {"hmm": hmm_summary(c, fits, cps), "topic_chain": acc["chain"],
           "compression": acc["compression"], "style_drift": acc["drift"]}
    ctx.set_output(db.sha(write(ctx, "markov", out)))
    h, t = out["hmm"], out["topic_chain"]
    log(f"markov : HMM {h['K']} regimes ({h['n_switches']} bascules) ; themes : entropie "
        f"{t['entropy_rate_bits']} bits contre {t['entropy_iid_bits']} (i.i.d.), "
        f"maintien {t['diag_share']} contre {t['null_session']['diag_mean']} (p = {t['null_session']['p_diag']})")
    return True


def _jsonable(f):
    return {k: (v.tolist() if isinstance(v, np.ndarray) else v) for k, v in f.items()}


def _unjson(f):
    return {k: (np.array(v) if isinstance(v, list) else v) for k, v in f.items()}

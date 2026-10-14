"""Analogies physiques appliquees au rythme des drops.

- Hawkes / ETAS (sismologie) : un drop en declenche-t-il d'autres, comme un
  seisme ses repliques ? Fond inhomogene (niveau par regime x profil horaire),
  noyau exponentiel ou d'Omori, estimation EM (Veen & Schoenberg 2008).
  Le rapport de branchement n est la part des drops "declenches" par un drop
  anterieur. Variante croisee : les tweets de Trump declenchent-ils des drops ?
- DFA (Peng et al. 1994) : memoire longue de la serie d'activite (exposant H).
- Avalanches : les tailles et durees des sessions suivent-elles une loi de
  puissance (criticite auto-organisee) ? Clauset, Shalizi & Newman (2009),
  avec test de Vuong contre exponentielle et lognormale.
- Phases : statistique circulaire des heures de publication (Rayleigh), derive
  mensuelle de la phase et verrouillage de phase avec Trump (Kuramoto).
"""
import json

import numpy as np
import pandas as pd
from scipy import optimize, special
from scipy import stats as sps

from .. import db
from ..log import log
from .common import ET, load_drops, load_tweets, run_parts, write
from .stats import SESSION_GAP_MIN

SEED = 20171028
HOUR = 3600.0
WINDOW_H = 720.0        # noyau tronque a 30 jours
MAX_LAGS = 1500
CROSS_WINDOW_H = 72.0   # tweets pris en compte jusqu'a 3 jours avant un drop
END_TWEETS = 1610064000
Q_END = 1607472000      # 2020-12-09 : apres le dernier drop de la periode principale


# ------------------------------------------------------------------ Hawkes
def circadian(hours, smooth=1.0):
    """Profil horaire (24 valeurs, moyenne 1) tire d'heures locales (0-23)."""
    h = np.bincount(np.asarray(hours, dtype=int) % 24, minlength=24) + smooth
    return h / h.mean()


class Pairs:
    """Paires (evenement i, evenement anterieur j de la source) a moins de `window` heures :
    retards a plat, sans matrice de remplissage. Les retards sont aussi ranges en classes
    logarithmiques fines pour l'etape M du noyau."""

    def __init__(self, t, src=None, window=WINDOW_H, n_bins=1500):
        self_ = src is None
        src = t if self_ else src
        hi = np.arange(len(t)) if self_ else np.searchsorted(src, t, side="left")
        lo = np.searchsorted(src, t - window, side="left")
        cnt = np.maximum(hi - lo, 0)
        self.rows = np.repeat(np.arange(len(t)), cnt)
        start = np.repeat(np.cumsum(cnt) - cnt, cnt)
        j = np.arange(cnt.sum()) - start + np.repeat(lo, cnt)
        self.lags = np.maximum(t[self.rows] - src[j], 1e-6)
        self.n, self.older = len(t), lo   # evenements de la source plus anciens que la fenetre
        edges = np.geomspace(1e-6, window * 1.0001, n_bins + 1)
        self.bins = np.clip(np.searchsorted(edges, self.lags) - 1, 0, n_bins - 1)
        self.centers = np.sqrt(edges[:-1] * edges[1:])
        self.window = window

    def rowsum(self, v):
        return np.bincount(self.rows, weights=v, minlength=self.n)


class Kernel:
    """Noyau de declenchement normalise sur [0, window]."""

    def __init__(self, kind, theta=None, window=WINDOW_H):
        self.kind, self.window = kind, window
        self.p = np.array(theta if theta is not None else ([0.5] if kind == "exp" else [0.5, 0.5]), dtype=float)

    def pdf(self, tau, p=None):
        p = self.p if p is None else p
        W = self.window
        if self.kind == "exp":
            b = p[0]
            return b * np.exp(-b * tau) / (1 - np.exp(-b * W))
        c, th = p
        return th * c ** th * (tau + c) ** (-1 - th) / (1 - (c / (W + c)) ** th)

    def logpdf(self, tau, p=None):
        p = self.p if p is None else p
        W = self.window
        if self.kind == "exp":
            b = p[0]
            return np.log(b) - b * tau - np.log1p(-np.exp(-b * W))
        c, th = p
        return np.log(th) + th * np.log(c) - (1 + th) * np.log(tau + c) - np.log1p(-(c / (W + c)) ** th)

    def cdf(self, tau, p=None):
        p = self.p if p is None else p
        W = self.window
        tau = np.minimum(tau, W)
        if self.kind == "exp":
            b = p[0]
            return (1 - np.exp(-b * tau)) / (1 - np.exp(-b * W))
        c, th = p
        return (1 - (c / (tau + c)) ** th) / (1 - (c / (W + c)) ** th)

    def m_step(self, pairs, w):
        """Maximise sum w log pdf(retards), retards regroupes en classes logarithmiques
        (bord de fin de serie neglige)."""
        wb = np.bincount(pairs.bins, weights=w, minlength=len(pairs.centers))
        m = wb > 0
        x, ww = pairs.centers[m], wb[m]
        if ww.sum() <= 0:
            return
        if self.kind == "exp":
            f = lambda v: -(ww * self.logpdf(x, [np.exp(v[0])])).sum()
        else:
            f = lambda v: -(ww * self.logpdf(x, [np.exp(v[0]), np.exp(v[1])])).sum()
        r = optimize.minimize(f, np.log(self.p), method="Nelder-Mead", options={"xatol": 1e-5, "fatol": 1e-8})
        self.p = np.exp(r.x) if self.kind == "exp" else np.clip(np.exp(r.x), [1e-5, 1e-3], [1e3, 20])

    def describe(self):
        if self.kind == "exp":
            return {"kind": "exp", "decay_per_hour": round(float(self.p[0]), 4),
                    "mean_delay_hours": round(float(1 / self.p[0]), 3)}
        c, th = self.p
        med = c * (2 ** (1 / th) - 1)
        return {"kind": "omori", "c_hours": round(float(c), 5), "theta": round(float(th), 4),
                "omori_p": round(float(1 + th), 4), "median_delay_hours": round(float(med), 3)}


class Baseline:
    """Fond mu(t) = mu_s * profil(h) : un niveau par regime, un profil horaire commun."""

    def __init__(self, t0, T, bounds, profile, tz_offset_h):
        self.profile = profile
        self.edges = np.concatenate([[t0], np.asarray(bounds, dtype=float), [T]])
        self.S = len(self.edges) - 1
        grid = np.arange(t0, T, 1.0)
        hours = ((grid + tz_offset_h(grid)) % 24).astype(int)
        seg = np.clip(np.searchsorted(self.edges, grid, side="right") - 1, 0, self.S - 1)
        self.exposure = np.bincount(seg, weights=profile[hours], minlength=self.S)
        self.grid, self.cum_w = grid, np.cumsum(profile[hours])
        self.tz = tz_offset_h

    def at(self, t):
        hours = ((t + self.tz(t)) % 24).astype(int)
        seg = np.clip(np.searchsorted(self.edges, t, side="right") - 1, 0, self.S - 1)
        return seg, self.profile[hours]


def hawkes_em(t, base, kernel, cross=None, n_iter=1000, tol=1e-6, fit_self=True):
    """EM d'un processus de Hawkes (Veen & Schoenberg 2008), t en heures, trie.
    cross : excitation par une source exterieure, dict(pairs, kernel, rest) ou rest
    est le temps restant apres chaque evenement source (compensateur)."""
    N = len(t)
    T = base.edges[-1]
    seg, prof = base.at(t)
    P = Pairs(t, window=kernel.window) if fit_self else None
    rest = T - t
    mu = np.maximum(np.bincount(seg, minlength=base.S) / np.maximum(base.exposure, 1e-9) * 0.5, 1e-9)
    n = 0.3 if fit_self else 0.0
    nc = 0.1 if cross is not None else 0.0
    prev = -np.inf
    for it in range(n_iter):
        bg = mu[seg] * prof
        gs = kernel.pdf(P.lags) * n if fit_self else None
        gc = cross["kernel"].pdf(cross["pairs"].lags) * nc if cross is not None else None
        lam = bg.copy()
        if fit_self:
            lam += P.rowsum(gs)
        if cross is not None:
            lam += cross["pairs"].rowsum(gc)
        comp = (mu * base.exposure).sum()
        cs = kernel.cdf(rest).sum() if fit_self else 0.0
        cc = cross["kernel"].cdf(cross["rest"]).sum() if cross is not None else 0.0
        ll = float(np.log(lam).sum() - comp - n * cs - nc * cc)
        # Arret sur un gain absolu de log-vraisemblance (l'EM de Hawkes converge lentement).
        if it > 20 and ll - prev < tol:
            break
        prev = ll
        # E-step (probabilites de filiation), puis M-step.
        mu = np.maximum(np.bincount(seg, weights=bg / lam, minlength=base.S) / np.maximum(base.exposure, 1e-9), 1e-9)
        if fit_self:
            w = gs / lam[P.rows]
            n = float(w.sum() / max(cs, 1e-9))
            kernel.m_step(P, w)
        if cross is not None:
            wc = gc / lam[cross["pairs"].rows]
            nc = float(wc.sum() / max(cc, 1e-9))
            cross["kernel"].m_step(cross["pairs"], wc)
    n_par = base.S + (1 + len(kernel.p) if fit_self else 0) + (1 + len(cross["kernel"].p) if cross is not None else 0)
    out = {"ll": round(ll, 2), "aic": round(-2 * ll + 2 * n_par, 2), "n_params": n_par, "iterations": it + 1,
           "branching_ratio": round(n, 4) if fit_self else None,
           "kernel": kernel.describe() if fit_self else None,
           "share_drops_endogenous": round(float((P.rowsum(gs) / lam).mean()), 4) if fit_self else 0.0}
    if cross is not None:
        out["cross_ratio"] = round(nc, 4)
        out["cross_kernel"] = cross["kernel"].describe()
        out["share_drops_from_cross"] = round(float((cross["pairs"].rowsum(gc) / lam).mean()), 4)
    out["_state"] = {"mu": mu, "n": n, "pairs": P}
    return out


def rescaled_ks(t, base, fit, kernel):
    """Theoreme du changement de temps : les increments du compensateur aux instants
    des evenements doivent suivre une loi Exp(1). Statistique de KS et quantiles."""
    mu, n = fit["_state"]["mu"], fit["_state"]["n"]
    # Fond cumule : interpolation sur la grille horaire, ponderee par regime.
    seg_grid = np.clip(np.searchsorted(base.edges, base.grid, side="right") - 1, 0, base.S - 1)
    hours = ((base.grid + base.tz(base.grid)) % 24).astype(int)
    cum = np.cumsum(mu[seg_grid] * base.profile[hours])
    Lb = np.interp(t, base.grid + 1.0, cum)
    if kernel is not None and n:
        P = fit["_state"]["pairs"]
        Lk = n * (P.rowsum(kernel.cdf(P.lags)) + P.older)
    else:
        Lk = 0.0
    Lam = Lb + Lk
    inc = np.diff(Lam)
    inc = inc[inc > 0]
    ks = sps.kstest(inc, "expon")
    qs = np.linspace(0.01, 0.99, 50)
    return {"ks_D": round(float(ks.statistic), 4), "ks_p": float(ks.pvalue),
            "qq": [{"theory": round(float(sps.expon.ppf(q)), 4), "observed": round(float(np.quantile(inc, q)), 4)}
                   for q in qs]}


def _tz_fast():
    """Decalage tabule par heure (2016-2023) : evite de reconvertir des millions d'instants."""
    grid = pd.date_range("2016-01-01", "2024-01-01", freq="h", tz="UTC")
    start = grid[0]
    off = np.array([x.utcoffset().total_seconds() / 3600 for x in grid.tz_convert(ET)])
    g0 = start.timestamp() / HOUR

    def f(t):
        return off[np.clip((np.asarray(t) - g0).astype(int), 0, len(off) - 1)]
    return f


def _setup(d, cps, end):
    """Instants des drops (heures depuis l'epoque, ex aequo departages) et fond :
    profil horaire tire des debuts de session, un niveau par regime de stats.changepoints."""
    t = np.sort(d["time"].to_numpy(dtype=float))
    t = t[t < end] / HOUR
    t = t + np.arange(len(t)) * 1e-7
    tz = _tz_fast()
    t0, T = t[0] - 1.0, t[-1] + 1.0
    sid = np.cumsum(np.concatenate([[True], np.diff(t) > SESSION_GAP_MIN / 60]))
    starts = t[np.concatenate([[True], sid[1:] != sid[:-1]])]
    profile = circadian(((starts + tz(starts)) % 24).astype(int))
    bounds = [pd.Timestamp(s["start"]).tz_localize(ET).timestamp() / HOUR for s in (cps or {}).get("segments", [])[1:]]
    bounds = [b for b in bounds if t0 < b < T]
    return t, t0, T, tz, profile, bounds


HAWKES_MODELS = [f"{b}/{k}" for b in ("regimes", "constant") for k in ("poisson", "exp", "omori")]


def hawkes(d, cps, model):
    """Un modele (fond / noyau) sur la periode principale (2017-10 -> 2020-12).
    Fond 'regimes' : un niveau par regime ; 'constant' : un seul niveau, ce qui
    laisse au noyau les variations lentes (borne haute du rapport de branchement)."""
    t, t0, T, tz, profile, bounds = _setup(d, cps, Q_END)
    bname, kind = model.split("/")
    base = Baseline(t0, T, bounds if bname == "regimes" else [], profile, tz)
    k = None if kind == "poisson" else Kernel(kind)
    fit = hawkes_em(t, base, k or Kernel("exp"), fit_self=k is not None)
    fit["gof"] = rescaled_ks(t, base, fit, k)
    fit.pop("_state")
    fit.update({"n_events": int(len(t)), "start": _iso(t[0]), "end": _iso(t[-1]), "n_regimes": base.S,
                "window_hours": WINDOW_H, "profile": [round(float(x), 3) for x in profile]})
    return fit


def hawkes_cross(d, cps, tweets, shift_days=0):
    """Drops excites par eux-memes et par les tweets originaux de Trump (decales de
    shift_days pour le modele nul). Noyaux exponentiels, fond par regimes."""
    t, t0, T, tz, profile, bounds = _setup(d, cps, min(Q_END, END_TWEETS))
    tw = tweets[tweets["is_retweet"] == 0]["time"].to_numpy(dtype=float) / HOUR + shift_days * 24
    tw = np.sort(tw[(tw > t[0] - CROSS_WINDOW_H) & (tw < t[-1])])
    base = Baseline(t0, T, bounds, profile, tz)
    cross = {"pairs": Pairs(t, tw, window=CROSS_WINDOW_H), "kernel": Kernel("exp", [1.0], window=CROSS_WINDOW_H),
             "rest": T - tw}
    fit = hawkes_em(t, base, Kernel("exp"), cross=cross)
    fit.pop("_state")
    return {"shift_days": shift_days, "n_tweets": int(len(tw)), **fit}


def _iso(t_hours):
    return pd.Timestamp(t_hours * HOUR, unit="s", tz="UTC").isoformat()


# ------------------------------------------------------------------ DFA
def dfa(x, scales=None, order=1):
    """Detrended fluctuation analysis : F(s) ~ s^H."""
    x = np.asarray(x, dtype=float)
    y = np.cumsum(x - x.mean())
    N = len(y)
    if scales is None:
        scales = np.unique(np.geomspace(8, N // 4, 24).astype(int))
    F = []
    for s in scales:
        nseg = N // s
        segs = np.concatenate([y[:nseg * s].reshape(nseg, s), y[N - nseg * s:].reshape(nseg, s)])
        xs = np.arange(s)
        V = np.vander(xs, order + 1)
        coef, *_ = np.linalg.lstsq(V, segs.T, rcond=None)
        res = segs.T - V @ coef
        F.append(np.sqrt((res ** 2).mean()))
    F = np.array(F)
    H = np.polyfit(np.log(scales), np.log(F), 1)[0]
    return float(H), scales, F


def dfa_series(d, tweets, seed=SEED):
    rng = np.random.default_rng(seed)
    t_q = d["time"].to_numpy()
    t_q = t_q[t_q < Q_END]
    t_t = tweets[(tweets["is_retweet"] == 0)]["time"].to_numpy()
    lo, hi = t_q.min(), min(Q_END, END_TWEETS)
    t_t = t_t[(t_t >= lo) & (t_t < hi)]
    out = []
    for res, sec in (("hour", 3600), ("day", 86400)):
        edges = np.arange(lo - lo % sec, hi + sec, sec)
        for name, ts in (("Q", t_q), ("Trump", t_t)):
            x = np.histogram(ts, bins=edges)[0]
            H, s, F = dfa(x)
            Hs, _, Fs = dfa(rng.permutation(x), s)
            # Pentes locales : petites et grandes echelles (croisement eventuel).
            half = len(s) // 2
            h_small = np.polyfit(np.log(s[:half]), np.log(F[:half]), 1)[0]
            h_large = np.polyfit(np.log(s[half:]), np.log(F[half:]), 1)[0]
            out.append({"series": name, "resolution": res, "n": int(len(x)), "H": round(H, 3),
                        "H_small_scales": round(float(h_small), 3), "H_large_scales": round(float(h_large), 3),
                        "H_shuffled": round(Hs, 3),
                        "curve": [{"scale": int(a), "F": float(b), "F_shuffled": float(c)}
                                  for a, b, c in zip(s, F, Fs)]})
    return out


# ------------------------------------------------------------------ avalanches
def _pl_discrete_alpha(x, xmin):
    x = x[x >= xmin]
    f = lambda a: -(-a * np.log(x).sum() - len(x) * np.log(special.zeta(a, xmin)))
    return optimize.minimize_scalar(f, bounds=(1.01, 6), method="bounded").x


def _pl_cont_alpha(x, xmin):
    x = x[x >= xmin]
    return 1 + len(x) / np.log(x / xmin).sum()


def _ks_pl(x, xmin, a, discrete):
    x = np.sort(x[x >= xmin])
    if discrete:
        u = np.arange(xmin, x.max() + 1)
        pmf = u ** (-a) / special.zeta(a, xmin)
        cdf = np.cumsum(pmf)
        emp = np.searchsorted(x, u, side="right") / len(x)
        return float(np.abs(emp - cdf).max())
    emp = np.arange(1, len(x) + 1) / len(x)
    cdf = 1 - (x / xmin) ** (1 - a)
    return float(np.abs(emp - cdf).max())


def powerlaw_fit(x, discrete=True, min_tail=50):
    """xmin par minimisation de la distance de KS (Clauset et al. 2009), puis alpha."""
    x = np.asarray(x, dtype=float)
    x = x[x > 0]
    cands = np.unique(x)
    cands = [c for c in cands if (x >= c).sum() >= min_tail]
    best = None
    for xm in cands:
        a = _pl_discrete_alpha(x, xm) if discrete else _pl_cont_alpha(x, xm)
        D = _ks_pl(x, xm, a, discrete)
        if best is None or D < best[2]:
            best = (xm, a, D)
    return best


def _loglik_tail(x, xmin, discrete, a):
    """Log-vraisemblances ponctuelles (queue x >= xmin) : loi de puissance, exponentielle, lognormale."""
    x = x[x >= xmin]
    if discrete:
        pl = -a * np.log(x) - np.log(special.zeta(a, xmin))
        m = (x - xmin).mean()
        q = m / (1 + m)
        ex = np.log(1 - q) + (x - xmin) * np.log(max(q, 1e-12))

        def ln_pmf(v, mu, s):
            lo = sps.norm.logsf((np.log(xmin - 0.5) - mu) / s)
            return np.log(np.maximum(sps.norm.cdf((np.log(v + 0.5) - mu) / s)
                                     - sps.norm.cdf((np.log(v - 0.5) - mu) / s), 1e-300)) - lo
    else:
        pl = np.log(a - 1) - np.log(xmin) - a * np.log(x / xmin)
        lam = 1 / (x - xmin).mean()
        ex = np.log(lam) - lam * (x - xmin)

        def ln_pmf(v, mu, s):
            return sps.norm.logpdf((np.log(v) - mu) / s) - np.log(v * s) - sps.norm.logsf((np.log(xmin) - mu) / s)
    r = optimize.minimize(lambda p: -ln_pmf(x, p[0], np.exp(p[1])).sum(),
                          [np.log(x).mean(), np.log(max(np.log(x).std(), 0.1))], method="Nelder-Mead")
    ln = ln_pmf(x, r.x[0], np.exp(r.x[1]))
    return pl, ex, ln


def vuong(l1, l2):
    """R > 0 : le premier modele est prefere ; p bilaterale (Vuong 1989)."""
    d = l1 - l2
    R = d.sum()
    sd = d.std()
    if sd == 0:
        return {"R": 0.0, "p": 1.0}
    z = R / (sd * np.sqrt(len(d)))
    return {"R": round(float(R), 2), "p": float(2 * sps.norm.sf(abs(z)))}


def gof_bootstrap(x, fit, discrete, n_boot=100, seed=SEED):
    """p-valeur de Clauset : part des echantillons synthetiques dont la distance KS
    (xmin re-estime) depasse celle observee."""
    rng = np.random.default_rng(seed)
    xm, a, D = fit
    x = np.asarray(x, dtype=float)
    body = x[x < xm]
    p_tail = (x >= xm).mean()
    worse = 0
    for _ in range(n_boot):
        n_tail = rng.binomial(len(x), p_tail)
        if discrete:
            u = np.arange(xm, xm + 100_000)
            pmf = u ** (-a)
            pmf /= pmf.sum()
            tail = rng.choice(u, size=n_tail, p=pmf)
        else:
            tail = xm * (1 - rng.random(n_tail)) ** (-1 / (a - 1))
        syn = np.concatenate([rng.choice(body, size=len(x) - n_tail) if len(body) else [], tail])
        f = powerlaw_fit(syn, discrete=discrete)
        if f and f[2] >= D:
            worse += 1
    return round((worse + 1) / (n_boot + 1), 4)


def avalanches(d, tweets):
    out = {}
    series = {"Q": np.sort(d["time"].to_numpy(dtype=float))}
    tw = tweets[(tweets["is_retweet"] == 0) & (tweets["time"] < END_TWEETS)]["time"].to_numpy(dtype=float)
    series["Trump"] = np.sort(tw[tw >= series["Q"].min()])
    for name, t in series.items():
        sid = np.cumsum(np.concatenate([[True], np.diff(t) > SESSION_GAP_MIN * 60]))
        df = pd.DataFrame({"sid": sid, "t": t}).groupby("sid")["t"]
        size = df.size().to_numpy(dtype=float)
        dur = ((df.max() - df.min()).to_numpy() / 60.0)
        dur = dur[size > 1]
        res = {}
        for key, x, disc in (("size", size, True), ("duration_min", dur, False)):
            fit = powerlaw_fit(x, discrete=disc)
            if not fit:
                continue
            xm, a, D = fit
            pl, ex, ln = _loglik_tail(np.asarray(x, dtype=float), xm, disc, a)
            ccdf_x = np.unique(np.quantile(x, np.linspace(0, 1, 200)))
            res[key] = {"n": int(len(x)), "xmin": float(xm), "alpha": round(float(a), 3), "ks_D": round(D, 4),
                        "n_tail": int((x >= xm).sum()),
                        "gof_p": gof_bootstrap(x, fit, disc) if key == "size" else None,
                        "vs_exponential": vuong(pl, ex), "vs_lognormal": vuong(pl, ln),
                        "ccdf": [{"x": float(v), "p": float((x >= v).mean())} for v in ccdf_x]}
        out[name] = res
    return out


# ------------------------------------------------------------------ phases
def circ(hours, period=24.0):
    a = 2 * np.pi * np.asarray(hours) / period
    z = np.exp(1j * a).mean()
    n = len(a)
    R = abs(z)
    # Rayleigh, approximation de Zar (1999).
    Z = n * R ** 2
    p = float(np.exp(np.sqrt(1 + 4 * n + 4 * (n ** 2 - (n * R) ** 2)) - (1 + 2 * n))) if n else 1.0
    return {"n": int(n), "R": round(float(R), 4), "peak": round(float((np.angle(z) % (2 * np.pi)) * period / (2 * np.pi)), 2),
            "rayleigh_Z": round(float(Z), 1), "rayleigh_p": min(p, 1.0), "_z": z}


def phase_split(hours, days, min_side=150, n_perm=200, seed=SEED):
    """Rupture de phase : date qui separe le mieux les heures de publication en deux
    blocs de phases distinctes. Statistique : gain de longueur resultante
    n1 R1 + n2 R2 - n R (analogue circulaire de la reduction de variance) ; p par
    permutation de l'ordre des drops (maximum recalcule a chaque tirage)."""
    z = np.exp(2j * np.pi * np.asarray(hours) / 24)
    n = len(z)
    cut = np.nonzero(np.diff(np.asarray(days)) > 0)[0] + 1   # coupures entre jours distincts
    cut = cut[(cut >= min_side) & (cut <= n - min_side)]

    def best(zz):
        c = np.cumsum(zz)
        tot = abs(c[-1])
        g = np.abs(c[cut - 1]) + np.abs(c[-1] - c[cut - 1]) - tot
        i = int(np.argmax(g))
        return float(g[i]), int(cut[i])

    g, k = best(z)
    rng = np.random.default_rng(seed)
    null = [best(rng.permutation(z))[0] for _ in range(n_perm)]
    peak = lambda zz: round(float((np.angle(zz.mean()) % (2 * np.pi)) * 12 / np.pi), 2)
    return {"index": k, "gain": round(g, 2), "p": round((1 + sum(x >= g for x in null)) / (n_perm + 1), 4),
            "before_peak": peak(z[:k]), "after_peak": peak(z[k:]), "n_before": k, "n_after": n - k,
            "before_R": round(float(abs(z[:k].mean())), 4), "after_R": round(float(abs(z[k:].mean())), 4)}


def phases(d, tweets):
    q = d.assign(et=d["ts"].dt.tz_convert(ET))
    tw = tweets[(tweets["is_retweet"] == 0) & (tweets["time"] < END_TWEETS)]
    tw = tw.assign(et=tw["ts"].dt.tz_convert(ET))
    tw = tw[tw["time"] >= d["time"].min()]
    hod = lambda e: e.dt.hour + e.dt.minute / 60
    dow = lambda e: e.dt.dayofweek + hod(e) / 24
    out = {"day": {}, "week": {}, "monthly": []}
    for name, df in (("Q", q), ("Trump", tw)):
        c = circ(hod(df["et"]))
        c.pop("_z")
        out["day"][name] = c
        w = circ(dow(df["et"]), 7.0)
        w.pop("_z")
        out["week"][name] = w
    mq = q.groupby(q["et"].dt.strftime("%Y-%m"))
    mt = tw.groupby(tw["et"].dt.strftime("%Y-%m"))
    dphi = []
    for m, g in mq:
        if len(g) < 20:
            continue
        cq = circ(hod(g["et"]))
        row = {"month": m, "n": cq["n"], "R": cq["R"], "peak": cq["peak"]}
        if m in mt.groups:
            gt = mt.get_group(m)
            ct = circ(hod(gt["et"]))
            row.update({"trump_peak": ct["peak"], "trump_R": ct["R"], "trump_n": ct["n"]})
            dphi.append(np.angle(cq["_z"] / ct["_z"]))
        out["monthly"].append(row)
    if dphi:
        z = np.exp(1j * np.array(dphi)).mean()
        out["phase_locking"] = {"months": len(dphi), "plv": round(float(abs(z)), 4),
                                "mean_lag_hours": round(float(np.angle(z) * 24 / (2 * np.pi)), 2)}
    # Rupture de phase de Q (periode principale) : date et heures de pointe avant / apres.
    qm = q[q["time"] < Q_END]
    sp = phase_split(hod(qm["et"]).to_numpy(), qm["et"].dt.strftime("%Y%m%d").astype(int).to_numpy())
    sp["date"] = qm["et"].iloc[sp["index"]].date().isoformat()
    out["phase_split"] = sp
    # Derive : la phase de Q bascule-t-elle ? Plus grand ecart entre mois consecutifs.
    pk = [(r["month"], r["peak"]) for r in out["monthly"]]
    jumps = [{"from": a[0], "to": b[0], "shift_hours": round(float(((b[1] - a[1] + 12) % 24) - 12), 2)}
             for a, b in zip(pk[:-1], pk[1:])]
    out["largest_shifts"] = sorted(jumps, key=lambda j: -abs(j["shift_hours"]))[:5]
    return out


# ------------------------------------------------------------------ etape
# Modele nul : tweets decales de 1 a 14 jours (heure du jour conservee) ; p minimale 1/29.
SHIFTS = tuple(s for s in range(-14, 15) if s)


def run(ctx):
    d = load_drops(ctx.conn)
    tweets = load_tweets(ctx.conn)
    stats_path = ctx.results / "stats.json"
    cps = json.loads(stats_path.read_text())["changepoints"] if stats_path.exists() else None
    parts = [(f"hawkes:{m}", (lambda m=m: hawkes(d, cps, m))) for m in HAWKES_MODELS]
    parts += [("cross", lambda: hawkes_cross(d, cps, tweets, 0))]
    parts += [(f"cross{s}", (lambda s=s: hawkes_cross(d, cps, tweets, s))) for s in SHIFTS]
    parts += [("dfa", lambda: dfa_series(d, tweets)),
              ("avalanches", lambda: avalanches(d, tweets)),
              ("phases", lambda: phases(d, tweets))]
    acc = run_parts(ctx, "physics", parts)
    if acc is None:
        return False
    null = [acc[f"cross{s}"]["cross_ratio"] for s in SHIFTS]
    obs = acc["cross"]
    obs["null_shifts"] = [{"shift_days": s, "cross_ratio": r} for s, r in zip(SHIFTS, null)]
    obs["p_shift"] = round((1 + sum(r >= obs["cross_ratio"] for r in null)) / (len(null) + 1), 4)
    models = {m: acc[f"hawkes:{m}"] for m in HAWKES_MODELS}
    best = min((m for m in models if m.startswith("regimes/")), key=lambda m: models[m]["aic"])
    out = {"hawkes": {"models": models, "best": best}, "hawkes_trump": obs, "dfa": acc["dfa"],
           "avalanches": acc["avalanches"], "phases": acc["phases"]}
    ctx.set_output(db.sha(write(ctx, "physics", out)))
    h = out["hawkes"]
    b = h["models"][h["best"]]
    log(f"physique : Hawkes {h['best']} n = {b['branching_ratio']} ; Trump -> Q {obs['cross_ratio']} "
        f"(p decalage = {obs['p_shift']}) ; H(jour) Q = {out['dfa'][2]['H']}")
    return True

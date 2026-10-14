"""Q et la scene complotiste americaine : qui informe qui, qui mene qui.

- S1 Reseau d'entropie de transfert (Schreiber 2000), une version non lineaire
  de Granger : series quotidiennes (Q, Trump, subreddits, Wikipedia, GDELT...),
  log, rythme hebdomadaire retire (moyenne par jour de la semaine), variations
  discretisees en terciles ; maximum sur les retards de 1 a 7 jours ;
  significativite par substituts IAAFT (Schreiber & Schmitz 2000), adaptatifs
  (200, puis 1 000 de plus pour les liens prometteurs), correction de
  Benjamini-Hochberg. Sans retrait du rythme hebdomadaire, toute paire de
  series a cycle de 7 jours ressortait au retard 7.
- S2 Syncretisme : pour chaque theme de la scene, Q en parle-t-il avant ou apres
  le public (Reddit, Wikipedia) ? Correlation croisee hebdomadaire apres
  pre-blanchiment AR(2), substituts IAAFT ; verdict mene / suit / synchrone /
  independant. Indice d'absorption : nombre de themes par trimestre chez Q.
- S3 Fonction de reponse : activite horaire de r/greatawakening et r/CBTS_Stream
  autour des debuts de session de Q, contre des instants tires au hasard selon
  le meme profil horaire (analyse d'epoque superposee).
- P2 Chocs endogenes et exogenes (Crane & Sornette 2008) : pour les pics
  d'attention, part de la montee qui precede le pic et exposant de relaxation.
- P6 Diffusion de Bass (1969) des formules forgees par Q dans Reddit, et delai
  entre leur premier usage par Q et leur premiere occurrence dans l'echantillon.

Reddit : compte estime = part des elements echantillonnes contenant le terme x
volume du jour ; jour non echantillonne = valeur manquante, pas zero.
"""
import numpy as np
import pandas as pd
from scipy import optimize
from scipy import stats as sps

from .. import db, lexicon
from ..log import log
from .common import load_drops, load_events, load_tweets, load_yaml, run_parts, write

SEED = 20171028
Q_START, Q_END = "2017-10-28", "2020-12-08"
END_TWEETS = "2021-01-08"
N_SURR = 200
LAGS = range(1, 8)
MIN_OVERLAP = 180
THEME_FAMILIES = ("classic", "health", "election", "spiritual", "q_mythos", "militia")
THEME_GLOSSARY = ("gl:pizzagate", "gl:adrenochrome", "gl:frazzledrip", "gl:save-the-children", "gl:jfk-jr",
                  "gl:kraken", "gl:deep-state", "gl:cabal")
# Themes de la scene que Q porte par ses acteurs (il cite rarement les complots par leur nom).
THEME_ACTORS = ("actor:epstein", "actor:maxwell", "actor:soros", "actor:rothschild_family", "actor:clinton_foundation",
                "actor:hollywood", "actor:wikileaks", "actor:assange", "actor:uranium_one", "actor:planned_parenthood",
                "actor:vatican_church")


# ------------------------------------------------------------------ outils
def iaaft(x, rng, n_iter=50):
    """Substitut IAAFT : meme distribution et (presque) meme spectre que x, phases melangees."""
    x = np.asarray(x, dtype=float)
    amp = np.abs(np.fft.rfft(x))
    sorted_x = np.sort(x)
    s = rng.permutation(x)
    for _ in range(n_iter):
        f = np.fft.rfft(s)
        s = np.fft.irfft(amp * np.exp(1j * np.angle(f)), n=len(x))
        s = sorted_x[np.argsort(np.argsort(s))]
    return s


def tercile(x):
    q = np.quantile(x, [1 / 3, 2 / 3])
    return np.searchsorted(q, x, side="right")


def _H(*cols):
    """Entropie (bits) de la loi jointe de colonnes d'entiers de 0 a 2."""
    code = np.zeros(len(cols[0]), dtype=int)
    for c in cols:
        code = code * 3 + c
    p = np.bincount(code) / len(code)
    p = p[p > 0]
    return float(-(p * np.log2(p)).sum())


def transfer_entropy(x, y, lag):
    """TE x -> y (bits) : I(y_t ; x_{t-lag} | y_{t-1}), series deja discretisees."""
    yt, yp, xp = y[lag:], y[lag - 1:-1], x[:-lag]
    return _H(yt, yp) + _H(yp, xp) - _H(yp) - _H(yt, yp, xp)


def deseason(v, days):
    """log(1 + v) moins sa moyenne par jour de la semaine, puis variation d'un jour a l'autre."""
    z = pd.Series(np.log1p(np.asarray(v, dtype=float)))
    dow = pd.to_datetime(pd.Index(days)).dayofweek
    z = z - z.groupby(np.asarray(dow)).transform("mean")
    return np.diff(z.to_numpy())


def te_max(xc, yd, lags=LAGS):
    xd = tercile(xc)
    vals = [transfer_entropy(xd, yd, k) for k in lags]
    i = int(np.argmax(vals))
    return vals[i], list(lags)[i]


def bh(pvals):
    """Benjamini-Hochberg : p ajustees."""
    p = np.asarray(pvals, dtype=float)
    n = len(p)
    if not n:
        return p
    o = np.argsort(p)
    adj = np.minimum.accumulate((p[o] * n / np.arange(1, n + 1))[::-1])[::-1]
    out = np.empty(n)
    out[o] = np.minimum(adj, 1)
    return out


def prewhiten(x, order=2):
    """Residus d'un AR(order) ajuste par moindres carres."""
    x = np.asarray(x, dtype=float) - np.mean(x)
    X = np.column_stack([x[order - k - 1:len(x) - k - 1] for k in range(order)])
    coef, *_ = np.linalg.lstsq(X, x[order:], rcond=None)
    return x[order:] - X @ coef


def ccf(a, b, lags):
    """corr(a_t, b_{t+k}) pour k dans lags (k > 0 : a precede b)."""
    out = []
    for k in lags:
        if k >= 0:
            u, v = a[:len(a) - k], b[k:]
        else:
            u, v = a[-k:], b[:len(b) + k]
        out.append(float(np.corrcoef(u, v)[0, 1]) if np.std(u) > 0 and np.std(v) > 0 else 0.0)
    return np.array(out)


def bass_F(t, p, q):
    e = np.exp(-(p + q) * t)
    return (1 - e) / (1 + (q / p) * e)


def bass_fit(counts):
    """Ajuste m, p, q du modele de Bass sur des increments mensuels (t = 0 au premier mois)."""
    y = np.asarray(counts, dtype=float)
    t = np.arange(len(y) + 1)
    m0 = max(y.sum(), 1.0)

    def resid(v):
        m, p, q = np.exp(v)
        return m * np.diff(bass_F(t, p, q)) - y

    best = None
    for p0, q0 in ((0.01, 0.3), (0.05, 0.1), (0.003, 0.6), (0.1, 0.05)):
        r = optimize.least_squares(resid, np.log([m0 * 1.2, p0, q0]),
                                   bounds=(np.log([m0 * 0.5, 1e-5, 1e-4]), np.log([m0 * 20, 1.0, 3.0])))
        if best is None or r.cost < best.cost:
            best = r
    m, p, q = np.exp(best.x)
    ss_tot = ((y - y.mean()) ** 2).sum()
    r2 = 1 - 2 * best.cost / ss_tot if ss_tot > 0 else None
    peak = np.log(q / p) / (p + q) if q > p else 0.0
    return {"m": float(m), "p": float(p), "q": float(q), "q_over_p": float(q / p), "peak_months": float(peak),
            "r2": None if r2 is None else float(r2)}


def endo_exo(v, peak_i, pre=14, post=45, base_win=(60, 15)):
    """Precurseur (part de la montee dans les `pre` jours avant le pic) et exposant de
    relaxation apres le pic (Crane & Sornette 2008), au-dessus d'un fond median."""
    lo = max(0, peak_i - base_win[0])
    base = float(np.median(v[lo:max(lo + 1, peak_i - base_win[1])]))
    h = v[peak_i] - base
    if h <= 0:
        return None
    precursor = float((v[max(0, peak_i - pre):peak_i] - base).clip(min=0).mean() / h)
    k = np.arange(1, post + 1)
    after = v[peak_i + 1:peak_i + 1 + post] - base
    k = k[:len(after)]
    ok = after > 0
    if ok.sum() < 10:
        return {"precursor": round(precursor, 3), "decay_exponent": None, "class": "indetermine"}
    beta = -np.polyfit(np.log(k[ok]), np.log(after[ok]), 1)[0]
    if beta <= 0.1:   # l'activite ne retombe pas : un changement de niveau, pas un choc
        cls = "palier"
    else:
        cls = "exogene" if precursor < 0.1 and beta > 0.5 else ("endogene" if precursor >= 0.2 else "intermediaire")
    return {"precursor": round(precursor, 3), "decay_exponent": round(float(beta), 3), "class": cls}


# ------------------------------------------------------------------ donnees
def _day_index(start, end):
    return pd.date_range(start, end, freq="D").strftime("%Y-%m-%d")


def drop_hits(d, terms):
    """DataFrame booleen drops x termes du lexique (texte integral des drops)."""
    m = lexicon.Matcher(terms)
    M = np.zeros((len(d), len(terms)), dtype=bool)
    for r, txt in enumerate(d["text"].fillna("")):
        for i in m.hits(txt):
            M[r, i] = True
    return pd.DataFrame(M, columns=[t.id for t in terms], index=d.index)


def reddit_estimates(conn):
    """Comptes estimes par (sub, jour, terme) et taux par element echantillonne.
    Les deux genres (posts, commentaires) sont estimes separement puis additionnes."""
    hits = pd.read_sql_query("SELECT * FROM reddit_term_day", conn)
    samp = pd.read_sql_query("SELECT sub, kind, day, n_sampled FROM reddit_sample_day", conn)
    vol = pd.read_sql_query("SELECT * FROM reddit_volume", conn)
    if hits.empty or samp.empty:
        return pd.DataFrame(columns=["sub", "day", "term", "est", "hits", "sampled"])
    kinds = {"posts": "posts", "comments": "comments"}
    df = hits.merge(samp, on=["sub", "kind", "day"]).merge(
        vol.rename(columns={"n": "vol"}).assign(kind=lambda x: x["kind"].map(kinds)), on=["sub", "kind", "day"], how="left")
    df["est"] = df["n"] / df["n_sampled"].clip(lower=1) * df["vol"].fillna(0)
    out = df.groupby(["sub", "day", "term"]).agg(est=("est", "sum"), hits=("n", "sum")).reset_index()
    sampled = samp.groupby(["sub", "day"])["n_sampled"].sum().rename("sampled").reset_index()
    return out.merge(sampled, on=["sub", "day"], how="left")


def sampled_days(conn):
    s = pd.read_sql_query("SELECT sub, day, sum(n_sampled) n FROM reddit_sample_day GROUP BY 1, 2", conn)
    return {sub: set(g["day"]) for sub, g in s.groupby("sub")}


def daily_series(conn, d, tweets, est):
    """Series quotidiennes (jour UTC) ; NaN hors de la periode couverte par une source."""
    idx = _day_index("2016-01-01", "2023-12-31")
    S = {}
    qd = d["ts"].dt.strftime("%Y-%m-%d").value_counts()
    S["Q"] = qd.reindex(idx, fill_value=0).astype(float).where((idx >= Q_START) & (idx <= Q_END))
    tw = tweets[tweets["is_retweet"] == 0]["ts"].dt.strftime("%Y-%m-%d").value_counts()
    S["Trump"] = tw.reindex(idx, fill_value=0).astype(float).where(idx <= END_TWEETS)
    vol = pd.read_sql_query("SELECT sub, day, sum(n) n FROM reddit_volume GROUP BY 1, 2", conn)
    for sub, g in vol.groupby("sub"):
        s = g.set_index("day")["n"].reindex(idx).astype(float)
        first, last = s.first_valid_index(), s.last_valid_index()
        S[f"r/{sub}"] = s.fillna(0).where((idx >= first) & (idx <= last)) if first else s
    pv = pd.read_sql_query("SELECT day, views FROM pageviews WHERE project = 'en.wikipedia' AND article = 'QAnon'", conn)
    if not pv.empty:
        S["wiki:QAnon"] = pv.set_index("day")["views"].reindex(idx).astype(float)
    ws = pd.read_sql_query("SELECT article, day, sum(views) v FROM wiki_scene_views GROUP BY 1, 2", conn)
    if not ws.empty:
        keep = ws[~ws["article"].isin(["2020_United_States_presidential_election", "January_6_United_States_Capitol_attack"])]
        S["wiki:scene"] = keep.groupby("day")["v"].sum().reindex(idx).astype(float)
    g = pd.read_sql_query("SELECT day, us_events FROM gdelt_day", conn)
    if not g.empty:
        g["day"] = pd.to_datetime(g["day"].astype(str)).dt.strftime("%Y-%m-%d")
        S["GDELT:US"] = g.set_index("day")["us_events"].reindex(idx).astype(float)
    # Q dans r/conspiracy : mentions estimees de Q (QAnon, attributions, drops), jours echantillonnes seulement.
    qterms = {"qanon", "q_attribution", "q_drop_term"}
    sub = est[(est["sub"] == "conspiracy") & est["term"].isin(qterms)]
    days = sampled_days(conn).get("conspiracy", set())
    if len(days) >= MIN_OVERLAP:
        s = sub.groupby("day")["est"].sum().reindex(idx).fillna(0)
        S["Q@r/conspiracy"] = s.where(pd.Index(idx).isin(days))
    return pd.DataFrame(S, index=idx)


def trends_series(conn):
    """Google Trends, par requete : serie hebdomadaire (jour = lundi de la semaine) et
    serie mensuelle. Forme : requete seule (fenetres hebdomadaires recollees sur
    2019-2020) ; niveau : multiple de la moyenne de l'ancre, d'apres la requete
    mensuelle avec l'ancre. Niveau non mesurable (terme trop rare face a l'ancre) :
    forme seule, ramenee a un maximum de 1, et requete signalee."""
    from ..sources.trends import ANCHOR, WINDOWS
    try:
        raw = pd.read_sql_query("SELECT * FROM trends_raw", conn)
    except Exception:
        return {}, {}, set()
    if raw.empty:
        return {}, {}, set()
    solo = {(k[5:], w): g.set_index("date")["value"].astype(float)
            for (k, w), g in raw[raw["batch"].str.startswith("solo:")].groupby(["batch", "window"])}
    weekly_out, monthly_out, no_level = {}, {}, set()
    for q in {k[0] for k in solo}:
        a, b, m = solo.get((q, WINDOWS[0])), solo.get((q, WINDOWS[1])), solo.get((q, WINDOWS[2]))
        if a is None or b is None or m is None:
            continue
        ov = a.index.intersection(b.index)
        ov = ov[(ov >= "2019-01-01") & (ov <= "2020-12-31")]
        k = a[ov].sum() / b[ov].sum() if b[ov].sum() > 0 else 1.0
        w = pd.concat([a[a.index < "2020-07-01"], b[b.index >= "2020-07-01"] * k])
        # Niveau : rapport (terme / moyenne de l'ancre) de la requete ancree, en mois.
        anc = raw[(raw["batch"] == f"anchor:{q}")].pivot(index="date", columns="query", values="value")
        level = None
        if not anc.empty and ANCHOR in anc and anc[ANCHOR].mean() > 0 and anc[q].sum() > 0 and m.sum() > 0:
            rel_m = anc[q] / anc[ANCHOR].mean()
            level = float(rel_m.sum() / m.sum())
        if level is None:
            no_level.add(q)
            scale_m, scale_w = 1 / max(m.max(), 1e-9), 1 / max(w.max(), 1e-9)
        else:
            scale_m = level
            # Hebdomadaire : meme total mensuel que la serie mensuelle mise a niveau.
            wm = w.groupby(pd.Index(w.index).str[:7]).mean()
            mm = (m * level).groupby(pd.Index(m.index).str[:7]).mean()
            common = wm.index.intersection(mm.index)
            scale_w = float(mm[common].sum() / wm[common].sum()) if wm[common].sum() > 0 else level
        w = w * scale_w
        w.index = (pd.to_datetime(w.index) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
        weekly_out[q], monthly_out[q] = w, m * scale_m
    return weekly_out, monthly_out, no_level


def trends_summary(conn):
    weekly_s, monthly_s, no_level = trends_series(conn)
    out = []
    for q, m in monthly_s.items():
        out.append({"query": q, "level_measured": q not in no_level, "peak_month": m.idxmax()[:7],
                    "peak_rel": round(float(m.max()), 4),
                    "monthly": [{"month": d[:7], "rel": round(float(v), 5)} for d, v in m.items()]})
    return sorted(out, key=lambda r: (not r["level_measured"], -r["peak_rel"]))


# ------------------------------------------------------------------ S1
def te_nodes(S):
    W = S[(S.index >= Q_START) & (S.index <= Q_END)]
    return [c for c in W.columns if W[c].notna().sum() >= MIN_OVERLAP]


def te_edges(S, a, seed=SEED, n_surr=N_SURR):
    """Liens sortants du noeud a (une partie de l'etape par noeud source)."""
    rng = np.random.default_rng([seed, sum(map(ord, a))])
    W = S[(S.index >= Q_START) & (S.index <= Q_END)]
    nodes = te_nodes(S)
    rows = []
    for b in nodes:
        if a == b:
            continue
        pair = W[[a, b]].dropna()
        # Plus longue plage contigue commune (les trous casseraient les retards).
        gaps = np.diff(pd.to_datetime(pair.index).values).astype("timedelta64[D]").astype(int)
        cut = np.split(np.arange(len(pair)), np.nonzero(gaps > 1)[0] + 1)
        seg = max(cut, key=len)
        if len(seg) < MIN_OVERLAP:
            continue
        p = pair.iloc[seg]
        xc, yc = deseason(p[a], p.index), deseason(p[b], p.index)
        if np.std(xc) == 0 or np.std(yc) == 0:
            continue
        yd = tercile(yc)
        te, lag = te_max(xc, yd)
        null = [te_max(iaaft(xc, rng), yd)[0] for _ in range(n_surr)]
        if sum(x >= te for x in null) <= 4:   # lien prometteur : resolution plus fine
            null += [te_max(iaaft(xc, rng), yd)[0] for _ in range(5 * n_surr)]
        rows.append({"source": a, "target": b, "te_bits": round(te, 5), "lag_days": lag,
                     "te_excess": round(te - float(np.mean(null)), 5), "n_surrogates": len(null),
                     "p": (1 + sum(x >= te for x in null)) / (len(null) + 1),
                     "n_days": int(len(seg)), "start": p.index[0], "end": p.index[-1]})
    return rows


def te_network(S, edges, n_surr=N_SURR):
    rows = [r for part in edges for r in part]
    q = bh([r["p"] for r in rows])
    for r, v in zip(rows, q):
        r["p_fdr"] = round(float(v), 4)
        r["significant"] = bool(v < 0.05)
    return {"nodes": te_nodes(S), "edges": rows, "n_surrogates": n_surr, "lags": list(LAGS),
            "window": [Q_START, Q_END]}


# ------------------------------------------------------------------ S2
def weekly(s):
    s = s.copy()
    s.index = pd.to_datetime(s.index)
    return s.resample("W-MON", label="left", closed="left").sum(min_count=1)


def syncretism(conn, d, H, terms, est, seed=SEED, n_surr=300):
    rng = np.random.default_rng(seed)
    theme_wiki = dict(load_yaml("scene", "theme_wiki") or {})
    themes = [t for t in terms if (t.family in THEME_FAMILIES or t.id in THEME_GLOSSARY + THEME_ACTORS)
              and not t.ambiguous]
    day = d["ts"].dt.strftime("%Y-%m-%d")
    days_c = sampled_days(conn).get("conspiracy", set())
    wv = pd.read_sql_query("SELECT article, day, sum(views) v FROM wiki_scene_views GROUP BY 1, 2", conn)
    tr_weekly, _, _ = trends_series(conn)
    idx = _day_index(Q_START, Q_END)
    q_week_n = weekly(day.value_counts().reindex(idx, fill_value=0).astype(float))
    rows, tests = [], []
    for t in themes:
        n_q = int(H[t.id].sum())
        row = {"term": t.id, "label_fr": t.label_fr, "label_en": t.label_en, "family": t.family,
               "sensitive": t.sensitive, "q_drops": n_q, "measures": {}}
        if n_q < 10:
            row["verdict"] = "absent_q" if n_q == 0 else "rare_q"
            rows.append(row)
            continue
        q = weekly(day[H[t.id]].value_counts().reindex(idx, fill_value=0).astype(float))
        q_share = (q / q_week_n.where(q_week_n > 0)).fillna(0)
        measures = {}
        if len(days_c) >= MIN_OVERLAP:
            e = est[(est["sub"] == "conspiracy") & (est["term"] == t.id)].set_index("day")["est"]
            s = e.reindex(idx).fillna(0).where(pd.Index(idx).isin(days_c))
            measures["reddit:conspiracy"] = weekly(s)
        art = theme_wiki.get(t.id)
        if art and not wv.empty:
            measures[f"wiki:{art}"] = weekly(wv[wv["article"] == art].set_index("day")["v"].reindex(idx).astype(float))
        tq = t.trends_query or t.label_en
        if t.trends and tq in tr_weekly:
            measures[f"trends:{tq}"] = weekly(tr_weekly[tq].reindex(idx).astype(float))
        for name, m in measures.items():
            pair = pd.concat([q_share, np.log1p(m)], axis=1).dropna()
            if len(pair) < 52 or pair.iloc[:, 1].std() == 0:
                continue
            a, b = prewhiten(pair.iloc[:, 0].to_numpy()), prewhiten(pair.iloc[:, 1].to_numpy())
            lags = list(range(-8, 9))
            c = ccf(a, b, lags)
            i = int(np.argmax(np.abs(c)))
            null = np.array([np.abs(ccf(iaaft(a, rng), b, lags)).max() for _ in range(n_surr)])
            p = (1 + (null >= abs(c[i])).sum()) / (n_surr + 1)
            measures_row = {"weeks": int(len(pair)), "peak_lag_weeks": lags[i], "peak_r": round(float(c[i]), 3),
                            "r_lag0": round(float(c[lags.index(0)]), 3), "p": round(float(p), 4),
                            "ccf": [round(float(x), 3) for x in c]}
            row["measures"][name] = measures_row
            tests.append((row, name))
        rows.append(row)
    adj = bh([r["measures"][n]["p"] for r, n in tests])
    for (r, n), v in zip(tests, adj):
        m = r["measures"][n]
        m["p_fdr"] = round(float(v), 4)
        lag = m["peak_lag_weeks"]
        m["verdict"] = ("independant" if v >= 0.05 or m["peak_r"] <= 0 else
                        "q_mene" if lag > 0 else "q_suit" if lag < 0 else "synchrone")
    for r in rows:
        if "verdict" not in r:
            vs = {m.get("verdict") for m in r["measures"].values()} - {None}
            r["verdict"] = (vs.pop() if len(vs) == 1 else "mixte" if vs else "non_mesure")
    # Indice d'absorption : themes distincts par trimestre chez Q.
    qtr = d["et"].dt.year.astype(str) + "Q" + d["et"].dt.quarter.astype(str)
    present = H[[t.id for t in themes]]
    absorb = [{"quarter": k, "drops": int(len(g)), "themes": int((present.loc[g.index].sum() > 0).sum())}
              for k, g in d.groupby(qtr)]
    return {"themes": rows, "absorption": absorb, "n_surrogates": n_surr, "lags_weeks": list(range(-8, 9))}


# ------------------------------------------------------------------ S3
def response_function(conn, d, seed=SEED, n_null=500, before=24, after=48):
    rng = np.random.default_rng(seed)
    out = {}
    try:
        hr = pd.read_sql_query("SELECT * FROM reddit_hour", conn)
    except Exception:   # base anterieure a la collecte horaire
        return out
    t = np.sort(d["time"].to_numpy())
    starts = t[np.concatenate([[True], np.diff(t) > 30 * 60])]
    for sub, g in hr.groupby("sub"):
        s = g.set_index("hour")["n"]
        h0, h1 = int(s.index.min()), int(s.index.max())
        full = s.reindex(np.arange(h0, h1 + 3600, 3600), fill_value=0).to_numpy(dtype=float)
        ev = (starts[(starts >= h0 + before * 3600) & (starts < h1 - after * 3600)] - h0) // 3600
        if len(ev) < 20:
            continue

        def windows(e):
            W = np.stack([full[int(i) - before:int(i) + after + 1] for i in e])
            base = W[:, :before].mean(axis=1, keepdims=True)
            return W / np.maximum(base, 1.0)

        obs = windows(ev).mean(axis=0)
        # Modele nul : jours tires au hasard, heure de la journee tiree du profil des debuts de session.
        hours = (ev % 24).astype(int)
        nd = (len(full) - before - after - 48) // 24
        null = []
        for _ in range(n_null):
            e = (rng.integers(2, nd, size=len(ev)) * 24 + rng.choice(hours, size=len(ev)))
            e = e[(e >= before) & (e < len(full) - after - 1)]
            null.append(windows(e).mean(axis=0))
        null = np.array(null)
        lo, hi = np.quantile(null, [0.025, 0.975], axis=0)
        k = np.arange(-before, after + 1)
        post = slice(before + 1, before + 7)
        out[sub] = {"n_events": int(len(ev)), "curve": [{"h": int(a), "obs": round(float(b), 4), "null_lo": round(float(c), 4),
                                                          "null_hi": round(float(e), 4)} for a, b, c, e in zip(k, obs, lo, hi)],
                    "excess_6h": round(float(obs[post].mean() - null[:, post].mean()), 4),
                    "p_6h": round(float((1 + (null[:, post].mean(axis=1) >= obs[post].mean()).sum()) / (len(null) + 1)), 4),
                    "peak_h": int(k[before + 1 + int(np.argmax(obs[before + 1:]))])}
    return out


# ------------------------------------------------------------------ P2
def attention_peaks(S, conn, d, n_peaks=3, sep=90):
    ev = load_events(conn)
    ev_dates = pd.to_datetime(ev["date"])
    qday = d["ts"].dt.strftime("%Y-%m-%d").value_counts()
    out = []
    for name in S.columns:
        if name in ("Q", "Trump", "GDELT:US"):
            continue
        s = S[name].dropna()
        if len(s) < 180:
            continue
        v = s.to_numpy()
        roll = pd.Series(v).rolling(61, center=True, min_periods=20).median().to_numpy()
        score = v / np.maximum(roll, 1)
        taken = []
        for i in np.argsort(score)[::-1]:
            if len(taken) == n_peaks:
                break
            if i < 60 or i > len(v) - 46 or any(abs(i - j) < sep for j in taken):
                continue
            taken.append(i)
            r = endo_exo(v, i)
            if not r:
                continue
            day = pd.Timestamp(s.index[i])
            near = ev[(ev_dates - day).abs() <= pd.Timedelta(days=7)]
            q7 = int(sum(qday.get((day - pd.Timedelta(days=k)).strftime("%Y-%m-%d"), 0) for k in range(1, 8)))
            out.append({"series": name, "day": s.index[i], "ratio_to_median": round(float(score[i]), 1), **r,
                        "events": near[["date", "label_fr", "label_en"]].to_dict("records"), "q_drops_7d_before": q7})
    return out


# ------------------------------------------------------------------ P6
def diffusion(conn, d, H, terms, est):
    """Formules forgees par Q : premier usage par Q, premiere occurrence dans l'echantillon
    Reddit, diffusion de Bass sur les mentions estimees (tous subreddits)."""
    coined = [t for t in terms if (t.source == "glossary" or t.family == "q_core") and not t.ambiguous]
    rows = []
    for t in coined:
        hits = H[t.id]
        if hits.sum() < 3:
            continue
        first_q = d.loc[hits, "ts"].min()
        e = est[est["term"] == t.id]
        row = {"term": t.id, "label_fr": t.label_fr, "label_en": t.label_en, "q_drops": int(hits.sum()),
               "first_q": first_q.strftime("%Y-%m-%d")}
        if not e.empty:
            first_r = e[e["hits"] > 0]["day"].min()
            row["first_reddit_sample"] = first_r
            row["lag_days"] = int((pd.Timestamp(first_r, tz="UTC") - first_q.normalize()).days) if first_r else None
            m = e.assign(m=e["day"].str[:7]).groupby("m")["est"].sum()
            start = max(first_q.strftime("%Y-%m"), m.index.min())
            months = pd.period_range(start, "2023-12", freq="M").astype(str)
            y = m.reindex(months, fill_value=0).to_numpy()
            if y.sum() >= 50 and (y > 0).sum() >= 6:
                row["bass"] = {k: (round(v, 4) if v is not None else None) for k, v in bass_fit(y).items()}
                row["monthly"] = [{"month": a, "est": round(float(b), 1)} for a, b in zip(months, y)]
        rows.append(row)
    return rows


# ------------------------------------------------------------------ etape
def run(ctx):
    d = load_drops(ctx.conn)
    tweets = load_tweets(ctx.conn)
    terms = lexicon.load()
    H = drop_hits(d, terms)
    est = reddit_estimates(ctx.conn)
    S = daily_series(ctx.conn, d, tweets, est)
    nodes = te_nodes(S)
    parts = [(f"te:{a}", (lambda a=a: te_edges(S, a))) for a in nodes]
    parts += [("syncretism", lambda: syncretism(ctx.conn, d, H, terms, est)),
             ("response", lambda: response_function(ctx.conn, d)),
             ("peaks", lambda: attention_peaks(S, ctx.conn, d)),
             ("diffusion", lambda: diffusion(ctx.conn, d, H, terms, est)),
             ("trends", lambda: trends_summary(ctx.conn))]
    acc = run_parts(ctx, "scene", parts)
    if acc is None:
        return False
    cov = pd.read_sql_query("SELECT sub, count(DISTINCT day) days FROM reddit_sample_day GROUP BY 1", ctx.conn)
    vol = pd.read_sql_query("SELECT sub, count(DISTINCT day) days FROM reddit_volume GROUP BY 1", ctx.conn)
    coverage = {r["sub"]: {"sampled_days": int(r["days_x"]), "active_days": int(r["days_y"])}
                for _, r in cov.merge(vol, on="sub", how="right").fillna(0).iterrows()}
    te = te_network(S, [acc.pop(f"te:{a}") for a in nodes])
    out = {"coverage": coverage, "lexicon": lexicon.fingerprint(terms), "te": te, **acc}
    ctx.set_output(db.sha(write(ctx, "scene", out)))
    sig = [e for e in te["edges"] if e["significant"]]
    verdicts = pd.Series([t["verdict"] for t in acc["syncretism"]["themes"]]).value_counts().to_dict()
    log(f"scene : {len(sig)} liens d'information significatifs sur {len(te['edges'])} ; "
        f"themes : {verdicts} ; couverture Reddit {sum(c['sampled_days'] for c in coverage.values())} jours")
    return True

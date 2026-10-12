"""Q et l'actualite mondiale (GDELT 1.0).

Pour chaque acteur du dictionnaire ayant des noms GDELT, et pour chaque pays :
- surrepresentation : part de l'acteur dans les mentions de Q rapportee a sa
  part dans le volume d'evenements GDELT (meme ensemble d'acteurs) ;
- dynamique : correlations hebdomadaires decalees (-4 a +4 semaines) sur les
  variations de log(1 + n), et test de Granger dans les deux sens.
Periode : du premier drop au 8 decembre 2020 (fin de l'activite reguliere)."""
import warnings

import numpy as np
import pandas as pd

from .. import db
from ..log import log
from .actors import mentions
from .common import load_drops, load_yaml, write

START, END = "2017-10-30", "2020-12-07"   # lundis
LAGS = range(-4, 5)


def weekly(series):
    s = series.copy()
    s.index = pd.to_datetime(s.index)
    return s.resample("W-MON", label="left", closed="left").sum().loc[START:END]


def dynamics(q, g):
    """q, g : series hebdomadaires alignees. Correlations decalees sur les
    differences de log1p ; lag > 0 = l'actualite precede Q."""
    dq, dg = np.log1p(q).diff(), np.log1p(g).diff()
    out = {"rho0": _spear(q, g), "xcorr": []}
    for lag in LAGS:
        c = dq.corr(dg.shift(lag))
        out["xcorr"].append({"lag": lag, "r": None if pd.isna(c) else round(float(c), 3)})
    best = max((x for x in out["xcorr"] if x["r"] is not None), key=lambda x: abs(x["r"]), default=None)
    out["best_lag"] = best
    out["granger_news_to_q"] = _granger(dq, dg)
    out["granger_q_to_news"] = _granger(dg, dq)
    return out


def _spear(a, b):
    c = a.corr(b, method="spearman")
    return None if pd.isna(c) else round(float(c), 3)


def _granger(y, x, maxlag=2):
    """p-value du test F : x aide-t-il a prevoir y ?"""
    from statsmodels.tsa.stattools import grangercausalitytests
    df = pd.concat([y, x], axis=1).dropna()
    if len(df) < 30 or df.iloc[:, 0].std() == 0 or df.iloc[:, 1].std() == 0:
        return None
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        res = grangercausalitytests(df.to_numpy(), maxlag=maxlag, verbose=False)
    return round(float(min(r[0]["ssr_ftest"][1] for r in res.values())), 4)


def run(ctx):
    actors = load_yaml("actors", "actors")
    d = load_drops(ctx.conn)
    d = d[(d["ts"] >= pd.Timestamp(START, tz="UTC")) & (d["ts"] < pd.Timestamp(END, tz="UTC") + pd.Timedelta(days=7))]
    day = d["ts"].dt.tz_convert("UTC").dt.strftime("%Y-%m-%d")
    M = mentions(d, actors)
    M.index = day.to_numpy()
    q_daily = M.groupby(level=0).sum()

    gday = pd.read_sql_query("SELECT * FROM gdelt_day", ctx.conn).set_index("day")
    # Seuls les noms du dictionnaire sont lus : la table compte des millions de lignes.
    wanted = sorted({n for a in actors for n in a.get("gdelt", [])})
    names = pd.read_sql_query(f"SELECT day, name, events FROM gdelt_name WHERE name IN ({','.join('?' * len(wanted))})",
                              ctx.conn, params=wanted) if wanted else pd.DataFrame(columns=["day", "name", "events"])
    gname = names.pivot_table(index="day", columns="name", values="events", aggfunc="sum", fill_value=0)

    q_week_total = weekly(pd.Series(1, index=day.to_numpy()).groupby(level=0).sum())
    g_week_total = weekly(gday["events"])

    rows = []
    for a in actors:
        gn = [n for n in a.get("gdelt", []) if n in gname.columns]
        if not gn or a["id"] not in q_daily or a["category"] == "country":
            continue
        q = weekly(q_daily[a["id"]]).reindex(g_week_total.index, fill_value=0)
        g = weekly(gname[gn].sum(axis=1)).reindex(g_week_total.index, fill_value=0)
        if q.sum() < 10:
            continue
        rows.append({"id": a["id"], "name": a["name"], "category": a["category"], "gdelt_names": gn,
                     "q": int(q.sum()), "news": int(g.sum()), **dynamics(q, g),
                     "series": [{"week": w.date().isoformat(), "q": int(x), "news": int(y)}
                                for w, x, y in zip(q.index, q, g)]})
    if rows:
        qs, ns = sum(r["q"] for r in rows), sum(r["news"] for r in rows)
        for r in rows:
            r["q_share"], r["news_share"] = r["q"] / qs, r["news"] / ns
            r["overrep"] = round(r["q_share"] / r["news_share"], 2) if r["news_share"] else None
    rows.sort(key=lambda r: -r["q"])

    # Pays : volume GDELT (lieu de l'action) contre mentions de Q.
    gc = pd.read_sql_query("SELECT fips, sum(events) AS events FROM gdelt_country "
                           "WHERE day BETWEEN ? AND ? GROUP BY fips", ctx.conn, params=(START, END))
    gc = dict(zip(gc["fips"], gc["events"]))
    countries = []
    for a in actors:
        if a["category"] != "country" or a["id"] not in M:
            continue
        countries.append({"id": a["id"], "name": a["name"], "iso3": a.get("iso3"), "fips": a.get("fips"),
                          "q": int(M[a["id"]].sum()), "news": int(gc.get(a.get("fips"), 0))})
    countries = [c for c in countries if c["news"]]
    if countries:
        qs, ns = sum(c["q"] for c in countries), sum(c["news"] for c in countries)
        for c in countries:
            c["overrep"] = round((c["q"] / qs) / (c["news"] / ns), 2) if c["q"] else 0.0
        cdf = pd.DataFrame(countries)
        country_rho = _spear(cdf["q"], cdf["news"])
    else:
        country_rho = None
    countries.sort(key=lambda c: -c["q"])

    out = {"period": [START, END], "n_weeks": int(len(g_week_total)), "actors": rows, "countries": countries,
           "country_rho": country_rho, "total": dynamics(q_week_total.reindex(g_week_total.index, fill_value=0),
                                                         g_week_total),
           "gdelt_days": int(len(gday)), "gdelt_events": int(gday["events"].sum())}
    ctx.set_output(db.sha(write(ctx, "news", out)))
    log(f"analyse Q/actualite : {len(rows)} acteurs et {len(countries)} pays compares a GDELT")
    return True

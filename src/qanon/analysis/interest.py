"""Interet public (pages vues Wikipedia) et activite de Q."""
import numpy as np
import pandas as pd

from .. import db
from ..log import log
from .common import ET, load_drops, load_events, write


def run(ctx):
    pv = pd.read_sql_query("SELECT * FROM pageviews", ctx.conn)
    if pv.empty:
        raise RuntimeError("aucune page vue en base")
    pv["day"] = pd.to_datetime(pv["day"])
    pv["key"] = pv["project"].str.split(".").str[0] + ":" + pv["article"]
    d = load_drops(ctx.conn)
    drops_day = d["et"].dt.tz_localize(None).dt.normalize().value_counts().sort_index()

    weekly = (pv.set_index("day").groupby("key")["views"].resample("W-MON", label="left", closed="left")
              .sum().reset_index())
    weekly_rows = [{"key": k, "week": w.date().isoformat(), "views": int(v)}
                   for k, w, v in weekly[["key", "day", "views"]].itertuples(index=False)]
    totals = pv.groupby("key")["views"].agg(["sum", "max"]).reset_index()
    peaks = pv.loc[pv.groupby("key")["views"].idxmax(), ["key", "day", "views"]]
    articles = []
    for k, tot, mx in totals.itertuples(index=False):
        pk = peaks[peaks["key"] == k].iloc[0]
        first = pv[(pv["key"] == k) & (pv["views"] > 0)]["day"].min()
        articles.append({"key": k, "total": int(tot), "peak": int(mx), "peak_day": pk["day"].date().isoformat(),
                         "first_day": first.date().isoformat() if pd.notna(first) else None})

    # Etude d'evenements : vues de l'article anglais "QAnon" 7 jours apres vs 7 jours avant.
    en = pv[pv["key"] == "en:QAnon"].set_index("day")["views"]
    events = []
    for e in load_events(ctx.conn).itertuples():
        t = pd.Timestamp(e.date)
        before = en[(en.index >= t - pd.Timedelta(days=7)) & (en.index < t)]
        after = en[(en.index >= t) & (en.index < t + pd.Timedelta(days=7))]
        if len(before) == 7 and len(after) == 7 and before.sum() > 0:
            events.append({"id": e.id, "date": e.date, "category": e.category, "label_fr": e.label_fr,
                           "label_en": e.label_en, "before": int(before.sum()), "after": int(after.sum()),
                           "ratio": round(float(after.sum() / before.sum()), 2)})
    events.sort(key=lambda x: -x["ratio"])

    # Q fait-il monter l'interet ? Correlation (Spearman) hebdomadaire drops / vues,
    # sur la periode active (avant le 8 dec. 2020).
    w_drops = drops_day.resample("W-MON", label="left", closed="left").sum()
    w_en = en.resample("W-MON", label="left", closed="left").sum()
    j = pd.concat([w_drops.rename("drops"), w_en.rename("views")], axis=1).dropna()
    j = j[(j.index >= "2018-01-01") & (j.index < "2020-12-07")]
    lags = []
    for lag in range(-4, 5):
        c = j["drops"].corr(j["views"].shift(-lag), method="spearman")
        lags.append({"lag_weeks": lag, "rho": round(float(c), 3) if pd.notna(c) else None})

    out = {"weekly": weekly_rows, "articles": sorted(articles, key=lambda a: -a["total"]),
           "events": events, "lags": lags, "n_weeks": int(len(j))}
    ctx.set_output(db.sha(write(ctx, "interest", out)))
    log(f"analyse interet public : {len(articles)} articles, {len(events)} evenements etudies")
    return True

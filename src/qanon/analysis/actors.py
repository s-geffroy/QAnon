"""Acteurs cites dans les drops (dictionnaire data/actors.yaml) : frequences,
evolution, co-mentions, pays."""
import itertools
import re
from collections import Counter

import pandas as pd

from .. import db
from ..log import log
from .common import load_drops, load_yaml, month, write


def mentions(d, actors):
    """DataFrame booleen drops x acteurs (l'acteur est-il cite dans le drop ?)."""
    cols = {}
    for a in actors:
        rx = re.compile("|".join(f"(?:{p})" for p in a["patterns"]))
        cols[a["id"]] = d["text"].map(lambda t, rx=rx: bool(rx.search(t or "")))
    return pd.DataFrame(cols, index=d.index)


def run(ctx):
    actors = load_yaml("actors", "actors")
    d = load_drops(ctx.conn)
    if not actors:
        ctx.set_output(db.sha(write(ctx, "actors", {"actors": []})))
        log("analyse des acteurs : dictionnaire absent")
        return True
    M = mentions(d, actors)
    months = month(d["ts"])
    meta = {a["id"]: a for a in actors}
    counts = M.sum().sort_values(ascending=False)
    rows = []
    for aid, n in counts.items():
        if not n:
            continue
        a = meta[aid]
        hit = M[aid]
        first = d.loc[hit, "ts"].min()
        rows.append({"id": aid, "name": a["name"], "category": a["category"],
                     "role_fr": a.get("role_fr"), "role_en": a.get("role_en"),
                     "iso3": a.get("iso3"), "n": int(n), "share": float(n / len(d)),
                     "first": first.date().isoformat(), "last": d.loc[hit, "ts"].max().date().isoformat()})

    top = [r["id"] for r in rows[:25]]
    quarter = d["et"].dt.tz_localize(None).dt.to_period("Q").astype(str)
    by_q = M[top].groupby(quarter).sum()
    timeline = [{"quarter": q, "id": aid, "n": int(v)} for q, r in by_q.iterrows() for aid, v in r.items()]
    monthly = M.groupby(months).sum()
    monthly_rows = [{"month": m, "id": aid, "n": int(v)} for m, r in monthly.iterrows() for aid, v in r.items() if v]

    # Co-mentions : paires d'acteurs cites dans un meme drop, et force de
    # l'association (PMI normalise : 1 = toujours ensemble, 0 = independants).
    pair = Counter()
    for row in M.itertuples(index=False):
        ids = [aid for aid, v in zip(M.columns, row) if v]
        for a, b in itertools.combinations(sorted(ids), 2):
            pair[(a, b)] += 1
    import math
    N = len(d)
    edges = []
    for (a, b), n in pair.most_common():
        if n < 5:
            break
        pa, pb, pab = counts[a] / N, counts[b] / N, n / N
        npmi = math.log(pab / (pa * pb)) / -math.log(pab)
        edges.append({"a": a, "b": b, "n": n, "npmi": round(npmi, 3)})

    countries = [r for r in rows if r["category"] == "country"]
    out = {"n_drops": N, "n_actors": len(actors), "actors": rows, "timeline": timeline, "top": top,
           "monthly": monthly_rows, "edges": edges[:300], "countries": countries,
           "share_with_actor": float(M.any(axis=1).mean())}
    ctx.set_output(db.sha(write(ctx, "actors", out)))
    log(f"analyse des acteurs : {len(rows)} acteurs cites, {len(edges)} paires (>= 5 drops)")
    return True

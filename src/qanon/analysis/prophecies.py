"""Prophéties recyclees et « Future proves past ».

1. Recyclage : les predictions extraites sont regroupees par sujet (meme type
   d'evenement, meme acteur du dictionnaire). Un sujet annonce sur au moins
   trois mois distincts est « recycle » ; on compte les annonces faites apres
   une echeance deja depassee et verifiee non realisee.
2. « Future proves past » : quand Q renvoie a l'un de ses propres drops, combien
   de temps s'est ecoule, le drop cite contenait-il une prediction, et
   laquelle a ete verifiee comment ?"""
import json
import re
from collections import Counter

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer

from .. import db
from ..log import log
from .common import load_drops, write

MIN_MONTHS = 3            # un sujet annonce sur au moins 3 mois distincts est « recycle »
FPP = re.compile(r"future\s+prove[sd]?\s+(?:the\s+)?past|\bFPP\b", re.I)


def _norm(claim):
    t = re.sub(r"^Q (?:claims|says|predicts|announces|suggests|implies|asserts|states|hints)( that)?\s*", "", claim)
    return t


def recycled(preds, verdicts):
    """Meme type d'evenement annonce pour le meme acteur sur au moins MIN_MONTHS mois differents."""
    P = pd.DataFrame(preds)
    P["key"] = P["drop_id"].astype(str) + "-" + P["k"].astype(str)
    P["verdict"] = P["key"].map(lambda k: verdicts.get(k, {}).get("verdict"))
    P["vdeadline"] = P["key"].map(lambda k: verdicts.get(k, {}).get("horizon"))
    E = P.explode("actor_ids").dropna(subset=["actor_ids"]).rename(columns={"actor_ids": "actor"})
    E = E[(E["actor"] != "usa") & (E["event_type"] != "other")]
    groups = []
    for (et, actor), g in E.groupby(["event_type", "actor"]):
        g = g.sort_values("date")
        if len(g) < 3 or g["month"].nunique() < MIN_MONTHS:
            continue
        failed = g[(g["verdict"] == "not_fulfilled") & g["vdeadline"].astype(str).str.match(r"^\d{4}-\d{2}-\d{2}$")]
        first_fail = failed["vdeadline"].min() if len(failed) else None
        after = int((g["date"] > first_fail).sum()) if first_fail else 0
        texts = g["claim"].map(_norm).tolist()
        X = TfidfVectorizer(stop_words="english", sublinear_tf=True).fit_transform(texts)
        centre = int(np.argmax(np.asarray((X @ X.T).mean(axis=1)).ravel()))
        groups.append({
            "event_type": et, "actor": actor, "n": len(g), "n_drops": int(g["drop_id"].nunique()),
            "first": g["date"].iloc[0], "last": g["date"].iloc[-1],
            "span_days": int((pd.Timestamp(g["date"].iloc[-1]) - pd.Timestamp(g["date"].iloc[0])).days),
            "months": int(g["month"].nunique()), "claim": g["claim"].iloc[centre],
            "n_deadlines": int(g["deadline"].notna().sum()),
            "verdicts": dict(Counter(v for v in g["verdict"] if v)),
            "first_failed_deadline": first_fail, "after_failure": after,
            "drop_ids": [int(x) for x in g["drop_id"]], "dates": g["date"].tolist(),
        })
    groups.sort(key=lambda x: (-x["n"], x["first"]))
    keys = {k for et, a in ((x["event_type"], x["actor"]) for x in groups)
            for k in E[(E["event_type"] == et) & (E["actor"] == a)]["key"]}
    return {"min_months": MIN_MONTHS, "n_predictions": len(P), "n_groups": len(groups),
            "n_in_groups": len(keys), "share_in_groups": round(len(keys) / len(P), 4) if len(P) else 0,
            "n_after_failure": sum(x["after_failure"] for x in groups),
            "n_groups_after_failure": sum(x["after_failure"] > 0 for x in groups), "groups": groups}


def future_proves_past(d, preds, verdicts):
    by_post = {str(p): i for p, i in zip(d["post_id"], d["id"]) if p}
    ts = d.set_index("id")["ts"]
    pred_drops = {p["drop_id"] for p in preds}
    keys_by_drop = {}
    for p in preds:
        keys_by_drop.setdefault(p["drop_id"], []).append(f"{p['drop_id']}-{p['k']}")
    rows = []
    for _, r in d.iterrows():
        refs = json.loads(r["refs_json"]) if r["refs_json"] else []
        for x in refs:
            j = by_post.get(str(x.get("post_id") or "").strip())
            if j is None or j == r["id"]:
                continue
            lag = (r["ts"] - ts[j]).total_seconds() / 86400
            vs = [verdicts[k]["verdict"] for k in keys_by_drop.get(j, []) if k in verdicts]
            rows.append({"drop": int(r["id"]), "cited": int(j), "lag_days": lag, "fpp": bool(FPP.search(r["text"] or "")),
                         "cited_pred": j in pred_drops, "verdicts": vs})
    R = pd.DataFrame(rows)
    if R.empty:
        return {"n": 0}
    late = R[R["lag_days"] >= 1]
    bins = [(0, 1 / 24, "< 1 h"), (1 / 24, 1, "1 h – 1 j"), (1, 7, "1–7 j"), (7, 30, "7–30 j"),
            (30, 180, "1–6 mois"), (180, 10 ** 5, "> 6 mois")]
    vc = Counter(v for vs in R["verdicts"] for v in vs)
    fpp = R[R["fpp"]]
    return {
        "n": len(R), "n_citing_drops": int(R["drop"].nunique()), "n_cited_drops": int(R["cited"].nunique()),
        "lag_median_days": round(float(R["lag_days"].median()), 2),
        "share_same_day": round(float((R["lag_days"] < 1).mean()), 4),
        "share_over_30d": round(float((R["lag_days"] >= 30).mean()), 4),
        "share_cited_pred": round(float(R["cited_pred"].mean()), 4),
        "share_cited_pred_late": round(float(late["cited_pred"].mean()), 4) if len(late) else None,
        "n_late": len(late),
        "lag_bins": [{"label": lab, "n": int(((R["lag_days"] >= a) & (R["lag_days"] < b)).sum())} for a, b, lab in bins],
        "verdicts_cited": dict(vc),
        "n_fpp_text": int(d["text"].fillna("").str.contains(FPP).sum()),
        "fpp_refs": len(fpp), "fpp_lag_median_days": round(float(fpp["lag_days"].median()), 1) if len(fpp) else None,
        "fpp_share_cited_pred": round(float(fpp["cited_pred"].mean()), 4) if len(fpp) else None,
    }


def run(ctx):
    d = load_drops(ctx.conn)
    preds = json.loads((ctx.results / "predictions_all.json").read_text())["predictions"]
    vpath = ctx.results / "verification.json"
    verdicts = {x["key"]: x for x in json.loads(vpath.read_text()).get("items", [])} if vpath.exists() else {}
    out = {"recycled": recycled(preds, verdicts), "fpp": future_proves_past(d, preds, verdicts)}
    ctx.set_output(db.sha(write(ctx, "prophecies", out)))
    r, f = out["recycled"], out["fpp"]
    log(f"propheties : {r['n_groups']} groupes recycles ({r['n_in_groups']} predictions), "
        f"{r['n_after_failure']} annonces apres echec ; autocitations {f.get('n')}, delai median {f.get('lag_median_days')} j")
    return True

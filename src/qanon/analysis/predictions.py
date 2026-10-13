"""Predictions extraites du corpus par le modele retenu (table llm_class)."""
import json
import re
from collections import Counter

import pandas as pd

from .. import db
from ..log import log
from .common import ET, load_drops, load_yaml, write


def subject_actor(subject, actors):
    """Rattache un sujet libre ("Hillary Clinton", "HRC", "the FBI") a un acteur du dictionnaire."""
    for a in actors:
        if subject.strip().lower() == a["name"].lower():
            return a["id"]
    for a in actors:
        for p in a["patterns"]:
            if re.search(p, subject):
                return a["id"]
    return None


def run(ctx):
    d = load_drops(ctx.conn).set_index("id")
    rows = ctx.conn.execute("SELECT drop_id, model, response, error FROM llm_class").fetchall()
    actors = load_yaml("actors", "actors")
    names = {a["id"]: a["name"] for a in actors}
    preds, drops_flag, errors = [], {}, 0
    model = rows[0]["model"] if rows else None
    for r in rows:
        if r["error"] or not r["response"]:
            errors += 1
            continue
        ans = json.loads(r["response"])
        drops_flag[r["drop_id"]] = bool(ans["is_prediction"])
        if not ans["is_prediction"]:
            continue
        ts = d.loc[r["drop_id"], "et"]
        for k, p in enumerate(ans["predictions"]):
            ids = [subject_actor(s, actors) for s in p["subjects"]]
            preds.append({"drop_id": int(r["drop_id"]), "k": k, "date": ts.date().isoformat(),
                          "month": ts.strftime("%Y-%m"), **p,
                          "actor_ids": sorted({i for i in ids if i})})
    P = pd.DataFrame(preds)
    flags = pd.Series(drops_flag)
    month = d.loc[flags.index, "et"].dt.strftime("%Y-%m")
    monthly = (pd.DataFrame({"month": month, "pred": flags.astype(int)}).groupby("month")
               .agg(n=("pred", "size"), pred=("pred", "sum")).reset_index())
    monthly["share"] = (monthly["pred"] / monthly["n"]).round(4)

    actor_counts = Counter(a for ids in P["actor_ids"] for a in ids) if len(P) else Counter()
    explicit = P[P["deadline"].notna()].sort_values("deadline") if len(P) else P
    # Horizon : delai entre le drop et l'echeance (dates completes seulement).
    horizon = []
    if len(P):
        full = P[P["deadline"].astype(str).str.match(r"^\d{4}-\d{2}-\d{2}$")]
        days = (pd.to_datetime(full["deadline"]) - pd.to_datetime(full["date"])).dt.days
        horizon = [int(x) for x in days if x >= 0]
    hz = pd.Series(horizon, dtype=float)
    # Echeances depassees a la date du dernier drop actif : base de la verification.
    out = {
        "model": model, "n_annotated": len(drops_flag), "n_errors": errors,
        "n_pred_drops": int(flags.sum()), "share_pred_drops": float(flags.mean()) if len(flags) else 0,
        "n_predictions": len(P),
        "by_type": Counter(P["event_type"]).most_common() if len(P) else [],
        "by_specificity": Counter(P["specificity"]).most_common() if len(P) else [],
        "by_deadline_type": Counter(P["deadline_type"]).most_common() if len(P) else [],
        "monthly": monthly.to_dict("records"),
        "horizon": {"n": len(horizon), "median_days": float(hz.median()) if len(hz) else None,
                    "share_7d": float((hz <= 7).mean()) if len(hz) else None,
                    "share_30d": float((hz <= 30).mean()) if len(hz) else None,
                    "bins": [{"label": lab, "n": int(((hz >= lo) & (hz <= hi)).sum())} for lab, lo, hi in
                             (("0-1", 0, 1), ("2-7", 2, 7), ("8-30", 8, 30), ("31-90", 31, 90),
                              ("91-365", 91, 365), ("365+", 366, 10 ** 6))]},
        "by_year": (P.assign(year=P["date"].str[:4]).groupby(["year", "specificity"]).size()
                    .reset_index(name="n").to_dict("records")) if len(P) else [],
        "actors": [{"id": a, "name": names.get(a, a), "n": n} for a, n in actor_counts.most_common(40)],
        "explicit": explicit[["drop_id", "k", "date", "deadline", "event_type", "specificity", "claim", "subjects"]]
                    .to_dict("records") if len(P) else [],
        "specific": P[P["specificity"] == "specific"][["drop_id", "k", "date", "deadline", "deadline_type", "event_type",
                                                       "claim", "subjects"]].to_dict("records") if len(P) else [],
    }
    write(ctx, "predictions_all", {"predictions": preds})
    ctx.set_output(db.sha(write(ctx, "predictions", out)))
    log(f"analyse des predictions : {out['n_predictions']} predictions dans {out['n_pred_drops']} drops "
        f"sur {out['n_annotated']} ({out['share_pred_drops']:.0%}), {len(out['specific'])} precises")
    return True

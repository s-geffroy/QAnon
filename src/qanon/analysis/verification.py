"""Verification des predictions : verdicts editoriaux (data/verification/*.yaml),
etablis un par un avec sources, joints aux predictions extraites."""
import json
import math
from collections import Counter

import yaml

from .. import db
from ..log import log
from ..pipeline import APP_DIR
from .common import write

VERDICTS = ["fulfilled", "partial", "not_fulfilled", "unverifiable", "not_a_prediction"]


def wilson(k, n, z=1.96):
    """Intervalle de confiance de Wilson (1927) a 95 % pour une proportion k/n."""
    if not n:
        return None, None
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return round(max(0.0, centre - half), 4), round(min(1.0, centre + half), 4)


def rate(items):
    """Taux de realisation parmi les predictions verifiables (partielles comptees a part)."""
    c = Counter(x["verdict"] for x in items)
    checkable = c["fulfilled"] + c["partial"] + c["not_fulfilled"]
    return {"n": len(items), **{v: c[v] for v in VERDICTS}, "checkable": checkable,
            "rate": round(c["fulfilled"] / checkable, 4) if checkable else None,
            "rate_with_partial": round((c["fulfilled"] + c["partial"]) / checkable, 4) if checkable else None,
            "rate_ci": wilson(c["fulfilled"], checkable),
            "rate_with_partial_ci": wilson(c["fulfilled"] + c["partial"], checkable)}


def run(ctx):
    preds = {f"{p['drop_id']}-{p['k']}": p
             for p in json.loads((ctx.results / "predictions_all.json").read_text())["predictions"]}
    items = []
    for f in sorted((APP_DIR / "data" / "verification").glob("part-*.yaml")):
        for x in yaml.safe_load(f.read_text())["items"]:
            p = preds.get(x["key"])
            if p is None:
                log(f"verification : cle {x['key']} absente des predictions, ignoree")
                continue
            items.append({**x, "drop_id": p["drop_id"], "date": p["date"], "claim": p["claim"],
                          "event_type": p["event_type"], "specificity": p["specificity"],
                          "deadline": p["deadline"], "subjects": p["subjects"],
                          "trivial": bool(x.get("trivial")), "sources": x.get("sources") or []})
    if not items:
        ctx.set_output(db.sha(write(ctx, "verification", {"items": []})))
        log("verification : aucun verdict")
        return True
    preds_only = [x for x in items if x["verdict"] != "not_a_prediction"]
    nontrivial = [x for x in preds_only if not x["trivial"]]
    group = lambda key: {k: rate([x for x in preds_only if key(x) == k])
                         for k in sorted({key(x) for x in preds_only})}
    out = {
        "n_items": len(items), "overall": rate(preds_only), "nontrivial": rate(nontrivial),
        "n_trivial": sum(x["trivial"] for x in preds_only),
        "n_not_a_prediction": sum(x["verdict"] == "not_a_prediction" for x in items),
        "by_type": group(lambda x: x["event_type"]), "by_year": group(lambda x: x["date"][:4]),
        "by_specificity": group(lambda x: x["specificity"]),
        "items": sorted(items, key=lambda x: (x["date"], x["key"])),
    }
    ctx.set_output(db.sha(write(ctx, "verification", out)))
    o = out["overall"]
    log(f"verification : {len(items)} verdicts ; realisees {o['fulfilled']}, partielles {o['partial']}, "
        f"non realisees {o['not_fulfilled']}, invérifiables {o['unverifiable']} ; "
        f"taux {o['rate']} (hors triviales : {out['nontrivial']['rate']})")
    return True

"""Statistiques descriptives du corpus de drops."""
import re

from .. import db
from ..log import log
from .common import load_drops, load_events, write

URL = re.compile(r"https?://\S+")


def run(ctx):
    d = load_drops(ctx.conn)
    words = d["text"].str.split().str.len().fillna(0)
    days = d["et"].dt.date
    out = {
        "n": len(d),
        "n_q": int(d["author"].eq("Q").sum()),
        "first": d["ts"].min(), "last": d["ts"].max(),
        "active_days": int(days.nunique()),
        "span_days": int((d["ts"].max() - d["ts"].min()).days) + 1,
        "words_median": float(words.median()),
        "words_total": int(words.sum()),
        "share_images": float((d["n_images"] > 0).mean()),
        "share_refs": float((d["n_refs"] > 0).mean()),
        "share_links": float(d["text"].str.contains(URL).mean()),
        "share_questions": float(d["text"].str.contains(r"\?").mean()),
        "questions_per_drop": float(d["text"].str.count(r"\?").mean()),
        "share_empty": float(d["text"].str.strip().eq("").mean()),
        "max_day": {"date": str(days.value_counts().idxmax()), "n": int(days.value_counts().max())},
    }

    # Plateformes : premiere et derniere apparition, effectifs.
    plat = (d.groupby(["site", "board"])
              .agg(n=("id", "size"), first=("ts", "min"), last=("ts", "max"))
              .reset_index().sort_values("first"))
    out["platforms"] = plat.to_dict("records")

    # Serie hebdomadaire (semaines commencant le lundi, heure de New York).
    week = d["et"].dt.tz_localize(None).dt.to_period("W-SUN").dt.start_time
    weekly = week.value_counts().sort_index()
    full = weekly.reindex(
        __import__("pandas").date_range(weekly.index.min(), weekly.index.max(), freq="7D"), fill_value=0)
    out["weekly"] = [{"week": k.date().isoformat(), "n": int(v)} for k, v in full.items()]
    out["yearly"] = {str(k): int(v) for k, v in d["et"].dt.year.value_counts().sort_index().items()}

    # Rythme : heure x jour de la semaine, heure de New York.
    hw = d.groupby([d["et"].dt.dayofweek, d["et"].dt.hour]).size()
    out["hour_weekday"] = [{"dow": int(k[0]), "hour": int(k[1]), "n": int(v)} for k, v in hw.items()]

    # Silences les plus longs entre deux drops.
    gaps = d["ts"].diff().dt.total_seconds() / 86400
    top = gaps.nlargest(6)
    out["gaps"] = [{"days": round(float(g), 1), "from": d["ts"].iloc[i - 1], "to": d["ts"].iloc[i]}
                   for i, g in top.items()]

    out["events"] = load_events(ctx.conn).to_dict("records")
    ctx.set_output(db.sha(write(ctx, "descriptive", out)))
    log(f"analyse descriptive : {out['n']} drops sur {out['span_days']} jours")
    return True

"""Q et les tweets de Trump.

Q revendiquait des "deltas" : un drop suivi a quelques minutes d'un tweet de
Trump serait une preuve de coordination. On teste si ces coincidences sont plus
frequentes que le hasard, a frequence de tweets egale.

Deux modeles nuls, chacun tire N_PERM fois :
- "days" : chaque drop est decale d'un nombre entier de jours (1 a 14, avant ou
  apres). L'heure de la journee est conservee, mais pas la co-activite des
  jours de grosse actualite, ou les deux comptes publient davantage.
- "local" : chaque drop est decale de 30 min a 3 h. L'activite du jour et des
  heures voisines est conservee ; seul le synchronisme a quelques minutes est
  casse. C'est le bon temoin pour la revendication des "deltas".
"""
import itertools
import re

import numpy as np

from .. import db
from ..log import log
from .common import load_drops, load_tweets, write

WINDOWS = [60, 300, 600, 1800, 3600]
N_PERM = 1000
END = 1610064000  # 2021-01-08 : suspension du compte @realDonaldTrump
STATUS = re.compile(r"twitter\.com/realDonaldTrump/status(?:es)?/(\d+)", re.I)
HAS_STATUS = r"(?i)twitter\.com/realDonaldTrump/status"
DAY = 86400


def within(drops, tweets, w, after=True):
    """Part des drops ayant au moins un tweet dans la fenetre w (s) apres (ou avant)."""
    if after:
        i = np.searchsorted(tweets, drops, side="left")
        ok = i < len(tweets)
        gap = np.where(ok, tweets[np.minimum(i, len(tweets) - 1)] - drops, np.inf)
    else:
        i = np.searchsorted(tweets, drops, side="right") - 1
        ok = i >= 0
        gap = np.where(ok, drops - tweets[np.maximum(i, 0)], np.inf)
    return (gap <= w).mean()


def offsets_days(rng, n):
    return rng.integers(1, 15, size=n) * rng.choice([-1, 1], size=n) * DAY


def offsets_local(rng, n):
    return rng.integers(1800, 3 * 3600 + 1, size=n) * rng.choice([-1, 1], size=n)


NULLS = {"local": offsets_local, "days": offsets_days}


def run(ctx):
    d = load_drops(ctx.conn)
    t = load_tweets(ctx.conn)
    d = d[d["time"] < END]
    orig = t[(t["is_retweet"] == 0)]
    tw = np.sort(orig["time"].to_numpy())
    dr = d["time"].to_numpy()
    rng = np.random.default_rng(20171028)

    tests = []
    for (model, offsets), after, w in itertools.product(NULLS.items(), (True, False), WINDOWS):
        obs = within(dr, tw, w, after)
        null = np.array([within(dr + offsets(rng, len(dr)), tw, w, after) for _ in range(N_PERM)])
        tests.append({
            "null": model,
            "direction": "tweet_after_drop" if after else "tweet_before_drop",
            "window_s": w, "observed": float(obs),
            "expected": float(null.mean()), "null_p05": float(np.quantile(null, 0.05)),
            "null_p95": float(np.quantile(null, 0.95)),
            "ratio": float(obs / null.mean()) if null.mean() else None,
            "p_value": float(((null >= obs).sum() + 1) / (N_PERM + 1)),
        })

    # Distribution des ecarts tweet - drop sur +/- 60 min, observee et attendue.
    def hist(drops):
        lo = np.searchsorted(tw, drops - 3600)
        hi = np.searchsorted(tw, drops + 3600)
        diffs = np.concatenate([tw[a:b] - x for a, b, x in zip(lo, hi, drops)]) / 60
        return np.histogram(diffs, bins=np.arange(-60, 62, 2))[0]
    observed = hist(dr)
    expected = np.mean([hist(dr + offsets_local(rng, len(dr))) for _ in range(100)], axis=0)
    bins = [{"minute": int(m), "observed": int(o), "expected": round(float(e), 2)}
            for m, o, e in zip(range(-60, 60, 2), observed, expected)]

    # Drops qui citent un tweet de Trump : delai entre le tweet et sa citation.
    by_id = dict(zip(t["id"], t["time"]))
    quotes = []
    for _, row in d.iterrows():
        for sid in set(STATUS.findall(row["text"] or "")):
            if sid in by_id:
                quotes.append((row["time"] - by_id[sid]) / 60)
    q = np.array(quotes)

    out = {
        "n_drops": int(len(dr)), "n_tweets": int(len(tw)),
        "tweets_per_day": float(len(tw[(tw >= dr.min()) & (tw <= dr.max())]) / ((dr.max() - dr.min()) / DAY)),
        "tests": tests, "hist": bins, "n_perm": N_PERM,
        "quotes": {
            "n_links": int(sum(len(set(STATUS.findall(x or ""))) for x in d["text"])),
            "n_matched": int(len(q)),
            "n_drops": int(d["text"].str.contains(HAS_STATUS).sum()),
            "median_lag_min": float(np.median(q)) if len(q) else None,
            "share_within_60": float((q <= 60).mean()) if len(q) else None,
        },
        "delta_mentions": int(d["text"].str.contains(r"Δ|\bdelta\b", case=False).sum()),
    }
    ctx.set_output(db.sha(write(ctx, "trump", out)))
    t5 = next(x for x in tests if x["window_s"] == 300 and x["direction"] == "tweet_after_drop"
              and x["null"] == "local")
    log(f"analyse Q/Trump : tweet <5 min apres un drop {t5['observed']:.1%} "
        f"(hasard {t5['expected']:.1%}, p={t5['p_value']:.3f})")
    return True

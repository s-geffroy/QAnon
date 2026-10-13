"""Statistiques complementaires du corpus : rythme (intervalles, rafales,
sessions), ruptures de regime du volume, sources citees (domaines des liens),
renvois, references religieuses, lisibilite et richesse lexicale."""
import json
import re
from collections import Counter
from urllib.parse import urlparse

import numpy as np
import pandas as pd

from .. import db
from ..log import log
from .common import ET, clean, load_drops, load_events, write

SESSION_GAP_MIN = 30


# ------------------------------------------------------------------ rythme
def rhythm(d):
    ts = d["ts"].sort_values().reset_index(drop=True)
    gaps = ts.diff().dt.total_seconds().iloc[1:].to_numpy()
    mu, sd = gaps.mean(), gaps.std()
    # Rafales (Goh & Barabasi 2008) : B = 0 pour un processus de Poisson,
    # -1 pour un rythme regulier, vers 1 pour une activite en rafales.
    burst = (sd - mu) / (sd + mu)
    memory = float(np.corrcoef(gaps[:-1], gaps[1:])[0, 1])
    # Meme mesure sur les intervalles logarithmiques : moins sensible aux silences extremes.
    lg = np.log10(np.maximum(gaps, 1))
    memory_log = float(np.corrcoef(lg[:-1], lg[1:])[0, 1])
    minutes = gaps / 60
    edges = np.logspace(np.log10(1 / 60), np.log10(minutes.max() * 1.01), 41)
    hist, _ = np.histogram(np.maximum(minutes, 1 / 60), bins=edges)
    # Sessions : drops separes de moins de SESSION_GAP_MIN minutes.
    sid = np.cumsum(np.concatenate([[True], minutes > SESSION_GAP_MIN]))
    sess = pd.DataFrame({"sid": sid, "ts": ts})
    g = sess.groupby("sid")["ts"]
    sizes = g.size()
    span = (g.max() - g.min()).dt.total_seconds() / 60
    size_dist = sizes.value_counts().sort_index()
    # Sensibilite au seuil de session.
    sens = []
    for thr in (10, 15, 30, 60, 120):
        sz = pd.Series(np.cumsum(np.concatenate([[True], minutes > thr]))).value_counts()
        sens.append({"gap_min": thr, "n_sessions": int(sz.size), "share_drops_in_multi": round(float(sz[sz > 1].sum() / sz.sum()), 4),
                     "size_median_multi": float(sz[sz > 1].median())})
    q = lambda x: float(np.quantile(minutes, x))
    return {
        "n_gaps": int(len(gaps)), "burstiness": round(float(burst), 4), "memory": round(memory, 4),
        "memory_log": round(memory_log, 4),
        "gap_median_min": round(q(0.5), 2), "gap_q25_min": round(q(0.25), 2), "gap_q75_min": round(q(0.75), 2),
        "share_within_5min": round(float((minutes <= 5).mean()), 4),
        "share_within_1h": round(float((minutes <= 60).mean()), 4),
        "share_over_1day": round(float((minutes >= 1440).mean()), 4),
        "hist": [{"lo": round(float(a), 4), "hi": round(float(b), 4), "n": int(c)}
                 for a, b, c in zip(edges[:-1], edges[1:], hist)],
        "session_gap_min": SESSION_GAP_MIN, "session_sensitivity": sens, "n_sessions": int(sizes.size),
        "session_size_median": float(sizes[sizes > 1].median()), "session_size_max": int(sizes.max()),
        "share_drops_in_multi": round(float(sizes[sizes > 1].sum() / sizes.sum()), 4),
        "session_span_median_min": round(float(span[sizes > 1].median()), 1),
        "session_sizes": [{"size": int(k), "n": int(v)} for k, v in size_dist.items() if k <= 30]
                         + ([{"size": 31, "n": int(size_dist[size_dist.index > 30].sum())}]
                            if (size_dist.index > 30).any() else []),
    }


# ------------------------------------------------------------------ ruptures
def _seg_cost(cs, i, j):
    """Cout de Poisson (moins la log-vraisemblance, sans constante) du segment [i, j)."""
    s, n = cs[j] - cs[i], j - i
    return 0.0 if s <= 0 else -(s * np.log(s / n) - s)


def changepoints(d, min_weeks=6):
    """Partition optimale (programmation dynamique, Jackson et al. 2005) des
    comptes hebdomadaires en segments de moyenne constante, cout de Poisson
    corrige de la surdispersion (quasi-vraisemblance), penalite BIC."""
    week = d["et"].dt.tz_localize(None).dt.to_period("W-SUN").dt.start_time
    w = week.value_counts().sort_index()
    w = w.reindex(pd.date_range(w.index.min(), w.index.max(), freq="7D"), fill_value=0)
    y = w.to_numpy().astype(float)
    n = len(y)
    cs = np.concatenate([[0], np.cumsum(y)])
    # Surdispersion estimee sur les differences premieres (robuste aux ruptures).
    phi = max(1.0, float(np.var(np.diff(y)) / (2 * max(y.mean(), 1e-9))))
    beta = 2 * np.log(n)  # BIC : un parametre par segment (deux en comptant la position)
    F = np.full(n + 1, np.inf)
    F[0] = -beta
    last = np.zeros(n + 1, dtype=int)
    for t in range(min_weeks, n + 1):
        best, arg = np.inf, 0
        for s in range(0, t - min_weeks + 1):
            if s and s < min_weeks:
                continue
            v = F[s] + _seg_cost(cs, s, t) * 2 / phi + beta
            if v < best:
                best, arg = v, s
        F[t], last[t] = best, arg
    cuts, t = [], n
    while t > 0:
        cuts.append(t)
        t = last[t]
    bounds = [0] + sorted(cuts)
    idx = w.index
    segs = []
    for a, b in zip(bounds[:-1], bounds[1:]):
        segs.append({"start": idx[a].date().isoformat(), "end": (idx[b - 1] + pd.Timedelta(days=6)).date().isoformat(),
                     "weeks": int(b - a), "mean_per_week": round(float(y[a:b].mean()), 2),
                     "total": int(y[a:b].sum())})
    return {"phi": round(phi, 2), "penalty": round(float(beta), 2), "min_weeks": min_weeks,
            "n_weeks": n, "segments": segs}


def attach_events(cp, events):
    """Evenement de la chronologie le plus proche de chaque rupture (± 3 semaines)."""
    ev = [(pd.Timestamp(e["date"]), e) for e in events]
    for s in cp["segments"][1:]:
        start = pd.Timestamp(s["start"])
        near = sorted(((abs((dt - start).days), e) for dt, e in ev if abs((dt - start).days) <= 21),
                      key=lambda x: x[0])
        s["event"] = ({"id": near[0][1]["id"], "date": near[0][1]["date"], "label_fr": near[0][1]["label_fr"],
                       "label_en": near[0][1]["label_en"]} if near else None)
    return cp


# ------------------------------------------------------------------ plateformes
def boards(d):
    t = d["text"].fillna("")
    df = pd.DataFrame({"board": d["site"] + " " + d["board"], "words": t.str.split().str.len().fillna(0),
                       "day": d["et"].dt.date, "link": t.str.contains(r"https?://"),
                       "img": d["n_images"] > 0, "q": t.str.contains(r"\?"), "ref": d["n_refs"] > 0,
                       "ts": d["ts"]})
    g = df.groupby("board")
    out = pd.DataFrame({
        "n": g.size(), "first": g["ts"].min(), "last": g["ts"].max(), "active_days": g["day"].nunique(),
        "words_median": g["words"].median(), "share_links": g["link"].mean(), "share_images": g["img"].mean(),
        "share_questions": g["q"].mean(), "share_refs": g["ref"].mean(),
    }).reset_index().sort_values("first")
    out["per_active_day"] = out["n"] / out["active_days"]
    return [{k: (round(v, 4) if isinstance(v, float) else (v.isoformat() if hasattr(v, "isoformat") else v))
             for k, v in r.items()} for r in out.to_dict("records")]


# ------------------------------------------------------------------ sources citees
SOCIAL = {"twitter.com", "mobile.twitter.com", "x.com", "youtube.com", "m.youtube.com", "youtu.be", "reddit.com",
          "facebook.com", "instagram.com", "voat.co", "8ch.net", "8kun.top", "4chan.org", "boards.4chan.org",
          "gab.com", "gab.ai", "pastebin.com", "imgur.com", "i.imgur.com", "t.co", "periscope.tv", "pscp.tv"}
ARCHIVE = {"archive.is", "archive.today", "archive.ph", "archive.org", "web.archive.org", "archive.fo", "scribd.com",
           "documentcloud.org", "wikileaks.org", "en.wikipedia.org", "wikipedia.org", "merriam-webster.com",
           "bing.com", "google.com", "duckduckgo.com", "qanon.pub", "qmap.pub"}


def domain_category(host):
    h = host.lower().removeprefix("www.")
    if h in SOCIAL:
        return "social"
    if h in ARCHIVE:
        return "archive"
    if re.search(r"\.(gov|mil)$", h) or h.endswith(".gov.uk") or h.endswith("un.org") or h.endswith("nato.int"):
        return "official"
    return "press"


def domains(d, top=30):
    rows = []
    for _, r in d.iterrows():
        for u in re.findall(r"https?://[^\s<>\"]+", r["text"] or ""):
            host = urlparse(u).netloc.lower().removeprefix("www.").split(":")[0]
            if host:
                rows.append({"drop": r["id"], "year": r["et"].year, "host": host})
    df = pd.DataFrame(rows)
    if df.empty:
        return {"n_links": 0}
    # Variantes d'un meme site (mobile, video) regroupees.
    df["site"] = df["host"].str.replace(r"^(mobile|m|video|edition|amp)\.", "", regex=True)
    df["cat"] = df["site"].map(domain_category)
    per_drop = df.drop_duplicates(["drop", "site"])
    counts = per_drop["site"].value_counts()
    cat_year = (df.groupby(["year", "cat"]).size().reset_index(name="n"))
    press = per_drop[per_drop["cat"] == "press"]["site"].value_counts()
    return {
        "n_links": int(len(df)), "n_drops_with_links": int(df["drop"].nunique()), "n_sites": int(counts.size),
        "top": [{"site": s, "drops": int(n), "cat": domain_category(s)} for s, n in counts.head(top).items()],
        "top_press": [{"site": s, "drops": int(n)} for s, n in press.head(20).items()],
        "by_cat": {k: int(v) for k, v in df["cat"].value_counts().items()},
        "cat_year": cat_year.to_dict("records"),
    }


# ------------------------------------------------------------------ renvois
def references(d):
    own = set(d["post_id"].dropna().astype(str))
    rows = []
    for _, r in d.iterrows():
        refs = json.loads(r["refs_json"]) if r["refs_json"] else []
        ids = [str(x.get("post_id") or "").strip() for x in refs]
        rows.append({"year": r["et"].year, "n": len(refs), "self": sum(i in own for i in ids if i),
                     "anon": sum(i not in own for i in ids if i)})
    df = pd.DataFrame(rows)
    g = df.groupby("year")
    by_year = pd.DataFrame({"drops": g.size(), "with_refs": g["n"].apply(lambda s: (s > 0).mean()),
                            "with_self": g["self"].apply(lambda s: (s > 0).mean()),
                            "with_anon": g["anon"].apply(lambda s: (s > 0).mean())}).reset_index()
    return {"share_with_refs": round(float((df["n"] > 0).mean()), 4),
            "share_self": round(float((df["self"] > 0).mean()), 4),
            "share_anon": round(float((df["anon"] > 0).mean()), 4),
            "n_refs": int(df["n"].sum()), "n_self": int(df["self"].sum()), "n_anon": int(df["anon"].sum()),
            "by_year": [{k: (round(v, 4) if isinstance(v, float) else int(v)) for k, v in r.items()}
                        for r in by_year.to_dict("records")]}


# ------------------------------------------------------------------ religion
BOOKS = (r"Genesis|Exodus|Leviticus|Numbers|Deuteronomy|Joshua|Judges|Ruth|Samuel|Kings|Chronicles|Ezra|"
         r"Nehemiah|Esther|Job|Psalms?|Proverbs|Ecclesiastes|Isaiah|Jeremiah|Lamentations|Ezekiel|Daniel|Hosea|"
         r"Joel|Amos|Micah|Nahum|Habakkuk|Zephaniah|Zechariah|Malachi|Matthew|Mark|Luke|John|Acts|Romans|"
         r"Corinthians|Galatians|Ephesians|Philippians|Colossians|Thessalonians|Timothy|Titus|Hebrews|James|"
         r"Peter|Jude|Revelations?")
VERSE = re.compile(rf"\b(?:[1-3]\s?)?(?:{BOOKS})\s+\d{{1,3}}:\d{{1,3}}", re.I)
FAITH = re.compile(r"\b(?:God|Jesus|Christ|Lord|pray(?:er|ers|ing)?|Bible|scripture|faith|blessed|Heaven|Satan|"
                   r"demonic|evil|good vs\.? evil|light vs\.? dark|armor of God)\b", re.I)


def religion(d):
    t = d["text"].fillna("")
    verse = t.str.contains(VERSE)
    faith = t.str.contains(FAITH)
    god = t.str.contains(r"\bGod\b")
    quarter = d["et"].dt.tz_localize(None).dt.to_period("Q").astype(str)
    df = pd.DataFrame({"q": quarter, "verse": verse, "faith": faith, "god": god})
    g = df.groupby("q")
    series = pd.DataFrame({"n": g.size(), "verse": g["verse"].mean(), "faith": g["faith"].mean(),
                           "god": g["god"].mean()}).reset_index()
    books = Counter()
    for m in t[verse]:
        for v in VERSE.findall(m):
            books[re.sub(r"\s+\d.*$", "", v).strip().title()] += 1
    first_verse = d.loc[verse, ["id", "ts"]].head(1)
    return {"share_verse": round(float(verse.mean()), 4), "n_verse": int(verse.sum()),
            "share_faith": round(float(faith.mean()), 4), "share_god": round(float(god.mean()), 4),
            "first_verse": ({"id": int(first_verse["id"].iloc[0]),
                             "date": first_verse["ts"].iloc[0].tz_convert(ET).date().isoformat()}
                            if len(first_verse) else None),
            "books": books.most_common(10),
            "quarterly": [{k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items()}
                          for r in series.to_dict("records") if r["n"] >= 10]}


# ------------------------------------------------------------------ lisibilite et lexique
def _syllables(word):
    w = word.lower()
    groups = re.findall(r"[aeiouy]+", w)
    n = len(groups) - (1 if w.endswith("e") and len(groups) > 1 and not w.endswith("le") else 0)
    return max(1, n)


def flesch(text):
    sentences = [s for s in re.split(r"[.!?]+|\n+", text) if re.search(r"[A-Za-z]", s)]
    words = re.findall(r"[A-Za-z][A-Za-z']*", text)
    if len(words) < 100 or not sentences:
        return None
    syl = sum(_syllables(w) for w in words)
    return 206.835 - 1.015 * len(words) / len(sentences) - 84.6 * syl / len(words), len(words) / len(sentences)


def mattr(tokens, window=500):
    """Moving-average type-token ratio (Covington & McFall 2010)."""
    if len(tokens) < window:
        return None
    counts = Counter(tokens[:window])
    total = len(counts)
    vals = [total]
    for i in range(window, len(tokens)):
        out_w, in_w = tokens[i - window], tokens[i]
        counts[out_w] -= 1
        if counts[out_w] == 0:
            del counts[out_w]
            total -= 1
        if counts[in_w] == 0:
            total += 1
        counts[in_w] += 1
        vals.append(total)
    return float(np.mean(vals)) / window


def lexicon(d):
    texts = [clean(x) for x in d["text"]]
    quarter = d["et"].dt.tz_localize(None).dt.to_period("Q").astype(str).to_numpy()
    rows = []
    for q in sorted(set(quarter)):
        blob = "\n".join(t for t, k in zip(texts, quarter) if k == q)
        f = flesch(blob)
        toks = re.findall(r"[a-z']+", blob.lower())
        m = mattr(toks)
        if f and m:
            rows.append({"q": q, "flesch": round(f[0], 1), "words_per_sentence": round(f[1], 1),
                         "mattr": round(m, 4), "tokens": len(toks)})
    all_toks = re.findall(r"[a-z']+", " ".join(texts).lower())
    freq = np.array(sorted(Counter(all_toks).values(), reverse=True), dtype=float)
    r = np.arange(1, len(freq) + 1)
    sel = (r >= 10) & (r <= 2000)
    zipf = -np.polyfit(np.log(r[sel]), np.log(freq[sel]), 1)[0]
    # Loi de Heaps : V(n) = K n^beta, ajustee sur la croissance du vocabulaire.
    seen, growth = set(), []
    for i, w in enumerate(all_toks, 1):
        seen.add(w)
        if i % 2000 == 0:
            growth.append((i, len(seen)))
    g = np.array(growth, dtype=float)
    heaps = np.polyfit(np.log(g[:, 0]), np.log(g[:, 1]), 1)[0]
    total = flesch("\n".join(texts))
    return {"quarterly": rows, "tokens": len(all_toks), "types": int(len(freq)),
            "hapax": int((freq == 1).sum()), "zipf_exponent": round(float(zipf), 3),
            "heaps_beta": round(float(heaps), 3), "flesch_all": round(total[0], 1) if total else None,
            "words_per_sentence_all": round(total[1], 1) if total else None,
            "mattr_all": round(mattr(all_toks), 4)}


def run(ctx):
    d = load_drops(ctx.conn)
    events = load_events(ctx.conn).to_dict("records")
    out = {
        "rhythm": rhythm(d),
        "changepoints": attach_events(changepoints(d), events),
        "boards": boards(d),
        "domains": domains(d),
        "references": references(d),
        "religion": religion(d),
        "lexicon": lexicon(d[d["text"].str.strip() != ""]),
    }
    ctx.set_output(db.sha(write(ctx, "stats", out)))
    r = out["rhythm"]
    log(f"statistiques : rafales B = {r['burstiness']}, {r['n_sessions']} sessions, "
        f"{len(out['changepoints']['segments'])} regimes, {out['domains']['n_sites']} sites cites")
    return True

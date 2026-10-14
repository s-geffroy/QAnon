"""Analyse du discours : themes (NMF), termes distinctifs par annee, formules
du glossaire, style, et stylometrie exploratoire (ruptures d'auteur)."""
import re

import numpy as np
import pandas as pd
from sklearn.decomposition import NMF
from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer

from .. import db
from ..log import log
from .common import ET, clean, load_drops, load_yaml, month, write

N_TOPICS = 12
STOP_EXTRA = ["q", "amp", "gt", "lt", "https", "http", "com", "www", "pdf", "jpg", "png", "html", "status",
              "twitter", "realdonaldtrump", "youtube", "watch", "anons", "anon"]


def topic_model(texts):
    """Modele de themes (TF-IDF + NMF, deterministe) : poids W (drops x themes),
    composantes et vocabulaire. Partage avec la chaine de Markov des themes."""
    vec = TfidfVectorizer(stop_words=list(_stop()), min_df=5, max_df=0.4,
                          token_pattern=r"(?u)\b[A-Za-z][A-Za-z0-9\-]{2,}\b", ngram_range=(1, 2),
                          sublinear_tf=True, lowercase=True)
    X = vec.fit_transform(texts)
    model = NMF(n_components=N_TOPICS, init="nndsvd", random_state=0, max_iter=400)
    W = model.fit_transform(X)
    return W, model.components_, np.array(vec.get_feature_names_out())


def topics(texts, months):
    W, components, vocab = topic_model(texts)
    out = []
    share = W / np.maximum(W.sum(axis=1, keepdims=True), 1e-12)
    weight = share.sum(axis=0)
    for k in range(N_TOPICS):
        top = vocab[np.argsort(components[k])[::-1][:12]].tolist()
        out.append({"id": k, "terms": top, "share": float(weight[k] / weight.sum())})
    df = pd.DataFrame(share, columns=range(N_TOPICS))
    df["month"] = months.to_numpy()
    by_month = df.groupby("month").mean()
    prevalence = [{"month": m, "topic": int(k), "share": round(float(v), 4)}
                  for m, row in by_month.iterrows() for k, v in row.items()]
    # Drop le plus representatif de chaque theme (identifiant seulement).
    for k in range(N_TOPICS):
        out[k]["exemplar_ids"] = [int(i) for i in np.argsort(W[:, k])[::-1][:3]]
    order = sorted(out, key=lambda x: -x["share"])
    return order, prevalence


def _stop():
    from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS
    return set(ENGLISH_STOP_WORDS) | set(STOP_EXTRA)


def distinctive(texts, years, top=15):
    """Termes distinctifs de chaque annee : log-odds avec a priori de Dirichlet
    informatif (Monroe, Colaresi & Quinn 2008), z-score."""
    vec = CountVectorizer(stop_words=list(_stop()), min_df=5, lowercase=True,
                          token_pattern=r"(?u)\b[A-Za-z][A-Za-z0-9\-]{2,}\b")
    X = vec.fit_transform(texts)
    vocab = np.array(vec.get_feature_names_out())
    total = np.asarray(X.sum(axis=0)).ravel().astype(float)
    alpha = total / total.sum() * 500
    out = {}
    for y in sorted(set(years)):
        mask = np.asarray(years == y)
        if mask.sum() < 20:
            continue
        a = np.asarray(X[mask].sum(axis=0)).ravel().astype(float)
        b = total - a
        na, nb, a0 = a.sum(), b.sum(), alpha.sum()
        delta = (np.log((a + alpha) / (na + a0 - a - alpha)) - np.log((b + alpha) / (nb + a0 - b - alpha)))
        var = 1 / (a + alpha) + 1 / (b + alpha)
        z = delta / np.sqrt(var)
        idx = np.argsort(z)[::-1][:top]
        out[str(y)] = [{"term": vocab[i], "z": round(float(z[i]), 1), "n": int(a[i])} for i in idx]
    return out


def glossary_counts(d, months):
    terms = load_yaml("glossary", "terms")
    rows, series = [], []
    for t in terms:
        pat = t.get("pattern")
        if not pat:
            rows.append({"id": t["id"], "n": None})
            continue
        hit = d["text"].str.contains(pat, regex=True, flags=0)
        n = int(hit.sum())
        first = d.loc[hit, ["id", "ts"]].head(1)
        rows.append({"id": t["id"], "n": n, "n_drops_share": float(hit.mean()),
                     "first_id": int(first["id"].iloc[0]) if n else None,
                     "first_date": first["ts"].iloc[0].tz_convert(ET).date().isoformat() if n else None})
        if n:
            per = hit.groupby(months).sum()
            series += [{"id": t["id"], "month": m, "n": int(v)} for m, v in per.items() if v]
    return rows, series


def style(d, months):
    t = d["text"].fillna("")
    words = t.str.split().str.len().fillna(0)
    letters = t.str.count(r"[A-Za-z]")
    caps = t.str.count(r"[A-Z]")
    df = pd.DataFrame({
        "month": months, "words": words, "q": t.str.count(r"\?"),
        "has_q": t.str.contains(r"\?"), "excl": t.str.count("!"),
        "caps": caps / letters.replace(0, np.nan), "link": t.str.contains(r"https?://"),
        "img": d["n_images"] > 0,
    })
    g = df.groupby("month")
    out = pd.DataFrame({
        "n": g.size(), "words_median": g["words"].median(), "questions_per_drop": g["q"].mean(),
        "share_questions": g["has_q"].mean(), "caps_ratio": g["caps"].mean(),
        "share_links": g["link"].mean(), "share_images": g["img"].mean(),
    }).reset_index()
    return [{k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items()}
            for r in out.to_dict("records")]


def stylometry(d, chunk_words=1500, n_mfw=150):
    """Burrows' Delta sur des blocs de drops consecutifs (~1 500 mots).

    Exploratoire : textes courts, sujets changeants, citations ; une rupture
    de style n'identifie personne. On cherche le point de coupure qui separe le
    mieux les blocs (rapport distance inter / intra), puis on positionne chaque
    bloc entre le profil du debut (4chan, oct.-nov. 2017) et celui du reste."""
    texts = [clean(x).lower() for x in d["text"]]
    chunks, cur, words, start = [], [], 0, None
    for txt, ts in zip(texts, d["ts"]):
        toks = re.findall(r"[a-z']+", txt)
        if not toks:
            continue
        start = start or ts
        cur += toks
        words += len(toks)
        if words >= chunk_words:
            chunks.append((start, ts, cur))
            cur, words, start = [], 0, None
    if len(chunks) < 10:
        return None
    from collections import Counter
    freq = Counter(w for _, _, c in chunks for w in c)
    mfw = [w for w, _ in freq.most_common(n_mfw)]
    counts = [Counter(c) for _, _, c in chunks]
    M = np.array([[cnt[w] / len(c) for w in mfw] for cnt, (_, _, c) in zip(counts, chunks)])
    Z = (M - M.mean(axis=0)) / (M.std(axis=0) + 1e-12)
    dist = np.abs(Z[:, None, :] - Z[None, :, :]).mean(axis=2)  # Delta de Burrows
    n = len(chunks)
    best, scores = None, []
    for k in range(3, n - 3):
        within = (dist[:k, :k].sum() + dist[k:, k:].sum()) / (k * k + (n - k) ** 2)
        between = dist[:k, k:].mean()
        r = between / within
        scores.append({"k": k, "date": chunks[k][0].tz_convert(ET).date().isoformat(), "ratio": round(float(r), 4)})
        if best is None or r > best["ratio"]:
            best = scores[-1]
    k = best["k"]
    early = dist[:, :k].mean(axis=1)
    late = dist[:, k:].mean(axis=1)
    points = [{"start": s.tz_convert(ET).date().isoformat(), "end": e.tz_convert(ET).date().isoformat(),
               "to_early": round(float(a), 4), "to_late": round(float(b), 4),
               "position": round(float(a - b), 4)} for (s, e, _), a, b in zip(chunks, early, late)]
    # Seconde coupure dans la partie posterieure (une 3e plume ?).
    sub = dist[k:, k:]
    m = len(sub)
    best2 = None
    for j in range(3, m - 3):
        within = (sub[:j, :j].sum() + sub[j:, j:].sum()) / (j * j + (m - j) ** 2)
        r = sub[:j, j:].mean() / within
        if best2 is None or r > best2["ratio"]:
            best2 = {"k": k + j, "date": chunks[k + j][0].tz_convert(ET).date().isoformat(), "ratio": round(float(r), 4)}
    return {"n_chunks": n, "chunk_words": chunk_words, "n_mfw": n_mfw, "split": best,
            "split_after": best2, "scores": scores, "points": points}


def run(ctx):
    d = load_drops(ctx.conn)
    d = d[d["text"].str.strip() != ""].reset_index(drop=True)
    texts = [clean(x) for x in d["text"]]
    months = month(d["ts"])
    years = d["et"].dt.year.to_numpy()
    topic_list, prevalence = topics(texts, months)
    for t in topic_list:
        t["exemplar_ids"] = [int(d["id"].iloc[i]) for i in t["exemplar_ids"]]
    gl_rows, gl_series = glossary_counts(d, months)
    out = {
        "n_docs": len(d), "topics": topic_list, "prevalence": prevalence,
        "distinctive": distinctive(texts, years), "glossary": gl_rows, "glossary_series": gl_series,
        "style": style(d, months), "stylometry": stylometry(d),
    }
    ctx.set_output(db.sha(write(ctx, "discourse", out)))
    s = out["stylometry"]
    log(f"analyse du discours : {N_TOPICS} themes, {len(gl_rows)} formules ; "
        f"rupture stylometrique la plus nette : {s['split']['date'] if s else '—'}")
    return True

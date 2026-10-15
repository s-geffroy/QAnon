"""Q et 4chan /pol/, son milieu d'origine (Papasavva et al. 2020 ; Zenodo 3606810).

Lit les couches produites par le balayage (sources/pol.py), jamais l'archive :
- naissance des formules : comptes hebdomadaires de chaque formule forgee par Q,
  rapportes au volume de /pol/ ; date d'apparition = premiere semaine qui depasse
  le quantile 0,999 de Poisson attendu au taux d'avant Q (juillet 2016 - 22 octobre
  2017) et le redepasse au moins deux fois dans les quatre semaines suivantes. La
  toute premiere occurrence n'est pas fiable (« I got a Q anons », Star Trek...) ;
- niche : part des posts de /pol/ dans les fils Q (CBTS, Q research...) par mois ;
- reponse : mentions horaires de Q sur /pol/ autour des debuts de session, pendant
  le mois ou Q y publie, puis apres son depart pour 8chan (epoque superposee) ;
- toxicite : scores Perspective du dataset, fils et posts Q contre tout /pol/ ;
- familles du lexique : part des posts touches par chaque famille dans les drops,
  dans les fils Q de /pol/ et dans l'echantillon a 1 % de /pol/ (avant et apres Q) ;
- vocabulaire propre aux fils Q : log-odds a prior de Dirichlet informatif
  (Monroe, Colaresi & Quinn 2008) contre les comptes de mots de tout /pol/ ; les
  mots qui touchent un motif sensible du lexique sont retires.
Aucun texte de /pol/ n'est publie : seulement des comptes et des taux.
"""
import collections

import numpy as np
import pandas as pd
from scipy import stats as sps

from .. import db, lexicon
from ..log import log
from ..sources.pol import _TOKEN
from .common import load_drops, run_parts, write
from .scene import epoch_response, session_starts

SEED = 20171028
BIRTH = "2017-10-28"
BASE_END = "2017-10-23"          # lundi de la semaine de la naissance : semaines anterieures = reference
POL_START, POL_END = "2016-07-01", "2019-10-31"   # mois complets du dataset
CHUNK = 100_000
Q_MENTIONS = ("qanon", "q_attribution", "q_drop_term", "cbts")
TOX_ATTRS = ("TOXICITY", "SEVERE_TOXICITY", "INSULT", "INFLAMMATORY", "PROFANITY", "OBSCENE", "SPAM")
CORPORA = ("drops", "q_threads", "pol_before", "pol_after")
# Fragments d'adresses et abreviations de dates : frequents dans les fils Q (liens, horodatages
# recopies), ils ne disent rien du vocabulaire.
NOT_WORDS = {"http", "https", "www", "com", "org", "net", "html", "php", "jpg", "png", "pdf", "gov", "amp",
             "jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec", "est", "pst"}


def coined(terms):
    """Formules forgees ou portees par Q (glossaire, noyau Q) et larps qui l'ont precede."""
    return [t for t in terms if (t.source == "glossary" or t.family in ("q_core", "larp")) and not t.ambiguous]


def _week(ts):
    return pd.to_datetime(ts, unit="s").dt.to_period("W-SUN").dt.start_time.dt.strftime("%Y-%m-%d")


def weekly(conn, ids):
    tot = pd.read_sql_query("SELECT hour, posts FROM pol_hour_total", conn)
    tot["week"] = _week(tot["hour"])
    posts = tot.groupby("week")["posts"].sum()
    q = ",".join("?" * len(ids))
    h = pd.read_sql_query(f"SELECT hour, term, n FROM pol_hour WHERE term IN ({q})", conn, params=list(ids))
    h["week"] = _week(h["hour"])
    counts = h.pivot_table(index="week", columns="term", values="n", aggfunc="sum").reindex(posts.index).fillna(0)
    return posts, counts.reindex(columns=list(ids), fill_value=0)


def onset(counts, posts, base_end=BASE_END, q=0.999, min_n=5, confirm=2):
    """Premiere semaine anormale et durable, au taux d'avant Q ; None si aucune."""
    base = counts.index < base_end
    lam = (counts[base].sum() + 0.5) / posts[base].sum()
    thr = sps.poisson.ppf(q, lam * posts.to_numpy())
    exceed = (counts.to_numpy() > thr) & (counts.to_numpy() >= min_n)
    for i in np.flatnonzero(exceed):
        if exceed[i + 1:i + 5].sum() >= confirm:
            return counts.index[i], float(lam)
    return None, float(lam)


def births(conn, d, terms):
    """Apparition de chaque formule sur /pol/, face a son premier usage par Q."""
    ts = coined(terms)
    posts, counts = weekly(conn, [t.id for t in ts])
    m = lexicon.Matcher(ts)
    first_q = {}
    for when, txt in zip(d["ts"], d["text"].fillna("")):
        for i in m.hits(txt):
            first_q.setdefault(ts[i].id, when)
    after = counts.index >= BASE_END
    rows = []
    for t in ts:
        c = counts[t.id]
        if c.sum() < 20:
            continue
        on, lam = onset(c, posts)
        fq = first_q.get(t.id)
        row = {"term": t.id, "label_fr": t.label_fr, "label_en": t.label_en, "family": t.family,
               "pol_posts": int(c.sum()), "rate_before": round(lam * 1e6, 2),
               "rate_after": round(float(c[after].sum() / posts[after].sum() * 1e6), 2),
               "onset_week": on, "first_q": fq.strftime("%Y-%m-%d") if fq is not None else None}
        if on and fq is not None:
            row["lag_days"] = int((pd.Timestamp(on, tz="UTC") - fq.normalize()).days)
        # before_q : deja anormal avant la naissance de Q ; about_q : apparu avec Q, mais Q ne
        # l'emploie pas (on parle de lui) ; pol_first / q_first : selon le premier usage par Q.
        row["status"] = ("no_onset" if on is None else "before_q" if on < BASE_END else "about_q" if fq is None else
                         "pol_first" if row["lag_days"] < -7 else "q_first")
        rows.append(row)
    return sorted(rows, key=lambda r: (r["onset_week"] or "9999", -r["pol_posts"]))


def monthly_rates(conn, terms, min_total=500):
    ts = [t for t in coined(terms)]
    tot = pd.read_sql_query("SELECT strftime('%Y-%m', hour, 'unixepoch') m, sum(posts) p FROM pol_hour_total GROUP BY m",
                            conn).set_index("m")["p"]
    q = ",".join("?" * len(ts))
    h = pd.read_sql_query(f"SELECT strftime('%Y-%m', hour, 'unixepoch') m, term, sum(n) n FROM pol_hour "
                          f"WHERE term IN ({q}) GROUP BY m, term", conn, params=[t.id for t in ts])
    lab = {t.id: (t.label_fr, t.label_en) for t in ts}
    out = []
    for term, g in h.groupby("term"):
        if g["n"].sum() < min_total:
            continue
        s = g.set_index("m")["n"].reindex(tot.index, fill_value=0)
        out.append({"term": term, "label_fr": lab[term][0], "label_en": lab[term][1], "total": int(s.sum()),
                    "monthly": [{"month": m, "n": int(v), "per_m": round(float(v / tot[m] * 1e6), 2)}
                                for m, v in s.items() if POL_START[:7] <= m <= POL_END[:7]]})
    return sorted(out, key=lambda r: -r["total"])


def niche(conn):
    tot = pd.read_sql_query("SELECT strftime('%Y-%m', hour, 'unixepoch') m, sum(posts) p, sum(threads) t "
                            "FROM pol_hour_total GROUP BY m", conn).set_index("m")
    qc = pd.read_sql_query("SELECT strftime('%Y-%m', ts, 'unixepoch') m, substr(reason, 1, instr(reason, ':') - 1) kind, "
                           "count(*) n, count(DISTINCT thread) th FROM pol_qcorpus GROUP BY m, kind", conn)
    out = []
    for m in tot.index:
        if not (POL_START[:7] <= m <= POL_END[:7]):
            continue
        g = qc[qc["m"] == m].set_index("kind")
        th = int(g["n"].get("thread", 0))
        out.append({"month": m, "posts": int(tot.loc[m, "p"]), "q_thread_posts": th,
                    "q_threads": int(g["th"].get("thread", 0)), "q_posts_elsewhere": int(g["n"].get("post", 0)),
                    "share": round(th / tot.loc[m, "p"], 6)})
    return out


def response(conn, d, seed=SEED, n_null=500):
    """Mentions horaires de Q sur /pol/ autour des debuts de session de Q."""
    rng = np.random.default_rng(seed)
    q = ",".join("?" * len(Q_MENTIONS))
    h = pd.read_sql_query(f"SELECT hour, sum(n) n FROM pol_hour WHERE term IN ({q}) GROUP BY hour", conn,
                          params=list(Q_MENTIONS)).set_index("hour")["n"]
    tot = pd.read_sql_query("SELECT hour FROM pol_hour_total", conn)["hour"]
    h0, h1 = int(tot.min()), int(tot.max())
    full = h.reindex(np.arange(h0, h1 + 3600, 3600), fill_value=0).to_numpy(dtype=float)
    pol_drops = d[d["board"].fillna("").str.strip("/").str.lower() == "pol"]
    last_pol = int(pol_drops["time"].max()) if len(pol_drops) else None
    starts = session_starts(d)
    t = lambda s: int(pd.Timestamp(s, tz="UTC").timestamp())
    periods = {"on_pol": (t(BIRTH), last_pol + 1 if last_pol else t("2017-12-01")),
               "exile": (t("2018-01-01"), t(POL_END) + 86400)}
    out = {"last_pol_drop": pd.Timestamp(last_pol, unit="s", tz="UTC").strftime("%Y-%m-%d") if last_pol else None,
           "pol_drops": int(len(pol_drops))}
    for name, (a, b) in periods.items():
        # Fenetre de la periode, marges comprises (24 h avant, 48 h apres).
        i0, i1 = max(0, (a - h0) // 3600 - 24 * 30), min(len(full), (b - h0) // 3600 + 48 + 24 * 30)
        st = starts[(starts >= a) & (starts < b)]
        r = epoch_response(full[i0:i1], h0 + i0 * 3600, st, rng, n_null, min_events=10)
        if r:
            out[name] = r
    return out


def toxicity(conn):
    df = pd.read_sql_query("SELECT * FROM pol_tox_day", conn)
    df = df[df["attr"].isin(TOX_ATTRS)]
    overall = {}
    for (scope, attr), g in df.groupby(["scope", "attr"]):
        overall.setdefault(attr, {})[scope] = {"mean": round(float(g["total"].sum() / g["n"].sum()), 4),
                                               "high": round(float(g["n_high"].sum() / g["n"].sum()), 4),
                                               "n": int(g["n"].sum())}
    # Ecart quotidien (Q - tout /pol/), jours ou le sous-corpus compte au moins 100 posts notes.
    paired = {}
    for attr, g in df.groupby("attr"):
        w = g.pivot_table(index="day", columns="scope", values=["total", "n"], aggfunc="sum").dropna()
        w = w[w[("n", "q")] >= 100]
        if len(w) < 30:
            continue
        diff = w[("total", "q")] / w[("n", "q")] - w[("total", "all")] / w[("n", "all")]
        paired[attr] = {"days": int(len(diff)), "median_diff": round(float(diff.median()), 4),
                        "share_days_q_higher": round(float((diff > 0).mean()), 3),
                        "p_wilcoxon": float(sps.wilcoxon(diff).pvalue)}
    df["month"] = df["day"].str[:7]
    m = df[df["attr"] == "TOXICITY"].groupby(["month", "scope"])[["total", "n", "n_high"]].sum()
    monthly = [{"month": k[0], "scope": k[1], "mean": round(float(r["total"] / r["n"]), 4),
                "high": round(float(r["n_high"] / r["n"]), 4), "n": int(r["n"])}
               for k, r in m.iterrows() if POL_START[:7] <= k[0] <= POL_END[:7]]
    return {"overall": overall, "paired": paired, "monthly": monthly,
            "composition": dict(conn.execute("SELECT substr(reason, 1, instr(reason, ':') - 1), count(*) "
                                              "FROM pol_qcorpus GROUP BY 1").fetchall())}


# ------------------------------------------------------------------ familles et vocabulaire (par paquets)
def _families(terms):
    return [t for t in terms if not t.ambiguous and not t.family.startswith("actor:")]


def family_part(conn, corpus, lo, hi, terms):
    """Posts touches par famille, et (fils Q seulement) comptes de mots, pour les rowid [lo, hi)."""
    ts = _families(terms)
    m = lexicon.Matcher(ts)
    if corpus == "q_threads":
        rows = conn.execute("SELECT text, thread FROM pol_qcorpus WHERE rowid >= ? AND rowid < ? AND reason LIKE 'thread:%'",
                            (lo, hi)).fetchall()
    else:
        op = "<" if corpus == "pol_before" else ">="
        cut = int(pd.Timestamp(BIRTH, tz="UTC").timestamp())
        rows = conn.execute(f"SELECT text, thread FROM pol_sample WHERE rowid >= ? AND rowid < ? AND ts {op} ?",
                            (lo, hi, cut)).fetchall()
    fam = collections.Counter()
    tok = collections.Counter()
    pairs = set()
    for txt, thread in rows:
        txt = txt or ""
        fam.update({ts[i].family for i in m.hits(txt)})
        if corpus == "q_threads":
            words = _TOKEN.findall(txt.lower())
            tok.update(words)
            pairs.update((thread, w) for w in words)
    out = {"n": len(rows), "families": dict(fam)}
    if corpus == "q_threads":
        out["tokens"] = dict(tok)
        # Fils distincts par mot (un fil a cheval sur deux paquets compte deux fois : borne haute).
        out["threads"] = dict(collections.Counter(w for _, w in pairs))
    return out


def drops_families(d, terms):
    ts = _families(terms)
    m = lexicon.Matcher(ts)
    fam = collections.Counter()
    for txt in d["text"].fillna(""):
        fam.update({ts[i].family for i in m.hits(txt)})
    return {"n": int(len(d)), "families": dict(fam)}


def wilson(k, n, z=1.96):
    if not n:
        return (0.0, 0.0)
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (round(float(c - h), 5), round(float(c + h), 5))


def keyness(conn, tok, terms, threads=None, top=30, a0=1e4, min_n=100, min_threads=20):
    """Mots sur-representes dans les fils Q face a /pol/ apres la naissance de Q. Un mot doit
    paraitre dans au moins 20 fils : les inondations (copier-coller repete dans un ou deux
    fils, « CALL OF DOODY ») ne disent rien du vocabulaire."""
    bg = dict(conn.execute("SELECT token, sum(n) FROM pol_unigram_month WHERE month >= ? GROUP BY token",
                           (BIRTH[:7],)).fetchall())
    nb, nq = sum(bg.values()), sum(tok.values())
    sens = [t.rx for t in terms if t.sensitive]
    rows = []
    for w, yq in tok.items():
        if yq < min_n or not w.isalpha() or len(w) < 3 or w in NOT_WORDS:
            continue
        if threads is not None and threads.get(w, 0) < min_threads:
            continue
        yb = bg.get(w, 0)
        a = max(a0 * yb / nb, 0.01)
        delta = np.log((yq + a) / (nq + a0 - yq - a)) - np.log((yb + a) / (nb + a0 - yb - a))
        z = delta / np.sqrt(1 / (yq + a) + 1 / (yb + a))
        rows.append((float(z), w, yq, yb))
    rows.sort(reverse=True)
    out = []
    for z, w, yq, yb in rows:
        # Les mots sont en minuscules ; certains motifs sensibles sont en capitales (ZOG).
        if any(rx.search(f) for rx in sens for f in (w, w.upper(), w.capitalize())):
            continue
        out.append({"token": w, "z": round(z, 1), "q_per_10k": round(yq / nq * 1e4, 2), "pol_per_10k": round(yb / nb * 1e4, 2)})
        if len(out) == top:
            break
    return {"q_tokens": int(nq), "pol_tokens": int(nb), "top": out}


def countries(conn):
    cut = int(pd.Timestamp(BIRTH, tz="UTC").timestamp())
    out = {}
    for name, sql in (("q_threads", "SELECT country, count(*) FROM pol_qcorpus WHERE reason LIKE 'thread:%' GROUP BY 1"),
                      ("pol_after", f"SELECT country, count(*) FROM pol_sample WHERE ts >= {cut} GROUP BY 1")):
        c = dict(conn.execute(sql).fetchall())
        flagged = sum(v for k, v in c.items() if k)
        out[name] = {"flagged": int(flagged), "unflagged": int(c.get("", 0) + c.get(None, 0)),
                     "top": [{"country": k, "share": round(v / flagged, 4)}
                             for k, v in sorted(((k, v) for k, v in c.items() if k), key=lambda x: -x[1])[:8]]}
    return out


# ------------------------------------------------------------------ etape
def run(ctx):
    conn = ctx.conn
    d = load_drops(conn)
    terms = lexicon.load()
    nq = conn.execute("SELECT max(rowid) FROM pol_qcorpus").fetchone()[0] or 0
    ns = conn.execute("SELECT max(rowid) FROM pol_sample").fetchone()[0] or 0
    parts = [("births", lambda: births(conn, d, terms)),
             ("rates", lambda: monthly_rates(conn, terms)),
             ("niche", lambda: niche(conn)),
             ("response", lambda: response(conn, d)),
             ("toxicity", lambda: toxicity(conn)),
             ("countries", lambda: countries(conn)),
             ("fam:drops", lambda: drops_families(d, terms))]
    parts += [(f"fam:q_threads:{lo}", lambda lo=lo: family_part(conn, "q_threads", lo, lo + CHUNK, terms))
              for lo in range(0, nq + 1, CHUNK)]
    parts += [(f"fam:{c}:{lo}", lambda lo=lo, c=c: family_part(conn, c, lo, lo + CHUNK, terms))
              for c in ("pol_before", "pol_after") for lo in range(0, ns + 1, CHUNK)]
    acc = run_parts(ctx, "pol", parts)
    if acc is None:
        return False
    fams = {c: {"n": 0, "families": collections.Counter()} for c in CORPORA}
    tok, thr = collections.Counter(), collections.Counter()
    for k in [k for k in acc if k.startswith("fam:")]:
        v = acc.pop(k)
        c = k.split(":")[1]
        fams[c]["n"] += v["n"]
        fams[c]["families"].update(v["families"])
        tok.update(v.get("tokens", {}))
        thr.update(v.get("threads", {}))
    names = sorted({t.family for t in _families(terms)})
    families = {c: {"n": f["n"], "rows": [{"family": nm, "posts": int(f["families"].get(nm, 0)),
                                           "share": round(f["families"].get(nm, 0) / f["n"], 6) if f["n"] else 0,
                                           "ci": wilson(f["families"].get(nm, 0), f["n"])} for nm in names]}
                for c, f in fams.items()}
    tot = conn.execute("SELECT sum(posts), sum(threads) FROM pol_hour_total").fetchone()
    overview = {"posts": int(tot[0]), "threads": int(tot[1]),
                "q_corpus": dict(conn.execute("SELECT reason, count(*) FROM pol_qcorpus GROUP BY reason").fetchall()),
                "q_threads": int(conn.execute("SELECT count(DISTINCT thread) FROM pol_qcorpus WHERE reason LIKE 'thread:%'")
                                 .fetchone()[0]),
                "sample": int(conn.execute("SELECT count(*) FROM pol_sample").fetchone()[0])}
    out = {"lexicon": lexicon.fingerprint(terms), "overview": overview, "families": families,
           "keyness": keyness(conn, tok, terms, thr), **acc}
    ctx.set_output(db.sha(write(ctx, "pol", out)))
    b = acc["births"]
    log(f"pol : analyse ecrite ; {sum(r['status'] == 'q_first' for r in b)} formules apparues sur /pol/ apres Q, "
        f"{sum(r['status'] == 'pol_first' for r in b)} avant, sur {len(b)}")
    return True

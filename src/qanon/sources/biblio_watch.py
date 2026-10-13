"""Veille bibliographique : publications sur QAnon reperees chaque semaine dans
Crossref et OpenAlex (titre ou resume contenant « QAnon »), depuis SINCE.

Rien n'entre dans la bibliographie sans relecture : le site publie ces
publications avec leur etat (dans la bibliographie, ecartee apres examen, ou
reperee mais non verifiee), calcule au rendu contre bibliography.yaml et
data/biblio_watch_review.yaml."""
import datetime as dt
import re
import time

import requests

from .. import db
from ..log import log

SINCE = "2024-01-01"
UA = {"User-Agent": "qanon-study/1.0 (+https://github.com/s-geffroy/QAnon)"}
QANON = re.compile(r"q\s?anon|\bQ-?drops?\b", re.I)


def norm_title(t):
    """Titre normalise ; sans prefixe de chapitre (« CHAPITRE 16 », « 15. »)."""
    t = re.sub(r"^\s*(?:chap(?:ter|itre)\s*\d+[.:]?|\d+\.)\s*", "", (t or "").lower())
    return re.sub(r"[^a-z0-9]+", "", t)


def same_title(a, b):
    """Meme titre, ou l'un contient l'autre (sous-titre absent d'une des sources)."""
    a, b = norm_title(a), norm_title(b)
    if not a or not b:
        return False
    short, long_ = sorted((a, b), key=len)
    return short == long_ or (len(short) >= 25 and short in long_)


def crossref():
    out, cursor = [], "*"
    for _ in range(10):
        r = requests.get("https://api.crossref.org/works", headers=UA, timeout=60, params={
            "query.bibliographic": "QAnon", "filter": f"from-pub-date:{SINCE}", "rows": 200, "cursor": cursor,
            "select": "DOI,title,author,issued,container-title,type,abstract,URL"})
        r.raise_for_status()
        msg = r.json()["message"]
        for it in msg["items"]:
            title = (it.get("title") or [""])[0]
            abstract = re.sub(r"<[^>]+>", " ", it.get("abstract") or "")
            if not QANON.search(title) and not QANON.search(abstract):
                continue
            parts = (it.get("issued") or {}).get("date-parts") or [[None]]
            date = "-".join(f"{x:02d}" if i else str(x) for i, x in enumerate(parts[0]) if x)
            out.append({"source": "crossref", "doi": it["DOI"].lower(), "title": title,
                        "authors": "; ".join(f"{a.get('family', '')}, {a.get('given', '')}".strip(", ")
                                             for a in it.get("author", [])[:8]),
                        "year": parts[0][0], "date": date, "container": (it.get("container-title") or [""])[0],
                        "url": f"https://doi.org/{it['DOI']}", "type": it.get("type"), "abstract": abstract.strip()[:2000]})
        cursor = msg.get("next-cursor")
        if not msg["items"] or not cursor:
            break
        time.sleep(2)  # politesse : l'API publique limite le debit
    return out


def openalex():
    out, cursor = [], "*"
    for _ in range(10):
        r = requests.get("https://api.openalex.org/works", headers=UA, timeout=60, params={
            "search": "qanon", "filter": f"from_publication_date:{SINCE}", "per-page": 200, "cursor": cursor})
        r.raise_for_status()
        js = r.json()
        for it in js["results"]:
            title = it.get("title") or ""
            inv = it.get("abstract_inverted_index") or {}
            words = sorted((p, w) for w, ps in inv.items() for p in ps)
            abstract = " ".join(w for _, w in words)
            if not QANON.search(title) and not QANON.search(abstract):
                continue
            doi = (it.get("doi") or "").replace("https://doi.org/", "").lower() or None
            src = ((it.get("primary_location") or {}).get("source") or {}).get("display_name") or ""
            out.append({"source": "openalex", "doi": doi, "title": title,
                        "authors": "; ".join(a["author"]["display_name"] for a in it.get("authorships", [])[:8]),
                        "year": it.get("publication_year"), "date": it.get("publication_date"), "container": src,
                        "url": it.get("doi") or (it.get("primary_location") or {}).get("landing_page_url") or it["id"],
                        "type": it.get("type"), "abstract": abstract[:2000]})
        cursor = js["meta"].get("next_cursor")
        if not js["results"] or not cursor:
            break
        time.sleep(1)
    return out


def run(ctx):
    today = dt.date.today().isoformat()
    found = crossref() + openalex()
    seen = 0
    for x in found:
        key = x["doi"] or "t:" + norm_title(x["title"])[:120]
        if not norm_title(x["title"]):
            continue
        row = ctx.conn.execute("SELECT key, source FROM biblio_watch WHERE key = ?", (key,)).fetchone()
        if row:
            src = row["source"] if x["source"] in row["source"] else f"{row['source']}+{x['source']}"
            ctx.conn.execute("UPDATE biblio_watch SET last_seen = ?, source = ? WHERE key = ?", (today, src, key))
        else:
            ctx.conn.execute("INSERT INTO biblio_watch VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                             (key, x["source"], x["doi"], x["title"], x["authors"], x["year"], x["date"],
                              x["container"], x["url"], x["type"], x["abstract"], today, today))
        seen += 1
    n = ctx.conn.execute("SELECT count(*) FROM biblio_watch").fetchone()[0]
    ctx.set_output(db.sha(n, ctx.conn.execute("SELECT group_concat(key) FROM biblio_watch").fetchone()[0]))
    log(f"veille bibliographique : {seen} publications reperees cette semaine, {n} au total depuis {SINCE}")
    return True

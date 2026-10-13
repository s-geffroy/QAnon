"""Verification hebdomadaire des liens du site : bibliographie, chronologie,
glossaire, sources des verdicts.

Chaque URL recoit un etat :
- ok : la page repond (2xx/3xx) ;
- blocked : le site refuse les robots (401, 403, 429...) ; la page existe sans doute ;
- dead : 404/410 ou nom de domaine introuvable ; une copie archivee (Wayback
  Machine) est alors recherchee et proposee sur le site ;
- error : autre echec (delai, 5xx), retente la semaine suivante.
Les DOI sont verifies aupres du resolveur doi.org (API des handles), plus fiable
que les pages des editeurs. Reprenable : une passe est numerotee par semaine,
chaque cycle verifie un lot."""
import glob
import time

import requests
import yaml

from .. import db
from ..log import log
from ..pipeline import APP_DIR

UA = {"User-Agent": "Mozilla/5.0 (compatible; qanon-study-linkcheck/1.0; +https://github.com/s-geffroy/QAnon)"}
WEEK = 7 * 86400


def collect():
    """URLs a verifier : (url, origine)."""
    out = {}
    refs = yaml.safe_load((APP_DIR / "data" / "bibliography.yaml").read_text())["references"]
    for r in refs:
        if r.get("doi"):
            out[f"doi:{r['doi'].lower()}"] = f"bibliography:{r['id']}"
        elif r.get("url"):
            out[r["url"]] = f"bibliography:{r['id']}"
    for e in yaml.safe_load((APP_DIR / "data" / "timeline.yaml").read_text())["events"]:
        if e.get("source"):
            out.setdefault(e["source"], f"timeline:{e['id']}")
    for g in yaml.safe_load((APP_DIR / "data" / "glossary.yaml").read_text())["terms"]:
        if g.get("source", "").startswith("http"):
            out.setdefault(g["source"], f"glossary:{g['id']}")
    for f in sorted(glob.glob(str(APP_DIR / "data" / "verification" / "part-*.yaml"))):
        for x in yaml.safe_load(open(f).read())["items"]:
            for u in x.get("sources") or []:
                out.setdefault(u, f"verification:{x['key']}")
    return out


def check_doi(doi):
    r = requests.get(f"https://doi.org/api/handles/{doi}", headers=UA, timeout=30)
    if r.status_code == 200 and r.json().get("responseCode") == 1:
        return "ok", 200
    return ("dead", r.status_code) if r.status_code == 404 else ("error", r.status_code)


def check_url(url):
    try:
        r = requests.head(url, headers=UA, timeout=30, allow_redirects=True)
        # Certains sites (Kaggle...) refusent HEAD mais servent la page en GET : tout echec est reverifie en GET.
        if r.status_code >= 400:
            r = requests.get(url, headers=UA, timeout=30, allow_redirects=True, stream=True)
            r.close()
    except requests.exceptions.ConnectionError as exc:
        return ("dead", None) if "Name or service not known" in str(exc) or "NameResolution" in str(exc) else ("error", None)
    except requests.RequestException:
        return "error", None
    c = r.status_code
    if c < 400:
        return "ok", c
    if c in (404, 410):
        return "dead", c
    if c in (401, 402, 403, 406, 429, 451, 999):
        return "blocked", c
    return "error", c


def wayback(url):
    try:
        r = requests.get("https://archive.org/wayback/available", params={"url": url}, headers=UA, timeout=30)
        snap = r.json().get("archived_snapshots", {}).get("closest") if r.ok else None
        return snap["url"] if snap and snap.get("available") else None
    except (requests.RequestException, ValueError):
        return None


def run(ctx):
    links = collect()
    week = str(int(time.time() // WEEK))
    # Deja verifies cette semaine et en bon etat : sautes. Les liens morts ou en erreur sont reverifies a chaque passe.
    done = {r["url"] for r in ctx.conn.execute("SELECT url FROM link_check WHERE pass = ? AND state IN ('ok', 'blocked')",
                                               (week,))}
    todo = [u for u in links if u not in done]
    for u in todo:
        if ctx.should_yield():
            return False
        if u.startswith("doi:"):
            try:
                state, code = check_doi(u[4:])
            except requests.RequestException:
                state, code = "error", None
        else:
            state, code = check_url(u)
        archive = wayback(u) if state == "dead" and not u.startswith("doi:") else None
        ctx.conn.execute("INSERT OR REPLACE INTO link_check VALUES (?,?,?,?,?,?,?)",
                         (u, links[u], state, code, archive, int(time.time()), week))
        ctx.conn.commit()
        time.sleep(0.3)
    ctx.conn.execute("DELETE FROM link_check WHERE pass != ?", (week,))
    rows = ctx.conn.execute("SELECT state, count(*) n FROM link_check GROUP BY state").fetchall()
    counts = {r["state"]: r["n"] for r in rows}
    ctx.set_output(db.sha(sorted(counts.items()), ctx.conn.execute(
        "SELECT group_concat(url || state) FROM (SELECT url, state FROM link_check WHERE state = 'dead' ORDER BY url)").fetchone()[0]))
    log(f"liens : {len(links)} verifies ; " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())))
    return True

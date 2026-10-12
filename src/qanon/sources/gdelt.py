"""GDELT 1.0 : un fichier d'evenements par jour (~5 Mo zippe, ~100 000 lignes).

Chaque jour est telecharge, lu en flux et reduit a des agregats (volume global,
par pays, par nom d'acteur), puis le curseur avance : un redemarrage reprend au
jour suivant. Rien du fichier brut n'est conserve.

Colonnes utilisees (58 au total, sans en-tete) : 6 Actor1Name, 16 Actor2Name,
28 EventRootCode, 30 GoldsteinScale, 31 NumMentions, 34 AvgTone,
51 ActionGeo_CountryCode (FIPS 10-4)."""
import datetime as dt
import io
import os
import zipfile
from collections import Counter, defaultdict

import requests

from .. import db
from ..log import log

URL = "https://data.gdeltproject.org/events/{}.export.CSV.zip"
START = dt.date.fromisoformat(os.environ.get("GDELT_START", "2017-10-01"))
END = dt.date.fromisoformat(os.environ.get("GDELT_END", "2021-01-31"))
MIN_NAME = 2
UA = {"User-Agent": "qanon-study/1.0 (+https://github.com/s-geffroy/QAnon)"}


def aggregate(raw):
    """Agregats d'un fichier quotidien (contenu zip en octets)."""
    day = {"events": 0, "mentions": 0, "tone_sum": 0.0, "us_events": 0, "us_protest": 0, "us_fight": 0}
    country = defaultdict(lambda: [0, 0, 0.0, 0.0])
    names = Counter()
    name_mentions = Counter()
    with zipfile.ZipFile(io.BytesIO(raw)) as z, z.open(z.namelist()[0]) as fh:
        for line in io.TextIOWrapper(fh, encoding="utf-8", errors="replace"):
            p = line.rstrip("\n").split("\t")
            if len(p) < 58:
                continue
            try:
                mentions = int(p[31] or 0)
                tone = float(p[34] or 0)
                goldstein = float(p[30] or 0)
            except ValueError:
                continue
            day["events"] += 1
            day["mentions"] += mentions
            day["tone_sum"] += tone
            fips = p[51]
            if fips:
                c = country[fips]
                c[0] += 1; c[1] += mentions; c[2] += tone; c[3] += goldstein
            if fips == "US":
                day["us_events"] += 1
                root = p[28]
                day["us_protest"] += root == "14"
                day["us_fight"] += root in ("18", "19", "20")
            for name in {p[6], p[16]} - {""}:
                names[name] += 1
                name_mentions[name] += mentions
    return day, country, {n: (k, name_mentions[n]) for n, k in names.items() if k >= MIN_NAME}


def run(ctx):
    cursor = ctx.cursor
    day = dt.date.fromisoformat(cursor) + dt.timedelta(days=1) if cursor else START
    done = 0
    while day <= END and not ctx.should_yield():
        key = day.isoformat()
        resp = requests.get(URL.format(day.strftime("%Y%m%d")), headers=UA, timeout=60)
        if resp.status_code == 404:
            ctx.conn.execute("INSERT OR REPLACE INTO gdelt_missing VALUES (?, ?)", (key, "404"))
            log(f"gdelt : {key} absent (404), ignore")
        else:
            resp.raise_for_status()
            agg, country, names = aggregate(resp.content)
            c = ctx.conn
            c.execute("DELETE FROM gdelt_country WHERE day = ?", (key,))
            c.execute("DELETE FROM gdelt_name WHERE day = ?", (key,))
            c.execute("INSERT OR REPLACE INTO gdelt_day VALUES (?,?,?,?,?,?,?)",
                      (key, agg["events"], agg["mentions"], agg["tone_sum"],
                       agg["us_events"], agg["us_protest"], agg["us_fight"]))
            c.executemany("INSERT INTO gdelt_country VALUES (?,?,?,?,?,?)",
                          [(key, f, *v) for f, v in country.items()])
            c.executemany("INSERT INTO gdelt_name VALUES (?,?,?,?)",
                          [(key, n, k, m) for n, (k, m) in names.items()])
        ctx.save_cursor(key)  # valide le jour et son curseur ensemble
        done += 1
        day += dt.timedelta(days=1)
    total = (END - START).days + 1
    progress = (day - START).days
    if day > END:
        n = ctx.conn.execute("SELECT count(*), sum(events) FROM gdelt_day").fetchone()
        ctx.set_output(db.sha(START, END, n[0], n[1]))
        log(f"gdelt : termine, {n[0]} jours, {n[1]} evenements")
        return True
    log(f"gdelt : {done} jour(s) traite(s), {progress}/{total} (jusqu'au {(day - dt.timedelta(days=1)).isoformat()})")
    return False

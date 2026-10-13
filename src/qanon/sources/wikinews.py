"""Actualite quotidienne : portail « Current events » de Wikipedia en anglais,
une page par jour (resume editorial des faits marquants, avec sources).

Sert de reference d'actualite au test de l'horoscope. Les items sont stockes
en texte brut, un par ligne ; reprenable jour par jour."""
import datetime as dt
import re
import time

import requests

from .. import db
from ..log import log

API = "https://en.wikipedia.org/w/api.php"
UA = {"User-Agent": "qanon-study/1.0 (+https://github.com/s-geffroy/QAnon)"}
START, END = dt.date(2017, 10, 1), dt.date(2021, 1, 31)


def page_title(day):
    return f"Portal:Current events/{day.year}_{day.strftime('%B')}_{day.day}"


def items(wikitext):
    """Items d'actualite (puces de second niveau ou de premier niveau sans sous-puce), en texte brut."""
    out = []
    for line in wikitext.splitlines():
        m = re.match(r"^(\*+)\s*(.*)$", line)
        if not m:
            continue
        text = m.group(2)
        text = re.sub(r"\[https?://\S+\s*\(([^)]*)\)\]", "", text)      # [url (Source)]
        text = re.sub(r"\[https?://\S+[^\]]*\]", "", text)
        text = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]", r"\1", text)   # [[cible|libelle]]
        text = re.sub(r"\{\{convert\|([\d.,]+)\|(\w+)[^}]*\}\}", r"\1 \2", text)
        text = re.sub(r"\{\{[^{}]*\}\}", "", text)
        text = re.sub(r"<[^>]+>", "", text).replace("'''", "").replace("''", "")
        text = re.sub(r"\s+", " ", text).strip()
        # Une puce de premier niveau est souvent un simple intitule (« Brexit ») : on garde les phrases.
        if len(text.split()) >= 6:
            out.append(text)
    return out


def run(ctx):
    day = dt.date.fromisoformat(ctx.cursor) if ctx.cursor else START
    while day <= END:
        if ctx.should_yield():
            return False
        r = requests.get(API, params={"action": "parse", "page": page_title(day), "prop": "wikitext",
                                      "format": "json", "formatversion": 2, "redirects": 1},
                         headers=UA, timeout=60)
        r.raise_for_status()
        data = r.json()
        found = items(data["parse"]["wikitext"]) if "parse" in data else []
        ctx.conn.execute("INSERT OR REPLACE INTO wikinews VALUES (?, ?)", (day.isoformat(), "\n".join(found)))
        day += dt.timedelta(days=1)
        ctx.save_cursor(day.isoformat())
        time.sleep(0.2)  # politesse envers l'API
    n = ctx.conn.execute("SELECT count(*), sum(length(text) - length(replace(text, char(10), '')) + (text != '')) "
                         "FROM wikinews").fetchone()
    ctx.set_output(db.sha(n[0], n[1]))
    log(f"actualite Wikipedia : {n[0]} jours, {n[1]} items")
    return True

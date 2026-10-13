"""Actualite quotidienne : portail « Current events » de Wikipedia en anglais,
une page par jour (resume editorial des faits marquants, avec sources).

Sert de reference d'actualite au test de l'horoscope. Le wikitexte est stocke
tel quel ; les items en sont extraits a la lecture. Reprenable jour par jour."""
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


def _plain(text):
    text = re.sub(r"\[https?://\S+\s*\(([^)]*)\)\]", "", text)      # [url (Source)]
    text = re.sub(r"\[https?://\S+[^\]]*\]", "", text)
    text = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]", r"\1", text)   # [[cible|libelle]]
    text = re.sub(r"\{\{convert\|([\d.,]+)\|(\w+)[^}]*\}\}", r"\1 \2", text)
    text = re.sub(r"\{\{[^{}]*\}\}", "", text)
    text = re.sub(r"<[^>]+>", "", text).replace("'''", "").replace("''", "")
    return re.sub(r"\s+", " ", text).strip()


def items(wikitext):
    """Items d'actualite en texte brut : les puces sans sous-puce. Une puce suivie
    de puces plus profondes est un intitule de sujet (« Brexit »), pas un item."""
    bullets = [(len(m.group(1)), m.group(2)) for m in
               (re.match(r"^(\*+)\s*(.*)$", line) for line in wikitext.splitlines()) if m]
    out = []
    for i, (level, text) in enumerate(bullets):
        if i + 1 < len(bullets) and bullets[i + 1][0] > level:
            continue
        text = _plain(text)
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
        # Texte source conserve tel quel : l'extraction des items se fait a la lecture.
        raw = data["parse"]["wikitext"] if "parse" in data else ""
        ctx.conn.execute("INSERT OR REPLACE INTO wikinews_raw VALUES (?, ?)", (day.isoformat(), raw))
        day += dt.timedelta(days=1)
        ctx.save_cursor(day.isoformat())
        time.sleep(0.2)  # politesse envers l'API
    rows = ctx.conn.execute("SELECT day, wikitext FROM wikinews_raw").fetchall()
    n_items = sum(len(items(r["wikitext"])) for r in rows)
    ctx.set_output(db.sha(len(rows), n_items))
    log(f"actualite Wikipedia : {len(rows)} jours, {n_items} items")
    return True

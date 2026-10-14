"""Google Trends (API non officielle, pytrends), Etats-Unis, 2016-2023.

Google normalise chaque requete a son propre maximum (0-100) : chaque lot de
quatre termes contient donc une meme ancre stable ('conspiracy theory', non
nulle avant Q), ce qui rend les lots comparables (terme / ancre). Trois
fenetres par lot : semaines 2016-2020 et 2019-2023 (recollees sur leur
recouvrement par l'analyse), mois 2016-2023. Une requete par appel, pause
entre deux ; un refus (429) remet au cycle suivant. Etape fragile par nature :
elle ne bloque pas le site."""
import time

from .. import db, lexicon
from ..log import log

ANCHOR = "conspiracy theory"
WINDOWS = ("2016-01-01 2020-12-31", "2019-01-01 2023-12-31", "2016-01-01 2023-12-31")
GEO = "US"
PER_BATCH = 4
PAUSE = 8


def queries():
    seen, out = set(), []
    for t in lexicon.load():
        if t.trends:
            q = t.trends_query or t.label_en
            if q.lower() not in seen and q != ANCHOR:
                seen.add(q.lower())
                out.append(q)
    return out


def jobs():
    qs = queries()
    batches = [qs[i:i + PER_BATCH] for i in range(0, len(qs), PER_BATCH)]
    return [(b, w) for b in batches for w in WINDOWS]


def fetch(batch, window):
    from pytrends.request import TrendReq
    # Sans relances internes : pytrends 4.9.2 les passe a urllib3 sous un nom retire en 2.x.
    p = TrendReq(hl="en-US", tz=0, timeout=(10, 30))
    p.build_payload(batch + [ANCHOR], timeframe=window, geo=GEO)
    return p.interest_over_time()


def run(ctx):
    J = jobs()
    i = start = int(ctx.cursor or 0)
    while i < len(J):
        if i > start:
            if ctx.should_yield():
                return False
            time.sleep(PAUSE)
        batch, window = J[i]
        try:
            df = fetch(batch, window)
        except Exception as exc:   # 429, blocage, reponse vide : on reessaie au cycle suivant
            log(f"trends : lot {i + 1}/{len(J)} differe ({exc!r:.160})")
            return None
        key = "|".join(batch)
        ctx.conn.execute("DELETE FROM trends_raw WHERE batch = ? AND window = ?", (key, window))
        rows = [(key, window, q, d.strftime("%Y-%m-%d"), int(r[q]), int(bool(r.get("isPartial", False))))
                for d, r in df.iterrows() for q in batch + [ANCHOR] if q in df.columns]
        ctx.conn.executemany("INSERT INTO trends_raw VALUES (?,?,?,?,?,?)", rows)
        i += 1
        ctx.save_cursor(str(i))
    n = ctx.conn.execute("SELECT count(DISTINCT query), count(*), sum(value) FROM trends_raw").fetchone()
    ctx.set_output(db.sha(*n))
    log(f"trends : {n[0]} requetes (ancre comprise), {n[1]} points")
    return True

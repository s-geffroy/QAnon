"""Google Trends (API non officielle, pytrends), Etats-Unis, 2016-2023.

Google normalise chaque requete a son propre maximum (0-100), en entiers : un
terme rare place a cote d'un terme frequent tombe a 0 ou 1. On mesure donc
separement :
- la FORME : chaque terme interroge seul, trois fenetres (semaines 2016-2020 et
  2019-2023, recollees par l'analyse ; mois 2016-2023), a pleine resolution ;
- le NIVEAU : chaque terme interroge avec une ancre stable ('conspiracy theory',
  non nulle avant Q), en mois 2016-2023 ; il rend les termes comparables entre eux.
Une requete par appel, pause entre deux ; un refus (429) suspend la collecte.
Etape fragile par nature : elle ne bloque pas le site."""
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
    """(cle de lot, requetes, fenetre) : forme seule sur trois fenetres, niveau avec l'ancre en mois."""
    out = []
    for q in queries():
        out += [(f"solo:{q}", [q], w) for w in WINDOWS]
        out.append((f"anchor:{q}", [q, ANCHOR], WINDOWS[2]))
    return out


def fetch(batch, window):
    from pytrends.request import TrendReq
    # Sans relances internes : pytrends 4.9.2 les passe a urllib3 sous un nom retire en 2.x.
    p = TrendReq(hl="en-US", tz=0, timeout=(10, 30))
    p.build_payload(batch, timeframe=window, geo=GEO)
    return p.interest_over_time()


def run(ctx):
    """Reprenable par les donnees : un lot deja en base n'est pas redemande. Un refus de
    Google suspend la collecte (15 min, puis le double a chaque refus, 6 h au plus) au
    lieu de le relancer a chaque cycle, ce qui entretiendrait le blocage."""
    now = time.time()
    until = float(db.get_meta(ctx.conn, "trends_blocked_until", 0) or 0)
    if now < until:
        return None
    J = jobs()
    have = {(r[0], r[1]) for r in ctx.conn.execute("SELECT DISTINCT batch, window FROM trends_raw")}
    todo = [(key, b, w) for key, b, w in J if (key, w) not in have]
    for k, (key, batch, window) in enumerate(todo):
        if k:
            if ctx.should_yield():
                return False
            time.sleep(PAUSE)
        try:
            df = fetch(batch, window)
        except Exception as exc:   # 429, blocage, reponse vide
            wait = min(2 * float(db.get_meta(ctx.conn, "trends_backoff", 450) or 450), 6 * 3600)
            db.set_meta(ctx.conn, "trends_backoff", wait)
            db.set_meta(ctx.conn, "trends_blocked_until", now + wait)
            ctx.conn.commit()
            log(f"trends : {len(J) - len(todo) + k}/{len(J)} lots acquis ; refus ({exc!r:.100}), "
                f"nouvel essai dans {wait / 60:.0f} min")
            return None
        ctx.conn.execute("DELETE FROM trends_raw WHERE batch = ? AND window = ?", (key, window))
        rows = [(key, window, q, d.strftime("%Y-%m-%d"), int(r[q]), int(bool(r.get("isPartial", False))))
                for d, r in df.iterrows() for q in batch if q in df.columns]
        ctx.conn.executemany("INSERT INTO trends_raw VALUES (?,?,?,?,?,?)", rows)
        db.set_meta(ctx.conn, "trends_backoff", 450)
        ctx.conn.commit()
    # Lots d'une liste anterieure de requetes : retires.
    keys = {(key, w) for key, _, w in J}
    for b, w in have - keys:
        ctx.conn.execute("DELETE FROM trends_raw WHERE batch = ? AND window = ?", (b, w))
    n = ctx.conn.execute("SELECT count(DISTINCT query), count(*), sum(value) FROM trends_raw").fetchone()
    ctx.set_output(db.sha(*n))
    log(f"trends : {n[0]} requetes (ancre comprise), {n[1]} points")
    return True

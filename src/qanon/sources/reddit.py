"""Reddit complotiste, via l'API Arctic Shift (archive de Reddit, subreddits
bannis compris).

La recherche plein texte de l'API ne cherche pas les phrases ('trust the plan'
ramene 'trust' ... 'plan') et ses agregats par terme expirent : on n'y compte
donc pas les termes. A la place :
- volumes exacts : posts et commentaires par jour (/api/time_series) ;
- echantillon systematique : chaque jour actif, les 100 premiers commentaires de
  chacun de trois creneaux de 8 h et les 50 premiers posts de deux creneaux de
  12 h ; le texte
  est garde (sans auteur) pour pouvoir rejouer tout lexique futur ;
- comptage : le lexique (qanon.lexicon), le meme que pour /pol/, est applique a
  l'echantillon. Compte estime = part des elements echantillonnes x volume.
"""
import calendar
import time

import requests

from .. import db, lexicon
from ..analysis.common import load_yaml
from ..log import log

API = "https://arctic-shift.photon-reddit.com/api"
UA = {"User-Agent": "qanon-study/1.0 (+https://github.com/s-geffroy/QAnon)"}
START_YEAR, END_YEAR = 2016, 2023
SLOTS_H = {"comments": (0, 8, 16), "posts": (0, 12)}
LIMIT = {"comments": 100, "posts": 50}
RETRIES = 4
DAY = 86400
GONE = {"[deleted]", "[removed]", ""}
BOTS = {"AutoModerator"}


class Busy(Exception):
    """Limite de debit ou expiration cote serveur : on reessaie au cycle suivant."""


def get(path, **params):
    try:
        r = requests.get(API + path, params=params, headers=UA, timeout=60)
    except requests.RequestException as exc:
        raise Busy(repr(exc)) from exc
    if r.status_code in (422, 429, 500, 502, 503, 504):
        raise Busy(f"{r.status_code} {r.text[:120]}")
    r.raise_for_status()
    return r.json()["data"]


def get_retry(path, pause, **params):
    """Les 422 'Timeout. Maybe slow down' sont frequents et passagers : on attend
    (3, 6, 9 s) et on reessaie avant d'abandonner le cycle."""
    for attempt in range(RETRIES):
        try:
            return get(path, **params)
        except Busy:
            if attempt == RETRIES - 1 or not pause(3 * (attempt + 1)):
                raise


def subreddits():
    return [s["name"] for s in load_yaml("scene", "subreddits")]


# ------------------------------------------------------------------ volumes
def run_volume(ctx):
    jobs = [(s, k, y) for s in subreddits() for k in ("posts", "comments") for y in range(START_YEAR, END_YEAR + 1)]
    i = start = int(ctx.cursor or 0)
    while i < len(jobs):
        if i > start and ctx.should_yield():
            return False
        sub, kind, year = jobs[i]
        try:
            data = get("/time_series", key=f"r/{sub}/{kind}/count", precision="day",
                       after=f"{year}-01-01", before=f"{year + 1}-01-01")
        except Busy as exc:
            log(f"reddit : volumes r/{sub} {kind} {year} differes ({exc})")
            return None
        rows = [(sub, kind, time.strftime("%Y-%m-%d", time.gmtime(x["date"])), int(x["value"]))
                for x in data or [] if x.get("value")]
        ctx.conn.execute("DELETE FROM reddit_volume WHERE sub = ? AND kind = ? AND day LIKE ?", (sub, kind, f"{year}-%"))
        ctx.conn.executemany("INSERT OR REPLACE INTO reddit_volume VALUES (?,?,?,?)", rows)
        i += 1
        ctx.save_cursor(str(i))
    n = ctx.conn.execute("SELECT count(*), sum(n) FROM reddit_volume").fetchone()
    ctx.set_output(db.sha(n[0], n[1]))
    log(f"reddit : volumes de {len(subreddits())} subreddits, {n[0]} jours, {n[1]} elements")
    return True


# ------------------------------------------------------------------ echantillon
def _text(kind, x):
    if kind == "comments":
        return x.get("body") or ""
    t, s = x.get("title") or "", x.get("selftext") or ""
    return t if s in GONE else f"{t}\n{s}"


def sample_day(conn, sub, day, pause=lambda s: False):
    """Echantillonne un jour : trois creneaux, commentaires et posts."""
    t0 = calendar.timegm(time.strptime(day, "%Y-%m-%d"))
    for kind in ("comments", "posts"):
        fields = "id,created_utc,author," + ("body" if kind == "comments" else "title,selftext")
        n = gone = bots = 0
        complete = True
        rows = []
        width = 24 // len(SLOTS_H[kind]) * 3600
        for h in SLOTS_H[kind]:
            a = t0 + h * 3600
            data = get_retry(f"/{kind}/search", pause, subreddit=sub, after=a, before=a + width,
                             limit=LIMIT[kind], sort="asc", fields=fields)
            complete &= len(data) < LIMIT[kind]
            for x in data:
                if x.get("author") in BOTS:
                    bots += 1
                    continue
                txt = _text(kind, x)
                if (x.get("body") if kind == "comments" else x.get("title")) in GONE:
                    gone += 1
                    continue
                n += 1
                rows.append((sub, kind, x["id"], int(x["created_utc"]), txt))
        conn.executemany("INSERT OR IGNORE INTO reddit_sample VALUES (?,?,?,?,?)", rows)
        conn.execute("INSERT OR REPLACE INTO reddit_sample_day VALUES (?,?,?,?,?,?,?)",
                     (sub, kind, day, n, gone, bots, int(complete)))


def _pause(ctx, seconds):
    """Attente fractionnee ; faux si le cycle doit rendre la main (budget, SIGTERM)."""
    for _ in range(seconds):
        if ctx.should_yield():
            return False
        time.sleep(1)
    return True


def run_sample(ctx):
    """Jours actifs (volume > 0) pas encore echantillonnes ; petits subreddits d'abord."""
    order = sorted(subreddits(), key=lambda s: ctx.conn.execute(
        "SELECT coalesce(sum(n), 0) FROM reddit_volume WHERE sub = ?", (s,)).fetchone()[0])
    done_any = False
    for sub in order:
        todo = [r[0] for r in ctx.conn.execute(
            "SELECT DISTINCT day FROM reddit_volume v WHERE sub = ? AND NOT EXISTS ("
            " SELECT 1 FROM reddit_sample_day d WHERE d.sub = v.sub AND d.day = v.day AND d.kind = 'posts')"
            " ORDER BY day", (sub,))]
        for day in todo:
            if done_any and ctx.should_yield():
                return False
            try:
                sample_day(ctx.conn, sub, day, pause=lambda s: _pause(ctx, s))
            except Busy as exc:
                ctx.conn.rollback()
                log(f"reddit : echantillon r/{sub} {day} differe ({exc})")
                return None
            ctx.conn.commit()
            done_any = True
    n = ctx.conn.execute("SELECT count(*), sum(n_sampled) FROM reddit_sample_day").fetchone()
    ctx.set_output(db.sha(n[0], n[1]))
    log(f"reddit : echantillon complet, {n[0]} jours-types, {n[1]} elements")
    return True


# ------------------------------------------------------------------ activite horaire
HOURLY = ("greatawakening", "CBTS_Stream")


def hour_bins(data):
    """Creneaux horaires de l'agregat Arctic Shift. L'etiquette est decalee d'une heure
    (verifie le 14/10/2026 : le creneau marque 23:00 contient les commentaires de
    00:00-01:00 UTC) : on la corrige."""
    out = []
    for x in data or []:
        t = calendar.timegm(time.strptime(x["created_utc"][:19], "%Y-%m-%dT%H:%M:%S")) + 3600
        out.append((t, int(x["count"])))
    return out


HOUR_SHARE = 15   # secondes par cycle : laisse le reste du budget a l'echantillon


def run_hour(ctx):
    """Commentaires par heure des subreddits Q (fonction de reponse aux drops), jour par jour."""
    done_any = False
    stop = time.monotonic() + HOUR_SHARE
    for sub in HOURLY:
        todo = [r[0] for r in ctx.conn.execute(
            "SELECT day FROM reddit_volume v WHERE sub = ? AND kind = 'comments' AND NOT EXISTS ("
            " SELECT 1 FROM reddit_hour_day d WHERE d.sub = v.sub AND d.day = v.day) ORDER BY day", (sub,))]
        for day in todo:
            if done_any and (ctx.should_yield() or time.monotonic() > stop):
                return False
            t0 = calendar.timegm(time.strptime(day, "%Y-%m-%d"))
            try:
                data = get_retry("/comments/search/aggregate", lambda s: _pause(ctx, s), subreddit=sub,
                                 aggregate="created_utc", frequency="hour", after=t0, before=t0 + DAY)
            except Busy as exc:
                log(f"reddit : heures r/{sub} {day} differees ({exc})")
                return None
            rows = [(sub, t, n) for t, n in hour_bins(data) if t0 <= t < t0 + DAY]
            ctx.conn.executemany("INSERT OR REPLACE INTO reddit_hour VALUES (?,?,?)", rows)
            ctx.conn.execute("INSERT OR REPLACE INTO reddit_hour_day VALUES (?,?,?)", (sub, day, sum(r[2] for r in rows)))
            ctx.conn.commit()
            done_any = True
    n = ctx.conn.execute("SELECT count(*), sum(n) FROM reddit_hour").fetchone()
    ctx.set_output(db.sha(n[0], n[1]))
    log(f"reddit : activite horaire de {', '.join(HOURLY)}, {n[0]} heures, {n[1]} commentaires")
    return True


# ------------------------------------------------------------------ comptage
def run_scan(ctx):
    """Applique le lexique a l'echantillon, par paquets (curseur = empreinte du
    lexique : rowid). Un lexique modifie recompte tout."""
    terms = lexicon.load()
    fp = lexicon.fingerprint(terms)
    cur = ctx.cursor or ""
    last = int(cur.split(":")[1]) if cur.startswith(fp + ":") else 0
    if not last:
        ctx.conn.execute("DELETE FROM reddit_term_day")
    m = lexicon.Matcher(terms)
    while True:
        rows = ctx.conn.execute("SELECT rowid, sub, kind, ts, text FROM reddit_sample WHERE rowid > ? "
                                "ORDER BY rowid LIMIT 5000", (last,)).fetchall()
        if not rows:
            break
        acc = {}
        for r in rows:
            day = time.strftime("%Y-%m-%d", time.gmtime(r["ts"]))
            for i in m.hits(r["text"]):
                k = (r["sub"], r["kind"], day, terms[i].id)
                acc[k] = acc.get(k, 0) + 1
        ctx.conn.executemany("INSERT INTO reddit_term_day VALUES (?,?,?,?,?) ON CONFLICT(sub, kind, day, term) "
                             "DO UPDATE SET n = n + excluded.n", [(*k, v) for k, v in acc.items()])
        last = rows[-1]["rowid"]
        ctx.save_cursor(f"{fp}:{last}")
        if ctx.should_yield():
            return False
    n = ctx.conn.execute("SELECT count(*), coalesce(sum(n), 0) FROM reddit_term_day").fetchone()
    ctx.set_output(db.sha(fp, last, n[0], n[1]))
    log(f"reddit : lexique {fp} applique jusqu'a l'element {last} ({n[1]} correspondances)")
    return True

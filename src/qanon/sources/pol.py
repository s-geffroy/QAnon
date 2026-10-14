"""4chan /pol/ (Papasavva et al., ICWSM 2020 ; Zenodo 3606810, CC BY 4.0) :
134,5 M posts, juin 2016 - novembre 2019. Lu une seule fois, puis supprime.

- fetch_pol : telechargement reprenable en fil de fond (requetes partielles ;
  l'etat est la taille du fichier), puis verification md5 par tranches.
"""
import hashlib
import time

import requests

from .. import db
from ..log import log

URL = "https://zenodo.org/records/3606810/files/pol_0616-1119_labeled.tar.zst?download=1"
SIZE = 24_039_475_594
MD5 = "3ad65640bf590d77af0f931045aef2e0"
CHUNK = 1 << 20
SHARE = 20   # secondes par cycle pour le md5 : laisse le reste du budget aux autres etapes
UA = {"User-Agent": "qanon-study/1.0 (+https://github.com/s-geffroy/QAnon)"}

# Hachage md5 en cours (24 Go ne se hachent pas en un cycle) : etat garde en memoire du
# processus ; un redemarrage le reprend au debut.
_md5 = {"h": None, "pos": 0}


def paths(state):
    d = state / "cache" / "pol"
    d.mkdir(parents=True, exist_ok=True)
    return d / "pol.tar.zst.part", d / "pol.tar.zst"


def _download(part):
    """Fil de fond : Zenodo plafonne le debit par adresse (~0,45 Mo/s, 4 connexions n'y
    changent rien), soit ~15 h pour 24 Go. Le telechargement attend le reseau, pas le
    processeur : il tourne a cote de la boucle au lieu d'en consommer le budget. L'etat
    est la taille du fichier partiel ; un arret brutal ne perd que le dernier bloc."""
    while True:
        have = part.stat().st_size if part.exists() else 0
        if have >= SIZE:
            return
        try:
            with requests.get(URL, headers={**UA, "Range": f"bytes={have}-"}, stream=True, timeout=60) as r:
                if r.status_code != 206:
                    raise RuntimeError(f"requete partielle refusee : HTTP {r.status_code}")
                with open(part, "ab") as f:
                    for block in r.iter_content(CHUNK):
                        f.write(block)
                        have += len(block)
                        if have % 10**9 < len(block):
                            f.flush()
                            log(f"pol : {have / 1e9:.0f} / {SIZE / 1e9:.1f} Go")
        except Exception as exc:
            log(f"pol : telechargement interrompu a {have / 1e9:.2f} Go ({exc!r:.120}) ; reprise dans 60 s")
            time.sleep(60)


_thread = {"t": None}


def run_fetch(ctx):
    import threading
    part, final = paths(ctx.state)
    if final.exists():
        ctx.set_output(db.sha(MD5))
        return True
    have = part.stat().st_size if part.exists() else 0
    if have < SIZE:
        t = _thread["t"]
        if t is None or not t.is_alive():
            _thread["t"] = threading.Thread(target=_download, args=(part,), daemon=True, name="pol-download")
            _thread["t"].start()
            log(f"pol : telechargement en fond depuis {have / 1e9:.2f} Go")
        ctx.save_cursor(str(have))
        return None
    if have > SIZE:
        part.unlink()
        raise RuntimeError("fichier plus grand qu'attendu : supprime, telechargement repris a zero")
    # Verification md5, par tranches.
    if _md5["h"] is None:
        _md5["h"], _md5["pos"] = hashlib.md5(), 0
    t0 = time.monotonic()
    with open(part, "rb") as f:
        f.seek(_md5["pos"])
        while _md5["pos"] < SIZE:
            block = f.read(64 * CHUNK)
            _md5["h"].update(block)
            _md5["pos"] += len(block)
            if ctx.should_yield() or time.monotonic() - t0 > SHARE:
                return False
    digest = _md5["h"].hexdigest()
    _md5["h"] = None
    if digest != MD5:
        part.unlink()
        raise RuntimeError(f"md5 {digest} different de {MD5} : fichier supprime, telechargement repris a zero")
    part.rename(final)
    ctx.set_output(db.sha(MD5))
    log(f"pol : archive complete et verifiee (md5 {MD5})")
    return True


# ------------------------------------------------------------------ lecture du flux
import html
import json
import random
import re

_TAG = re.compile(r"<br\s*/?>|</?(?:wbr)>", re.I)
_ANY_TAG = re.compile(r"<[^>]+>")
_TIME = re.compile(rb'"time": "(\d+)"')


def text_of(com):
    """HTML d'un post 4chan -> texte (sauts de ligne gardes, balises retirees, entites decodees)."""
    if not com:
        return ""
    t = _TAG.sub(lambda m: "\n" if m.group(0)[1:3].lower() == "br" else "", com)
    return html.unescape(_ANY_TAG.sub("", t))


def thread_time(line):
    """Heure du message d'ouverture, lue dans les premiers octets de la ligne, sans decoder le JSON."""
    m = _TIME.search(line, 0, 2000)
    return int(m.group(1)) if m else None


class Stream:
    """Fils de l'archive, un par ligne (NDJSON dans un tar compresse en zstd). L'etat du flux
    vit en memoire du processus d'un cycle a l'autre ; apres un redemarrage, on saute les
    lignes deja traitees (sans les decoder)."""

    def __init__(self, path):
        import tarfile
        import zstandard
        self.f = open(path, "rb")
        self.tar = tarfile.open(fileobj=zstandard.ZstdDecompressor().stream_reader(self.f, read_size=1 << 22), mode="r|")
        self.member = self.tar.extractfile(next(iter(self.tar)))
        self.n = 0

    def skip_to(self, target, should_yield):
        """Saute jusqu'a la ligne `target`, par paquets : vrai une fois arrive."""
        while self.n < target:
            for _ in range(min(10_000, target - self.n)):
                if not self.member.readline():
                    return True
                self.n += 1
            if should_yield():
                return self.n >= target
        return True

    def next(self):
        line = self.member.readline()
        if not line:
            return None
        self.n += 1
        return line

    def close(self):
        self.f.close()


_streams = {}


def stream(ctx, name, path, n_done):
    """Flux positionne a la ligne n_done, ou None s'il faut encore sauter des lignes au cycle suivant."""
    s = _streams.get(name)
    if s is None or s.n > n_done:
        if s:
            s.close()
        s = _streams[name] = Stream(path)
    if s.n < n_done and not s.skip_to(n_done, ctx.should_yield):
        log(f"pol : reprise de la lecture ({name}), {s.n} / {n_done} fils sautes")
        return None
    return s


# ------------------------------------------------------------------ calibration
Q_BIRTH = (1509148800, 1512086400)    # 2017-10-28 -> 2017-12-01 UTC
CAL_END = 1514764800                  # premier fil ouvert apres le 01/01/2018 : fin de la calibration
CAL_SAMPLE = 20                       # un fil sur 20 hors de la naissance de Q
N_EX = 5


def calib_path(state):
    return state / "cache" / "pol" / "calibration.json"


def run_calibrate(ctx):
    """Lexique applique a /pol/ jusqu'a fin 2017 : tous les fils de la naissance de Q, un
    fil sur 20 avant. Rapport (comptes, extraits tires au hasard, motifs muets ou trop
    bavards) dans /state/cache/pol, hors des resultats publies. Le balayage complet
    attend ensuite l'approbation de l'empreinte du lexique (scene.yaml : lexicon_approved)."""
    from .. import lexicon
    part, final = paths(ctx.state)
    terms = lexicon.load()
    fp = lexicon.fingerprint(terms)
    path = calib_path(ctx.state)
    state = json.loads(path.read_text()) if path.exists() else None
    if not state or state.get("fingerprint") != fp:
        state = {"fingerprint": fp, "lines": 0, "done": False, "posts": {"birth": 0, "sample": 0},
                 "threads": {"birth": 0, "sample": 0}, "months": {},
                 "terms": {t.id: {"birth": 0, "sample": 0, "ex": [], "seen": 0} for t in terms}}
    if state["done"]:
        ctx.set_output(db.sha(fp, "calibre"))
        return True
    m = lexicon.Matcher(terms)
    rng = random.Random(state["lines"])
    s = stream(ctx, "calibrate", final, state["lines"])
    if s is None:
        return False
    late = 0
    while True:
        line = s.next()
        if line is None:
            break
        t0 = thread_time(line) or 0
        late = late + 1 if t0 >= CAL_END else 0
        if late > 2000:          # l'archive est presque chronologique : on a depasse fin 2017
            break
        where = "birth" if Q_BIRTH[0] <= t0 < Q_BIRTH[1] else ("sample" if s.n % CAL_SAMPLE == 0 and t0 < Q_BIRTH[0] else None)
        if where:
            posts = json.loads(line)["posts"]
            state["threads"][where] += 1
            for p in posts:
                txt = text_of(p.get("com"))
                if p.get("sub"):
                    txt = f"{html.unescape(p['sub'])}\n{txt}"
                state["posts"][where] += 1
                mo = time.strftime("%Y-%m", time.gmtime(int(p.get("time", t0))))
                state["months"][mo] = state["months"].get(mo, 0) + 1
                for i in m.hits(txt):
                    r = state["terms"][terms[i].id]
                    r[where] += 1
                    r["seen"] += 1
                    # Echantillon par reservoir : chaque occurrence a la meme chance d'etre gardee.
                    if len(r["ex"]) < N_EX:
                        r["ex"].append(_snippet(txt, terms[i].rx))
                    elif rng.random() < N_EX / r["seen"]:
                        r["ex"][rng.randrange(N_EX)] = _snippet(txt, terms[i].rx)
        if s.n % 200 == 0 and ctx.should_yield():
            break
    state["lines"] = s.n
    if line is None or late > 2000:
        state["done"] = True
        _streams.pop("calibrate").close()
    path.write_text(json.dumps(state, ensure_ascii=False))
    ctx.save_cursor(str(s.n))
    if not state["done"]:
        return False
    silent = [k for k, v in state["terms"].items() if v["birth"] + v["sample"] == 0]
    log(f"pol : calibration terminee ({state['posts']['birth']} posts de la naissance de Q, "
        f"{state['posts']['sample']} en echantillon) ; {len(silent)} termes muets ; lexique {fp}")
    ctx.set_output(db.sha(fp, "calibre"))
    return True


def _snippet(txt, rx, width=90):
    mt = rx.search(txt)
    a = max(0, mt.start() - width)
    return " ".join(txt[a:mt.end() + width].split())


# ------------------------------------------------------------------ balayage complet
# Couches produites (toutes en une transaction a chaque point de reprise) :
#   pol_hour (heure, terme, posts)           comptes du lexique, a l'heure
#   pol_hour_total (heure, posts, fils)      denominateurs
#   pol_first (terme, ts, post)              premiere occurrence
#   pol_qcorpus                              sous-corpus Q en texte integral
#   pol_sample                               1 % de tous les posts (numero divisible par 100), texte integral
#   pol_unigram_month / pol_entity_month     mots (>= 5 par mois) et entites nommees du dataset, par mois
#   pol_tox_day                              scores Perspective par jour, tout /pol/ et sous-corpus Q
# Les pseudonymes et identifiants d'auteurs ne sont jamais gardes.
CHECKPOINT = 50_000          # fils entre deux points de reprise (~2 M de posts)
SCAN_SHARE = 30              # secondes par cycle
MIN_MONTH = 5                # mots gardes : au moins 5 occurrences dans le mois
MAX_VOCAB = 2_000_000        # au-dela, les mots vus une seule fois sont elagues (perte documentee)
Q_FAMILIES = ("q_core", "q_mythos", "larp", "promoter")
_THREAD_Q = re.compile(r"(?i)\bCBTS\b|calm before the storm|\bQ ?(?:research|general|anon|drops?|posts?)\b|\bqanon\b|"
                       r"\bthe storm\b.{0,20}\bgeneral\b|!ITPb\.qbhqo")
_TOKEN = re.compile(r"[a-z][a-z0-9']{1,29}")
_ENT = re.compile(r"'entity_text': '((?:[^'\\]|\\.){1,80})'.{0,80}?'entity_label': '([A-Z_]+)'")
_PERSP = re.compile(r"'([A-Z_]+)': ([0-9.eE-]+)")


def approved(terms):
    from .. import lexicon
    import yaml
    from ..pipeline import APP_DIR
    doc = yaml.safe_load((APP_DIR / "data" / "scene.yaml").read_text())
    return doc.get("lexicon_approved") == lexicon.fingerprint(terms)


class Scan:
    """Accumulateurs entre deux points de reprise."""

    def __init__(self):
        self.hour, self.total, self.first = {}, {}, {}
        self.qcorpus, self.sample, self.tox = [], [], {}
        self.uni, self.ent = {}, {}           # mois -> Counter

    def month_counter(self, store, month):
        from collections import Counter
        return store.setdefault(month, Counter())


def _drop_posts(conn):
    rows = conn.execute("SELECT post_id FROM drops WHERE site = '4ch' AND board LIKE '%pol%'").fetchall()
    return {str(r[0]) for r in rows if r[0]}


def _load_staging(conn, acc):
    from collections import Counter
    for m, tok, n in conn.execute("SELECT month, token, n FROM pol_unigram_stage"):
        acc.uni.setdefault(m, Counter())[tok] = n
    for m, ent, lab, n in conn.execute("SELECT month, entity, label, n FROM pol_entity_stage"):
        acc.ent.setdefault(m, Counter())[(ent, lab)] = n


def _checkpoint(conn, acc, closed_before, cursor_value, cursor_save):
    """Ecrit tout, mois clos elagues dans les tables finales, mois ouverts en transit."""
    c = conn
    c.executemany("INSERT INTO pol_hour VALUES (?,?,?) ON CONFLICT(hour, term) DO UPDATE SET n = n + excluded.n",
                  [(h, t, n) for (h, t), n in acc.hour.items()])
    c.executemany("INSERT INTO pol_hour_total VALUES (?,?,?) ON CONFLICT(hour) DO UPDATE SET "
                  "posts = posts + excluded.posts, threads = threads + excluded.threads",
                  [(h, p, t) for h, (p, t) in acc.total.items()])
    c.executemany("INSERT INTO pol_first VALUES (?,?,?) ON CONFLICT(term) DO UPDATE SET ts = excluded.ts, "
                  "post = excluded.post WHERE excluded.ts < pol_first.ts", [(t, ts, no) for t, (ts, no) in acc.first.items()])
    c.executemany("INSERT OR IGNORE INTO pol_qcorpus VALUES (?,?,?,?,?,?,?)", acc.qcorpus)
    c.executemany("INSERT OR IGNORE INTO pol_sample VALUES (?,?,?,?,?)", acc.sample)
    c.executemany("INSERT INTO pol_tox_day VALUES (?,?,?,?,?,?) ON CONFLICT(day, scope, attr) DO UPDATE SET "
                  "total = total + excluded.total, n = n + excluded.n, n_high = n_high + excluded.n_high",
                  [(d, s, a, v[0], v[1], v[2]) for (d, s, a), v in acc.tox.items()])
    c.execute("DELETE FROM pol_unigram_stage")
    c.execute("DELETE FROM pol_entity_stage")
    for m in sorted(acc.uni):
        cu = acc.uni[m]
        if m < closed_before:
            c.executemany("INSERT INTO pol_unigram_month VALUES (?,?,?) ON CONFLICT(month, token) DO UPDATE SET n = n + excluded.n",
                          [(m, k, v) for k, v in cu.items() if v >= MIN_MONTH])
            del acc.uni[m]
        else:
            c.executemany("INSERT INTO pol_unigram_stage VALUES (?,?,?)", [(m, k, v) for k, v in cu.items()])
    for m in sorted(acc.ent):
        ce = acc.ent[m]
        if m < closed_before:
            c.executemany("INSERT INTO pol_entity_month VALUES (?,?,?,?) ON CONFLICT(month, entity, label) DO UPDATE "
                          "SET n = n + excluded.n", [(m, e, l, v) for (e, l), v in ce.items() if v >= 2])
            del acc.ent[m]
        else:
            c.executemany("INSERT INTO pol_entity_stage VALUES (?,?,?,?)", [(m, e, l, v) for (e, l), v in ce.items()])
    acc.hour, acc.total, acc.first, acc.qcorpus, acc.sample, acc.tox = {}, {}, {}, [], [], {}
    cursor_save(cursor_value)    # valide la transaction avec le curseur


def _prune(acc):
    n = sum(len(c) for c in acc.uni.values())
    if n > MAX_VOCAB:
        for c in acc.uni.values():
            for k in [k for k, v in c.items() if v == 1]:
                del c[k]
        return n
    return 0


_scan = {"acc": None, "ckpt": None}


def process_thread(posts, terms, m, qids, drop_posts, acc):
    """Applique toutes les couches a un fil (liste de posts du dataset)."""
    op = posts[0]
    op_txt = f"{html.unescape(op.get('sub') or '')}\n{text_of(op.get('com'))}"
    thread_no = str(op.get("no"))
    reason = "thread:cbts" if _THREAD_Q.search(op_txt) else (
        "thread:drop" if drop_posts and any(str(p.get("no")) in drop_posts for p in posts) else None)
    t0 = int(op.get("time", 0))
    h0 = t0 - t0 % 3600
    acc.total[h0] = (acc.total.get(h0, (0, 0))[0], acc.total.get(h0, (0, 0))[1] + 1)
    for p in posts:
        ts = int(p.get("time", t0))
        hour = ts - ts % 3600
        day = time.strftime("%Y-%m-%d", time.gmtime(ts))
        month = day[:7]
        no = str(p.get("no"))
        txt = text_of(p.get("com"))
        if p is op and op.get("sub"):
            txt = f"{html.unescape(op['sub'])}\n{txt}"
        tot = acc.total.get(hour, (0, 0))
        acc.total[hour] = (tot[0] + 1, tot[1])
        hits = m.hits(txt)
        post_reason = reason
        for i in hits:
            tid = terms[i].id
            acc.hour[(hour, tid)] = acc.hour.get((hour, tid), 0) + 1
            f = acc.first.get(tid)
            if f is None or ts < f[0]:
                acc.first[tid] = (ts, no)
            if post_reason is None and i in qids:
                post_reason = f"post:{terms[i].family}"
        country = p.get("country") or ""
        if post_reason:
            acc.qcorpus.append((thread_no, no, ts, html.unescape(op.get("sub") or "") if p is op else "", txt,
                                country, post_reason))
        if no.isdigit() and int(no) % 100 == 0:
            acc.sample.append((no, thread_no, ts, txt, country))
        cu = acc.month_counter(acc.uni, month)
        cu.update(_TOKEN.findall(txt.lower()))
        ents = p.get("entities") or ""
        if ents and ents != "[]":
            ce = acc.month_counter(acc.ent, month)
            ce.update((e.replace("\\'", "'"), lab) for e, lab in _ENT.findall(ents))
        persp = p.get("perspectives") or ""
        for attr, val in _PERSP.findall(persp):
            v = float(val)
            for scope in (("all", "q") if post_reason else ("all",)):
                k = (day, scope, attr)
                a = acc.tox.get(k, (0.0, 0, 0))
                acc.tox[k] = (a[0] + v, a[1] + 1, a[2] + (v > 0.8))


def run_scan(ctx):
    from .. import lexicon
    terms = lexicon.load()
    fp = lexicon.fingerprint(terms)
    if not approved(terms):
        if db.get_meta(ctx.conn, "pol_scan_waiting") != fp:
            db.set_meta(ctx.conn, "pol_scan_waiting", fp)
            ctx.conn.commit()
            log(f"pol : balayage en attente de l'approbation du lexique {fp} (scene.yaml : lexicon_approved)")
        return None
    part, final = paths(ctx.state)
    cur = ctx.cursor or ""
    if not cur.startswith(fp + ":"):
        for t in ("pol_hour", "pol_hour_total", "pol_first", "pol_qcorpus", "pol_sample", "pol_unigram_month",
                  "pol_entity_month", "pol_tox_day", "pol_unigram_stage", "pol_entity_stage"):
            ctx.conn.execute(f"DELETE FROM {t}")
        ctx.save_cursor(f"{fp}:0")
        cur = f"{fp}:0"
        _scan["acc"] = None
    ckpt = int(cur.split(":")[1])
    if _scan["acc"] is None or _scan["ckpt"] != ckpt or "scan" not in _streams:
        # Demarrage ou redemarrage : accumulateurs du dernier point de reprise, lecture depuis ce point.
        _scan["acc"], _scan["ckpt"] = Scan(), ckpt
        _load_staging(ctx.conn, _scan["acc"])
        want = ckpt
    else:
        # Meme processus : on continue ou l'on s'etait arrete, sauf si le saut jusqu'au point
        # de reprise n'est pas fini (on ne relit jamais une ligne deja comptee).
        want = max(_streams["scan"].n, ckpt)
    acc = _scan["acc"]
    s = stream(ctx, "scan", final, want)
    if s is None:
        return False
    m = lexicon.Matcher(terms)
    qids = {i for i, t in enumerate(terms) if t.family in Q_FAMILIES and not t.ambiguous}
    drop_posts = _drop_posts(ctx.conn)
    stop = time.monotonic() + SCAN_SHARE
    finished = False
    while True:
        line = s.next()
        if line is None:
            finished = True
            break
        try:
            posts = json.loads(line)["posts"]
        except ValueError:
            continue
        if posts:
            process_thread(posts, terms, m, qids, drop_posts, acc)
        if s.n % CHECKPOINT == 0:
            t = thread_time(line) or 0
            closed = time.strftime("%Y-%m", time.gmtime(t - 45 * 86400))   # mois clos : plus de 45 jours avant le fil courant
            pruned = _prune(acc)
            _checkpoint(ctx.conn, acc, closed, f"{fp}:{s.n}", ctx.save_cursor)
            _scan["ckpt"] = s.n
            log(f"pol : {s.n} fils balayes ({time.strftime('%Y-%m', time.gmtime(t))})"
                + (f", vocabulaire elague ({pruned} entrees)" if pruned else ""))
        if s.n % 200 == 0 and (ctx.should_yield() or time.monotonic() > stop):
            break
    # Entre deux points de reprise, le travail en memoire continue au cycle suivant (meme processus).
    if not finished:
        return False
    _checkpoint(ctx.conn, acc, "9999-99", f"{fp}:{s.n}:fin", ctx.save_cursor)
    _streams.pop("scan").close()
    _scan["acc"] = None
    n = ctx.conn.execute("SELECT sum(posts), sum(threads) FROM pol_hour_total").fetchone()
    q = ctx.conn.execute("SELECT count(*) FROM pol_qcorpus").fetchone()[0]
    ctx.set_output(db.sha(fp, n[0], n[1], q))
    log(f"pol : balayage termine, {n[1]} fils, {n[0]} posts, sous-corpus Q {q} posts")
    return True

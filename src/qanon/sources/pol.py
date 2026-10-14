"""4chan /pol/ (Papasavva et al., ICWSM 2020 ; Zenodo 3606810, CC BY 4.0) :
134,5 M posts, juin 2016 - novembre 2019. Lu une seule fois, puis supprime.

- fetch_pol : telechargement reprenable (requetes partielles, un morceau par
  cycle ; le curseur est la taille du fichier), puis verification md5.
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
SHARE = 20   # secondes par cycle : laisse le reste du budget a l'echantillon Reddit
UA = {"User-Agent": "qanon-study/1.0 (+https://github.com/s-geffroy/QAnon)"}

# Hachage md5 en cours (24 Go ne se hachent pas en un cycle) : etat garde en memoire du
# processus ; un redemarrage le reprend au debut.
_md5 = {"h": None, "pos": 0}


def paths(state):
    d = state / "cache" / "pol"
    d.mkdir(parents=True, exist_ok=True)
    return d / "pol.tar.zst.part", d / "pol.tar.zst"


def run_fetch(ctx):
    part, final = paths(ctx.state)
    if final.exists():
        ctx.set_output(db.sha(MD5))
        return True
    have = part.stat().st_size if part.exists() else 0
    if have < SIZE:
        try:
            with requests.get(URL, headers={**UA, "Range": f"bytes={have}-"}, stream=True, timeout=60) as r:
                if r.status_code != 206:
                    raise RuntimeError(f"requete partielle refusee : HTTP {r.status_code}")
                t0, got = time.monotonic(), 0
                with open(part, "ab") as f:
                    for block in r.iter_content(CHUNK):
                        f.write(block)
                        got += len(block)
                        if ctx.should_yield() or time.monotonic() - t0 > SHARE:
                            break
        except requests.RequestException as exc:
            log(f"pol : telechargement interrompu a {have / 1e9:.2f} Go ({exc!r:.120}) ; reprise au cycle suivant")
            return None
        have = part.stat().st_size
        ctx.save_cursor(str(have))
        rate = got / max(time.monotonic() - t0, 1e-3) / 1e6
        # Une ligne par Go environ : le volume de logs est une ressource.
        if have // 10**9 != (have - got) // 10**9 or have >= SIZE:
            log(f"pol : {have / 1e9:.1f} / {SIZE / 1e9:.1f} Go ({rate:.0f} Mo/s)")
        return False
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

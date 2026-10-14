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

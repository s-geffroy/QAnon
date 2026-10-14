"""Publication automatique du site sur la branche gh-pages (HTTPS + jeton).

Autorisee par le proprietaire du depot. Jeton « fine-grained » limite au depot
s-geffroy/QAnon, droit Contents: Read and write, lu dans le secret github_token.
Sans secret, l'etape ne fait rien et la publication reste manuelle
(scripts/publish-pages.sh, en SSH depuis l'hote).

Le jeton ne passe ni par l'URL ni par la ligne de commande : git le lit dans une
variable d'environnement via un assistant d'authentification ; il n'est jamais
journalise."""
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import requests

from .. import db
from ..log import log
from ..secrets import read_secret

REPO = "s-geffroy/QAnon"
NAME, EMAIL = "qanon worker", "qanon-worker@users.noreply.github.com"
HELPER = "!f() { echo username=x-access-token; echo \"password=$GIT_TOKEN\"; }; f"


def head_commit():
    """Commit court de main : le code est toujours pousse sur main avant d'etre deploye."""
    r = requests.get(f"https://api.github.com/repos/{REPO}/commits/main", timeout=30,
                     headers={"Accept": "application/vnd.github+json"})
    r.raise_for_status()
    return r.json()["sha"][:7]


WARN_DAYS = 30


def token_expiry(token):
    """Date d'expiration du jeton, lue dans l'en-tete que GitHub renvoie a chaque appel authentifie."""
    import datetime as dt
    r = requests.get(f"https://api.github.com/repos/{REPO}", timeout=30,
                     headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"})
    if r.status_code == 401:
        raise RuntimeError("jeton github_token refuse par GitHub (401) : expire, revoque ou mal copie")
    raw = r.headers.get("github-authentication-token-expiration")
    if not raw:
        return None
    return dt.datetime.strptime(raw.replace(" UTC", " +0000"), "%Y-%m-%d %H:%M:%S %z")


def run(ctx):
    # Suspension volontaire (compose.yaml : PUBLISH_HOLD=1), le temps d'une relecture :
    # le site est construit dans /state/site, mais pas pousse.
    if os.environ.get("PUBLISH_HOLD", "") not in ("", "0"):
        if db.get_meta(ctx.conn, "publish_hold_logged") != "1":
            db.set_meta(ctx.conn, "publish_hold_logged", "1")
            ctx.conn.commit()
            log("publication suspendue (PUBLISH_HOLD) : site construit dans /state/site, non pousse")
        return None
    db.set_meta(ctx.conn, "publish_hold_logged", "0")
    token = read_secret("github_token")
    if not token:
        ctx.set_output("manuel")
        log("publication automatique desactivee (secret github_token absent)")
        return True
    import datetime as dt
    exp = token_expiry(token)
    if exp:
        days = (exp - dt.datetime.now(dt.timezone.utc)).days
        if days <= WARN_DAYS:
            log(f"ATTENTION : le jeton github_token expire dans {days} jours ({exp.date()}) : le renouveler "
                "(voir README, section publication)")
    version = head_commit()
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "site"
        shutil.copytree(ctx.state / "site", out)
        for p in out.rglob("*"):
            if p.is_file() and p.suffix in (".html", ".xml", ".json", ".txt"):
                text = p.read_text(errors="ignore")
                if "@@VERSION@@" in text:
                    p.write_text(text.replace("@@VERSION@@", version))
        env = {**os.environ, "GIT_TOKEN": token, "GIT_TERMINAL_PROMPT": "0"}

        def git(*args):
            return subprocess.run(["git", "-c", f"credential.helper={HELPER}", *args], cwd=out, env=env,
                                  check=True, capture_output=True, text=True, timeout=300)
        try:
            git("init", "-q", "-b", "gh-pages")
            git("add", "-A")
            git("-c", f"user.name={NAME}", "-c", f"user.email={EMAIL}", "commit", "-q", "-m",
                f"site genere par le worker qanon (version {version})")
            git("push", "-q", "--force", f"https://github.com/{REPO}.git", "gh-pages")
        except subprocess.CalledProcessError as exc:
            msg = (exc.stderr or "").replace(token, "***").strip()[:300]
            raise RuntimeError(f"publication gh-pages en echec : {msg}") from None
    site_fp = ctx.conn.execute("SELECT fingerprint FROM stages WHERE name = 'build_site'").fetchone()
    ctx.set_output(db.sha(version, site_fp[0] if site_fp else ""))
    log(f"site publie sur gh-pages (version {version})" + (f" ; jeton valable jusqu'au {exp.date()}" if exp else ""))
    return True

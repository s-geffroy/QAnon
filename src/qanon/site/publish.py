"""Publication du site sur la branche gh-pages (GitHub Pages).

La branche est reecrite a chaque publication : un seul commit, force-push.
Le jeton (secret `github_token`, PAT fine-grained "Contents: write" limite au
depot) passe par GIT_ASKPASS : il n'apparait ni dans l'URL, ni dans les
arguments, ni dans les messages d'erreur."""
import os
import shutil
import subprocess
import tempfile

from ..log import log
from ..secrets import read_secret

REPO = os.environ.get("PAGES_REPO", "s-geffroy/QAnon")
AUTHOR = ["-c", "user.name=qanon-worker", "-c", "user.email=qanon-worker@users.noreply.github.com"]


def git(args, cwd, env):
    res = subprocess.run(["git", *AUTHOR, *args], cwd=cwd, env=env, capture_output=True, text=True, timeout=120)
    if res.returncode:
        raise RuntimeError(f"git {args[0]} : {res.stderr.strip()[-300:]}")


def run(ctx):
    token = read_secret("github_token")
    if not token:
        raise RuntimeError("secret github_token absent : publication en attente")
    site = ctx.state / "site"
    work = ctx.state / "publish"
    shutil.rmtree(work, ignore_errors=True)
    shutil.copytree(site, work)
    with tempfile.TemporaryDirectory() as tmp:
        askpass = os.path.join(tmp, "askpass")
        with open(askpass, "w") as fh:
            fh.write('#!/bin/sh\nprintf "%s\\n" "$QANON_GIT_TOKEN"\n')
        os.chmod(askpass, 0o700)
        env = {**os.environ, "GIT_ASKPASS": askpass, "QANON_GIT_TOKEN": token,
               "GIT_TERMINAL_PROMPT": "0", "HOME": tmp}
        git(["init", "-q", "-b", "gh-pages"], work, env)
        git(["add", "-A"], work, env)
        git(["commit", "-q", "-m", "site genere par le worker qanon"], work, env)
        git(["push", "-q", "--force", f"https://x-access-token@github.com/{REPO}.git", "gh-pages"], work, env)
    shutil.rmtree(work, ignore_errors=True)
    log(f"site publie sur {REPO}@gh-pages")
    return True

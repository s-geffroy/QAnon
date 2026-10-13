"""Verification du site genere a partir de l'etat reel (lancee par tests/test_site.sh,
dans un conteneur jetable, sur une copie de /state/results ; la base est ouverte
en lecture seule) :
- chaque graphe et chaque bloc JSON-LD se relit avec un analyseur JSON ;
- aucun renvoi non resolu ({fig:..}, {val:..}, [@..], [[..]]) ni gabarit Jinja ;
- chaque lien interne pointe vers un fichier genere et, s'il a une ancre, vers un id existant."""
import json
import re
import shutil
import sqlite3
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlparse

from qanon.site import build


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids, self.links = set(), []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if a.get("id"):
            self.ids.add(a["id"])
        for k in ("href", "src"):
            if a.get(k):
                self.links.append(a[k])


def main():
    st = Path("/tmp/site-check")
    shutil.rmtree(st, ignore_errors=True)
    shutil.copytree("/state/results", st / "results")
    conn = sqlite3.connect("file:/state/qanon.db?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    out = st / "site"
    build.Site(st, conn).render(out)
    errors, pages, charts = [], {}, 0
    for p in sorted(out.rglob("*.html")):
        h = p.read_text()
        for cid, raw in re.findall(r'<script type="application/json" data-chart="([^"]+)">(.*?)</script>', h, re.S):
            charts += 1
            try:
                json.loads(raw)
            except ValueError as exc:
                errors.append(f"{p.relative_to(out)} : graphe {cid} illisible ({exc})")
        for raw in re.findall(r'<script type="application/ld\+json">(.*?)</script>', h, re.S):
            try:
                json.loads(raw)
            except ValueError as exc:
                errors.append(f"{p.relative_to(out)} : JSON-LD illisible ({exc})")
        text = re.sub(r"<script.*?</script>", "", h, flags=re.S)
        for pat in (r"\{fig:[^}]*\}", r"\{val:[^}]*\}", r"\[@[^\]]*\]", r"\[\[[a-z]+\]\]", r"\{\{ |\{% "):
            for m in re.findall(pat, text):
                errors.append(f"{p.relative_to(out)} : renvoi non resolu {m}")
        parser = Page()
        parser.feed(h)
        pages[p] = parser
    n_links = 0
    for p, parser in pages.items():
        for link in parser.links:
            u = urlparse(link)
            if u.scheme or link.startswith(("mailto:", "//", "data:")):
                continue
            n_links += 1
            target = (p.parent / unquote(u.path)).resolve() if u.path else p
            if not target.exists():
                errors.append(f"{p.relative_to(out)} : lien vers un fichier absent {link}")
                continue
            # Ancres des pages rendues cote client (explorateur : #d123) non verifiables ici.
            if u.fragment and target.suffix == ".html" and target.name != "corpus.html":
                ids = pages.get(target).ids if target in pages else set()
                if u.fragment not in ids:
                    errors.append(f"{p.relative_to(out)} : ancre absente {link}")
    print(f"{len(pages)} pages, {charts} graphes, {n_links} liens internes, {len(errors)} erreurs")
    from collections import Counter
    kinds = Counter(re.sub(r" (\S+)$", "", e.split(" : ", 1)[1]) for e in errors)
    for k, v in kinds.most_common():
        print(f"  {v} x {k}")
    for e in errors[:40]:
        print("  " + e)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())

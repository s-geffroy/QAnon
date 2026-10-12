"""Pages vues Wikipedia (API Wikimedia REST), par jour, utilisateurs humains.

Indicateur d'interet public : l'article "QAnon" dans plusieurs langues (diffusion
internationale) et quelques articles connexes en anglais. Donnees disponibles
depuis juillet 2015 ; un article inexistant a une date renvoie 404."""
import requests

from .. import db
from ..log import log

API = ("https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/"
       "{project}/all-access/user/{article}/daily/{start}/{end}")
START, END = "20171001", "20231231"
UA = {"User-Agent": "qanon-study/1.0 (+https://github.com/s-geffroy/QAnon)"}

ARTICLES = [
    ("en.wikipedia", "QAnon"), ("fr.wikipedia", "QAnon"), ("de.wikipedia", "QAnon"),
    ("es.wikipedia", "QAnon"), ("it.wikipedia", "QAnon"), ("pt.wikipedia", "QAnon"),
    ("nl.wikipedia", "QAnon"), ("ja.wikipedia", "Qアノン"), ("pl.wikipedia", "QAnon"),
    ("sv.wikipedia", "QAnon"), ("ru.wikipedia", "QAnon"),
    ("en.wikipedia", "Pizzagate_conspiracy_theory"), ("en.wikipedia", "8chan"),
    ("en.wikipedia", "Deep_state_in_the_United_States"), ("en.wikipedia", "Adrenochrome"),
]


def run(ctx):
    start = int(ctx.cursor or 0)
    for i in range(start, len(ARTICLES)):
        if ctx.should_yield():
            return False
        project, article = ARTICLES[i]
        resp = requests.get(API.format(project=project, article=requests.utils.quote(article, safe=""),
                                       start=START, end=END), headers=UA, timeout=60)
        if resp.status_code == 404:
            log(f"pages vues : {project}/{article} sans donnees (404)")
            items = []
        else:
            resp.raise_for_status()
            items = resp.json()["items"]
        ctx.conn.execute("DELETE FROM pageviews WHERE project = ? AND article = ?", (project, article))
        ctx.conn.executemany("INSERT INTO pageviews VALUES (?,?,?,?)", [
            (project, article, f"{x['timestamp'][:4]}-{x['timestamp'][4:6]}-{x['timestamp'][6:8]}", x["views"])
            for x in items])
        ctx.save_cursor(str(i + 1))
    n = ctx.conn.execute("SELECT count(*), sum(views) FROM pageviews").fetchone()
    ctx.set_output(db.sha(n[0], n[1]))
    log(f"pages vues : {len(ARTICLES)} articles, {n[0]} jours-articles, {n[1]} vues")
    return True

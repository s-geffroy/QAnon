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


def fetch(ctx, table, articles):
    start = int(ctx.cursor or 0)
    for i in range(start, len(articles)):
        if i > start and ctx.should_yield():
            return False
        project, article = articles[i]
        resp = requests.get(API.format(project=project, article=requests.utils.quote(article, safe=""),
                                       start=START, end=END), headers=UA, timeout=60)
        if resp.status_code == 404:
            log(f"pages vues : {project}/{article} sans donnees (404)")
            items = []
        else:
            resp.raise_for_status()
            items = resp.json()["items"]
        ctx.conn.execute(f"DELETE FROM {table} WHERE project = ? AND article = ?", (project, article))
        ctx.conn.executemany(f"INSERT INTO {table} VALUES (?,?,?,?)", [
            (project, article, f"{x['timestamp'][:4]}-{x['timestamp'][4:6]}-{x['timestamp'][6:8]}", x["views"])
            for x in items])
        ctx.save_cursor(str(i + 1))
    n = ctx.conn.execute(f"SELECT count(*), sum(views) FROM {table}").fetchone()
    ctx.set_output(db.sha(n[0], n[1]))
    log(f"pages vues ({table}) : {len(articles)} articles, {n[0]} jours-articles, {n[1]} vues")
    return True


def run(ctx):
    return fetch(ctx, "pageviews", ARTICLES)


REDIRECTS = "https://{project}.org/w/api.php"


def titles(project, article):
    """L'article et toutes ses redirections : un article renomme garde ses vues
    anterieures sous son ancien titre."""
    r = requests.get(REDIRECTS.format(project=project), headers=UA, timeout=60, params={
        "action": "query", "prop": "redirects", "titles": article.replace("_", " "), "rdlimit": "max",
        "rdnamespace": 0, "format": "json", "formatversion": 2})
    r.raise_for_status()
    page = r.json()["query"]["pages"][0]
    return [article] + [x["title"].replace(" ", "_") for x in page.get("redirects", [])]


def run_scene(ctx):
    """Articles de la scene complotiste (data/scene.yaml), en anglais, redirections comprises.
    Curseur : indice de l'article, puis indice du titre ('i:j')."""
    from ..analysis.common import load_yaml
    arts = load_yaml("scene", "wikipedia_articles")
    i, j = (int(x) for x in (ctx.cursor or "0:0").split(":"))
    start = (i, j)
    project = "en.wikipedia"
    while i < len(arts):
        names = titles(project, arts[i])
        while j < len(names):
            if (i, j) != start and ctx.should_yield():
                return False
            resp = requests.get(API.format(project=project, article=requests.utils.quote(names[j], safe=""),
                                           start=START, end=END), headers=UA, timeout=60)
            items = [] if resp.status_code == 404 else (resp.raise_for_status() or resp.json()["items"])
            ctx.conn.execute("DELETE FROM wiki_scene_views WHERE project = ? AND article = ? AND title = ?",
                             (project, arts[i], names[j]))
            ctx.conn.executemany("INSERT INTO wiki_scene_views VALUES (?,?,?,?,?)", [
                (project, arts[i], names[j], f"{x['timestamp'][:4]}-{x['timestamp'][4:6]}-{x['timestamp'][6:8]}",
                 x["views"]) for x in items])
            j += 1
            ctx.save_cursor(f"{i}:{j}")
        i, j = i + 1, 0
        ctx.save_cursor(f"{i}:0")
    n = ctx.conn.execute("SELECT count(DISTINCT title), sum(views) FROM wiki_scene_views").fetchone()
    ctx.set_output(db.sha(n[0], n[1]))
    log(f"pages vues de la scene : {len(arts)} articles, {n[0]} titres (redirections comprises), {n[1]} vues")
    return True

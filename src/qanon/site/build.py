"""Generation du site statique bilingue a partir de /state/results."""
import json
import shutil
import time
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .. import db
from ..log import log
from . import charts, fmt
from .i18n import REFS, REPO, T

HERE = Path(__file__).resolve().parent
UPDATED = "@@UPDATED@@"
PAGES = ["index", "activity", "trump", "timeline", "method"]
NAV = {"index": "nav_home", "activity": "nav_activity", "trump": "nav_trump",
       "timeline": "nav_timeline", "method": "nav_method"}


def _load(ctx, name):
    return json.loads((ctx.results / f"{name}.json").read_text())


def _duration(lang, minutes):
    t = T[lang]
    if minutes is None:
        return "—"
    if minutes < 120:
        return f"{fmt.num(lang, minutes)} {t['min']}"
    return f"{fmt.num(lang, minutes / 60, 1)} {t['h']}"


def context(lang, desc, trump):
    t = T[lang]
    n = lambda x, d=0: fmt.num(lang, x, d)
    p = lambda x, d=1: fmt.pct(lang, x, d)
    t5 = next(x for x in trump["tests"] if x["window_s"] == 300 and x["direction"] == "tweet_after_drop"
              and x["null"] == "local")
    pv = fmt.num(lang, t5["p_value"], 3)
    verdict = (t["verdict_sig"] if t5["p_value"] < 0.05 else t["verdict_ns"]).format(p=pv)
    gap = desc["gaps"][0]
    q = trump["quotes"]
    tests = [{
        "null": t[f"null_{x['null']}"],
        "window": _duration(lang, x["window_s"] / 60),
        "dir": t["dir_after"] if x["direction"] == "tweet_after_drop" else t["dir_before"],
        "obs": p(x["observed"]), "exp": p(x["expected"]),
        "ratio": n(x["ratio"], 2) if x["ratio"] else "—", "p": n(x["p_value"], 3),
        "sig": x["p_value"] < 0.05,
    } for x in trump["tests"]]
    events = sorted(desc["events"], key=lambda e: e["date"])
    return {
        "lang": lang, "t": t, "repo": REPO, "refs": REFS,
        "updated": UPDATED,
        "lead": t["home_lead"].format(first=fmt.date(lang, desc["first"]),
                                      last=fmt.date(lang, desc["last"]), n=n(desc["n"])),
        "kpis": [(n(desc["n"]), t["kpi_drops"]), (n(desc["active_days"]), t["kpi_days"]),
                 (n(desc["words_total"]), t["kpi_words"]), (p(desc["share_questions"], 0), t["kpi_questions"])],
        "findings": [
            t["f_trump"].format(obs=p(t5["observed"]), exp=p(t5["expected"]), verdict=verdict),
            t["f_gap"].format(days=n(gap["days"]), from_=fmt.date(lang, gap["from"]), to=fmt.date(lang, gap["to"])),
            t["f_maxday"].format(n=n(desc["max_day"]["n"]), date=fmt.date(lang, desc["max_day"]["date"])),
            t["f_questions"].format(q=n(desc["questions_per_drop"], 1)),
        ],
        "platforms": [{"site": x["site"], "board": x["board"], "n": n(x["n"]),
                       "first": fmt.date(lang, x["first"]), "last": fmt.date(lang, x["last"])}
                      for x in desc["platforms"]],
        "gaps": [{"days": n(g["days"], 1), "from": fmt.date(lang, g["from"]), "to": fmt.date(lang, g["to"])}
                 for g in desc["gaps"]],
        "yearly": [(k, n(v)) for k, v in desc["yearly"].items()],
        "events": [{"date": fmt.date(lang, e["date"]), "iso": e["date"], "cat": e["category"],
                    "cat_label": t[f"cat_{e['category']}"], "label": e[f"label_{lang}"], "source": e["source"]}
                   for e in events],
        "trump_lead": t["trump_lead"].format(tpd=n(trump["tweets_per_day"], 0)),
        "trump_method": t["trump_method"].format(n_perm=n(trump["n_perm"]), n_drops=n(trump["n_drops"]),
                                                 n_tweets=n(trump["n_tweets"])),
        "tests": tests,
        "quotes": t["quotes_text"].format(n_drops=n(q["n_drops"]), n_matched=n(q["n_matched"]),
                                          lag=_duration(lang, q["median_lag_min"])),
        "delta": t["delta_text"].format(n=n(trump["delta_mentions"])),
        "src_drops": t["src_drops"].format(n=n(desc["n"])),
        "hist_rows": trump["hist"],
        "charts": {
            "weekly": charts.weekly(desc, lang), "yearly": charts.yearly(desc, lang),
            "heatmap": charts.heatmap(desc, lang), "hist": charts.tweet_hist(trump, lang),
        },
    }


def render(out, desc, trump):
    env = Environment(loader=FileSystemLoader(HERE / "templates"), autoescape=select_autoescape(["html"]))
    env.filters["tojson_compact"] = lambda v: json.dumps(v, ensure_ascii=False, separators=(",", ":"))
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(HERE / "static", out / "static")
    (out / ".nojekyll").write_text("")
    for lang in T:
        ctx = context(lang, desc, trump)
        (out / lang).mkdir(parents=True)
        for page in PAGES:
            html = env.get_template(f"{page}.html").render(page=page, nav=NAV, pages=PAGES, **ctx)
            (out / lang / f"{page}.html").write_text(html)
    (out / "index.html").write_text(env.get_template("root.html").render())


def run(ctx):
    out = ctx.state / "site"
    render(out, _load(ctx, "descriptive"), _load(ctx, "trump"))
    files = sorted(p for p in out.rglob("*") if p.is_file())
    # L'empreinte est prise avant d'inscrire la date de mise a jour : sinon le
    # site changerait chaque jour sans que rien n'ait change.
    digest = db.sha(*(f"{p.relative_to(out)}:{db.sha(p.read_bytes())}" for p in files))
    for p in files:
        if p.suffix == ".html":
            lang = p.parent.name if p.parent.name in T else "fr"
            p.write_text(p.read_text().replace(UPDATED, fmt.date(lang, time.strftime("%Y-%m-%d"))))
    ctx.set_output(digest)
    log(f"site : {len(files)} fichiers generes dans {out}")
    return True

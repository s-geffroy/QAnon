"""Generation du site statique bilingue a partir de /state/results."""
import csv
import json
import shutil
import time
from pathlib import Path

import pandas as pd
from jinja2 import Environment, FileSystemLoader, select_autoescape

from .. import db
from ..analysis.common import load_yaml
from ..log import log
from ..pipeline import APP_DIR
from . import biblio, charts, fmt
from .i18n import REFS, REPO, T

HERE = Path(__file__).resolve().parent
UPDATED = "@@UPDATED@@"
VERSION = "@@VERSION@@"   # remplace par le commit au moment de la publication (scripts/publish-pages.sh)
NAV = [
    ("analyses", ["index", "activity", "discourse", "actors", "predictions", "trump", "news", "interest", "timeline"]),
    ("resources", ["glossary", "bibliography", "data", "method", "cite"]),
]
PAGES = [p for _, group in NAV for p in group]


def _load(state, name):
    path = state / "results" / f"{name}.json"
    return json.loads(path.read_text()) if path.exists() else None


def _duration(lang, minutes):
    t = T[lang]
    if minutes is None:
        return "—"
    if minutes < 120:
        return f"{fmt.num(lang, minutes)} {t['min']}"
    return f"{fmt.num(lang, minutes / 60, 1)} {t['h']}"


def _iso_num():
    import pycountry
    return {c.alpha_3: int(c.numeric) for c in pycountry.countries}


class Site:
    def __init__(self, state, conn):
        self.state = state
        self.conn = conn
        self.r = {k: _load(state, k) for k in ("descriptive", "trump", "discourse", "actors", "interest", "news",
                                                "llm_eval")}
        self.glossary = load_yaml("glossary", "terms")
        self.refs = biblio.load()

    # -- contexte commun a toutes les pages
    def base(self, lang):
        t = T[lang]
        desc = self.r["descriptive"]
        n = lambda x, d=0: fmt.num(lang, x, d)
        return {"lang": lang, "t": t, "repo": REPO, "refs": REFS, "updated": UPDATED, "version": VERSION,
                "nav": NAV, "n": n, "p": lambda x, d=1: fmt.pct(lang, x, d), "date": lambda v: fmt.date(lang, v),
                "desc": desc}

    def page_index(self, lang, c):
        t, desc, trump = c["t"], self.r["descriptive"], self.r["trump"]
        n, p = c["n"], c["p"]
        t5 = next(x for x in trump["tests"] if x["window_s"] == 300 and x["direction"] == "tweet_after_drop"
                  and x["null"] == "local")
        verdict = (t["verdict_sig"] if t5["p_value"] < 0.05 else t["verdict_ns"]).format(p=n(t5["p_value"], 3))
        gap = desc["gaps"][0]
        findings = [
            t["f_trump"].format(obs=p(t5["observed"]), exp=p(t5["expected"]), verdict=verdict),
            t["f_gap"].format(days=n(gap["days"]), from_=c["date"](gap["from"]), to=c["date"](gap["to"])),
            t["f_maxday"].format(n=n(desc["max_day"]["n"]), date=c["date"](desc["max_day"]["date"])),
            t["f_questions"].format(q=n(desc["questions_per_drop"], 1)),
        ]
        extra = []
        act, disc, news, inter = self.r["actors"], self.r["discourse"], self.r["news"], self.r["interest"]
        if act and act["actors"]:
            top = ", ".join(f"{a['name']} ({n(a['n'])})" for a in act["actors"][:5])
            extra.append(t["f_actors"].format(top=top))
        if disc and disc.get("stylometry"):
            split = disc["stylometry"]["split"]["date"]
            # La phrase "rejoint les analyses de 2022" n'est vraie que si la
            # coupure tombe dans la fenetre qu'elles decrivent.
            key = "f_stylo" if "2017-11-01" <= split <= "2018-04-30" else "f_stylo_other"
            extra.append(t[key].format(date=c["date"](split)))
        if news and news["actors"]:
            ranked = sorted([a for a in news["actors"] if a.get("overrep") and a["q"] >= 30], key=lambda a: -a["overrep"])
            if ranked:
                extra.append(t["f_overrep"].format(names=", ".join(f"{a['name']} (×{n(a['overrep'], 1)})"
                                                                   for a in ranked[:3])))
        if inter and inter["events"]:
            e = inter["events"][0]
            extra.append(t["f_interest"].format(label=e[f"label_{lang}"], ratio=n(e["ratio"], 1)))
        return {
            "lead": t["home_lead"].format(first=c["date"](desc["first"]), last=c["date"](desc["last"]), n=n(desc["n"])),
            "kpis": [(n(desc["n"]), t["kpi_drops"]), (n(desc["active_days"]), t["kpi_days"]),
                     (n(desc["words_total"]), t["kpi_words"]), (p(desc["share_questions"], 0), t["kpi_questions"])],
            "findings": findings + extra,
            "charts": {"weekly": charts.weekly(desc, lang)},
        }

    def page_activity(self, lang, c):
        desc = self.r["descriptive"]
        d = c["date"]
        return {
            "platforms": [{"site": x["site"], "board": x["board"], "n": c["n"](x["n"]), "first": d(x["first"]),
                           "last": d(x["last"])} for x in desc["platforms"]],
            "gaps": [{"days": c["n"](g["days"], 1), "from": d(g["from"]), "to": d(g["to"])} for g in desc["gaps"]],
            "charts": {"yearly": charts.yearly(desc, lang), "heatmap": charts.heatmap(desc, lang)},
        }

    def page_trump(self, lang, c):
        t, trump, n, p = c["t"], self.r["trump"], c["n"], c["p"]
        q = trump["quotes"]
        tests = [{"null": t[f"null_{x['null']}"], "window": _duration(lang, x["window_s"] / 60),
                  "dir": t["dir_after"] if x["direction"] == "tweet_after_drop" else t["dir_before"],
                  "obs": p(x["observed"]), "exp": p(x["expected"]),
                  "ratio": n(x["ratio"], 2) if x["ratio"] else "—", "pv": n(x["p_value"], 3),
                  "sig": x["p_value"] < 0.05} for x in trump["tests"]]
        return {
            "trump_lead": t["trump_lead"].format(tpd=n(trump["tweets_per_day"])),
            "trump_method": t["trump_method"].format(n_perm=n(trump["n_perm"]), n_drops=n(trump["n_drops"]),
                                                     n_tweets=n(trump["n_tweets"])),
            "tests": tests, "hist_rows": trump["hist"],
            "quotes": t["quotes_text"].format(n_drops=n(q["n_drops"]), n_matched=n(q["n_matched"]),
                                              lag=_duration(lang, q["median_lag_min"])),
            "delta": t["delta_text"].format(n=n(trump["delta_mentions"])),
            "charts": {"hist": charts.tweet_hist(trump, lang)},
        }

    def page_discourse(self, lang, c):
        t, disc, n, p = c["t"], self.r["discourse"], c["n"], c["p"]
        if not disc:
            return {"is_pending": True}
        s = disc["stylometry"]
        out = {
            "lead": t["discourse_lead"].format(n=n(disc["n_docs"])),
            "topics_note": t["topics_note"].format(k=len(disc["topics"])),
            "topics": [{"i": i + 1, "terms": ", ".join(x["terms"][:10]), "share": p(x["share"]),
                        "examples": ", ".join(str(e) for e in x["exemplar_ids"])} for i, x in enumerate(disc["topics"])],
            "distinctive": [(y, ", ".join(w["term"] for w in words[:12])) for y, words in disc["distinctive"].items()],
            "charts": {"prevalence": charts.prevalence(disc, lang), "style": charts.style(disc, lang)},
        }
        if self.glossary and any(g["n"] for g in disc["glossary"]):
            out["charts"]["formulas"] = charts.formulas(disc, self.glossary, lang)
        if s:
            out["stylo_method"] = t["stylo_method"].format(n=n(s["n_chunks"]), w=n(s["chunk_words"]), m=n(s["n_mfw"]))
            out["stylo_result"] = t["stylo_result"].format(date=c["date"](s["split"]["date"]),
                                                           date2=c["date"](s["split_after"]["date"]))
            out["charts"]["stylo"] = charts.stylometry(disc, lang)
            # Une coupure qui tombe sur un changement de plateforme ne permet pas
            # de distinguer changement d'auteur et changement de contexte.
            split = pd.Timestamp(s["split"]["date"])
            for pl in self.r["descriptive"]["platforms"]:
                first = pd.Timestamp(pl["first"]).tz_convert(None).normalize()
                if abs((first - split).days) <= 3 and first > pd.Timestamp("2017-10-29"):
                    out["stylo_platform"] = t["stylo_coincide"].format(
                        platform=f"{pl['site']} {pl['board']}", date=c["date"](pl["first"]))
                    break
            ranked = sorted(s["scores"], key=lambda x: -x["ratio"])[:5]
            out["stylo_candidates"] = ", ".join(f"{c['date'](x['date'])} ({c['n'](x['ratio'], 3)})" for x in ranked)
        return out

    def page_actors(self, lang, c):
        t, act, n, p = c["t"], self.r["actors"], c["n"], c["p"]
        if not act or not act["actors"]:
            return {"is_pending": True}
        names = {a["id"]: a["name"] for a in act["actors"]}
        nums = _iso_num()
        countries = [{**x, "num": nums.get(x.get("iso3"))} for x in act["countries"]]
        return {
            "lead": t["actors_lead"].format(n=n(len(act["actors"])), share=p(act["share_with_actor"], 0)),
            "rows": [{"name": a["name"], "cat": t[f"cat_{a['category']}"], "role": a.get(f"role_{lang}") or "",
                      "n": n(a["n"]), "first": c["date"](a["first"]), "last": c["date"](a["last"])}
                     for a in act["actors"]],
            "pairs": [{"a": names.get(e["a"], e["a"]), "b": names.get(e["b"], e["b"]), "n": n(e["n"]),
                       "npmi": n(e["npmi"], 2)} for e in sorted(act["edges"], key=lambda e: -e["n"])[:40]],
            "charts": {"top": charts.top_actors(act, lang), "time": charts.actors_time(act, lang),
                       "world": charts.world(countries, lang)},
        }

    def page_news(self, lang, c):
        t, news, n = c["t"], self.r["news"], c["n"]
        if not news:
            return {"is_pending": True}
        def lag(b):
            return f"{b['lag']:+d} {t['weeks']} (r = {n(b['r'], 2)})" if b else "—"
        def pv(x):
            return "—" if x is None else n(x, 3)
        nums = _iso_num()
        countries = [{**x, "num": nums.get(x.get("iso3"))} for x in news["countries"]]
        return {
            "lead": t["news_lead"].format(events=n(news["gdelt_events"]), days=n(news["gdelt_days"])),
            "rows": [{"name": r["name"], "q": n(r["q"]), "news": n(r["news"]),
                      "overrep": n(r["overrep"], 2) if r.get("overrep") else "—",
                      "rho": "—" if r["rho0"] is None else n(r["rho0"], 2), "lag": lag(r["best_lag"]),
                      "g1": pv(r["granger_news_to_q"]), "g2": pv(r["granger_q_to_news"]),
                      "sig": (r["granger_news_to_q"] or 1) < 0.05} for r in news["actors"]],
            "countries": [{"name": x["name"], "q": n(x["q"]), "news": n(x["news"]), "overrep": n(x["overrep"], 2)}
                          for x in news["countries"][:40]],
            "country_rho": t["countries_rho"].format(rho=n(news["country_rho"] or 0, 2)),
            "charts": {"overrep": charts.overrep(news, lang), "series": charts.news_series(news, lang)},
        }

    def page_interest(self, lang, c):
        t, inter, n = c["t"], self.r["interest"], c["n"]
        if not inter:
            return {"is_pending": True}
        return {
            "events": [{"date": c["date"](e["date"]), "label": e[f"label_{lang}"], "before": n(e["before"]),
                        "after": n(e["after"]), "ratio": n(e["ratio"], 2)} for e in inter["events"]],
            "lags": [{"lag": f"{x['lag_weeks']:+d}", "rho": "—" if x["rho"] is None else n(x["rho"], 2)}
                     for x in inter["lags"]],
            "lags_note": t["lags_note"].format(n=n(inter["n_weeks"])),
            "articles": [{"key": a["key"], "total": n(a["total"]), "peak": n(a["peak"]),
                          "peak_day": c["date"](a["peak_day"]),
                          "first_day": c["date"](a["first_day"]) if a["first_day"] else "—"} for a in inter["articles"]],
            "charts": {"views": charts.views(inter, self.r["descriptive"], lang),
                       "langs": charts.languages(inter, lang)},
        }

    def page_predictions(self, lang, c):
        t, n, p = c["t"], c["n"], c["p"]
        path = APP_DIR / "data" / "gold.jsonl"
        gold = [json.loads(x) for x in path.read_text().splitlines() if x.strip()] if path.exists() else []
        preds = [q for g in gold for q in g["predictions"]]
        from collections import Counter
        by_sample = Counter((g["sample"], g["is_prediction"]) for g in gold)
        out = {
            "gold_n": n(len(gold)), "gold_pos": n(sum(g["is_prediction"] for g in gold)),
            "gold_random": t["gold_sample"].format(pos=n(by_sample[("random", True)]),
                                                   tot=n(by_sample[("random", True)] + by_sample[("random", False)])),
            "gold_likely": t["gold_sample"].format(pos=n(by_sample[("likely", True)]),
                                                   tot=n(by_sample[("likely", True)] + by_sample[("likely", False)])),
            "gold_types": ", ".join(f"{k} ({v})" for k, v in Counter(q["event_type"] for q in preds).most_common()),
            "gold_spec": t["gold_spec"].format(spec=n(sum(q["specificity"] == "specific" for q in preds)),
                                               vague=n(sum(q["specificity"] == "vague" for q in preds))),
        }
        ev = self.r["llm_eval"]
        if ev:
            out["eval"] = [{"model": m["model"], "f1": n(m["f1"], 2), "ci": f"{n(m['f1_lo'], 2)}–{n(m['f1_hi'], 2)}",
                            "prec": n(m["precision"], 2), "rec": n(m["recall"], 2),
                            "type": "—" if m["type_acc"] is None else p(m["type_acc"], 0),
                            "deadline": "—" if m["deadline_acc"] is None else p(m["deadline_acc"], 0),
                            "cost": f"{n(m['corpus_cost_batch_usd'], 2)} $", "lat": n(m["latency_median_s"], 1),
                            "rec_flag": m["model"] == ev["recommended"]} for m in ev["models"]]
            out["eval_note"] = t["eval_note"].format(date=c["date"](ev["pricing_date"]), n=n(ev["n_gold"]),
                                                     pos=n(ev["n_positive"]))
            out["recommended"] = ev["recommended"]
        return out

    def page_timeline(self, lang, c):
        t = c["t"]
        events = sorted(self.r["descriptive"]["events"], key=lambda e: e["date"])
        return {"events": [{"date": c["date"](e["date"]), "iso": e["date"], "cat": e["category"],
                            "cat_label": t[f"cat_{e['category']}"], "label": e[f"label_{lang}"],
                            "source": e["source"]} for e in events]}

    def page_glossary(self, lang, c):
        disc = self.r["discourse"] or {"glossary": []}
        stats = {g["id"]: g for g in disc["glossary"]}
        rows = []
        for g in sorted(self.glossary, key=lambda g: g["term"].lower()):
            s = stats.get(g["id"], {})
            rows.append({"id": g["id"], "term": g["term"], "expansion": g.get("expansion"),
                         "definition": g.get(f"def_{lang}"), "source": g.get("source"),
                         "n": c["n"](s["n"]) if s.get("n") is not None else "—",
                         "first": c["date"](s["first_date"]) if s.get("first_date") else None,
                         "first_id": s.get("first_id")})
        return {"terms": rows}

    def page_bibliography(self, lang, c):
        t = c["t"]
        entries = []
        for r in self.refs:
            cit = biblio.citation(r, lang)
            entries.append({**r, "cit": cit, "summary": r.get(f"summary_{lang}"), "type_label": t.get(f"type_{r['type']}", r["type"]),
                            "bibtex": biblio.bibtex(r), "search": " ".join(
                                [r["title"], " ".join(r.get("authors", [])), r.get("container") or "",
                                 " ".join(r.get("topics", [])), str(r.get("year", ""))]).lower()})
        types = [(ty, t.get(f"type_{ty}", ty)) for ty in biblio.TYPE_ORDER if any(r["type"] == ty for r in self.refs)]
        topics = sorted({tp for r in self.refs for tp in r.get("topics", [])})
        return {"entries": entries, "types": types, "topics": topics,
                "lead": t["bib_lead"].format(n=c["n"](len(self.refs)))}

    def page_data(self, lang, c):
        return {"files": self.files}

    def page_method(self, lang, c):
        return {"src_drops": c["t"]["src_drops"].format(n=c["n"](self.r["descriptive"]["n"]))}

    def page_cite(self, lang, c):
        t = c["t"]
        year = time.strftime("%Y")
        return {"cite_text": t["cite_text"].format(year=year, version=VERSION),
                "cite_version": t["cite_version"].format(version=VERSION, updated=UPDATED),
                "cite_bibtex": "@misc{geffroy_qdrops,\n  author = {Geffroy, Sylvain},\n"
                               f"  title = {{{t['site_title']}}},\n  year = {{{year}}},\n"
                               f"  version = {{{VERSION}}},\n  url = {{https://s-geffroy.github.io/QAnon/}}\n}}"}

    # -- export des donnees derivees
    def export(self, out):
        d = out / "data"
        d.mkdir()
        files = []

        def add(name, desc_fr, desc_en):
            files.append({"name": name, "fr": desc_fr, "en": desc_en, "size": (d / name).stat().st_size})

        drops = pd.read_sql_query("SELECT id, time, author, site, board, n_images, n_refs, text FROM drops ORDER BY id",
                                  self.conn)
        drops["date_utc"] = pd.to_datetime(drops["time"], unit="s", utc=True).dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        drops["n_words"] = drops["text"].str.split().str.len().fillna(0).astype(int)
        drops["has_link"] = drops["text"].str.contains(r"https?://").astype(int)
        drops["has_question"] = drops["text"].str.contains(r"\?").astype(int)
        drops.drop(columns=["text", "time"]).to_csv(d / "drops_metadata.csv", index=False)
        add("drops_metadata.csv", "Métadonnées de chaque drop (sans texte) : n°, date UTC, auteur, site, forum, mots, images, renvois, lien, question.",
            "Metadata of each drop (no text): #, UTC date, author, site, board, words, images, references, link, question.")
        r = self.r
        pd.DataFrame(r["descriptive"]["weekly"]).to_csv(d / "drops_weekly.csv", index=False)
        add("drops_weekly.csv", "Drops par semaine (heure de New York).", "Drops per week (New York time).")
        pd.DataFrame(r["trump"]["tests"]).to_csv(d / "trump_tests.csv", index=False)
        add("trump_tests.csv", "Tests Q / tweets de Trump : fenêtres, sens, modèle nul, observé, attendu, p.",
            "Q / Trump tweet tests: windows, direction, null model, observed, expected, p.")
        if r["discourse"]:
            pd.DataFrame([{"rank": i + 1, "share": x["share"], "terms": " ".join(x["terms"]),
                           "exemplar_ids": " ".join(map(str, x["exemplar_ids"]))}
                          for i, x in enumerate(r["discourse"]["topics"])]).to_csv(d / "topics.csv", index=False)
            add("topics.csv", "Thèmes (NMF) : rang, part, termes, drops typiques.", "Themes (NMF): rank, share, terms, typical drops.")
            pd.DataFrame(r["discourse"]["prevalence"]).to_csv(d / "topics_monthly.csv", index=False)
            add("topics_monthly.csv", "Poids mensuel de chaque thème.", "Monthly weight of each theme.")
            pd.DataFrame(r["discourse"]["glossary"]).to_csv(d / "glossary_counts.csv", index=False)
            add("glossary_counts.csv", "Formules du glossaire : nombre de drops, première occurrence.",
                "Glossary formulas: number of drops, first occurrence.")
            pd.DataFrame(r["discourse"]["style"]).to_csv(d / "style_monthly.csv", index=False)
            add("style_monthly.csv", "Indicateurs de style par mois.", "Monthly style indicators.")
        if r["actors"] and r["actors"]["actors"]:
            pd.DataFrame(r["actors"]["actors"]).to_csv(d / "actors.csv", index=False)
            add("actors.csv", "Acteurs cités : catégorie, nombre de drops, première et dernière mention.",
                "Named actors: category, number of drops, first and last mention.")
            pd.DataFrame(r["actors"]["monthly"]).to_csv(d / "actors_monthly.csv", index=False)
            add("actors_monthly.csv", "Mentions mensuelles par acteur.", "Monthly mentions per actor.")
            pd.DataFrame(r["actors"]["edges"]).to_csv(d / "actors_pairs.csv", index=False)
            add("actors_pairs.csv", "Co-mentions d'acteurs (≥ 5 drops) et NPMI.", "Actor co-mentions (≥ 5 drops) and NPMI.")
        if r["news"]:
            pd.DataFrame([{k: v for k, v in a.items() if k not in ("series", "xcorr")} for a in r["news"]["actors"]]) \
                .to_csv(d / "news_actors.csv", index=False)
            add("news_actors.csv", "Acteurs : Q contre GDELT (surreprésentation, corrélations, Granger).",
                "Actors: Q versus GDELT (over-representation, correlations, Granger).")
            pd.DataFrame(r["news"]["countries"]).to_csv(d / "news_countries.csv", index=False)
            add("news_countries.csv", "Pays : mentions par Q et événements GDELT.", "Countries: Q mentions and GDELT events.")
        if r["interest"]:
            pd.DataFrame(r["interest"]["weekly"]).to_csv(d / "wikipedia_weekly.csv", index=False)
            add("wikipedia_weekly.csv", "Pages vues Wikipédia par semaine et article.", "Weekly Wikipedia page views per article.")
        for name in ("timeline", "actors", "glossary", "bibliography"):
            src = APP_DIR / "data" / f"{name}.yaml"
            if src.exists():
                shutil.copy(src, d / f"{name}.yaml")
                add(f"{name}.yaml", f"Source éditoriale : {name}.yaml (versionnée dans le dépôt).",
                    f"Editorial source: {name}.yaml (versioned in the repository).")
        if self.refs:
            biblio.export(d, self.refs)
            add("bibliography.bib", "Bibliographie au format BibTeX.", "Bibliography in BibTeX format.")
            add("bibliography.json", "Bibliographie au format CSL-JSON (Zotero, Pandoc).", "Bibliography in CSL-JSON (Zotero, Pandoc).")
        gold = APP_DIR / "data" / "gold.jsonl"
        if gold.exists():
            shutil.copy(gold, d / "gold.jsonl")
            add("gold.jsonl", "Jeu d'annotation de référence (prédictions), 150 drops.", "Reference annotation set (predictions), 150 drops.")
        guide = APP_DIR / "data" / "gold_guidelines.md"
        if guide.exists():
            shutil.copy(guide, d / "gold_guidelines.md")
            add("gold_guidelines.md", "Consignes d'annotation du jeu de référence (français).",
                "Annotation guidelines of the reference set (French).")
        res = d / "results"
        res.mkdir()
        for k, v in r.items():
            if v is not None:
                (res / f"{k}.json").write_text(json.dumps(v, ensure_ascii=False))
        files.append({"name": "results/*.json", "fr": "Résultats bruts de chaque analyse.", "en": "Raw results of each analysis.",
                      "size": sum(p.stat().st_size for p in res.iterdir())})
        self.files = files

    def render(self, out):
        env = Environment(loader=FileSystemLoader(HERE / "templates"), autoescape=select_autoescape(["html"]))
        env.filters["tojson_compact"] = lambda v: json.dumps(v, ensure_ascii=False, separators=(",", ":"))
        env.filters["size"] = lambda b: f"{b / 1024:.0f} Ko" if b < 1024 ** 2 else f"{b / 1024 ** 2:.1f} Mo"
        if out.exists():
            shutil.rmtree(out)
        shutil.copytree(HERE / "static", out / "static")
        (out / ".nojekyll").write_text("")
        self.export(out)
        for lang in T:
            base = self.base(lang)
            (out / lang).mkdir(parents=True)
            for page in PAGES:
                ctx = {**base, "page": page, **getattr(self, f"page_{page}")(lang, base)}
                html = env.get_template(f"{page}.html").render(**ctx)
                (out / lang / f"{page}.html").write_text(html)
        (out / "index.html").write_text(env.get_template("root.html").render())


def run(ctx):
    out = ctx.state / "site"
    Site(ctx.state, ctx.conn).render(out)
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

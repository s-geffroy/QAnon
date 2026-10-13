"""Generation du site statique bilingue a partir de /state/results."""
import json
import re
import shutil
import time
from pathlib import Path

import pandas as pd
from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup

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
    ("analyses", ["index", "activity", "stats", "discourse", "actors", "predictions", "trump", "news", "interest", "timeline"]),
    ("resources", ["research", "glossary", "bibliography", "data", "method", "cite"]),
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


def script_json(v):
    """JSON a inserer dans un <script> : le navigateur n'y decode pas les entites
    HTML, donc pas d'echappement HTML (Markup), et chaque "<" ecrit \\u003c pour
    ne jamais fermer la balise."""
    return Markup(json.dumps(v, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c"))


def make_env():
    env = Environment(loader=FileSystemLoader(HERE / "templates"), autoescape=select_autoescape(["html"]))
    env.filters["tojson_compact"] = script_json
    env.filters["size"] = lambda b: f"{b / 1024:.0f} Ko" if b < 1024 ** 2 else f"{b / 1024 ** 2:.1f} Mo"
    return env


class Site:
    def __init__(self, state, conn):
        self.state = state
        self.conn = conn
        self.r = {k: _load(state, k) for k in ("descriptive", "trump", "discourse", "actors", "interest", "news",
                                                "llm_eval", "predictions", "verification", "stats")}
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
        ve = self.r["verification"]
        if ve and ve.get("items"):
            legal = [ve["by_type"].get(k) for k in ("arrest", "indictment") if ve["by_type"].get(k)]
            extra.insert(0, t["f_verif"].format(
                c=n(ve["overall"]["checkable"]), rate=p(ve["overall"]["rate"] or 0, 0),
                rate_nt=p(ve["nontrivial"]["rate"] or 0, 0),
                legal=n(sum(x["checkable"] for x in legal)), legal_ok=n(sum(x["fulfilled"] for x in legal))))
        st = self.r["stats"]
        if st:
            r = st["rhythm"]
            extra.append(t["f_rhythm"].format(w5=p(r["share_within_5min"], 0), b=n(r["burstiness"], 2),
                                              ns=n(r["n_sessions"])))
            press = st["domains"]["top_press"]
            if press:
                extra.append(t["f_domains"].format(first=press[0]["site"], fn=n(press[0]["drops"]),
                                                   second=press[1]["site"], sn=n(press[1]["drops"]),
                                                   ahead=t["ahead_far" if press[0]["drops"] >= 2 * press[1]["drops"] else "ahead"]))
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

    def page_stats(self, lang, c):
        t, st, n, p, d = c["t"], self.r["stats"], c["n"], c["p"], c["date"]
        if not st:
            return {"is_pending": True}
        r, dm, rf, rel, lx = st["rhythm"], st["domains"], st["references"], st["religion"], st["lexicon"]
        mins = lambda m: _duration(lang, m) if m >= 1 else f"{n(m * 60)} s"
        press = dm["top_press"]
        out = {
            "lead": t["stats_lead"].format(n=n(self.r["descriptive"]["n"])),
            "rhythm": t["rhythm_text"].format(med=mins(r["gap_median_min"]), q25=mins(r["gap_q25_min"]),
                                              q75=mins(r["gap_q75_min"]), w5=p(r["share_within_5min"], 0),
                                              w1h=p(r["share_within_1h"], 0), b=n(r["burstiness"], 2),
                                              m=n(r["memory"], 2), ml=n(r["memory_log"], 2)),
            "sessions": t["sessions_text"].format(gap=n(r["session_gap_min"]), ns=n(r["n_sessions"]),
                                                  multi=p(r["share_drops_in_multi"], 0),
                                                  med=n(r["session_size_median"]),
                                                  span=n(r["session_span_median_min"]), max=n(r["session_size_max"])),
            "rhythm_method": t["rhythm_method"].format(sens=" ; ".join(
                t["sens_item"].format(gap=n(x["gap_min"]), ns=n(x["n_sessions"]), multi=p(x["share_drops_in_multi"], 0))
                for x in r.get("session_sensitivity", []))),
            "regimes_note": t["regimes_note"].format(phi=n(st["changepoints"]["phi"], 1),
                                                     w=n(st["changepoints"]["min_weeks"])),
            "segments": [{"from": d(s["start"]), "to": d(s["end"]), "weeks": n(s["weeks"]),
                          "mean": n(s["mean_per_week"], 1), "total": n(s["total"]),
                          "event": (f"{s['event'][f'label_{lang}']} ({d(s['event']['date'])})" if s.get("event") else "—")}
                         for s in st["changepoints"]["segments"]],
            "boards": [{"board": b["board"], "n": n(b["n"]), "days": n(b["active_days"]),
                        "per_day": n(b["per_active_day"], 1), "words": n(b["words_median"]),
                        "links": p(b["share_links"], 0), "images": p(b["share_images"], 0),
                        "questions": p(b["share_questions"], 0), "refs": p(b["share_refs"], 0),
                        "first": d(b["first"]), "last": d(b["last"])} for b in st["boards"]],
            "domains": t["domains_text"].format(nl=n(dm["n_links"]), ns=n(dm["n_sites"]), nd=n(dm["n_drops_with_links"]),
                                                first=press[0]["site"], fn=n(press[0]["drops"]),
                                                next=", ".join(f"{x['site']} ({n(x['drops'])})" for x in press[1:5])),
            "refs": t["refs_text"].format(share=p(rf["share_with_refs"], 0), anon=p(rf["share_anon"], 0),
                                          self_=p(rf["share_self"], 0), n_self=n(rf["n_self"])),
            "refs_rows": [{"year": x["year"], "n": n(x["drops"]), "all": p(x["with_refs"], 0),
                           "anon": p(x["with_anon"], 0), "self": p(x["with_self"], 0)} for x in rf["by_year"]],
            "religion": t["religion_text"].format(faith=p(rel["share_faith"], 1), god=p(rel["share_god"], 1),
                                                  nv=n(rel["n_verse"]),
                                                  first=rel["first_verse"]["id"] if rel["first_verse"] else "—",
                                                  date=d(rel["first_verse"]["date"]) if rel["first_verse"] else "—",
                                                  books=", ".join(f"{b} ({k})" for b, k in rel["books"][:4])),
            "lexicon": t["lexicon_text"].format(f=n(lx["flesch_all"], 0), wps=n(lx["words_per_sentence_all"], 1),
                                                types=n(lx["types"]), tokens=n(lx["tokens"]), hapax=n(lx["hapax"]),
                                                z=n(lx["zipf_exponent"], 2), h=n(lx["heaps_beta"], 2),
                                                mattr=n(lx["mattr_all"], 2)),
            "charts": {"gaps": charts.gaps_hist(st, lang), "sessions": charts.session_sizes(st, lang),
                       "regimes": charts.regimes(st, self.r["descriptive"], lang),
                       "domains": charts.top_domains(st, lang), "domain_years": charts.domain_years(st, lang),
                       "religion": charts.religion(st, lang), "flesch": charts.readability(st, lang),
                       "mattr": charts.richness(st, lang)},
        }
        pr = self.r["predictions"]
        if pr and pr.get("horizon", {}).get("n"):
            h = pr["horizon"]
            out["horizon"] = t["horizon_text"].format(n=n(h["n"]), med=n(h["median_days"]), s7=p(h["share_7d"], 0),
                                                      s30=p(h["share_30d"], 0))
            out["charts"]["horizon"] = charts.horizon(pr, lang)
        return out

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
                       "world": charts.world(countries, lang, field="n")},
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
        pr = self.r["predictions"]
        if pr and pr["n_predictions"]:
            spec = dict(pr["by_specificity"])
            out["pr"] = {
                "lead": t["pred_result"].format(model=pr["model"], n=n(pr["n_annotated"]), k=n(pr["n_pred_drops"]),
                                                share=p(pr["share_pred_drops"], 0), m=n(pr["n_predictions"]),
                                                spec=n(spec.get("specific", 0)), vague=n(spec.get("vague", 0))),
                "explicit": [{"drop": x["drop_id"], "date": c["date"](x["date"]), "deadline": c["date"](x["deadline"])
                              if re.match(r"\d{4}-\d{2}-\d{2}$", str(x["deadline"])) else x["deadline"],
                              "type": t.get(f"et_{x['event_type']}", x["event_type"]), "claim": x["claim"]}
                             for x in pr["explicit"]],
                "specific": [{"drop": x["drop_id"], "date": c["date"](x["date"]),
                              "type": t.get(f"et_{x['event_type']}", x["event_type"]), "claim": x["claim"]}
                             for x in pr["specific"]],
                "charts": {"monthly": charts.pred_monthly(pr, lang), "types": charts.pred_types(pr, lang),
                           "actors": charts.pred_actors(pr, lang)},
            }
        ve = self.r["verification"]
        if ve and ve.get("items"):
            def row(label, r):
                return {"label": label, "n": n(r["n"]), "f": n(r["fulfilled"]), "pa": n(r["partial"]),
                        "nf": n(r["not_fulfilled"]), "u": n(r["unverifiable"]),
                        "rate": "—" if r["rate"] is None else p(r["rate"], 0),
                        "rate2": "—" if r["rate_with_partial"] is None else p(r["rate_with_partial"], 0),
                        "ci": "—" if not r.get("rate_ci") or r["rate_ci"][0] is None
                              else f"{p(r['rate_ci'][0], 0)}–{p(r['rate_ci'][1], 0)}"}
            o, nt = ve["overall"], ve["nontrivial"]
            out["ve"] = {
                "lead": t["ve_result"].format(n=n(o["n"]), c=n(o["checkable"]), f=n(o["fulfilled"]), pa=n(o["partial"]),
                                              nf=n(o["not_fulfilled"]), u=n(o["unverifiable"]),
                                              rate=p(o["rate"] or 0, 0), triv=n(ve["n_trivial"]),
                                              rate_nt=p(nt["rate"] or 0, 0), nap=n(ve["n_not_a_prediction"])),
                "rows": [row(t["ve_all"], o), row(t["ve_nontrivial"], nt)]
                        + [row(y, r) for y, r in ve["by_year"].items()],
                "types": [row(t.get(f"et_{k}", k), r) for k, r in
                          sorted(ve["by_type"].items(), key=lambda kv: -kv[1]["n"])],
                "list": [{"key": x["key"], "drop": x["drop_id"], "date": c["date"](x["date"]), "verdict": x["verdict"],
                           "verdict_label": t[f"vd_{x['verdict']}"], "trivial": x["trivial"],
                           "type": t.get(f"et_{x['event_type']}", x["event_type"]), "claim": x["claim"],
                           "explanation": x.get(f"explanation_{lang}") or "", "sources": x["sources"]}
                          for x in ve["items"]],
            }
        return out

    def page_timeline(self, lang, c):
        t = c["t"]
        events = sorted(self.r["descriptive"]["events"], key=lambda e: e["date"])
        def source_label(e):
            meta = json.loads(e["source_meta"]) if e.get("source_meta") else {}
            if not meta.get("outlet"):
                return t["source"], None
            when = c["date"](meta["date"]) if meta.get("date") else ""
            return f"{meta['outlet']}{', ' + when if when else ''}", meta.get("title")
        out = []
        for e in events:
            label, title = source_label(e)
            out.append({"date": c["date"](e["date"]), "iso": e["date"], "cat": e["category"],
                        "cat_label": t[f"cat_{e['category']}"], "label": e[f"label_{lang}"],
                        "source": e["source"], "source_label": label, "source_title": title})
        return {"events": out}

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

    def _prose(self, text, lang):
        """Paragraphes avec appels [@a; @b] (bibliographie) et renvois [[page]] (site)."""
        from markupsafe import Markup, escape
        t = T[lang]
        def one(par):
            out, pos = [], 0
            for m in re.finditer(r"\[(@[^\]]+)\]|\[\[([a-z]+)\]\]", par):
                out.append(str(escape(par[pos:m.start()])))
                if m.group(1):
                    out.append(str(self.cite(*[x.strip().lstrip("@") for x in m.group(1).split(";")])))
                else:
                    page = m.group(2)
                    if page not in PAGES:
                        raise KeyError(f"page inconnue dans un renvoi : {page}")
                    out.append(f'<a href="{page}.html">{escape(t[f"nav_{page}" if page != "index" else "nav_home"])}</a>')
                pos = m.end()
            out.append(str(escape(par[pos:])))
            return Markup("".join(out))
        return [one(p) for p in text.strip().split("\n") if p.strip()]

    def page_research(self, lang, c):
        data = load_yaml("research", "sections")
        import yaml
        start = yaml.safe_load((APP_DIR / "data" / "research.yaml").read_text())["start_here"]
        by_id = {r["id"]: r for r in self.refs}
        cited = set()
        sections = []
        for s_ in data:
            body = s_[f"body_{lang}"]
            cited |= {x.strip().lstrip("@") for g in re.findall(r"\[(@[^\]]+)\]", body) for x in g.split(";")}
            sections.append({"id": s_["id"], "title": s_[f"title_{lang}"], "paras": self._prose(body, lang)})
        return {"sections": sections, "n_cited": c["n"](len(cited)),
                "start": [{"id": i, "cit": biblio.citation(by_id[i], lang), "title": by_id[i]["title"],
                           "summary": by_id[i].get(f"summary_{lang}")} for i in start]}

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

    def cite(self, *ids, pre=""):
        """Appel de reference auteur-date, lie a la bibliographie : cite("a", "b") -> (A, 2020 ; B, 2021)."""
        from markupsafe import Markup, escape
        by_id = {r["id"]: r for r in self.refs}
        parts = []
        for i in ids:
            r = by_id.get(i)
            if r is None:
                raise KeyError(f"reference inconnue dans un gabarit : {i}")
            names = [a.split(",")[0].strip() for a in r.get("authors", [])] or [r.get("container") or r["title"]]
            who = names[0] if len(names) == 1 else (f"{names[0]} & {names[1]}" if len(names) == 2 else f"{names[0]} et al.")
            parts.append(f'<a href="bibliography.html#{escape(i)}">{escape(who)}, {escape(str(r.get("year") or "s.d."))}</a>')
        return Markup(f'<span class="cite">({escape(pre)}{" ; ".join(parts)})</span>')

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
        if r["predictions"] and r["predictions"]["n_predictions"]:
            allp = _load(self.state, "predictions_all")["predictions"]
            pd.DataFrame(allp).assign(subjects=lambda x: x["subjects"].map("; ".join),
                                      actor_ids=lambda x: x["actor_ids"].map("; ".join)) \
                .to_csv(d / "predictions.csv", index=False)
            add("predictions.csv", "Prédictions extraites de chaque drop (paraphrase, type, échéance, cibles) — annotation automatique.",
                "Predictions extracted from each drop (paraphrase, type, deadline, targets) — automatic annotation.")
        if r["verification"] and r["verification"].get("items"):
            pd.DataFrame([{**x, "subjects": "; ".join(x["subjects"]), "sources": " ".join(x["sources"])}
                          for x in r["verification"]["items"]]).to_csv(d / "verification.csv", index=False)
            add("verification.csv", "Vérification des prédictions une à une : verdict, horizon, caractère trivial, explication, sources.",
                "Prediction-by-prediction verification: verdict, horizon, triviality, explanation, sources.")
            for f in sorted((APP_DIR / "data" / "verification").glob("part-*.yaml")):
                shutil.copy(f, d / f"verification-{f.name}")
            shutil.copy(APP_DIR / "data" / "verification" / "README.md", d / "verification-README.md")
            add("verification-README.md", "Protocole de vérification (verdicts, horizon, citations, historique des corrections).",
                "Verification protocol (verdicts, horizon, quotes, correction history).")
        if r["stats"]:
            st = r["stats"]
            pd.DataFrame(st["changepoints"]["segments"]).assign(
                event=lambda x: x.get("event", pd.Series(dtype=object)).map(lambda e: e["id"] if isinstance(e, dict) else "")) \
                .to_csv(d / "regimes.csv", index=False)
            add("regimes.csv", "Régimes d'activité (ruptures du volume hebdomadaire) et événement le plus proche.",
                "Activity regimes (breaks in weekly volume) and nearest event.")
            pd.DataFrame(st["boards"]).to_csv(d / "boards.csv", index=False)
            add("boards.csv", "Indicateurs par forum (plateforme).", "Indicators per board (platform).")
            pd.DataFrame(st["domains"]["top"]).to_csv(d / "cited_sites.csv", index=False)
            add("cited_sites.csv", "Sites cités dans les liens des drops (nombre de drops, type de site).",
                "Sites linked in drops (number of drops, type of site).")
            pd.DataFrame(st["lexicon"]["quarterly"]).merge(pd.DataFrame(st["religion"]["quarterly"]), on="q", how="outer") \
                .to_csv(d / "lexicon_quarterly.csv", index=False)
            add("lexicon_quarterly.csv", "Par trimestre : lisibilité (Flesch), MATTR, vocabulaire religieux, versets.",
                "Per quarter: readability (Flesch), MATTR, religious vocabulary, verses.")
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
        env = make_env()
        env.globals["cite"] = self.cite
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

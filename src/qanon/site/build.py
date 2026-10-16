"""Generation du site statique bilingue a partir de /state/results."""
import collections
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
from . import biblio, charts, fmt, latex
from .i18n import REFS, REPO, T

HERE = Path(__file__).resolve().parent
UPDATED = "@@UPDATED@@"
SITE_URL = "https://s-geffroy.github.io/QAnon/"
# Archive Zenodo : DOI de concept (toutes versions, toujours la derniere) et DOI par version publiee.
ZENODO_CONCEPT = "10.5281/zenodo.23338131"
ZENODO_VERSIONS = {"1.0.0": "10.5281/zenodo.23338132"}
VERSION = "@@VERSION@@"   # remplace par le commit au moment de la publication (scripts/publish-pages.sh)
# Quatre rubriques, par question du lecteur ; l'accueil (index) est le lien du titre.
NAV = [
    ("written", ["activity", "discourse", "actors", "timeline", "corpus"]),
    ("facts", ["predictions", "trump", "news", "interest"]),
    ("models", ["stats", "models"]),
    ("resources", ["paper", "figures", "faq", "research", "watch", "teaching", "glossary", "bibliography", "data",
                   "method", "cite"]),
]
PAGES = ["index"] + [p for _, group in NAV for p in group]
GROUP_OF = {p: g for g, group in NAV for p in group}


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


POL_DATA_START = "2016-07-25"   # quatre premieres semaines du jeu de donnees /pol/


TOX_GROUP_ORDER = ("all", "q_threads", "q_posts", "promoter", "larp")


def tox_groups(pol):
    """Toxicite (score TOXICITY) par groupe du sous-corpus Q, pour la page et le document ; None avant la
    ventilation par raison (passe split_pol_tox)."""
    tx = pol["toxicity"]
    if not tx.get("split"):
        return None
    o, pr, per = tx["overall"]["TOXICITY"], tx["paired"], tx.get("periods", {})
    out = {}
    for k in TOX_GROUP_ORDER:
        if k not in o:
            continue
        v = {"n": o[k]["n"], "mean": o[k]["mean"], "high": o[k]["high"],
             "birth": per.get(k, {}).get("birth", {}).get("mean"), "after": per.get(k, {}).get("after", {}).get("mean")}
        x = pr.get(k, {}).get("TOXICITY")
        if x:
            v.update(days=x["days"], diff=x["median_diff"], days_higher=x["share_days_q_higher"], p=x["p_wilcoxon"],
                     obscene_days=pr[k].get("OBSCENE", {}).get("share_days_q_higher"))
        out[k] = v
    mix = {r["id"]: r["share"] for r in (pol.get("promoter_mix") or {}).get("rows", [])}
    out_ok = all(k in out and "days" in out[k] for k in ("q_threads", "q_posts", "promoter"))
    if not out_ok:
        return None
    out["alex_jones"] = mix.get("alex_jones", 0)
    return out


def paper_block(site, kind, name):
    """Tableaux et figures du document de travail, calcules a partir des resultats."""
    from markupsafe import escape
    r, n, p = site.r, (lambda x, d=0: fmt.num("fr", x, d)), (lambda x, d=0: fmt.pct("fr", x, d))
    T_ = T["fr"]
    if kind == "table" and name == "trump":
        rows = [x for x in r["trump"]["tests"] if x["null"] == "local"]
        body = "".join(f"<tr><td>{n(x['window_s'] / 60)} min</td><td>{'tweet après le drop' if x['direction'] == 'tweet_after_drop' else 'tweet avant le drop'}</td>"
                       f"<td class='r'>{p(x['observed'], 1)}</td><td class='r'>{p(x['expected'], 1)}</td><td class='r'>{n(x['p_value'], 3)}</td></tr>"
                       for x in rows)
        return ("<table class='paper-table'><caption>Tableau 1. Tweets de Trump à proximité des drops, modèle nul local "
                f"({n(r['trump']['n_perm'])} permutations).</caption><thead><tr><th>Fenêtre</th><th>Sens</th><th class='r'>Observé</th>"
                f"<th class='r'>Attendu</th><th class='r'>p</th></tr></thead><tbody>{body}</tbody></table>")
    if kind == "table" and name == "verif_types":
        bt = r["verification"]["by_type"]
        rows = sorted(bt.items(), key=lambda kv: -kv[1]["checkable"])
        body = "".join(f"<tr><td>{escape(T_.get('et_' + k, k))}</td><td class='r'>{n(v['checkable'])}</td><td class='r'>{n(v['fulfilled'])}</td>"
                       f"<td class='r'>{n(v['partial'])}</td><td class='r'>{n(v['not_fulfilled'])}</td>"
                       f"<td class='r'>{p(v['rate'], 0) if v['rate'] is not None else '—'}</td></tr>" for k, v in rows if v["checkable"])
        o = r["verification"]["overall"]
        body += (f"<tr class='tot'><td>Ensemble</td><td class='r'>{n(o['checkable'])}</td><td class='r'>{n(o['fulfilled'])}</td>"
                 f"<td class='r'>{n(o['partial'])}</td><td class='r'>{n(o['not_fulfilled'])}</td><td class='r'>{p(o['rate'], 0)}</td></tr>")
        return ("<table class='paper-table'><caption>Tableau 2. Prédictions vérifiables par type d'événement annoncé.</caption>"
                "<thead><tr><th>Type</th><th class='r'>Vérifiables</th><th class='r'>Réalisées</th><th class='r'>Partielles</th>"
                f"<th class='r'>Non réalisées</th><th class='r'>Taux</th></tr></thead><tbody>{body}</tbody></table>")
    if kind == "table" and name == "diffusion":
        sc = r["scene"] or {}
        rows = sorted([x for x in sc.get("diffusion", []) if x["term"].startswith("gl:") and x["q_drops"] >= 8],
                      key=lambda x: x["first_q"])
        cov = sc.get("coverage", {})
        done, total = sum(x["sampled_days"] for x in cov.values()), sum(x["active_days"] for x in cov.values())
        body = "".join(f"<tr><td>{escape(x['label_fr'])}</td><td class='r'>{n(x['q_drops'])}</td><td>{fmt.date('fr', x['first_q'])}</td>"
                       f"<td>{fmt.date('fr', x['first_reddit_sample']) if x.get('first_reddit_sample') else '—'}</td>"
                       f"<td class='r'>{n(x['lag_days']) if x.get('lag_days') is not None else '—'}</td></tr>" for x in rows)
        return ("<table class='paper-table'><caption>Tableau 3. Formules de Q : premier drop et première occurrence dans "
                f"l'échantillon quotidien de Reddit ({p(done / total if total else 0)} des jours actifs échantillonnés ; "
                "un écart négatif signifie que la formule circulait avant Q).</caption><thead><tr><th>Formule</th>"
                "<th class='r'>Drops</th><th>Premier drop</th><th>Première occurrence sur Reddit</th>"
                f"<th class='r'>Écart (jours)</th></tr></thead><tbody>{body}</tbody></table>")
    if kind == "table" and name == "pol_births":
        pol = r.get("pol")
        if not pol:
            return ""
        lab = {"before_q": "déjà là avant Q", "about_q": "naît avec Q", "pol_first": "/pol/ avant Q", "q_first": "Q d'abord"}
        rows = [x for x in pol["births"] if x["status"] in lab and x["pol_posts"] >= 500]
        body = "".join(f"<tr><td>{escape(x['label_fr'])}</td><td class='r'>{n(x['pol_posts'])}</td>"
                       f"<td class='r'>{n(x['rate_before'], 1)}</td><td class='r'>{n(x['rate_after'], 1)}</td>"
                       f"<td>{'dès le début des données' if x['onset_week'] < POL_DATA_START else fmt.date('fr', x['onset_week'])}</td>"
                       f"<td>{fmt.date('fr', x['first_q']) if x['first_q'] else '—'}</td>"
                       f"<td>{lab[x['status']]}</td></tr>" for x in rows)
        return ("<table class='paper-table'><caption>Tableau 4. Formules liées à Q sur /pol/ (au moins 500 posts) : taux par "
                "million de posts avant et après le 28 octobre 2017, semaine d'apparition (premier dépassement durable du "
                "taux d'avant Q) et premier drop qui emploie la formule.</caption><thead><tr><th>Formule</th>"
                "<th class='r'>Posts</th><th class='r'>Avant</th><th class='r'>Après</th><th>Apparition</th>"
                f"<th>Premier drop</th><th>Lecture</th></tr></thead><tbody>{body}</tbody></table>")
    if kind == "table" and name == "pol_tox_groups":
        g = tox_groups(r["pol"]) if r.get("pol") else None
        if not g:
            return ""
        sign = lambda x: ("+" if x > 0 else "") + n(x, 3)
        body = "".join(f"<tr><td>{escape(T_['pol_group_' + k])}</td><td class='r'>{n(v['n'])}</td><td class='r'>{n(v['mean'], 3)}</td>"
                       f"<td class='r'>{p(v['high'], 1)}</td><td class='r'>{sign(v['diff']) if v.get('days') else '—'}</td>"
                       f"<td class='r'>{p(v['days_higher'], 0) if v.get('days') else '—'}</td>"
                       f"<td class='r'>{n(v['days']) if v.get('days') else '—'}</td></tr>"
                       for k, v in g.items() if k in TOX_GROUP_ORDER)
        return ("<table class='paper-table'><caption>Tableau 5. Toxicité (score TOXICITY de Perspective) des posts liés à Q "
                "sur /pol/, par groupe, juillet 2016 – novembre 2019. Écart médian : moyenne du groupe moins moyenne de tout "
                "/pol/, jour par jour, sur les jours où le groupe compte au moins 100 posts notés.</caption><thead><tr>"
                "<th>Groupe</th><th class='r'>Posts notés</th><th class='r'>Moyenne</th><th class='r'>Part &gt; 0,8</th>"
                "<th class='r'>Écart médian</th><th class='r'>Jours où le groupe dépasse /pol/</th>"
                f"<th class='r'>Jours comparés</th></tr></thead><tbody>{body}</tbody></table>")
    if kind == "figure":
        return paper_figure(site, name)
    raise KeyError(f"bloc inconnu dans le document : {kind}:{name}")


def paper_figure(site, name):
    import io
    import matplotlib.pyplot as plt
    fig, cap = paper_fig(site, name)
    buf = io.StringIO()
    fig.savefig(buf, format="svg")
    plt.close(fig)
    svg = re.sub(r"^.*?(<svg)", r"\1", buf.getvalue(), flags=re.S)
    return f"<figure class='paper-fig'>{svg}<figcaption>{cap}</figcaption></figure>"


def paper_fig(site, name):
    """Figure du document de travail (matplotlib) et sa legende ; SVG pour le site et le PDF,
    PDF vectoriel pour l'export LaTeX."""
    import matplotlib
    matplotlib.use("svg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 8, "axes.spines.top": False, "axes.spines.right": False,
                         "svg.fonttype": "none"})
    r = site.r
    fig, ax = plt.subplots(figsize=(6.3, 2.3))
    if name == "weekly":
        w = pd.DataFrame(r["descriptive"]["weekly"])
        w["week"] = pd.to_datetime(w["week"])
        ax.fill_between(w["week"], w["n"], step="post", color="#9cc3ef", lw=0)
        for sg in r["stats"]["changepoints"]["segments"]:
            ax.hlines(sg["mean_per_week"], pd.Timestamp(sg["start"]), pd.Timestamp(sg["end"]), color="#c0392b", lw=1.6)
        ax.set_ylabel("drops par semaine")
        cap = "Figure 1. Drops par semaine (heure de New York) et moyenne de chacun des régimes d'activité détectés."
    elif name == "horoscope":
        k = r["horoscope"]["kinds"]["future"]["hist"]
        import numpy as np
        x = np.arange(len(k))
        ax.bar(x - .2, [h["true"] for h in k], .4, color="#2a78d6", label="30 jours après le drop")
        ax.bar(x + .2, [h["random"] for h in k], .4, color="#eb6834", label="30 jours au hasard")
        ax.set_xticks(x)
        ax.set_xlabel("note de lien attribuée par le modèle (0 = aucun lien précis)")
        ax.set_ylabel("comparaisons")
        ax.legend(frameon=False)
        cap = "Figure 2. Test de l'horoscope : notes de lien pour la vraie période « avenir » et pour une période tirée au hasard."
    elif name == "overrep":
        a = sorted([x for x in r["news"]["actors"] if x.get("overrep")], key=lambda x: x["overrep"])
        ax.barh([x["name"] for x in a], [x["overrep"] for x in a], color="#2a78d6")
        ax.axvline(1, color="#555", lw=.8, ls="--")
        ax.set_xscale("log")
        ax.set_xlabel("sur-représentation dans les drops par rapport à GDELT (échelle log, 1 = même place)")
        fig.set_size_inches(6.3, 3.2)
        cap = "Figure 3. Place des principaux acteurs dans les drops rapportée à leur place dans l'actualité mondiale."
    elif name == "models":
        fig.clf()
        fig.set_size_inches(6.3, 2.5)
        a1, a2 = fig.subplots(1, 2, gridspec_kw={"width_ratios": [1.7, 1]})
        h = pd.DataFrame(r["markov"]["hmm"]["series"])
        h["date"] = pd.to_datetime(h["date"])
        top = r["markov"]["hmm"]["K"] - 1
        a1.bar(h["date"], h["n"], width=1.0, color=["#2a78d6" if s_ == top else "#b9b6ae" for s_ in h["state"]], lw=0)
        a1.set_ylabel("drops par jour")
        a1.set_title("a. Régime « actif » du modèle de Markov caché (bleu)", fontsize=8, loc="left")
        hm = r["physics"]["hawkes"]["models"]
        for key, col, lab in (("regimes/poisson", "#eb6834", "Poisson"), (r["physics"]["hawkes"]["best"], "#2a78d6", "Hawkes (Omori)")):
            q = hm[key]["gof"]["qq"]
            a2.plot([x["theory"] for x in q], [x["observed"] for x in q], color=col, lw=1.6, label=lab)
        lim = max(x["theory"] for x in hm["regimes/poisson"]["gof"]["qq"])
        a2.plot([0, lim], [0, lim], color="#555", lw=.8, ls="--")
        a2.set_xlabel("quantile théorique")
        a2.set_ylabel("quantile observé")
        a2.set_title("b. Résidus : adéquation des modèles", fontsize=8, loc="left")
        a2.legend(frameon=False)
        cap = ("Figure 4. (a) Drops par jour ; les jours du régime « actif » du modèle de Markov caché sont en bleu. "
               "(b) Diagramme quantile-quantile des intervalles après changement de temps : un modèle bien ajusté suit la "
               "diagonale. Le processus de Poisson (même fond par régime et cycle quotidien) s'en écarte, le processus de "
               "Hawkes s'en approche.")
    else:
        raise KeyError(f"figure inconnue : {name}")
    fig.tight_layout()
    return fig, cap


def dt_rfc(day):
    import email.utils
    import datetime as _dt
    return email.utils.format_datetime(_dt.datetime.fromisoformat(day[:10]).replace(hour=12, tzinfo=_dt.timezone.utc))


def og_image(path):
    """Vignette de partage 1200x630 (OpenGraph), sans police externe."""
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new("RGB", (1200, 630), "#fbfaf7")
    d = ImageDraw.Draw(img)
    big, mid = ImageFont.load_default(size=64), ImageFont.load_default(size=34)
    d.rectangle([0, 0, 1200, 14], fill="#2a78d6")
    d.text((80, 170), "Les drops de Q", fill="#0b0b0b", font=big)
    d.text((80, 250), "à l'épreuve des faits", fill="#0b0b0b", font=big)
    d.text((80, 370), "Étude statistique des messages de « Q » (2017-2022)", fill="#52514e", font=mid)
    d.text((80, 420), "Q drops against the facts — FR / EN", fill="#52514e", font=mid)
    d.text((80, 540), "s-geffroy.github.io/QAnon", fill="#2a78d6", font=mid)
    img.save(path, optimize=True)


def script_json(v):
    """JSON a inserer dans un <script> : le navigateur n'y decode pas les entites
    HTML, donc pas d'echappement HTML (Markup), et chaque "<" ecrit \\u003c pour
    ne jamais fermer la balise."""
    return Markup(json.dumps(v, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c"))


def unlabel(text):
    """Note de methode sans son prefixe ("Methode : ...") : le bloc replie porte deja ce titre."""
    out = re.sub(r"^\s*(?:Méthode|Method)\s*:\s*", "", str(text))
    out = out[:1].upper() + out[1:]
    return Markup(out) if isinstance(text, Markup) else out


def make_env():
    env = Environment(loader=FileSystemLoader(HERE / "templates"), autoescape=select_autoescape(["html"]))
    env.filters["tojson_compact"] = script_json
    env.filters["unlabel"] = unlabel
    env.filters["size"] = lambda b: f"{b / 1024:.0f} Ko" if b < 1024 ** 2 else f"{b / 1024 ** 2:.1f} Mo"
    return env


class Site:
    def __init__(self, state, conn):
        self.state = state
        self.conn = conn
        self.r = {k: _load(state, k) for k in ("descriptive", "trump", "discourse", "actors", "interest", "news",
                                                "llm_eval", "predictions", "verification", "stats",
                                                "horoscope", "prophecies", "translations", "markov", "physics", "scene", "pol")}
        self.glossary = load_yaml("glossary", "terms")
        self.refs = biblio.load()
        self._figures = {}

    # -- contexte commun a toutes les pages
    def base(self, lang):
        t = T[lang]
        desc = self.r["descriptive"]
        n = lambda x, d=0: fmt.num(lang, x, d)
        jsonld = {"@context": "https://schema.org", "@type": "WebSite", "name": t["site_title"],
                  "description": t["site_sub"], "url": f"{SITE_URL}{lang}/index.html", "inLanguage": lang,
                  "author": {"@type": "Person", "name": "Sylvain Geffroy"},
                  "license": "https://creativecommons.org/licenses/by/4.0/"}
        return {"lang": lang, "t": t, "repo": REPO, "refs": REFS, "updated": UPDATED, "version": VERSION,
                "site_url": SITE_URL, "jsonld": jsonld,
                "nav": NAV, "group_of": GROUP_OF, "n": n, "p": lambda x, d=1: fmt.pct(lang, x, d), "date": lambda v: fmt.date(lang, v),
                "desc": desc}

    def page_index(self, lang, c):
        t, desc, trump = c["t"], self.r["descriptive"], self.r["trump"]
        n, p = c["n"], c["p"]
        t5 = next(x for x in trump["tests"] if x["window_s"] == 300 and x["direction"] == "tweet_after_drop"
                  and x["null"] == "local")
        verdict = (t["verdict_sig"] if t5["p_value"] < 0.05 else t["verdict_ns"]).format(p=n(t5["p_value"], 3))
        gap = desc["gaps"][0]
        # Constats regroupes par question du lecteur ; chaque groupe renvoie a sa page.
        q = {k: [] for k in ("right", "trump", "who", "what", "origin")}
        q["trump"].append(t["f_trump"].format(obs=p(t5["observed"]), exp=p(t5["expected"]), verdict=verdict))
        act, disc, news, inter = self.r["actors"], self.r["discourse"], self.r["news"], self.r["interest"]
        if disc and disc.get("stylometry"):
            split = disc["stylometry"]["split"]["date"]
            # La phrase "rejoint les analyses de 2022" n'est vraie que si la
            # coupure tombe dans la fenetre qu'elles decrivent.
            key = "f_stylo" if "2017-11-01" <= split <= "2018-04-30" else "f_stylo_other"
            q["who"].append(t[key].format(date=c["date"](split)))
        q["who"].append(t["f_questions"].format(q=n(desc["questions_per_drop"], 1)))
        st = self.r["stats"]
        if st:
            r = st["rhythm"]
            q["who"].append(t["f_rhythm"].format(w5=p(r["share_within_5min"], 0), b=n(r["burstiness"], 2),
                                                 ns=n(r["n_sessions"])))
        q["who"].append(t["f_gap"].format(days=n(gap["days"]), from_=c["date"](gap["from"]), to=c["date"](gap["to"])))
        if act and act["actors"]:
            top = ", ".join(f"{a['name']} ({n(a['n'])})" for a in act["actors"][:5])
            q["what"].append(t["f_actors"].format(top=top))
        if news and news["actors"]:
            ranked = sorted([a for a in news["actors"] if a.get("overrep") and a["q"] >= 30], key=lambda a: -a["overrep"])
            if ranked:
                q["what"].append(t["f_overrep"].format(names=", ".join(f"{a['name']} (×{n(a['overrep'], 1)})"
                                                                       for a in ranked[:3])))
        if st and st["domains"]["top_press"]:
            press = st["domains"]["top_press"]
            q["what"].append(t["f_domains"].format(first=press[0]["site"], fn=n(press[0]["drops"]),
                                                   second=press[1]["site"], sn=n(press[1]["drops"]),
                                                   ahead=t["ahead_far" if press[0]["drops"] >= 2 * press[1]["drops"] else "ahead"]))
        if inter and inter["events"]:
            e = inter["events"][0]
            q["trump"].append(t["f_interest"].format(label=e[f"label_{lang}"], ratio=n(e["ratio"], 1)))
        for fid in ("horoscope", "propheties-recyclees"):
            f = next((x for x in self.figures(lang) if x["id"] == fid), None)
            if f:
                q["right"].append(f["text"])
        pol = self.r["pol"]
        if pol:
            cnt = collections.Counter(b["status"] for b in pol["births"])
            nov = next((x["share"] for x in pol["niche"] if x["month"] == "2017-11"), None)
            if nov is not None:
                q["origin"].append(t["f_pol"].format(q_first=n(cnt.get("q_first", 0)), n=n(len(pol["births"])),
                                                     before_q=n(cnt.get("before_q", 0)), share=p(nov, 1)))
        links = {"right": "predictions.html", "trump": "trump.html", "who": "discourse.html", "what": "actors.html",
                 "origin": "models.html#pol"}
        go = {"right": "go_predictions", "trump": "go_trump", "who": "go_who", "what": "go_what", "origin": "go_origin"}
        questions = [{"q": t["q_" + k], "facts": v, "href": links[k], "go": t[go[k]]} for k, v in q.items() if v]
        out = {
            "lead": t["home_lead"].format(first=c["date"](desc["first"]), last=c["date"](desc["last"]), n=n(desc["n"])),
            "kpis": [(n(desc["n"]), t["kpi_drops"]), (n(desc["active_days"]), t["kpi_days"]),
                     (n(desc["words_total"]), t["kpi_words"]), (p(desc["share_questions"], 0), t["kpi_questions"])],
            "questions": questions,
            "charts": {"weekly": charts.weekly(desc, lang)},
        }
        ve = self.r["verification"]
        if ve and ve.get("items"):
            legal = [ve["by_type"].get(k) for k in ("arrest", "indictment") if ve["by_type"].get(k)]
            fmt_ = dict(c=n(ve["overall"]["checkable"]), rate=p(ve["overall"]["rate"] or 0, 0),
                        rate_nt=p(ve["nontrivial"]["rate"] or 0, 0),
                        legal=n(sum(x["checkable"] for x in legal)), legal_ok=n(sum(x["fulfilled"] for x in legal)))
            out["h1"], out["h1_sub"] = t["home_h1"].format(**fmt_), t["home_h1_sub"].format(**fmt_)
            # En ouverture : la premiere prediction du premier drop, son texte original et son verdict.
            first = min((x for x in ve["items"] if x.get("verdict") in ("fulfilled", "partial", "not_fulfilled")),
                        key=lambda x: (x["drop_id"], x["key"]))
            row = self.conn.execute("SELECT text FROM drops WHERE id = ?", (first["drop_id"],)).fetchone()
            if row and row[0]:
                # Sans les renvois a d'autres posts (">>147005...") qui ouvrent souvent un drop.
                text = re.sub(r"^(?:>>\d+\s*)+", "", " ".join(row[0].split()))
                cut = [m.end() for m in re.finditer(r"[.!?](?=\s|$)", text) if m.end() >= 120]
                out["hero"] = {"text": text[:cut[0]] if cut and cut[0] <= 260 else text[:240].rsplit(" ", 1)[0] + "…",
                               "source": t["hero_source"].format(date=c["date"](first["date"])),
                               "drop": first["drop_id"], "fact": first.get(f"explanation_{lang}") or "",
                               "verdict": first["verdict"], "verdict_label": t["vd_" + first["verdict"]],
                               "more": t["hero_more"].format(n=n(ve["overall"]["checkable"]))}
        return out

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
                              "type": t.get(f"et_{x['event_type']}", x["event_type"]),
                              "claim": self.tr(f"{x['drop_id']}-{x.get('k', 0)}", x["claim"], lang)}
                             for x in pr["explicit"]],
                "specific": [{"drop": x["drop_id"], "date": c["date"](x["date"]),
                              "type": t.get(f"et_{x['event_type']}", x["event_type"]),
                              "claim": self.tr(f"{x['drop_id']}-{x.get('k', 0)}", x["claim"], lang)}
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
                           "type": t.get(f"et_{x['event_type']}", x["event_type"]),
                           "claim": self.tr(x["key"], x["claim"], lang), "explanation": x.get(f"explanation_{lang}") or "", "sources": [self.src(u) for u in x["sources"]]}
                          for x in ve["items"]],
            }
        ho = self.r.get("horoscope")
        if ho and ho.get("kinds"):
            rows = []
            for kind in ("past", "future"):
                k = ho["kinds"].get(kind)
                if not k:
                    continue
                ci = k["ci_true_decided"]
                rows.append({"label": t[f"horo_{kind}"], "n": n(k["n"]), "true": n(k["chose_true"]),
                             "random": n(k["chose_random"]), "none": n(k["none"]),
                             "share": p(k["share_true_decided"], 0) if k["share_true_decided"] is not None else "—",
                             "ci": f"{p(ci[0], 0)}–{p(ci[1], 0)}" if ci[0] is not None else "—",
                             "p": "—" if k["p_value"] is None else (f"< {n(0.001, 3)}" if k["p_value"] < 0.001 else n(k["p_value"], 3)),
                             "sig": (k["p_value"] or 1) < 0.05,
                             "mt": n(k["mean_true"], 1), "mr": n(k["mean_random"], 1), "barnum": p(k["share_random_ge5"], 0)})
            f, pa = ho["kinds"].get("future", {}), ho["kinds"].get("past", {})
            out["horo"] = {
                "rows": rows,
                "result": t["horo_result"].format(
                    past=p(pa.get("share_true_decided") or 0, 0), future=p(f.get("share_true_decided") or 0, 0),
                    none=p(f["none"] / f["n"], 0) if f.get("n") else "—", barnum=p(f.get("share_random_ge5") or 0, 0)),
                "reading": t["horo_reading"].format(
                    none=p(f["none"] / f["n"], 0) if f.get("n") else "—",
                    pdiff=n((ho.get("past_vs_future") or {}).get("p_value") or 1, 2)),
                "examples": [{**e, "reason": self.tr(f"horo:future:{e['drop_id']}", e["reason"], lang)}
                             for e in f.get("examples", [])[:5]],
                "robust": (lambda rb: t["horo_robust"].format(
                    model=rb["model"], n=n(rb["n_drops"]), nf=n(rb["future"]["n"]),
                    none_c=n(rb["future"]["check"]["none"]), none_m=n(rb["future"]["main"]["none"]),
                    dec_c=n(rb["future"]["check"]["true"] + rb["future"]["check"]["random"]),
                    true_c=n(rb["future"]["check"]["true"]), kappa=n(rb["future"]["kappa"] or 0, 2),
                    agree=p(rb["future"]["agreement"] or 0, 0))
                    if rb and rb.get("future", {}).get("n") else None)(ho.get("robustness")),
                "method": t["horo_method"].format(n=n(ho["n_sample"]), items=n(ho["n_items"]), model=ho["model"]),
            }
            out.setdefault("charts", {})["horo"] = charts.horoscope(ho, lang)
        pp = self.r.get("prophecies")
        if pp:
            rc, fp = pp["recycled"], pp["fpp"]
            names = {a["id"]: a["name"] for a in load_yaml("actors", "actors")}
            vlab = lambda vs: ", ".join(f"{t['vd_' + k]} {v}" for k, v in sorted(vs.items(), key=lambda kv: -kv[1]))
            out["recy"] = {
                "lead": t["recy_lead"].format(g=n(rc["n_groups"]), k=n(rc["n_in_groups"]), share=p(rc["share_in_groups"], 0),
                                              m=n(rc["min_months"]), after=n(rc["n_after_failure"]),
                                              ga=n(rc["n_groups_after_failure"])),
                "groups": [{"subject": f"{t.get('et_' + g['event_type'], g['event_type'])} — {names.get(g['actor'], g['actor'])}",
                            "n": n(g["n"]), "months": n(g["months"]), "first": c["date"](g["first"]),
                            "last": c["date"](g["last"]), "after": n(g["after_failure"]),
                            "verdicts": vlab(g["verdicts"]) or "—",
                            "claim": self.tr(g.get("claim_key", ""), g["claim"], lang)} for g in rc["groups"]],
            }
            out.setdefault("charts", {})["recy"] = charts.recycled(rc, names, lang)
            if fp.get("n"):
                out["fpp"] = {"lead": t["fpp_lead"].format(
                    n=n(fp["n"]), same=p(fp["share_same_day"], 0), late=n(fp["n_late"]),
                    pred=p(fp["share_cited_pred_late"] or 0, 0), txt=n(fp["n_fpp_text"]), fref=n(fp["fpp_refs"]))}
                out["charts"]["fpp"] = charts.fpp(fp, lang)
        return out

    def page_models(self, lang, c):
        """Modeles : chaines de Markov, analogies physiques, Q dans la scene complotiste."""
        t, n, p, d = c["t"], c["n"], c["p"], c["date"]
        mk, ph, sc = self.r["markov"], self.r["physics"], self.r["scene"]
        if not mk or not ph:
            return {"is_pending": True}
        out = {"charts": {}}
        # -- regimes caches
        h = mk["hmm"]
        names = charts.regime_names(h["K"], lang)
        near = [x["nearest_hmm_switch_days"] for x in h["changepoint_agreement"] if x["nearest_hmm_switch_days"] is not None]
        top = h["states"][-1]
        out["hmm"] = t["hmm_text"].format(k=n(h["K"]), sw=n(h["n_switches"]), name=names[-1], rate=n(top["rate_per_day"], 1),
                                          days=p(top["share_days"], 0), drops=p(top["share_drops"], 0),
                                          dwell=n(top["mean_dwell_days"], 1), agree=n(sum(x <= 7 for x in near)),
                                          ncp=n(len(h["changepoint_agreement"])))
        out["hmm_rows"] = [{"name": names[s["state"]], "rate": n(s["rate_per_day"], 2), "disp": n(s["var_to_mean"], 1),
                            "dwell": n(s["mean_dwell_days"], 1), "days": p(s["share_days"], 0), "drops": p(s["share_drops"], 0)}
                           for s in h["states"]]
        out["hmm_bic"] = ", ".join(f"K = {b['K']} : {n(b['bic'], 0)}" for b in h["bic"])
        out["charts"]["hmm"] = charts.hmm_regimes(mk, lang)
        # -- chaine de themes
        ch = mk["topic_chain"]
        ns_ = ch["null_session"]
        out["chain"] = t["chain_text"].format(nd=n(ch["n_drops"]), np_=n(ch["n_pairs"]), ns=n(ch["n_sessions_multi"]),
                                              h0=n(ch["entropy_iid_bits"], 2), h1=n(ch["entropy_rate_bits"], 2),
                                              diag=p(ch["diag_share"], 1), null=p(ns_["diag_mean"], 1),
                                              pv=n(ns_["p_diag"], 3), perm=n(ch["n_perm"]))
        lab = ch["labels"]
        out["chain_rows"] = [{"from": lab[x["from"]], "to": lab[x["to"]], "n": n(x["n"]), "exp": n(x["expected"], 1),
                              "lift": n(x["lift"], 2)} for x in ch["lift"][:8]]
        # -- compression et derive du style
        sd, cp = mk["style_drift"], mk["compression"]
        steps = sorted(sd["steps"], key=lambda x: -x["drift"])
        out["drift"] = t["drift_text"].format(a=steps[0]["from"].replace("Q ", ""), b=steps[0]["to"].replace("Q ", ""),
                                              da=n(steps[0]["drift"], 2), c=steps[1]["from"].replace("Q ", ""),
                                              e=steps[1]["to"].replace("Q ", ""), dc=n(steps[1]["drift"], 2))
        out["drift_rows"] = [{"from": x["from"].replace("Q ", ""), "to": x["to"].replace("Q ", ""), "bits": n(x["bits"], 2),
                              "self": n(x["self"], 2), "drift": n(x["drift"], 2)} for x in sd["steps"]]
        qn = {k: v for k, v in cp["nearest"].items() if k.startswith("Q ")}
        first = min(qn)
        out["compression"] = t["compression_text"].format(first=first.replace("Q ", ""), near=qn[first]["name"],
                                                          dist=n(qn[first]["distance"], 2),
                                                          trump=n(min(v["distance"] for k, v in cp["nearest"].items()
                                                                      if k.startswith("Trump")), 2))
        out["charts"]["style"] = charts.style_matrix(mk, lang)
        # -- Hawkes
        hm = ph["hawkes"]["models"]
        b, up = hm["regimes/omori"], hm.get("constant/omori", {})
        out["hawkes"] = t["hawkes_text"].format(n=p(b["branching_ratio"], 0), up=p(up.get("branching_ratio") or 0, 0),
                                                med=n(b["kernel"]["median_delay_hours"] * 60, 0),
                                                pomori=n(b["kernel"]["omori_p"], 2), ks=n(b["gof"]["ks_D"], 3),
                                                ks0=n(hm["regimes/poisson"]["gof"]["ks_D"], 2), nreg=n(b["n_regimes"]))
        label = {"poisson": t["model_poisson"], "exp": t["model_exp"], "omori": t["model_omori"]}
        out["hawkes_rows"] = [{"base": t[f"base_{k.split('/')[0]}"], "kernel": label[k.split("/")[1]],
                               "aic": n(m["aic"], 0), "n": p(m["branching_ratio"], 0) if m["branching_ratio"] is not None else "—",
                               "ks": n(m["gof"]["ks_D"], 3), "best": k == ph["hawkes"]["best"]}
                              for k, m in sorted(hm.items(), key=lambda kv: (not kv[0].startswith("regimes/"), kv[1]["aic"]))]
        out["charts"]["qq"] = charts.hawkes_qq(ph, lang)
        ht = ph["hawkes_trump"]
        out["hawkes_trump"] = t["hawkes_trump_text"].format(share=p(ht["share_drops_from_cross"], 1),
                                                            delay=n(ht["cross_kernel"]["mean_delay_hours"], 1),
                                                            pv=n(ht["p_shift"], 3), ns=n(len(ht["null_shifts"])))
        # -- DFA
        dfa = {(x["series"], x["resolution"]): x for x in ph["dfa"]}
        out["dfa"] = t["dfa_text"].format(q=n(dfa[("Q", "day")]["H"], 2), tr=n(dfa[("Trump", "day")]["H"], 2),
                                          sh=n(dfa[("Q", "day")]["H_shuffled"], 2), qh=n(dfa[("Q", "hour")]["H"], 2))
        out["charts"]["dfa"] = charts.dfa_curves(ph, lang)
        # -- avalanches
        av = ph["avalanches"]
        qs, ts_ = av["Q"]["size"], av["Trump"]["size"]
        out["avalanches"] = t["avalanche_text"].format(a=n(qs["alpha"], 1), xmin=n(qs["xmin"]), tail=n(qs["n_tail"]),
                                                       n_=n(qs["n"]), gof=n(qs["gof_p"], 2),
                                                       pexp=n(qs["vs_exponential"]["p"], 2), pln=n(qs["vs_lognormal"]["p"], 2),
                                                       at=n(ts_["alpha"], 1))
        out["charts"]["ccdf"] = charts.avalanche_ccdf(ph, lang)
        # -- phases
        pz = ph["phases"]
        sp = pz["phase_split"]
        def hh(x):
            h, m = int(x) % 24, int(round((x % 1) * 60)) % 60
            return f"{h:02d} h {m:02d}" if lang == "fr" else f"{h:02d}:{m:02d}"
        out["phases"] = t["phases_text"].format(q=hh(pz["day"]["Q"]["peak"]), tr=hh(pz["day"]["Trump"]["peak"]),
                                                date=d(sp["date"]), before=hh(sp["before_peak"]), after=hh(sp["after_peak"]),
                                                pv=n(sp["p"], 3), plv=n(pz.get("phase_locking", {}).get("plv", 0), 2),
                                                lag=n(pz.get("phase_locking", {}).get("mean_lag_hours", 0), 1))
        out["charts"]["phases"] = charts.phase_months(ph, lang)
        # -- scene complotiste
        if sc:
            extra = self._scene_context(lang, c, sc)
            out["charts"].update(extra.pop("charts"))
            out.update(extra)
        if self.r["pol"]:
            extra = self._pol_context(lang, c, self.r["pol"])
            out["charts"].update(extra.pop("charts"))
            out.update(extra)
        return out

    def _pol_context(self, lang, c, pol):
        """Q sur /pol/ : chiffres et tableaux de la section, d'apres analyze_pol."""
        t, n, p, d = c["t"], c["n"], c["p"], c["date"]
        month = lambda m: f"{fmt.MONTHS[lang][int(m[5:7]) - 1]} {m[:4]}"
        pval = lambda x: f"< {n(0.001, 3)}" if x < 0.001 else n(x, 3)
        ov = pol["overview"]
        out = {"charts": {"pol_niche": charts.pol_niche(pol, lang), "pol_tox": charts.pol_toxicity(pol, lang)}}
        out["pol_lead"] = t["pol_lead"].format(posts=n(ov["posts"]), threads=n(ov["threads"]), qth=n(ov["q_threads"]),
                                               qposts=n(sum(v for k, v in ov["q_corpus"].items() if k.startswith("thread:"))))
        ni = pol["niche"]
        peak = max(ni, key=lambda x: x["share"])
        nxt = ni[ni.index(peak) + 1] if ni.index(peak) + 1 < len(ni) else peak
        later = [x["share"] for x in ni if x["month"] >= "2018-01"]
        out["pol_niche"] = t["pol_niche_text"].format(month=month(peak["month"]), share=p(peak["share"], 1),
                                                      next=p(nxt["share"], 2), later=p(float(pd.Series(later).median()) if later else 0, 2))
        b = pol["births"]
        # Semaine d'apparition dans le premier mois des donnees : le terme circulait deja.
        onset = lambda w: t["pol_onset_start"] if w < POL_DATA_START else d(w)
        cnt = {}
        for r in b:
            cnt[r["status"]] = cnt.get(r["status"], 0) + 1
        out["pol_births"] = t["pol_births_text"].format(n=n(len(b)), **{k: n(cnt.get(k, 0)) for k in
                                                        ("before_q", "about_q", "pol_first", "q_first", "no_onset")})
        cb = next((r for r in b if r["term"] == "cbts" and r["status"] == "before_q"), None)
        if cb and "2017-09-25" <= cb["onset_week"] <= "2017-10-09":
            out["pol_births"] += " " + t["pol_births_cbts"].format(week=d(cb["onset_week"]))
        out["pol_birth_rows"] = [{"term": r[f"label_{lang}"], "posts": n(r["pol_posts"]), "before": n(r["rate_before"], 1),
                                  "after": n(r["rate_after"], 1), "onset": onset(r["onset_week"]),
                                  "first_q": d(r["first_q"]) if r["first_q"] else "—",
                                  "lag": n(r["lag_days"]) if r.get("lag_days") is not None else "—",
                                  "status": t["pol_status_" + r["status"]]} for r in b if r["onset_week"]]
        rs = pol["response"]
        out["pol_response"] = []
        for k in ("on_pol", "exile"):
            if k in rs:
                v = rs[k]
                period = t["pol_period_" + k].format(last=d(rs["last_pol_drop"]) if rs.get("last_pol_drop") else "")
                out["pol_response"].append({"id": f"pol-resp-{k}", "spec": charts.response_curve(v, lang), "period": period,
                                            "text": t["pol_response_text"].format(period=period, ne=n(v["n_events"]),
                                                                                  ex=n(v["excess_6h"], 2), pv=n(v["p_6h"], 3))
                                            # Un pic a 24 h n'est que le cycle quotidien : on ne le commente pas.
                                            + (" " + t["pol_response_peak"].format(peak=n(v["peak_h"])) if v["peak_h"] <= 12 else "")})
        tx = pol["toxicity"]
        o, pr = tx["overall"]["TOXICITY"], tx["paired"].get("q", {}).get("TOXICITY")
        text = t["pol_tox_text"].format(q=n(o["q"]["mean"], 3), all=n(o["all"]["mean"], 3), qh=p(o["q"]["high"], 1),
                                        ah=p(o["all"]["high"], 1))
        if pr:
            simpson = (pr["median_diff"] > 0) != (o["q"]["mean"] > o["all"]["mean"])
            text += " " + t["pol_tox_paired_simpson" if simpson else "pol_tox_paired"].format(
                share=p(pr["share_days_q_higher"], 0), diff=n(pr["median_diff"], 3), days=n(pr["days"]),
                pv=pval(pr["p_wilcoxon"]))
        out["pol_tox"] = text
        g = tox_groups(pol)
        out["pol_tox_groups"] = ""
        out["pol_tox_group_rows"] = []
        if g:
            sign = lambda x: ("+" if x > 0 else "") + n(x, 3)
            out["pol_tox_groups"] = t["pol_tox_groups_text"].format(
                tn=n(g["q_threads"]["n"]), tm=n(g["q_threads"]["mean"], 3), all=n(g["all"]["mean"], 3),
                tlow=p(1 - g["q_threads"]["days_higher"], 0), tdays=n(g["q_threads"]["days"]),
                tbirth=n(g["q_threads"]["birth"], 3), tafter=n(g["q_threads"]["after"], 3), aafter=n(g["all"]["after"], 3),
                pn=n(g["promoter"]["n"]), aj=p(g["alex_jones"], 0), pshare=p(g["promoter"]["days_higher"], 0),
                pdays=n(g["promoter"]["days"]), pdiff=sign(g["promoter"]["diff"]), ppv=pval(g["promoter"]["p"]),
                pobs=p(g["promoter"]["obscene_days"], 0), qn=n(g["q_posts"]["n"]), qdiff=sign(g["q_posts"]["diff"]),
                qshare=p(g["q_posts"]["days_higher"], 0))
            out["pol_tox_group_rows"] = [
                {"group": t["pol_group_" + k], "n": n(v["n"]), "mean": n(v["mean"], 3), "high": p(v["high"], 1),
                 "diff": sign(v["diff"]) if v.get("days") else "—",
                 "share": f"{p(v['days_higher'], 0)} ({n(v['days'])})" if v.get("days") else "—"}
                for k, v in g.items() if k in TOX_GROUP_ORDER]
        pq = tx["paired"].get("q", {})
        out["pol_tox_rows"] = [{"attr": t["tox_" + a.lower()], "q": n(v["q"]["mean"], 3), "all": n(v["all"]["mean"], 3),
                                "diff": n(pq[a]["median_diff"], 3) if a in pq else "—",
                                "share": p(pq[a]["share_days_q_higher"], 0) if a in pq else "—"}
                               for a, v in tx["overall"].items() if "q" in v and "all" in v]
        fl = load_yaml("scene", "families") or {}
        fam = pol["families"]
        corpora = ("drops", "q_threads", "pol_before", "pol_after")
        rows = {}
        for cpus in corpora:
            for r in fam[cpus]["rows"]:
                rows.setdefault(r["family"], {})[cpus] = r["share"]
        label = lambda f: fl.get(f, {}).get(lang) or t["pol_family_" + f]
        out["pol_family_rows"] = sorted(({"family": label(f), **{k: p(v.get(k, 0), 1) for k in corpora},
                                          "_q": v.get("q_threads", 0)} for f, v in rows.items()), key=lambda r: -r["_q"])
        out["pol_family_n"] = {k: n(fam[k]["n"]) for k in corpora}
        hate = rows.get("hate", {})
        cl = rows.get("classic", {})
        out["pol_families"] = t["pol_families_text"].format(drops=p(hate.get("drops", 0), 1), qt=p(hate.get("q_threads", 0), 1),
                                                            before=p(hate.get("pol_before", 0), 1), after=p(hate.get("pol_after", 0), 1),
                                                            cl_drops=p(cl.get("drops", 0), 1), cl_pol=p(cl.get("pol_after", 0), 1))
        out["pol_keyness"] = t["pol_keyness_text"].format(words=", ".join(f"« {x['token']} »" if lang == "fr" else f"“{x['token']}”"
                                                                          for x in pol["keyness"]["top"][:30]))
        co = pol["countries"]
        us = lambda k: next((x["share"] for x in co[k]["top"] if x["country"] == "US"), 0)
        out["pol_countries"] = t["pol_countries_text"].format(q=p(us("q_threads"), 0), pol=p(us("pol_after"), 0))
        return out

    def _scene_context(self, lang, c, sc):
        t, n, p, d = c["t"], c["n"], c["p"], c["date"]
        cov = sc["coverage"]
        done = sum(v["sampled_days"] for v in cov.values())
        total = sum(v["active_days"] for v in cov.values())
        out = {"scene_cov": t["scene_cov"].format(done=n(done), total=n(total), share=p(done / total if total else 0, 0)),
               "scene_provisional": total and done / total < 0.95, "charts": {}}
        sy = sc["syncretism"]
        verdicts = {}
        for th in sy["themes"]:
            verdicts[th["verdict"]] = verdicts.get(th["verdict"], 0) + 1
        out["sync"] = t["sync_text"].format(n=n(len(sy["themes"])), absent=n(verdicts.get("absent_q", 0)),
                                            rare=n(verdicts.get("rare_q", 0)))
        rows = []
        for th in sy["themes"]:
            for name, m in th["measures"].items():
                kind, _, what = name.partition(":")
                rows.append({"theme": th[f"label_{lang}"], "q": n(th["q_drops"]), "measure": f"{t['src_' + kind]} : {what.replace('_', ' ')}",
                             "lag": n(m["peak_lag_weeks"]), "r": n(m["peak_r"], 2), "p": n(m.get("p_fdr", m["p"]), 3),
                             "verdict": t["verdict_" + m.get("verdict", "independant")], "sig": m.get("verdict") in ("q_mene", "q_suit", "synchrone")})
        out["sync_rows"] = sorted(rows, key=lambda r: (not r["sig"], r["theme"]))
        ab = [x for x in sy["absorption"] if x["drops"]]
        best = sorted(sorted(ab, key=lambda x: -x["themes"])[:2], key=lambda x: x["quarter"])
        qlab = lambda q: t["quarter_fmt"].format(q=t["quarter_ord"][int(q[-1]) - 1], y=q[:4])
        out["absorption"] = t["absorption_text"].format(q1=qlab(best[0]["quarter"]), n1=n(best[0]["themes"]),
                                                        q2=qlab(best[1]["quarter"]), n2=n(best[1]["themes"]))
        out["charts"]["absorption"] = charts.absorption(sc, lang)
        te = sc["te"]
        sig = [e for e in te["edges"] if e["significant"]]
        out["te"] = t["te_text"].format(nodes=n(len(te["nodes"])), edges=n(len(te["edges"])), sig=n(len(sig)))
        out["te_rows"] = [{"src": e["source"], "dst": e["target"], "te": n(e["te_bits"], 3), "lag": n(e["lag_days"]),
                           "p": n(e["p_fdr"], 3)} for e in sorted(te["edges"], key=lambda e: e["p_fdr"])[:10]]
        resp = sc.get("response") or {}
        out["response"] = [{"sub": f"r/{k}", "id": f"resp-{k.lower()}", "spec": charts.response(sc, k, lang),
                            "text": t["response_text"].format(sub=f"r/{k}", ne=n(v["n_events"]), ex=n(v["excess_6h"], 2),
                                                              pv=n(v["p_6h"], 3), peak=n(v["peak_h"]))}
                           for k, v in resp.items()]
        out["peaks_rows"] = [{"series": x["series"], "day": d(x["day"]), "ratio": n(x["ratio_to_median"], 1),
                              "pre": p(x["precursor"], 0), "beta": n(x["decay_exponent"], 2) if x["decay_exponent"] is not None else "—",
                              "cls": t["class_" + x["class"]], "q7": n(x["q_drops_7d_before"]),
                              "event": "; ".join(e[f"label_{lang}"] for e in x["events"]) or "—"} for x in sc["peaks"]]
        out["diff_rows"] = [{"term": x[f"label_{lang}"], "q": n(x["q_drops"]), "first_q": d(x["first_q"]),
                             "first_r": d(x["first_reddit_sample"]) if x.get("first_reddit_sample") else "—",
                             "lag": n(x["lag_days"]) if x.get("lag_days") is not None else "—",
                             "qp": n(x["bass"]["q_over_p"], 1) if x.get("bass") else "—",
                             "peak": n(x["bass"]["peak_months"], 0) if x.get("bass") else "—"} for x in sc["diffusion"]]
        if sc.get("trends"):
            out["charts"]["trends"] = charts.trends_waves(sc, lang)
            out["trends_rows"] = [{"q": r["query"], "peak": r["peak_month"], "rel": n(r["peak_rel"], 2) if r["level_measured"] else "—"}
                                  for r in sc["trends"]]
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
                        "source": e["source"], "source_label": label, "source_title": title,
                        "source_archive": self.src(e["source"])["archive"] if e["source"] else None})
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
            for m in re.finditer(r"\[(@[^\]]+)\]|\[\[([a-z]+)\]\]|\{fig:([a-z0-9-]+)\}|\{val:([a-z0-9_]+)\}", par):
                out.append(str(escape(par[pos:m.start()])))
                if m.group(4):
                    vals = self.values(lang)
                    if m.group(4) not in vals:
                        raise KeyError(f"valeur inconnue dans un texte : {m.group(4)}")
                    out.append(str(escape(vals[m.group(4)])))
                elif m.group(3):
                    out.append(str(self.fig(lang, m.group(3))))
                elif m.group(1):
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

    # -- chiffres cles : chacun a une ancre stable et une citation propre
    def figures(self, lang):
        if lang in self._figures:
            return self._figures[lang]
        t, r = T[lang], self.r
        c = self.base(lang)
        n, p, d = c["n"], c["p"], c["date"]
        F = []
        def add(fid, page, key, **kw):
            F.append({"id": fid, "page": page, "text": t[f"fig_{key}"].format(**kw)})
        desc = r["descriptive"]
        add("drops", "activity", "drops", n=n(desc["n"]), first=d(desc["first"]), last=d(desc["last"]))
        add("jours-actifs", "activity", "active", n=n(desc["active_days"]), span=n(desc["span_days"]))
        add("record", "activity", "record", n=n(desc["max_day"]["n"]), date=d(desc["max_day"]["date"]))
        g = desc["gaps"][0]
        add("silence", "activity", "silence", days=n(g["days"]), from_=d(g["from"]), to=d(g["to"]))
        add("questions", "discourse", "questions", q=n(desc["questions_per_drop"], 2), share=p(desc["share_questions"], 0))
        tr = r["trump"]
        t5 = next(x for x in tr["tests"] if x["window_s"] == 300 and x["direction"] == "tweet_after_drop" and x["null"] == "local")
        add("deltas", "trump", "deltas" if t5["p_value"] >= 0.05 else "deltas_sig", obs=p(t5["observed"]), exp=p(t5["expected"]), pv=n(t5["p_value"], 3))
        add("tweets-cites", "trump", "quotes", n=n(tr["quotes"]["n_drops"]), lag=_duration(lang, tr["quotes"]["median_lag_min"]))
        if r["discourse"] and r["discourse"].get("stylometry"):
            split = pd.Timestamp(r["discourse"]["stylometry"]["split"]["date"])
            on8 = any(pl["site"] == "8ch" and abs((pd.Timestamp(pl["first"]).tz_convert(None).normalize() - split).days) <= 3
                      for pl in desc["platforms"])
            add("stylometrie", "discourse", "stylo" if on8 else "stylo_plain", date=d(split.date().isoformat()))
        if r["actors"] and r["actors"]["actors"]:
            top = r["actors"]["actors"][:3]
            add("acteurs", "actors", "actors", top=", ".join(f"{a['name']} ({n(a['n'])})" for a in top),
                share=p(r["actors"]["share_with_actor"], 0))
        if r["news"]:
            ranked = sorted([a for a in r["news"]["actors"] if a.get("overrep") and a["q"] >= 30], key=lambda a: -a["overrep"])
            add("surrepresentation", "news", "overrep",
                top=", ".join(f"{a['name']} (×{n(a['overrep'], 1)})" for a in ranked[:3]))
            add("pays", "news", "countries", rho=n(r["news"]["country_rho"] or 0, 2))
        if r["interest"] and r["interest"]["events"]:
            e = r["interest"]["events"][0]
            add("curiosite", "interest", "interest", label=e[f"label_{lang}"], ratio=n(e["ratio"], 1))
        pr = r["predictions"]
        if pr and pr["n_predictions"]:
            spec = dict(pr["by_specificity"])
            add("predictions", "predictions", "preds", share=p(pr["share_pred_drops"], 0), k=n(pr["n_pred_drops"]),
                m=n(pr["n_predictions"]), spec=n(spec.get("specific", 0)))
            h = pr.get("horizon") or {}
            if h.get("n"):
                add("horizon", "stats", "horizon", med=n(h["median_days"]), s7=p(h["share_7d"], 0), n=n(h["n"]))
        ve = r["verification"]
        if ve and ve.get("items"):
            o, nt = ve["overall"], ve["nontrivial"]
            ci = lambda x: f"{p(x[0], 0)}–{p(x[1], 0)}"
            add("realisation", "predictions", "fulfil", rate=p(o["rate"], 0), ci=ci(o["rate_ci"]), c=n(o["checkable"]),
                f=n(o["fulfilled"]))
            add("realisation-hors-triviales", "predictions", "fulfil_nt", rate=p(nt["rate"], 0), ci=ci(nt["rate_ci"]),
                c=n(nt["checkable"]))
            legal = [ve["by_type"][k] for k in ("arrest", "indictment") if k in ve["by_type"]]
            add("arrestations", "predictions", "legal", ok=n(sum(x["fulfilled"] for x in legal)),
                c=n(sum(x["checkable"] for x in legal)))
        ev = r["llm_eval"]
        if ev:
            m = next(x for x in ev["models"] if x["model"] == ev["recommended"])
            add("modele", "predictions", "model", model=m["model"], f1=n(m["f1"], 2), cost=n(m["corpus_cost_batch_usd"], 2))
        st = r["stats"]
        if st:
            rh = st["rhythm"]
            add("rafales", "stats", "burst", b=n(rh["burstiness"], 2), w5=p(rh["share_within_5min"], 0),
                w1h=p(rh["share_within_1h"], 0))
            add("sessions", "stats", "sessions", ns=n(rh["n_sessions"]), multi=p(rh["share_drops_in_multi"], 0))
            add("regimes", "stats", "regimes", k=n(len(st["changepoints"]["segments"])))
            pr_ = st["domains"]["top_press"]
            add("medias", "stats", "press", nl=n(st["domains"]["n_links"]), ns=n(st["domains"]["n_sites"]),
                first=pr_[0]["site"], fn=n(pr_[0]["drops"]))
            add("autocitation", "stats", "selfref", share=p(st["references"]["share_self"], 0),
                anon=p(st["references"]["share_anon"], 0))
            add("religion", "stats", "religion", share=p(st["religion"]["share_faith"], 1), nv=n(st["religion"]["n_verse"]))
            add("lisibilite", "stats", "flesch", f=n(st["lexicon"]["flesch_all"], 0), wps=n(st["lexicon"]["words_per_sentence_all"], 1))
        ho = r.get("horoscope")
        if ho and ho.get("kinds", {}).get("future"):
            fk, pk = ho["kinds"]["future"], ho["kinds"].get("past", {})
            add("horoscope", "predictions", "horo", n=n(ho["n_sample"]),
                past=p(pk.get("share_true_decided") or 0, 0), future=p(fk["share_true_decided"] or 0, 0),
                barnum=p(fk["share_random_ge5"], 0))
        pp = r.get("prophecies")
        if pp:
            rc = pp["recycled"]
            add("propheties-recyclees", "predictions", "recy", g=n(rc["n_groups"]), k=n(rc["n_in_groups"]),
                ga=n(rc["n_groups_after_failure"]))
            if pp["fpp"].get("n"):
                add("autocitations-delai", "predictions", "fpp", n=n(pp["fpp"]["n"]), same=p(pp["fpp"]["share_same_day"], 0))
        year = time.strftime("%Y")
        for f in F:
            f["url"] = f"{SITE_URL}{lang}/figures.html#{f['id']}"
            quoted = f["text"].replace('"', "'") if lang == "en" else f["text"]
            f["citation"] = t["fig_citation"].format(year=year, text=quoted, version=VERSION, url=f["url"])
        self._figures[lang] = F
        return F

    def values(self, lang):
        """Valeurs isolees citees dans les textes ({val:cle}), recalculees a chaque rendu."""
        c = self.base(lang)
        n = c["n"]
        r = self.r
        tr = r["trump"]
        t5 = next(x for x in tr["tests"] if x["window_s"] == 300 and x["direction"] == "tweet_after_drop" and x["null"] == "local")
        v = {"tweets_per_day": n(tr["tweets_per_day"]), "p_deltas": n(t5["p_value"], 3), "n_trump_tests": n(len(tr["tests"])),
             "n_perm": n(tr["n_perm"])}
        if r["news"]:
            ranked = sorted([a for a in r["news"]["actors"] if a.get("overrep") and a["q"] >= 30], key=lambda a: -a["overrep"])
            if ranked:
                v["top_overrep"] = "×" + n(ranked[0]["overrep"], 1)
                v["top_overrep_raw"] = n(ranked[0]["overrep"], 1)
        ho = r.get("horoscope") or {}
        rb = ho.get("robustness") or {}
        if rb.get("future", {}).get("n"):
            f_ = rb["future"]
            v["horo_robust_sentence"] = T[lang]["horo_robust"].format(
                model=rb["model"], n=n(rb["n_drops"]), nf=n(f_["n"]), none_c=n(f_["check"]["none"]),
                none_m=n(f_["main"]["none"]), dec_c=n(f_["check"]["true"] + f_["check"]["random"]),
                true_c=n(f_["check"]["true"]), kappa=n(f_["kappa"] or 0, 2), agree=fmt.pct(lang, f_["agreement"] or 0, 0))
        else:
            v["horo_robust_sentence"] = ""
        if r["verification"] and r["verification"].get("overall"):
            v["n_unverifiable"] = n(r["verification"]["overall"]["unverifiable"])
        return v

    def paper_values(self):
        """Valeurs du document de travail (francais) : celles des textes, plus les modeles et la scene.
        Les phrases sur la scene sont construites ici, car leur contenu depend de l'avancement des collectes."""
        v = dict(self.values("fr"))
        mk, ph, sc = self.r["markov"], self.r["physics"], self.r["scene"]
        n, p, d = (lambda x, k=0: fmt.num("fr", x, k)), (lambda x, k=0: fmt.pct("fr", x, k)), (lambda x: fmt.date("fr", x))
        hh = lambda x: f"{int(x) % 24:02d} h {int(round((x % 1) * 60)) % 60:02d}"
        if mk:
            h = mk["hmm"]
            top = h["states"][-1]
            near = [x["nearest_hmm_switch_days"] for x in h["changepoint_agreement"] if x["nearest_hmm_switch_days"] is not None]
            ch, sd = mk["topic_chain"], sorted(mk["style_drift"]["steps"], key=lambda x: -x["drift"])
            per = lambda x: x.replace("Q ", "").replace("-S", " S")
            v.update(hmm_k=n(h["K"]), hmm_rate=n(top["rate_per_day"], 1), hmm_mid=n(h["states"][1]["rate_per_day"], 2),
                     hmm_days=p(top["share_days"]), hmm_drops=p(top["share_drops"]), hmm_dwell=n(top["mean_dwell_days"], 1),
                     hmm_switches=n(h["n_switches"]), hmm_agree=n(sum(x <= 7 for x in near)), hmm_ncp=n(len(h["changepoint_agreement"])),
                     chain_k=n(ch["K"]), chain_pairs=n(ch["n_pairs"]), chain_diag=p(ch["diag_share"], 1),
                     chain_null=p(ch["null_session"]["diag_mean"], 1), chain_p=n(ch["null_session"]["p_diag"], 3),
                     chain_h0=n(ch["entropy_iid_bits"], 2), chain_h1=n(ch["entropy_rate_bits"], 2),
                     drift_a=f"{per(sd[0]['from'])} → {per(sd[0]['to'])}", drift_da=n(sd[0]["drift"], 2),
                     drift_b=f"{per(sd[1]['from'])} → {per(sd[1]['to'])}", drift_db=n(sd[1]["drift"], 2))
        if ph:
            hm = ph["hawkes"]["models"]
            b, ht = hm[ph["hawkes"]["best"]], ph["hawkes_trump"]
            dfa = {(x["series"], x["resolution"]): x for x in ph["dfa"]}
            qs, pz = ph["avalanches"]["Q"]["size"], ph["phases"]
            sp, pl = pz["phase_split"], pz.get("phase_locking") or {}
            v.update(hk_n=p(b["branching_ratio"]), hk_n_exp=p(hm["regimes/exp"]["branching_ratio"]),
                     hk_med=n(b["kernel"]["median_delay_hours"] * 60), hk_p=n(b["kernel"]["omori_p"], 1),
                     hk_ks=n(b["gof"]["ks_D"], 3), hk_ks0=n(hm["regimes/poisson"]["gof"]["ks_D"], 2), hk_nreg=n(b["n_regimes"]),
                     hk_daic=n(hm["regimes/poisson"]["aic"] - b["aic"]),
                     ht_share=p(ht["share_drops_from_cross"], 1), ht_p=n(ht["p_shift"], 3), ht_nshift=n(len(ht["null_shifts"])),
                     dfa_q=n(dfa[("Q", "day")]["H"], 2), dfa_t=n(dfa[("Trump", "day")]["H"], 2),
                     dfa_sh=n(dfa[("Q", "day")]["H_shuffled"], 2),
                     av_alpha=n(qs["alpha"], 1), av_xmin=n(qs["xmin"]), av_tail=n(qs["n_tail"]), av_n=n(qs["n"]),
                     av_pln=n(qs["vs_lognormal"]["p"], 2), av_pexp=n(qs["vs_exponential"]["p"], 2),
                     ph_q=hh(pz["day"]["Q"]["peak"]), ph_t=hh(pz["day"]["Trump"]["peak"]), ph_date=d(sp["date"]),
                     ph_before=hh(sp["before_peak"]), ph_after=hh(sp["after_peak"]), ph_p=n(sp["p"], 3),
                     ph_plv=n(pl.get("plv", 0), 2), ph_lag=n(pl.get("mean_lag_hours", 0)))
        v.update(self._paper_scene(sc, n, p, d) if sc else {})
        return v

    def _paper_scene(self, sc, n, p, d):
        """Phrases de la section 4.9, selon ce qui est deja mesure."""
        v = {}
        cov = sc["coverage"]
        done, total = sum(x["sampled_days"] for x in cov.values()), sum(x["active_days"] for x in cov.values())
        n_tr = len(sc.get("trends") or [])
        if total and done / total < 0.95 or not n_tr:
            v["scene_status"] = (f"Les mesures de cette section sont provisoires : à la date de ce calcul, {n(done)} des "
                                 f"{n(total)} jours actifs des six subreddits sont échantillonnés ({p(done / total if total else 0)}), "
                                 + (f"{n(n_tr)} requêtes Google Trends sont collectées" if n_tr else
                                    "Google Trends limite encore la collecte")
                                 + " ; elles seront recalculées à la fin des collectes.")
        sy = sc["syncretism"]
        cnt = {}
        for th in sy["themes"]:
            cnt[th["verdict"]] = cnt.get(th["verdict"], 0) + 1
        ms = [(th, k, m) for th in sy["themes"] for k, m in th["measures"].items()]
        sig = [(th, k, m) for th, k, m in ms if m.get("verdict") in ("q_mene", "q_suit", "synchrone")]
        lead = {"q_mene": "Q précède", "q_suit": "Q suit", "synchrone": "Q et la scène évoluent ensemble pour"}
        src = {"reddit": "r/conspiracy", "wiki": "Wikipédia", "trends": "Google Trends"}
        s = (f"Sur {n(len(sy['themes']))} thèmes de la scène suivis, {n(cnt.get('absent_q', 0))} n'apparaissent dans aucun drop "
             f"et {n(cnt.get('rare_q', 0))} dans moins de dix : Q puise dans un répertoire restreint. ")
        if not ms:
            s += "Aucun thème n'a encore assez de mesures de la scène pour être comparé semaine par semaine."
        elif not sig:
            s += (f"Pour les {n(len(ms))} comparaisons hebdomadaires possibles, aucune corrélation ne résiste à la correction "
                  "pour comparaisons multiples : ni meneur ni suiveur.")
        else:
            parts = [f"{lead[m['verdict']]} {th['label_fr']} ({src[k.split(':')[0]]}, "
                     f"{n(abs(m['peak_lag_weeks']))} semaine{'s' if abs(m['peak_lag_weeks']) > 1 else ''}, r = {n(m['peak_r'], 2)}, "
                     f"p ajustée = {n(m['p_fdr'], 3)})" for th, k, m in sig]
            s += (f"Sur {n(len(ms))} comparaisons hebdomadaires, {n(len(sig))} résiste{'nt' if len(sig) > 1 else ''} à la correction "
                  "pour comparaisons multiples : " + " ; ".join(parts) + ".")
        v["scene_sync"] = s
        ab = sorted(sorted([x for x in sy["absorption"] if x["drops"]], key=lambda x: -x["themes"])[:2], key=lambda x: x["quarter"])
        if len(ab) == 2:
            ql = lambda q: f"{['premier', 'deuxième', 'troisième', 'quatrième'][int(q[-1]) - 1]} trimestre {q[:4]}"
            v["scene_absorption"] = (f"Le nombre de thèmes distincts abordés par trimestre culmine au {ql(ab[0]['quarter'])} "
                                     f"({n(ab[0]['themes'])}) et au {ql(ab[1]['quarter'])} ({n(ab[1]['themes'])}).")
        te = sc["te"]
        ns = sum(e["significant"] for e in te["edges"])
        v["scene_te"] = (f"Entre {n(len(te['nodes']))} séries quotidiennes ({n(len(te['edges']))} liens orientés testés), "
                         + (f"{n(ns)} lien{'s' if ns > 1 else ''} d'information reste{'nt' if ns > 1 else ''} significatif{'s' if ns > 1 else ''}"
                            if ns else "aucun lien d'information ne reste significatif")
                         + " une fois retirés les cycles hebdomadaires et corrigées les comparaisons multiples.")
        resp = sc.get("response") or {}
        if resp:
            v["scene_response"] = ("À l'échelle horaire, les forums de Q réagissent à ses drops : dans les six heures qui "
                                   "suivent une session, leur activité rapportée à la veille dépasse celle d'instants tirés au "
                                   "hasard de " + " et de ".join(
                f"{p(x['excess_6h'], 1)} sur r/{k} (p = {n(x['p_6h'], 3)}, {n(x['n_events'])} sessions)"
                for k, x in resp.items()) + ".")
        pk = sc["peaks"]
        cls = {}
        for x in pk:
            cls[x["class"]] = cls.get(x["class"], 0) + 1
        exo = [x for x in pk if x["class"] == "exogene" and x["events"]]
        v["scene_peaks"] = (f"Parmi les plus grands pics d'attention de chaque série de la scène ({n(len(pk))} en tout), "
                            f"{n(cls.get('exogene', 0))} ont la forme "
                            f"d'un choc extérieur et {n(cls.get('endogene', 0))} celle d'une cascade interne"
                            + (" ; les chocs extérieurs datés coïncident avec des événements de la chronologie ("
                               + " ; ".join(f"« {e} »" for e in sorted({e['label_fr'] for x in exo for e in x['events']})) + ")"
                               if exo else "") + ".")
        cov = sc.get("coverage", {})
        sampled, active = sum(x["sampled_days"] for x in cov.values()), sum(x["active_days"] for x in cov.values())
        try:
            msgs = self.conn.execute("SELECT count(*) FROM reddit_sample").fetchone()[0]
        except Exception:   # base sans echantillon Reddit
            msgs = 0
        if active:
            v["reddit_sample"] = (f"{n(msgs)} messages, {n(sampled)} jours sur {n(active)} jours actifs"
                                  if sampled < active else f"{n(msgs)} messages, tous les {n(active)} jours actifs")
        dif = [x for x in sc["diffusion"] if x["term"].startswith("gl:") and x.get("lag_days") is not None and x["q_drops"] >= 8]
        if dif:
            # Deux cas : les expressions qui circulaient avant Q (souvent de l'anglais ordinaire) et
            # les formules qui n'apparaissent sur Reddit qu'apres leur premier drop.
            neg = sorted((x for x in dif if x["lag_days"] < 0), key=lambda x: x["lag_days"])
            pos = [x for x in dif if x["lag_days"] >= 0]
            out = []
            if neg:
                ex = ", ".join(f"« {x['label_fr']} »" for x in neg[:3])
                out.append(f"Le tableau 3 sépare deux cas. Sur les {n(len(dif))} formules de Q retrouvées sur Reddit, "
                           f"{n(len(neg))} y circulaient déjà avant lui, souvent comme expressions ordinaires de l'anglais ({ex}).")
            if pos:
                lags = [x["lag_days"] for x in pos]
                out.append(f"{'Les ' + n(len(pos)) + ' autres' if neg else 'Les ' + n(len(pos)) + ' formules retrouvées'} "
                           f"n'y apparaissent qu'après le premier drop qui les emploie, de {n(min(lags))} à {n(max(lags))} jours "
                           f"plus tard (médiane {n(float(pd.Series(lags).median()))} jours).")
            v["scene_diffusion"] = " ".join(out)
        pol = self.r["pol"]
        if not pol:
            v["scene_pol"] = ("Le balayage de /pol/ [@papasavva2020raiders], milieu d'origine de Q, est en cours ; ses résultats "
                              "(diffusion des formules, toxicité, sous-corpus des fils Q) compléteront cette section.")
            v["scene_pol2"] = ""
        else:
            v.update(self._paper_pol(pol, n, p, d))
        return v

    def _paper_pol(self, pol, n, p, d):
        """Phrases de la section 4.10 (/pol/), d'apres analyze_pol."""
        ov, ni, b = pol["overview"], pol["niche"], pol["births"]
        peak = max(ni, key=lambda x: x["share"])
        later = pd.Series([x["share"] for x in ni if x["month"] >= "2018-01"]).median()
        months = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre",
                  "novembre", "décembre"]
        cnt = {}
        for r in b:
            cnt[r["status"]] = cnt.get(r["status"], 0) + 1
        qth = sum(v for k, v in ov["q_corpus"].items() if k.startswith("thread:"))
        s = (f"Le forum /pol/ de 4chan, où Q est apparu, a été lu en entier [@papasavva2020raiders] : {n(ov['posts'])} posts "
             f"dans {n(ov['threads'])} fils, dont {n(ov['q_threads'])} fils Q ({n(qth)} posts). En "
             f"{months[int(peak['month'][5:]) - 1]} {peak['month'][:4]}, {p(peak['share'], 1)} des posts de /pol/ sont écrits dans "
             f"ces fils ; dès 2018, la part retombe autour de {p(later, 2)} par mois. ")
        s += (f"Sur {n(len(b))} formules liées à Q assez fréquentes pour être datées, {n(cnt.get('before_q', 0))} étaient déjà en "
              f"hausse avant le 28 octobre 2017, {n(cnt.get('about_q', 0))} naissent avec Q sans qu'il les emploie, "
              f"{n(cnt.get('pol_first', 0))} sont employées par /pol/ avant Q et {n(cnt.get('q_first', 0))} d'abord par Q (tableau 4).")
        cb = next((r for r in b if r["term"] == "cbts" and r["status"] == "before_q"), None)
        if cb:
            s += (f" « CBTS » décolle dès la semaine du {d(cb['onset_week'])}, celle du « calme avant la tempête » lancé par "
                  "Donald Trump le 5 octobre 2017 : Q s'installe dans des fils déjà ouverts.")
        rs = pol["response"]
        resp = [(k, rs[k]) for k in ("on_pol", "exile") if k in rs]
        if resp:
            last = d(rs["last_pol_drop"]) if rs.get("last_pol_drop") else ""
            lab = {"on_pol": f"pendant sa période /pol/, jusqu'à son dernier drop sur /pol/ le {last}",
                   "exile": "après son départ pour 8chan, en 2018-2019"}
            s += (" Les mentions de Q sur /pol/ augmentent dans les six heures qui suivent ses sessions, "
                  + " et ".join(f"{lab[k]} (+{n(x['excess_6h'], 2)} par rapport au hasard, p = {n(x['p_6h'], 3)}, "
                                f"{n(x['n_events'])} sessions)" for k, x in resp) + ".")
        v = {"scene_pol": s}
        tx = pol["toxicity"]
        o, pr = tx["overall"]["TOXICITY"], tx["paired"].get("q", {}).get("TOXICITY")
        s2 = (f"Les posts liés à Q sont en moyenne moins toxiques que /pol/ (score Perspective {n(o['q']['mean'], 3)} contre "
              f"{n(o['all']['mean'], 3)})" if o["q"]["mean"] < o["all"]["mean"] else
              f"Les posts liés à Q sont en moyenne plus toxiques que /pol/ (score Perspective {n(o['q']['mean'], 3)} contre "
              f"{n(o['all']['mean'], 3)})")
        g = tox_groups(pol)
        if pr and (pr["median_diff"] > 0) != (o["q"]["mean"] > o["all"]["mean"]):
            s2 += f", mais jour par jour ils le sont davantage {p(pr['share_days_q_higher'], 0)} des jours."
        else:
            s2 += "."
        if g:
            sign = lambda x: ("+" if x > 0 else "") + n(x, 3)
            pv = lambda x: "p < 0,001" if x < 0.001 else f"p = {n(x, 3)}"
            s2 += (f" La ventilation par groupe (tableau 5) lève ce paradoxe apparent. Les fils Q sont plus calmes que /pol/ "
                   f"({n(g['q_threads']['mean'], 3)}) et le sont {p(1 - g['q_threads']['days_higher'], 0)} des jours comparés : "
                   f"surtout pendant la naissance de Q, consacrée au déchiffrement des drops ({n(g['q_threads']['birth'], 3)} "
                   f"de fin octobre à décembre 2017), mais encore en 2018-2019 ({n(g['q_threads']['after'], 3)} contre "
                   f"{n(g['all']['after'], 3)}). Les posts isolés qui citent un promoteur, pour {p(g['alex_jones'], 0)} "
                   f"d'entre eux Alex Jones ou InfoWars, sont au contraire plus toxiques que /pol/ "
                   f"{p(g['promoter']['days_higher'], 0)} des jours (écart médian {sign(g['promoter']['diff'])}, "
                   f"{pv(g['promoter']['p'])}), et les posts isolés au vocabulaire de Q à peine "
                   f"(écart médian {sign(g['q_posts']['diff'])}). La moyenne d'ensemble est tirée vers le bas par le poids "
                   "des fils Q, surtout en novembre 2017 ; les jours ordinaires, par les posts isolés.")
        fam = {c: {r["family"]: r["share"] for r in pol["families"][c]["rows"]} for c in pol["families"]}
        shill = next((x for x in pol.get("added_terms", []) if x["term"] == "shills"), None)
        s2 += (f" Les codes de haine, surtout antisémites, touchent {p(fam['pol_before'].get('hate', 0), 1)} des posts de /pol/ "
               f"avant Q et {p(fam['pol_after'].get('hate', 0), 1)} après, {p(fam['q_threads'].get('hate', 0), 1)} des posts des "
               f"fils Q et {p(fam['drops'].get('hate', 0), 1)} des drops."
               + (f" La culture du forum (argot, mèmes, accusations de « shills ») est en revanche plus présente dans les "
                  f"fils Q que sur /pol/ lui-même ({p(fam['q_threads']['pol_culture'], 1)} de leurs posts, contre "
                  f"{p(fam['pol_before']['pol_culture'], 1)} avant Q et {p(fam['pol_after']['pol_culture'], 1)} après)"
                  + (f", et « shills » y revient {n(shill['q_threads']['per_m'] / shill['pol_after']['per_m'], 1)} fois "
                     "plus souvent." if shill and shill['pol_after']['per_m'] else ".")
                  if 'pol_culture' in fam['q_threads'] else "")
               + " Les mots les plus caractéristiques des fils Q "
               "[@monroe2008fightin] sont " + ", ".join(f"« {x['token']} »" for x in pol["keyness"]["top"][:10])
               + " : le lexique d'un atelier de déchiffrement, de ses cibles et d'un soupçon permanent d'imposture.")
        v["scene_pol2"] = s2
        return v

    def fig(self, lang, fid):
        """Lien vers un chiffre cle, pour les textes (FAQ)."""
        from markupsafe import Markup, escape
        f = next((x for x in self.figures(lang) if x["id"] == fid), None)
        if f is None:
            raise KeyError(f"chiffre inconnu dans un texte : {fid}")
        return Markup(f'<a class="fig-link" href="figures.html#{escape(fid)}">{escape(f["text"])}</a>')

    def page_figures(self, lang, c):
        return {"figs": self.figures(lang)}

    def page_faq(self, lang, c):
        items = load_yaml("faq", "questions")
        return {"items": [{"id": q["id"], "q": q[f"q_{lang}"], "paras": self._prose(q[f"a_{lang}"], lang)} for q in items]}

    # -- veille bibliographique : etat de chaque publication reperee dans notre bibliographie
    def watch_items(self):
        if hasattr(self, "_watch"):
            return self._watch
        from ..sources.biblio_watch import QANON, norm_title, same_title
        import yaml
        import sqlite3
        try:
            rows = [dict(r) for r in self.conn.execute("SELECT * FROM biblio_watch")]
        except sqlite3.OperationalError:  # base anterieure a la veille
            rows = []
        by_doi = {r["doi"].lower(): r for r in self.refs if r.get("doi")}
        by_title = {norm_title(r["title"]): r for r in self.refs}
        path = APP_DIR / "data" / "biblio_watch_review.yaml"
        review = {x["key"].lower(): x for x in (yaml.safe_load(path.read_text()) or {}).get("reviewed") or []} \
            if path.exists() else {}
        out = []
        for r in rows:
            ref = by_doi.get((r["doi"] or "").lower()) or by_title.get(norm_title(r["title"])) \
                or next((x for x in self.refs if same_title(x["title"], r["title"])), None)
            rv = review.get(r["key"].lower()) or (review.get(r["doi"].lower()) if r["doi"] else None)
            if not ref and rv and rv.get("decision") == "included":
                ref = next((x for x in self.refs if x["id"] == rv.get("ref")), None)
            status = "in" if ref else ("rejected" if rv and rv.get("decision") == "rejected" else "new")
            today = time.strftime("%Y-%m-%d")
            # Date future (fin d'annee fictive de certaines notices) : on ne garde que l'annee.
            shown = r["date"] if r["date"] and r["date"] <= today else (str(r["year"]) if r["year"] else None)
            # Notices brutes des API : auteur vide ("; Travis, Justin"), entites deja encodees ("&amp;").
            from html import unescape
            r["authors"] = "; ".join(a for a in (x.strip() for x in (r["authors"] or "").split(";")) if a)
            for k in ("title", "container"):
                r[k] = unescape(unescape(r[k])) if r.get(k) else r.get(k)
            out.append({**r, "status": status, "ref_id": ref["id"] if ref else None, "review": rv,
                        "shown_date": shown, "in_title": bool(QANON.search(r["title"] or ""))})
        out.sort(key=lambda x: (x["shown_date"] or ""), reverse=True)
        self._watch = out
        return out

    def page_watch(self, lang, c):
        t = T[lang]
        items = self.watch_items()
        cnt = {k: sum(x["status"] == k for x in items) for k in ("in", "rejected", "new")}
        from ..sources.biblio_watch import SINCE
        last = max((x["last_seen"] for x in items), default=None)
        return {"items": [{**x, "date_label": c["date"](x["shown_date"]) if x["shown_date"] and len(x["shown_date"]) == 10
                           else (x["shown_date"] or "—"),
                           "status_label": t[f"watch_{x['status']}"],
                           "reason": (x["review"] or {}).get(f"reason_{lang}")} for x in items],
                "n_title": c["n"](sum(x["in_title"] for x in items)),
                "lead": t["watch_lead"].format(n=c["n"](len(items)), since=c["date"](SINCE),
                                               last=c["date"](last) if last else "—",
                                               inn=c["n"](cnt["in"]), new=c["n"](cnt["new"]), rej=c["n"](cnt["rejected"]))}

    def page_corpus(self, lang, c):
        return {"n": c["n"](self.r["descriptive"]["n"])}

    def page_teaching(self, lang, c):
        import yaml
        path = APP_DIR / "data" / "teaching.yaml"
        if not path.exists():
            return {"is_pending": True}
        data = yaml.safe_load(path.read_text())
        pr = lambda txt: self._prose(txt, lang)
        one = lambda txt: pr(txt)[0] if txt and pr(txt) else ""
        sheets = []
        for sh in data["sheets"]:
            sheets.append({"id": sh["id"], "title": sh[f"title_{lang}"], "level": sh[f"level_{lang}"],
                           "duration": sh[f"duration_{lang}"], "goals": [one(x) for x in sh[f"goals_{lang}"]],
                           "materials": pr(sh[f"materials_{lang}"]), "steps": [one(x) for x in sh[f"steps_{lang}"]],
                           "questions": [one(x) for x in sh[f"questions_{lang}"]], "answers": pr(sh[f"answers_{lang}"]),
                           "caution": pr(sh[f"caution_{lang}"])})
        return {"intro": pr(data[f"intro_{lang}"]), "sheets": sheets}

    def export_corpus(self, d):
        """data/corpus.json, lu par l'explorateur (une ligne par drop, champs courts)."""
        from ..analysis.actors import mentions
        from ..analysis.common import load_drops
        drops = load_drops(self.conn)
        actors = load_yaml("actors", "actors")
        M = mentions(drops, actors)
        names = [a["name"] for a in actors]
        allp = (_load(self.state, "predictions_all") or {}).get("predictions", [])
        npred = {}
        for x in allp:
            npred[x["drop_id"]] = npred.get(x["drop_id"], 0) + 1
        verdicts = {}
        for x in (self.r["verification"] or {}).get("items", []):
            verdicts.setdefault(x["drop_id"], []).append(x["verdict"])
        rows = []
        for i, r in drops.iterrows():
            hit = [k for k, v in enumerate(M.loc[i].to_numpy()) if v]
            rows.append([int(r["id"]), r["et"].strftime("%Y-%m-%d %H:%M"), f"{r['site']} {r['board']}", r["text"] or "",
                         hit, npred.get(int(r["id"]), 0), verdicts.get(int(r["id"]), []), int(r["n_images"] or 0)])
        (d / "corpus.json").write_text(json.dumps({"fields": ["id", "date_et", "board", "text", "actors", "n_predictions",
                                                             "verdicts", "n_images"],
                                                  "actors": names, "drops": rows}, ensure_ascii=False, separators=(",", ":")))

    # -- document de travail : Markdown (data/paper/paper-fr.md) -> page HTML et PDF
    def paper(self):
        if hasattr(self, "_paper"):
            return self._paper
        import markdown
        import yaml
        from markupsafe import Markup
        path = APP_DIR / "data" / "paper" / "paper-fr.md"
        if not path.exists():
            self._paper = None
            return None
        raw = path.read_text()
        _, front, body = raw.split("---", 2)
        meta = yaml.safe_load(front)
        cited = []
        def cite_md(m):
            ids = [x.strip().lstrip("@") for x in m.group(1).split(";")]
            for i in ids:
                if i not in cited:
                    cited.append(i)
            return str(self.cite(*ids))
        vals = self.paper_values()
        body = re.sub(r"\{val:([a-z0-9_]+)\}", lambda m: vals.get(m.group(1), ""), body)
        body = re.sub(r"\{(table|figure):([a-z0-9_]+)\}", lambda m: "\n\n" + paper_block(self, m.group(1), m.group(2)) + "\n\n", body)
        body = re.sub(r"\[(@[^\]]+)\]", cite_md, body)
        html = markdown.markdown(body, extensions=["extra", "sane_lists"])
        html = re.sub(r'href="bibliography.html#', 'href="#ref-', html)
        by_id = {r["id"]: r for r in self.refs}
        refs = sorted((by_id[i] for i in cited), key=lambda r: ((r.get("authors") or [r["title"]])[0].lower(), r.get("year") or 0))
        self._paper = {"meta": meta, "html": Markup(html), "refs": [{"id": r["id"], "cit": biblio.citation(r, "fr"), **r} for r in refs]}
        return self._paper

    def page_paper(self, lang, c):
        pp = self.paper()
        if not pp:
            return {"is_pending": True}
        return {"pp": pp}

    def write_paper_pdf(self, env, out):
        pp = self.paper()
        if not pp:
            return
        from weasyprint import HTML
        html = env.get_template("paper_pdf.html").render(pp=pp, t=T["fr"], version=VERSION, site_url=SITE_URL,
                                                          doi=ZENODO_CONCEPT)
        HTML(string=fmt.fr_html(html), base_url=str(out)).write_pdf(out / "data" / "working-paper-fr.pdf")

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

    def links(self):
        """Etat des liens (verification hebdomadaire) : url -> ligne de link_check."""
        if not hasattr(self, "_links"):
            import sqlite3
            try:
                self._links = {r["url"]: dict(r) for r in self.conn.execute("SELECT * FROM link_check")}
            except sqlite3.OperationalError:
                self._links = {}
        return self._links

    def tr(self, key, text, lang):
        """Paraphrase dans la langue de la page : traduction francaise si elle existe."""
        if lang != "fr":
            return text
        return ((self.r.get("translations") or {}).get("fr") or {}).get(key) or text

    def src(self, url):
        """Source citee : adresse et, si le lien est mort, sa copie archivee."""
        st = self.link_state(url) or {}
        return {"url": url, "dead": st.get("state") == "dead", "archive": st.get("archive") if st.get("state") == "dead" else None}

    def link_state(self, url=None, doi=None):
        return self.links().get(f"doi:{doi.lower()}" if doi else url)

    def page_bibliography(self, lang, c):
        t = c["t"]
        entries = []
        L = self.links()
        if L:
            cnt = {k: sum(v["state"] == k for v in L.values()) for k in ("ok", "blocked", "dead", "error")}
            last = max(v["checked_at"] for v in L.values())
            links_note = t["links_note"].format(n=c["n"](len(L)), date=c["date"](time.strftime("%Y-%m-%d", time.gmtime(last))),
                                                ok=c["n"](cnt["ok"]), blocked=c["n"](cnt["blocked"]),
                                                dead=c["n"](cnt["dead"]), error=c["n"](cnt["error"]))
        else:
            links_note = None
        for r in self.refs:
            cit = biblio.citation(r, lang)
            entries.append({**r, "cit": cit, "link": self.link_state(r.get("url"), r.get("doi")), "summary": r.get(f"summary_{lang}"), "type_label": t.get(f"type_{r['type']}", r["type"]),
                            "bibtex": biblio.bibtex(r), "search": " ".join(
                                [r["title"], " ".join(r.get("authors", [])), r.get("container") or "",
                                 " ".join(r.get("topics", [])), str(r.get("year", ""))]).lower()})
        types = [(ty, t.get(f"type_{ty}", ty)) for ty in biblio.TYPE_ORDER if any(r["type"] == ty for r in self.refs)]
        topics = sorted({tp for r in self.refs for tp in r.get("topics", [])})
        return {"entries": entries, "types": types, "topics": topics, "links_note": links_note,
                "lead": t["bib_lead"].format(n=c["n"](len(self.refs)))}

    def page_data(self, lang, c):
        t = T[lang]
        ds = {"@context": "https://schema.org", "@type": "Dataset", "name": t["dataset_name"],
              "description": t["dataset_desc"], "url": f"{SITE_URL}{lang}/data.html", "inLanguage": ["fr", "en"],
              "creator": {"@type": "Person", "name": "Sylvain Geffroy"},
              "license": "https://creativecommons.org/licenses/by/4.0/", "isAccessibleForFree": True,
              "keywords": ["QAnon", "Q drops", "conspiracy theories", "GDELT", "computational social science"],
              "temporalCoverage": "2017-10-28/2022-11-27", "version": VERSION,
              "distribution": [{"@type": "DataDownload", "contentUrl": f"{SITE_URL}data/{f['name']}",
                                "encodingFormat": "text/csv" if f["name"].endswith(".csv") else
                                ("application/json" if f["name"].endswith(".json") else "text/plain")}
                               for f in self.files if "*" not in f["name"]]}
        return {"files": self.files, "jsonld": ds}

    def page_method(self, lang, c):
        return {"src_drops": c["t"]["src_drops"].format(n=c["n"](self.r["descriptive"]["n"]))}

    def page_cite(self, lang, c):
        t = c["t"]
        year = time.strftime("%Y")
        return {"cite_text": t["cite_text"].format(year=year, version=VERSION) + f" https://doi.org/{ZENODO_CONCEPT}",
                "cite_version": t["cite_version"].format(version=VERSION, updated=UPDATED),
                "doi_concept": ZENODO_CONCEPT,
                "doi_versions": sorted(ZENODO_VERSIONS.items(), reverse=True),
                "cite_bibtex": "@misc{geffroy_qdrops,\n  author = {Geffroy, Sylvain},\n"
                               f"  title = {{{t['site_title']}}},\n  year = {{{year}}},\n"
                               f"  version = {{{VERSION}}},\n  doi = {{{ZENODO_CONCEPT}}},\n"
                               f"  url = {{https://s-geffroy.github.io/QAnon/}}\n}}"}

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
        if latex.write(self, d):
            add("working-paper-fr.tex", "Document de travail au format LaTeX (biblatex, avec bibliography.bib).",
                "Working paper in LaTeX (biblatex, with bibliography.bib).")
            add("working-paper-fr-latex.zip", "Document de travail, version LaTeX complète : source, bibliographie, figures en PDF.",
                "Working paper, complete LaTeX version: source, bibliography, PDF figures.")
        gold = APP_DIR / "data" / "gold.jsonl"
        if gold.exists():
            shutil.copy(gold, d / "gold.jsonl")
            add("gold.jsonl", "Jeu d'annotation de référence (prédictions), 150 drops.", "Reference annotation set (predictions), 150 drops.")
        guide = APP_DIR / "data" / "gold_guidelines.md"
        if guide.exists():
            shutil.copy(guide, d / "gold_guidelines.md")
            add("gold_guidelines.md", "Consignes d'annotation du jeu de référence (français).",
                "Annotation guidelines of the reference set (French).")
        self.export_corpus(d)
        add("corpus.json", "Corpus complet pour l'explorateur : texte de chaque drop, date (New York), forum, acteurs, prédictions et verdicts.",
            "Full corpus for the explorer: text of each drop, date (New York), board, actors, predictions and verdicts.")
        rows = []
        for lang in T:
            rows += [{"lang": lang, "id": f["id"], "page": f["page"], "text": f["text"], "url": f["url"]}
                     for f in self.figures(lang)]
        pd.DataFrame(rows).to_csv(d / "figures.csv", index=False)
        add("figures.csv", "Chiffres clés (FR et EN), avec leur adresse citable.", "Key figures (FR and EN), with their citable address.")
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
        # Empreinte de chaque fichier dans son adresse (style.css?v=...) : une nouvelle version n'est
        # jamais masquee par le cache du navigateur (GitHub Pages : max-age=600).
        env.globals["v"] = {p.name: db.sha(p.read_bytes())[:10] for p in (out / "static").iterdir() if p.is_file()}
        (out / ".nojekyll").write_text("")
        self.export(out)
        for lang in T:
            base = self.base(lang)
            (out / lang).mkdir(parents=True)
            for page in PAGES:
                ctx = {**base, "page": page, **getattr(self, f"page_{page}")(lang, base)}
                html = env.get_template(f"{page}.html").render(**ctx)
                if lang == "fr":
                    html = fmt.fr_html(html)
                (out / lang / f"{page}.html").write_text(html)
        (out / "index.html").write_text(env.get_template("root.html").render())
        self.write_paper_pdf(env, out)
        self.write_seo(out)

    # -- referencement : plan du site, robots, flux RSS, vignette de partage
    def write_seo(self, out):
        from xml.sax.saxutils import escape as x
        today = time.strftime("%Y-%m-%d")
        urls = [f"{SITE_URL}{lang}/{p}.html" for lang in T for p in PAGES]
        (out / "sitemap.xml").write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
            'xmlns:xhtml="http://www.w3.org/1999/xhtml">\n' + "".join(
                f"<url><loc>{x(u)}</loc><lastmod>{today}</lastmod>"
                + "".join(f'<xhtml:link rel="alternate" hreflang="{l}" href="{x(u.replace(f"/{u.split("/")[-2]}/", f"/{l}/"))}"/>'
                          for l in T) + "</url>\n" for u in urls) + "</urlset>\n")
        (out / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}sitemap.xml\n")
        import yaml
        log_ = yaml.safe_load((APP_DIR / "data" / "changelog.yaml").read_text())["entries"]
        watch = [w for w in self.watch_items() if w["status"] == "in" or (w["status"] == "new" and w["in_title"])][:40]
        for lang in T:
            t = T[lang]
            items = []
            for e in log_:
                d = dt_rfc(str(e["date"]))
                items.append((str(e["date"]), f"<item><title>{x(t['feed_update'])} — {x(fmt.date(lang, str(e['date'])))}</title>"
                              f"<link>{SITE_URL}{lang}/index.html</link><guid isPermaLink=\"false\">update-{e['date']}-{db.sha(e['fr'])[:8]}</guid>"
                              f"<pubDate>{d}</pubDate><description>{x(fmt.fr_typo(e[lang]) if lang == 'fr' else e[lang])}</description></item>"))
            for w in watch:
                seen = w["first_seen"] or today
                items.append((seen, f"<item><title>{x(t['feed_watch'])} : {x(w['title'])}</title><link>{x(w['url'])}</link>"
                              f"<guid isPermaLink=\"false\">watch-{x(w['key'])}</guid><pubDate>{dt_rfc(seen)}</pubDate>"
                              f"<description>{x(t['watch_' + w['status']])}{(' — ' + x(w['authors'])) if w['authors'] else ''}</description></item>"))
            items.sort(key=lambda z: z[0], reverse=True)
            (out / lang / "feed.xml").write_text(
                '<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom"><channel>'
                f"<title>{x(t['site_title'])}</title><link>{SITE_URL}{lang}/index.html</link>"
                f'<atom:link href="{SITE_URL}{lang}/feed.xml" rel="self" type="application/rss+xml"/>'
                f"<description>{x(t['site_sub'])}</description><language>{lang}</language>"
                + "".join(i for _, i in items[:60]) + "</channel></rss>\n")
        og_image(out / "static" / "og.png")


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

"""Specifications Vega-Lite. Les couleurs sont des jetons "@nom", remplaces au
rendu par les valeurs CSS du theme courant (static/charts.js) : un meme graphe
suit le mode clair et le mode sombre."""
from .i18n import T

BASE = {
    "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
    "width": "container",
    "background": None,
}


def _spec(**kw):
    spec = {**BASE, **kw}
    if "facet" in spec:
        spec.pop("width")  # largeur portee par chaque facette
    return spec


def weekly(desc, lang):
    t = T[lang]
    top = max(w["n"] for w in desc["weekly"]) * 1.12
    events = [{"date": e["date"], "label": e[f"label_{lang}"], "y": top} for e in desc["events"]]
    return _spec(
        height=260,
        layer=[
            {"data": {"values": desc["weekly"]},
             "mark": {"type": "area", "interpolate": "step-after", "color": "@series1", "opacity": 0.85,
                      "line": {"color": "@series1", "strokeWidth": 1}},
             "encoding": {
                 "x": {"field": "week", "type": "temporal", "title": None,
                       "axis": {"format": "%Y", "tickCount": "year"}},
                 "y": {"field": "n", "type": "quantitative", "title": t["drops"]},
                 "tooltip": [{"field": "week", "type": "temporal", "title": t["col_first"], "format": "%d/%m/%Y"},
                             {"field": "n", "type": "quantitative", "title": t["drops"]}]}},
            {"data": {"values": events},
             "mark": {"type": "point", "shape": "triangle-down", "size": 70, "filled": True,
                      "color": "@ink3", "opacity": 0.9},
             "encoding": {
                 "x": {"field": "date", "type": "temporal"},
                 "y": {"field": "y", "type": "quantitative"},
                 "tooltip": [{"field": "date", "type": "temporal", "format": "%d/%m/%Y", "title": "date"},
                             {"field": "label", "type": "nominal", "title": " "}]}},
        ],
    )


def yearly(desc, lang):
    t = T[lang]
    years = range(int(min(desc["yearly"])), int(max(desc["yearly"])) + 1)
    data = [{"year": str(y), "n": desc["yearly"].get(str(y), 0)} for y in years]
    return _spec(
        height=180, data={"values": data},
        mark={"type": "bar", "color": "@series1", "cornerRadiusEnd": 4},
        encoding={"x": {"field": "year", "type": "ordinal", "title": None, "axis": {"labelAngle": 0}},
                  "y": {"field": "n", "type": "quantitative", "title": t["drops"]},
                  "tooltip": [{"field": "year", "title": " "}, {"field": "n", "title": t["drops"]}]})


def heatmap(desc, lang):
    t = T[lang]
    labels = t["dow"]
    data = [{**c, "day": labels[c["dow"]]} for c in desc["hour_weekday"]]
    return _spec(
        height=220, data={"values": data},
        mark={"type": "rect", "cornerRadius": 2, "stroke": "@surface", "strokeWidth": 2},
        encoding={
            "x": {"field": "hour", "type": "ordinal", "title": t["hour"], "axis": {"labelAngle": 0}},
            "y": {"field": "day", "type": "ordinal", "sort": labels, "title": None},
            "color": {"field": "n", "type": "quantitative", "title": t["drops"],
                      "scale": {"range": ["@seqlo", "@seqhi"]}},
            "tooltip": [{"field": "day", "title": " "}, {"field": "hour", "title": t["hour"]},
                        {"field": "n", "title": t["drops"]}]})


def tweet_hist(trump, lang):
    t = T[lang]
    obs, exp = t["observed"], t["expected"]
    data = []
    for b in trump["hist"]:
        # Barres de 2 min avec 0,3 min de jeu de chaque cote : l'espace entre barres.
        m = b["minute"]
        data.append({"minute": m, "m0": m + 0.15, "m1": m + 1.85, "value": b["observed"], "series": obs})
        data.append({"minute": m, "m0": m, "m1": m + 2, "value": b["expected"], "series": exp})
    color = {"field": "series", "type": "nominal", "title": None,
             "scale": {"domain": [obs, exp], "range": ["@series1", "@ink2"]},
             "legend": {"orient": "top"}}
    x = {"field": "minute", "type": "quantitative", "title": t["minutes"], "scale": {"domain": [-60, 60]}}
    tip = [{"field": "minute", "title": t["min"]}, {"field": "series", "title": " "},
           {"field": "value", "title": "n", "format": ".1f"}]
    return _spec(
        height=240, data={"values": data},
        layer=[
            {"transform": [{"filter": {"field": "series", "equal": obs}}],
             "mark": {"type": "bar", "cornerRadiusEnd": 2},
             "encoding": {"x": {**x, "field": "m0"}, "x2": {"field": "m1"},
                          "y": {"field": "value", "type": "quantitative", "title": "tweets",
                                "scale": {"zero": True}},
                          "y2": {"datum": 0},
                          "color": color, "tooltip": tip}},
            {"transform": [{"filter": {"field": "series", "equal": exp}}],
             "mark": {"type": "line", "strokeWidth": 2, "interpolate": "step-after"},
             "encoding": {"x": x, "y": {"field": "value", "type": "quantitative"},
                          "color": color, "tooltip": tip}},
        ])


# --- Discours
# Series mensuelles arretees a decembre 2020 : 2022 ne compte que 13 drops.
LAST_MONTH = "2020-12"

def topic_label(t):
    return " · ".join(t["terms"][:3])


def prevalence(disc, lang):
    t = T[lang]
    labels = {x["id"]: f"{i + 1}. {topic_label(x)}" for i, x in enumerate(disc["topics"])}
    order = [labels[x["id"]] for x in disc["topics"]]
    data = [{"month": p["month"], "topic": labels[p["topic"]], "share": p["share"]} for p in disc["prevalence"]
            if p["month"] <= LAST_MONTH]
    return _spec(
        height=300, data={"values": data},
        mark={"type": "rect"},
        encoding={
            "x": {"field": "month", "type": "temporal", "timeUnit": "yearmonth", "title": None,
                  "axis": {"format": "%Y", "tickCount": "year"}},
            "y": {"field": "topic", "type": "nominal", "sort": order, "title": None, "axis": {"labelLimit": 260}},
            "color": {"field": "share", "type": "quantitative", "title": t["col_share"],
                      "scale": {"range": ["@seqlo", "@seqhi"]}, "legend": {"format": ".0%"}},
            "tooltip": [{"field": "topic", "title": t["col_topic"]},
                        {"field": "month", "type": "temporal", "timeUnit": "yearmonth", "title": " ", "format": "%m/%Y"},
                        {"field": "share", "format": ".1%", "title": t["col_share"]}]})


def formulas(disc, glossary, lang, n=6):
    t = T[lang]
    terms = {g["id"]: g["term"] for g in glossary}
    # Termes generiques ou trop bruites (messages, participants, mots courants) : pas des formules.
    generic = {"drops", "anons", "bakers-bread", "crumbs", "boom", "the-plan", "clowns"}
    ranked = [g["id"] for g in sorted(disc["glossary"], key=lambda g: -(g["n"] or 0)) if g["id"] not in generic][:n]
    data = [{**s, "term": terms.get(s["id"], s["id"])} for s in disc["glossary_series"]
            if s["id"] in ranked and s["month"] <= LAST_MONTH]
    order = [terms.get(i, i) for i in ranked]
    return _spec(
        data={"values": data},
        facet={"field": "term", "type": "nominal", "sort": order, "title": None, "header": {"labelFontWeight": 600}},
        columns=3,
        spec={"width": 250, "height": 90, "mark": {"type": "bar", "color": "@series1"},
              "encoding": {
                  "x": {"field": "month", "type": "temporal", "timeUnit": "yearmonth", "title": None,
                        "axis": {"format": "%Y", "tickCount": "year"}, "scale": {"domain": ["2017-10", "2021-01"]}},
                  "y": {"field": "n", "type": "quantitative", "title": None},
                  "tooltip": [{"field": "term", "title": " "},
                              {"field": "month", "type": "temporal", "timeUnit": "yearmonth", "format": "%m/%Y", "title": " "},
                              {"field": "n", "title": t["drops"]}]}},
        resolve={"scale": {"y": "independent"}},
    )


def style(disc, lang):
    t = T[lang]
    data = []
    for r in disc["style"]:
        if r["n"] < 5 or r["month"] > LAST_MONTH:
            continue
        data.append({"month": r["month"], "value": r["share_questions"], "series": t["share_questions"]})
        data.append({"month": r["month"], "value": r["share_links"], "series": t["share_links"]})
    s1, s2 = t["share_questions"], t["share_links"]
    return _spec(
        height=220, data={"values": data},
        mark={"type": "line", "strokeWidth": 2, "point": {"size": 18}},
        encoding={
            "x": {"field": "month", "type": "temporal", "timeUnit": "yearmonth", "title": None,
                  "axis": {"format": "%Y", "tickCount": "year"}},
            "y": {"field": "value", "type": "quantitative", "title": None, "axis": {"format": ".0%"}},
            "color": {"field": "series", "type": "nominal", "title": None,
                      "scale": {"domain": [s1, s2], "range": ["@series1", "@series2"]}, "legend": {"orient": "top"}},
            "tooltip": [{"field": "series", "title": " "},
                        {"field": "month", "type": "temporal", "timeUnit": "yearmonth", "format": "%m/%Y", "title": " "},
                        {"field": "value", "format": ".0%", "title": " "}]})


def stylometry(disc, lang):
    t = T[lang]
    s = disc["stylometry"]
    return _spec(
        height=220,
        layer=[
            {"data": {"values": s["points"]},
             "mark": {"type": "point", "filled": True, "size": 60, "color": "@series1", "opacity": 0.85},
             "encoding": {
                 "x": {"field": "start", "type": "temporal", "title": None, "axis": {"format": "%Y", "tickCount": "year"}},
                 "y": {"field": "position", "type": "quantitative", "title": t["position"]},
                 "tooltip": [{"field": "start", "type": "temporal", "format": "%d/%m/%Y", "title": t["col_from"]},
                             {"field": "end", "type": "temporal", "format": "%d/%m/%Y", "title": t["col_to"]},
                             {"field": "position", "format": ".3f", "title": t["position"]}]}},
            {"data": {"values": [{"date": s["split"]["date"]}]},
             "mark": {"type": "rule", "color": "@ink2", "strokeWidth": 1.5},
             "encoding": {"x": {"field": "date", "type": "temporal"}}},
            {"data": {"values": [{"y": 0}]}, "mark": {"type": "rule", "color": "@rule"},
             "encoding": {"y": {"field": "y", "type": "quantitative"}}},
        ])


# --- Acteurs
CATS = ["person", "institution", "country", "organization", "media", "platform", "group"]
CAT_TOKENS = ["@series1", "@series2", "@series3", "@series4", "@series5", "@series6", "@series7"]


def top_actors(act, lang, n=30):
    t = T[lang]
    rows = act["actors"][:n]
    data = [{"name": r["name"], "n": r["n"], "cat": t[f"cat_{r['category']}"]} for r in rows]
    domain = [t[f"cat_{c}"] for c in CATS]
    return _spec(
        height=n * 18, data={"values": data},
        mark={"type": "bar", "cornerRadiusEnd": 3},
        encoding={
            "y": {"field": "name", "type": "nominal", "sort": "-x", "title": None, "axis": {"labelLimit": 200}},
            "x": {"field": "n", "type": "quantitative", "title": t["drops"]},
            "color": {"field": "cat", "type": "nominal", "title": None,
                      "scale": {"domain": domain, "range": CAT_TOKENS}, "legend": {"orient": "top"}},
            "tooltip": [{"field": "name", "title": " "}, {"field": "cat", "title": t["col_category"]},
                        {"field": "n", "title": t["drops"]}]})


def actors_time(act, lang):
    t = T[lang]
    names = {r["id"]: r["name"] for r in act["actors"]}
    order = [names[i] for i in act["top"]]
    data = [{"quarter": x["quarter"], "name": names[x["id"]], "n": x["n"]} for x in act["timeline"]]
    return _spec(
        height=25 * 18, data={"values": data}, mark={"type": "rect", "stroke": "@surface", "strokeWidth": 1},
        encoding={
            "x": {"field": "quarter", "type": "ordinal", "title": None, "axis": {"labelAngle": -45}},
            "y": {"field": "name", "type": "nominal", "sort": order, "title": None, "axis": {"labelLimit": 200}},
            "color": {"field": "n", "type": "quantitative", "title": t["drops"],
                      "scale": {"range": ["@seqlo", "@seqhi"]}},
            "tooltip": [{"field": "name", "title": " "}, {"field": "quarter", "title": t["quarter"]},
                        {"field": "n", "title": t["drops"]}]})


def world(countries, lang, field="q", title=None):
    """Carte : fond gris pour tous les pays, puis les pays cites colores (une
    seule couche avec lookup ecarte les pays sans correspondance)."""
    t = T[lang]
    data = [{"id": c["num"], "name": c["name"], "v": c[field]} for c in countries
            if c.get("num") is not None and c[field]]
    geo = {"url": "https://cdn.jsdelivr.net/npm/world-atlas@2.0.2/countries-110m.json",
           "format": {"type": "topojson", "feature": "countries"}}
    return _spec(
        height=380, projection={"type": "equalEarth"},
        layer=[
            {"data": geo, "mark": {"type": "geoshape", "fill": "@rule", "stroke": "@surface", "strokeWidth": 0.5}},
            {"data": geo,
             "transform": [{"lookup": "id", "from": {"data": {"values": data}, "key": "id", "fields": ["name", "v"]}},
                           {"filter": "datum.v > 0"}],
             "mark": {"type": "geoshape", "stroke": "@surface", "strokeWidth": 0.5},
             "encoding": {
                 "color": {"field": "v", "type": "quantitative", "title": title or t["drops"],
                           "scale": {"type": "sqrt", "range": ["@seqlo", "@seqhi"]}},
                 "tooltip": [{"field": "name", "title": " "}, {"field": "v", "title": title or t["drops"]}]}},
        ])


# --- Actualite
def overrep(news, lang, n=30):
    t = T[lang]
    rows = [r for r in news["actors"] if r.get("overrep")][:n]
    data = [{"name": r["name"], "overrep": r["overrep"], "q": r["q"], "news": r["news"]} for r in rows]
    return _spec(
        height=len(rows) * 18,
        layer=[
            {"data": {"values": data},
             "mark": {"type": "point", "filled": True, "size": 70, "color": "@series1"},
             "encoding": {
                 "y": {"field": "name", "type": "nominal", "sort": {"field": "overrep", "order": "descending"},
                       "title": None, "axis": {"labelLimit": 200}},
                 "x": {"field": "overrep", "type": "quantitative", "title": t["col_overrep"],
                       "scale": {"type": "log"}},
                 "tooltip": [{"field": "name", "title": " "}, {"field": "overrep", "title": t["col_overrep"]},
                             {"field": "q", "title": t["col_q"]}, {"field": "news", "title": t["col_news"]}]}},
            {"data": {"values": [{"x": 1}]}, "mark": {"type": "rule", "color": "@ink2"},
             "encoding": {"x": {"field": "x", "type": "quantitative"}}},
        ])


def news_series(news, lang, n=6):
    t = T[lang]
    a, b = t["q_mentions"], t["news_volume"]
    data = []
    for r in news["actors"][:n]:
        # Affichage mensuel : a l'echelle de la semaine, la serie de Q n'est que du bruit.
        months = {}
        for x in r["series"]:
            m = months.setdefault(x["week"][:7], [0, 0])
            m[0] += x["q"]; m[1] += x["news"]
        mq = sum(v[0] for v in months.values()) / len(months) or 1
        mn = sum(v[1] for v in months.values()) / len(months) or 1
        for month, (q, nw) in sorted(months.items()):
            data.append({"name": r["name"], "week": month, "series": a, "v": round(100 * q / mq, 1)})
            data.append({"name": r["name"], "week": month, "series": b, "v": round(100 * nw / mn, 1)})
    order = [r["name"] for r in news["actors"][:n]]
    return _spec(
        data={"values": data},
        facet={"field": "name", "type": "nominal", "sort": order, "title": None, "header": {"labelFontWeight": 600}},
        columns=3,
        spec={"width": 250, "height": 120, "mark": {"type": "line", "strokeWidth": 1.5},
              "encoding": {
                  "x": {"field": "week", "type": "temporal", "timeUnit": "yearmonth", "title": None,
                        "axis": {"format": "%Y", "tickCount": "year"}},
                  "y": {"field": "v", "type": "quantitative", "title": t["index"]},
                  "color": {"field": "series", "type": "nominal", "title": None,
                            "scale": {"domain": [a, b], "range": ["@series1", "@ink3"]}, "legend": {"orient": "top"}},
                  "tooltip": [{"field": "name", "title": " "}, {"field": "series", "title": " "},
                              {"field": "week", "type": "temporal", "timeUnit": "yearmonth", "format": "%m/%Y", "title": " "},
                              {"field": "v", "title": t["index"]}]}},
        resolve={"scale": {"y": "independent"}},
    )


# --- Interet public
def views(interest, desc, lang):
    t = T[lang]
    data = [w for w in interest["weekly"] if w["key"] == "en:QAnon"]
    top = max((w["views"] for w in data), default=1) * 1.1
    events = [{"date": e["date"], "label": e[f"label_{lang}"], "y": top} for e in desc["events"]]
    return _spec(
        height=260,
        layer=[
            {"data": {"values": data},
             "mark": {"type": "area", "color": "@series1", "opacity": 0.85, "interpolate": "step-after",
                      "line": {"color": "@series1", "strokeWidth": 1}},
             "encoding": {"x": {"field": "week", "type": "temporal", "title": None,
                                "axis": {"format": "%Y", "tickCount": "year"}},
                          "y": {"field": "views", "type": "quantitative", "title": t["views"]},
                          "tooltip": [{"field": "week", "type": "temporal", "format": "%d/%m/%Y", "title": " "},
                                      {"field": "views", "title": t["views"], "format": ","}]}},
            {"data": {"values": events},
             "mark": {"type": "point", "shape": "triangle-down", "size": 70, "filled": True, "color": "@ink3"},
             "encoding": {"x": {"field": "date", "type": "temporal"}, "y": {"field": "y", "type": "quantitative"},
                          "tooltip": [{"field": "date", "type": "temporal", "format": "%d/%m/%Y", "title": "date"},
                                      {"field": "label", "title": " "}]}},
        ])


def languages(interest, lang):
    t = T[lang]
    data = [w for w in interest["weekly"] if w["key"].endswith(":QAnon") or w["key"] == "ja:Qアノン"]
    keys = sorted({w["key"] for w in data}, key=lambda k: -sum(w["views"] for w in data if w["key"] == k))
    return _spec(
        data={"values": data},
        facet={"field": "key", "type": "nominal", "sort": keys, "title": None, "header": {"labelFontWeight": 600}},
        columns=3,
        spec={"width": 250, "height": 90,
              "mark": {"type": "area", "color": "@series1", "opacity": 0.85, "interpolate": "step-after"},
              "encoding": {"x": {"field": "week", "type": "temporal", "title": None,
                                 "axis": {"format": "%Y", "tickCount": "year"}},
                           "y": {"field": "views", "type": "quantitative", "title": None},
                           "tooltip": [{"field": "key", "title": " "},
                                       {"field": "week", "type": "temporal", "format": "%d/%m/%Y", "title": " "},
                                       {"field": "views", "title": t["views"]}]}},
        resolve={"scale": {"y": "independent"}},
    )


# --- Predictions
def pred_monthly(pr, lang):
    t = T[lang]
    data = [m for m in pr["monthly"] if m["n"] >= 5 and m["month"] <= LAST_MONTH]
    return _spec(
        height=220, data={"values": data},
        mark={"type": "bar", "color": "@series1", "cornerRadiusEnd": 2},
        encoding={"x": {"field": "month", "type": "temporal", "timeUnit": "yearmonth", "title": None,
                        "axis": {"format": "%Y", "tickCount": "year"}},
                  "y": {"field": "share", "type": "quantitative", "title": None, "axis": {"format": ".0%"}},
                  "tooltip": [{"field": "month", "type": "temporal", "timeUnit": "yearmonth", "format": "%m/%Y", "title": " "},
                              {"field": "share", "format": ".0%", "title": t["pred_share"]},
                              {"field": "pred", "title": t["pred_drops"]}, {"field": "n", "title": t["drops"]}]})


def pred_types(pr, lang):
    t = T[lang]
    data = [{"type": t.get(f"et_{k}", k), "n": v} for k, v in pr["by_type"]]
    return _spec(
        height=len(data) * 22, data={"values": data},
        mark={"type": "bar", "color": "@series1", "cornerRadiusEnd": 3},
        encoding={"y": {"field": "type", "type": "nominal", "sort": "-x", "title": None},
                  "x": {"field": "n", "type": "quantitative", "title": t["pred_n"]},
                  "tooltip": [{"field": "type", "title": " "}, {"field": "n", "title": t["pred_n"]}]})


def pred_actors(pr, lang, n=20):
    t = T[lang]
    # "United States" absorbe tout sujet du type "the U.S. military" : trop generique pour ce graphe.
    data = [a for a in pr["actors"] if a["id"] != "usa"][:n]
    return _spec(
        height=len(data) * 20, data={"values": data},
        mark={"type": "bar", "color": "@series1", "cornerRadiusEnd": 3},
        encoding={"y": {"field": "name", "type": "nominal", "sort": "-x", "title": None, "axis": {"labelLimit": 200}},
                  "x": {"field": "n", "type": "quantitative", "title": t["pred_n"]},
                  "tooltip": [{"field": "name", "title": " "}, {"field": "n", "title": t["pred_n"]}]})


# --- Page Statistiques
def gaps_hist(stats, lang):
    t = T[lang]
    data = [h for h in stats["rhythm"]["hist"] if h["n"]]
    marks = [{"x": m, "label": lab} for m, lab in ((1, "1 min"), (60, "1 h"), (1440, t["one_day"]), (10080, t["one_week"]))]
    return _spec(
        height=220,
        layer=[
            {"data": {"values": data},
             "mark": {"type": "bar", "color": "@series1", "cornerRadiusEnd": 2},
             "encoding": {
                 "x": {"field": "lo", "type": "quantitative", "scale": {"type": "log"}, "title": t["gap_axis"],
                       "axis": {"values": [1, 10, 60, 600, 1440, 10080, 100000], "format": "~s"}},
                 "x2": {"field": "hi"},
                 "y": {"field": "n", "type": "quantitative", "title": t["n_intervals"]},
                 "tooltip": [{"field": "lo", "title": t["gap_from"], "format": ".2~f"},
                             {"field": "hi", "title": t["gap_to"], "format": ".2~f"},
                             {"field": "n", "title": t["n_intervals"]}]}},
            {"data": {"values": marks},
             "mark": {"type": "rule", "color": "@ink3", "strokeDash": [3, 3]},
             "encoding": {"x": {"field": "x", "type": "quantitative"}}},
            {"data": {"values": marks},
             "mark": {"type": "text", "color": "@ink2", "align": "left", "dx": 3, "dy": -4, "baseline": "top", "y": 0},
             "encoding": {"x": {"field": "x", "type": "quantitative"}, "text": {"field": "label"}}},
        ])


def session_sizes(stats, lang):
    t = T[lang]
    data = [{"size": "31+" if s["size"] == 31 else str(s["size"]), "k": s["size"], "n": s["n"]}
            for s in stats["rhythm"]["session_sizes"]]
    return _spec(
        height=180, data={"values": data},
        mark={"type": "bar", "color": "@series1", "cornerRadiusEnd": 3},
        encoding={"x": {"field": "size", "type": "ordinal", "sort": {"field": "k"}, "title": t["session_size"],
                        "axis": {"labelAngle": 0}},
                  "y": {"field": "n", "type": "quantitative", "title": t["n_sessions"]},
                  "tooltip": [{"field": "size", "title": t["session_size"]}, {"field": "n", "title": t["n_sessions"]}]})


def regimes(stats, desc, lang):
    t = T[lang]
    segs = stats["changepoints"]["segments"]
    return _spec(
        height=260,
        layer=[
            {"data": {"values": desc["weekly"]},
             "mark": {"type": "area", "interpolate": "step-after", "color": "@seqlo", "opacity": 0.9},
             "encoding": {"x": {"field": "week", "type": "temporal", "title": None,
                                "axis": {"format": "%Y", "tickCount": "year"}},
                          "y": {"field": "n", "type": "quantitative", "title": t["drops_per_week"]},
                          "tooltip": [{"field": "week", "type": "temporal", "format": "%d/%m/%Y", "title": t["col_first"]},
                                      {"field": "n", "title": t["drops"]}]}},
            {"data": {"values": segs},
             "mark": {"type": "rule", "color": "@series2", "strokeWidth": 3},
             "encoding": {"x": {"field": "start", "type": "temporal"}, "x2": {"field": "end"},
                          "y": {"field": "mean_per_week", "type": "quantitative"},
                          "tooltip": [{"field": "start", "type": "temporal", "format": "%d/%m/%Y", "title": t["col_from"]},
                                      {"field": "end", "type": "temporal", "format": "%d/%m/%Y", "title": t["col_to"]},
                                      {"field": "mean_per_week", "title": t["mean_per_week"], "format": ".1f"}]}},
        ])


DOMAIN_CATS = ["social", "press", "official", "archive"]


def _cat_scale(t):
    return {"domain": [t[f"dcat_{c}"] for c in DOMAIN_CATS], "range": ["@series1", "@series2", "@series3", "@series4"]}


def top_domains(stats, lang):
    t = T[lang]
    data = [{**x, "cat_label": t[f"dcat_{x['cat']}"]} for x in stats["domains"]["top"][:25]]
    return _spec(
        height=25 * 17, data={"values": data},
        mark={"type": "bar", "cornerRadiusEnd": 3, "height": {"band": 0.75}},
        encoding={"y": {"field": "site", "type": "nominal", "sort": "-x", "title": None},
                  "x": {"field": "drops", "type": "quantitative", "title": t["drops_citing"], "scale": {"type": "sqrt"}},
                  "color": {"field": "cat_label", "type": "nominal", "title": None, "scale": _cat_scale(t),
                            "legend": {"orient": "top"}},
                  "tooltip": [{"field": "site", "title": " "}, {"field": "cat_label", "title": " "},
                              {"field": "drops", "title": t["drops_citing"]}]})


def domain_years(stats, lang):
    t = T[lang]
    data = [{**x, "year": str(x["year"]), "cat_label": t[f"dcat_{x['cat']}"], "o": DOMAIN_CATS.index(x["cat"])}
            for x in stats["domains"]["cat_year"] if x["year"] <= 2020]
    return _spec(
        height=200, data={"values": data},
        mark={"type": "bar", "stroke": "@surface", "strokeWidth": 2},
        encoding={"x": {"field": "year", "type": "ordinal", "title": None, "axis": {"labelAngle": 0}},
                  "y": {"field": "n", "type": "quantitative", "stack": "normalize", "title": t["share_links_axis"],
                        "axis": {"format": ".0%"}},
                  "order": {"field": "o"},
                  "color": {"field": "cat_label", "type": "nominal", "title": None, "scale": _cat_scale(t),
                            "legend": {"orient": "top"}},
                  "tooltip": [{"field": "year", "title": " "}, {"field": "cat_label", "title": " "},
                              {"field": "n", "title": t["n_links"]}]})


def religion(stats, lang):
    t = T[lang]
    s1, s2 = t["rel_faith"], t["rel_god"]
    data = []
    for r in stats["religion"]["quarterly"]:
        if r["q"] > "2020Q4":
            continue
        data += [{"q": r["q"], "series": s1, "value": r["faith"]}, {"q": r["q"], "series": s2, "value": r["god"]}]
    return _quarter_lines(data, [s1, s2], lang, ".0%")


def _quarter_lines(data, domain, lang, fmt_, title=None, zero=True):
    return _spec(
        height=200, data={"values": data},
        mark={"type": "line", "strokeWidth": 2, "point": {"size": 30, "filled": True}},
        encoding={"x": {"field": "q", "type": "ordinal", "title": None, "axis": {"labelAngle": -45}},
                  "y": {"field": "value", "type": "quantitative", "title": title, "axis": {"format": fmt_},
                        "scale": {"zero": zero}},
                  "color": {"field": "series", "type": "nominal", "title": None,
                            "scale": {"domain": domain, "range": ["@series1", "@series2"][:len(domain)]},
                            "legend": {"orient": "top"} if len(domain) > 1 else None},
                  "tooltip": [{"field": "series", "title": " "}, {"field": "q", "title": " "},
                              {"field": "value", "format": fmt_, "title": " "}]})


def readability(stats, lang):
    t = T[lang]
    data = [{"q": r["q"], "series": t["flesch"], "value": r["flesch"]}
            for r in stats["lexicon"]["quarterly"] if r["q"] <= "2020Q4"]
    return _quarter_lines(data, [t["flesch"]], lang, ".0f", t["flesch"], zero=False)


def richness(stats, lang):
    t = T[lang]
    data = [{"q": r["q"], "series": "MATTR", "value": r["mattr"]}
            for r in stats["lexicon"]["quarterly"] if r["q"] <= "2020Q4"]
    return _quarter_lines(data, ["MATTR"], lang, ".2f", "MATTR", zero=False)


def horizon(pred, lang):
    t = T[lang]
    data = [{**b, "o": i} for i, b in enumerate(pred["horizon"]["bins"])]
    return _spec(
        height=180, data={"values": data},
        mark={"type": "bar", "color": "@series1", "cornerRadiusEnd": 3},
        encoding={"x": {"field": "label", "type": "ordinal", "sort": {"field": "o"}, "title": t["horizon_axis"],
                        "axis": {"labelAngle": 0}},
                  "y": {"field": "n", "type": "quantitative", "title": t["pred_n"]},
                  "tooltip": [{"field": "label", "title": t["horizon_axis"]}, {"field": "n", "title": t["pred_n"]}]})


# --- Predictions a l'epreuve : horoscope, recyclage, « Future proves past »
def horoscope(ho, lang):
    t = T[lang]
    k = ho["kinds"].get("future") or next(iter(ho["kinds"].values()))
    s1, s2 = t["horo_series_true"], t["horo_series_random"]
    data = [x for h in k["hist"] for x in ({"score": h["score"], "series": s1, "n": h["true"]},
                                           {"score": h["score"], "series": s2, "n": h["random"]})]
    return _spec(
        height=200, data={"values": data},
        mark={"type": "bar", "cornerRadiusEnd": 3, "stroke": "@surface", "strokeWidth": 2},
        encoding={"x": {"field": "score", "type": "ordinal", "title": t["horo_score_axis"], "axis": {"labelAngle": 0}},
                  "xOffset": {"field": "series", "sort": [s1, s2]},
                  "y": {"field": "n", "type": "quantitative", "title": t["horo_n"]},
                  "color": {"field": "series", "type": "nominal", "title": None, "legend": {"orient": "top"},
                            "scale": {"domain": [s1, s2], "range": ["@series1", "@series2"]}},
                  "tooltip": [{"field": "series", "title": " "}, {"field": "score", "title": t["horo_score_axis"]},
                              {"field": "n", "title": t["horo_n"]}]})


def recycled(rc, names, lang):
    t = T[lang]
    data = [{"subject": f"{t.get('et_' + g['event_type'], g['event_type'])} — {names.get(g['actor'], g['actor'])}",
             "date": dte, "drop": did} for g in rc["groups"][:15] for dte, did in zip(g["dates"], g["drop_ids"])]
    order = [f"{t.get('et_' + g['event_type'], g['event_type'])} — {names.get(g['actor'], g['actor'])}" for g in rc["groups"][:15]]
    return _spec(
        height=22 * len(order) + 30, data={"values": data},
        mark={"type": "point", "filled": True, "size": 70, "color": "@series1", "opacity": 0.8,
              "stroke": "@surface", "strokeWidth": 1.5},
        encoding={"x": {"field": "date", "type": "temporal", "title": None, "axis": {"format": "%Y", "tickCount": "year"}},
                  "y": {"field": "subject", "type": "nominal", "sort": order, "title": None},
                  "tooltip": [{"field": "subject", "title": " "},
                              {"field": "date", "type": "temporal", "format": "%d/%m/%Y", "title": "date"},
                              {"field": "drop", "title": t["drop_no"]}]})


def fpp(fp, lang):
    t = T[lang]
    labels = t["fpp_bins"]
    data = [{"label": labels[i], "o": i, "n": b["n"]} for i, b in enumerate(fp["lag_bins"])]
    return _spec(
        height=180, data={"values": data},
        mark={"type": "bar", "color": "@series1", "cornerRadiusEnd": 3},
        encoding={"x": {"field": "label", "type": "ordinal", "sort": {"field": "o"}, "title": t["fpp_axis"],
                        "axis": {"labelAngle": 0}},
                  "y": {"field": "n", "type": "quantitative", "scale": {"type": "symlog"}, "title": t["fpp_n"]},
                  "tooltip": [{"field": "label", "title": t["fpp_axis"]}, {"field": "n", "title": t["fpp_n"]}]})


# ------------------------------------------------------------------ page Modeles
def _legend(title=None):
    return {"orient": "top", "title": title, "direction": "horizontal"}


def regime_names(K, lang):
    t = T[lang]
    return [t[f"regime_{k}"] for k in range(3)] if K == 3 else [t["regime_n"].format(k=k + 1) for k in range(K)]


def hmm_regimes(markov, lang):
    """Drops par jour, colores par regime du HMM (chemin de Viterbi)."""
    t = T[lang]
    h = markov["hmm"]
    names = regime_names(h["K"], lang)
    data = [{"date": x["date"], "n": x["n"], "regime": names[x["state"]]} for x in h["series"] if x["n"] or x["state"]]
    return _spec(
        height=220, data={"values": data},
        mark={"type": "bar", "width": {"band": 1}},
        encoding={
            "x": {"field": "date", "type": "temporal", "title": None, "axis": {"format": "%Y", "tickCount": "year"}},
            "y": {"field": "n", "type": "quantitative", "title": t["drops_per_day"]},
            "color": {"field": "regime", "type": "nominal", "sort": names, "title": None, "legend": _legend(),
                      "scale": {"domain": names, "range": ["@ink3", "@series4", "@series1"][:len(names)]}},
            "tooltip": [{"field": "date", "type": "temporal", "format": "%d/%m/%Y", "title": "date"},
                        {"field": "n", "title": t["drops"]}, {"field": "regime", "title": t["col_regime"]}]})


def style_matrix(markov, lang):
    """Entropie croisee (bits/caractere) : modele appris sur un semestre (ligne), teste sur un autre (colonne)."""
    t = T[lang]
    sd = markov["style_drift"]
    lab = [x.replace("Q ", "") for x in sd["names"]]
    data = [{"train": lab[i], "test": lab[j], "bits": v} for i, row in enumerate(sd["matrix"]) for j, v in enumerate(row)]
    return _spec(
        height=240, data={"values": data},
        mark={"type": "rect", "cornerRadius": 2, "stroke": "@surface", "strokeWidth": 2},
        encoding={
            "x": {"field": "test", "type": "ordinal", "sort": lab, "title": t["style_test"], "axis": {"labelAngle": 0}},
            "y": {"field": "train", "type": "ordinal", "sort": lab, "title": t["style_train"]},
            "color": {"field": "bits", "type": "quantitative", "title": t["bits_per_char"],
                      "scale": {"range": ["@seqlo", "@seqhi"]}},
            "tooltip": [{"field": "train", "title": t["style_train"]}, {"field": "test", "title": t["style_test"]},
                        {"field": "bits", "format": ".2f", "title": t["bits_per_char"]}]})


def hawkes_qq(physics, lang):
    """Quantiles des increments du compensateur contre Exp(1) : la diagonale = modele adequat."""
    t = T[lang]
    models = physics["hawkes"]["models"]
    keys = [("regimes/poisson", t["model_poisson"]), ("regimes/exp", t["model_exp"]), ("regimes/omori", t["model_omori"])]
    data = [{"model": lab, "theory": q["theory"], "observed": q["observed"]}
            for k, lab in keys if k in models for q in models[k]["gof"]["qq"]]
    top = max(max(d["theory"] for d in data), 1)
    order = [lab for _, lab in keys]
    return _spec(
        height=260,
        layer=[
            {"data": {"values": [{"x": 0, "y": 0}, {"x": top, "y": top}]},
             "mark": {"type": "line", "color": "@ink3", "strokeDash": [4, 4], "strokeWidth": 1},
             "encoding": {"x": {"field": "x", "type": "quantitative"}, "y": {"field": "y", "type": "quantitative"}}},
            {"data": {"values": data},
             "mark": {"type": "line", "strokeWidth": 2, "point": {"size": 30, "filled": True}},
             "encoding": {
                 "x": {"field": "theory", "type": "quantitative", "title": t["qq_theory"]},
                 "y": {"field": "observed", "type": "quantitative", "title": t["qq_observed"], "scale": {"domainMax": top * 1.6, "clamp": True}},
                 "color": {"field": "model", "type": "nominal", "sort": order, "title": None, "legend": _legend(),
                           "scale": {"domain": order, "range": ["@series2", "@series3", "@series1"]}},
                 "tooltip": [{"field": "model", "title": " "}, {"field": "theory", "format": ".2f", "title": t["qq_theory"]},
                             {"field": "observed", "format": ".2f", "title": t["qq_observed"]}]}}])


def dfa_curves(physics, lang):
    t = T[lang]
    data = []
    for x in physics["dfa"]:
        if x["resolution"] != "day":
            continue
        for c in x["curve"]:
            data.append({"series": f"{x['series']} (H = {x['H']:.2f})".replace(".", "," if lang == "fr" else "."),
                         "scale": c["scale"], "F": c["F"]})
        if x["series"] == "Q":
            data += [{"series": t["dfa_shuffled"], "scale": c["scale"], "F": c["F_shuffled"]} for c in x["curve"]]
    order = sorted({d["series"] for d in data}, key=lambda s: (s == t["dfa_shuffled"], s))
    return _spec(
        height=240, data={"values": data},
        mark={"type": "line", "strokeWidth": 2, "point": {"size": 30, "filled": True}},
        encoding={
            "x": {"field": "scale", "type": "quantitative", "scale": {"type": "log"}, "title": t["dfa_scale"]},
            "y": {"field": "F", "type": "quantitative", "scale": {"type": "log"}, "title": t["dfa_F"]},
            "color": {"field": "series", "type": "nominal", "sort": order, "title": None, "legend": _legend(),
                      "scale": {"domain": order, "range": ["@series1", "@series2", "@ink3"]}},
            "tooltip": [{"field": "series", "title": " "}, {"field": "scale", "title": t["dfa_scale"]},
                        {"field": "F", "format": ".3g", "title": "F"}]})


def avalanche_ccdf(physics, lang):
    t = T[lang]
    data = [{"series": name, "x": c["x"], "p": c["p"]}
            for name, v in physics["avalanches"].items() if "size" in v for c in v["size"]["ccdf"] if c["p"] > 0]
    order = ["Q", "Trump"]
    return _spec(
        height=240, data={"values": data},
        mark={"type": "line", "interpolate": "step-after", "strokeWidth": 2},
        encoding={
            "x": {"field": "x", "type": "quantitative", "scale": {"type": "log"}, "title": t["session_size"]},
            "y": {"field": "p", "type": "quantitative", "scale": {"type": "log"}, "title": t["ccdf"]},
            "color": {"field": "series", "type": "nominal", "sort": order, "title": None, "legend": _legend(),
                      "scale": {"domain": order, "range": ["@series1", "@series2"]}},
            "tooltip": [{"field": "series", "title": " "}, {"field": "x", "title": t["session_size"]},
                        {"field": "p", "format": ".3f", "title": t["ccdf"]}]})


def phase_months(physics, lang):
    """Heure de pointe mensuelle (New York) de Q et de Trump ; trait : rupture de phase de Q."""
    t = T[lang]
    ph = physics["phases"]
    data = []
    for m in ph["monthly"]:
        data.append({"month": m["month"], "who": "Q", "peak": m["peak"]})
        if "trump_peak" in m:
            data.append({"month": m["month"], "who": "Trump", "peak": m["trump_peak"]})
    sp = ph.get("phase_split") or {}
    order = ["Q", "Trump"]
    layers = [{"data": {"values": data},
               "mark": {"type": "line", "strokeWidth": 2, "point": {"size": 40, "filled": True}},
               "encoding": {
                   "x": {"field": "month", "type": "temporal", "title": None, "axis": {"format": "%Y", "tickCount": "year"}},
                   "y": {"field": "peak", "type": "quantitative", "title": t["peak_hour"], "scale": {"domain": [0, 24]},
                         "axis": {"values": [0, 6, 12, 18, 24]}},
                   "color": {"field": "who", "type": "nominal", "sort": order, "title": None, "legend": _legend(),
                             "scale": {"domain": order, "range": ["@series1", "@series2"]}},
                   "tooltip": [{"field": "who", "title": " "}, {"field": "month", "type": "temporal", "format": "%m/%Y", "title": "date"},
                               {"field": "peak", "format": ".1f", "title": t["peak_hour"]}]}}]
    if sp.get("date"):
        layers.append({"data": {"values": [{"date": sp["date"], "label": t["phase_split_mark"]}]},
                       "mark": {"type": "rule", "color": "@ink3", "strokeDash": [4, 4]},
                       "encoding": {"x": {"field": "date", "type": "temporal"},
                                    "tooltip": [{"field": "label", "title": " "},
                                                {"field": "date", "type": "temporal", "format": "%d/%m/%Y", "title": "date"}]}})
    return _spec(height=240, layer=layers)


def absorption(scene, lang):
    t = T[lang]
    data = [x for x in scene["syncretism"]["absorption"] if x["drops"] > 0]
    return _spec(
        height=200, data={"values": data},
        mark={"type": "bar", "color": "@series1", "cornerRadiusEnd": 4},
        encoding={"x": {"field": "quarter", "type": "ordinal", "title": None, "axis": {"labelAngle": -45}},
                  "y": {"field": "themes", "type": "quantitative", "title": t["n_themes"]},
                  "tooltip": [{"field": "quarter", "title": " "}, {"field": "themes", "title": t["n_themes"]},
                              {"field": "drops", "title": t["drops"]}]})


def response(scene, sub, lang):
    """Activite horaire d'un subreddit autour des debuts de session de Q, contre le modele nul."""
    return response_curve(scene["response"][sub], lang)


def response_curve(r, lang):
    """Courbe d'epoque superposee (observe, bande a 95 % du modele nul)."""
    t = T[lang]
    band = [{"h": c["h"], "lo": c["null_lo"], "hi": c["null_hi"]} for c in r["curve"]]
    obs = [{"h": c["h"], "v": c["obs"], "who": t["observed"]} for c in r["curve"]]
    return _spec(
        height=220,
        layer=[
            {"data": {"values": band}, "mark": {"type": "area", "color": "@ink3", "opacity": 0.25},
             "encoding": {"x": {"field": "h", "type": "quantitative", "title": t["hours_from_drop"]},
                          "y": {"field": "lo", "type": "quantitative", "title": t["activity_ratio"]},
                          "y2": {"field": "hi"},
                          "tooltip": [{"field": "h", "title": t["hours_from_drop"]},
                                      {"field": "lo", "format": ".2f", "title": t["null_lo"]},
                                      {"field": "hi", "format": ".2f", "title": t["null_hi"]}]}},
            {"data": {"values": [{"h": 0}]}, "mark": {"type": "rule", "color": "@ink3", "strokeDash": [4, 4]},
             "encoding": {"x": {"field": "h", "type": "quantitative"}}},
            {"data": {"values": obs}, "mark": {"type": "line", "strokeWidth": 2, "color": "@series1"},
             "encoding": {"x": {"field": "h", "type": "quantitative"}, "y": {"field": "v", "type": "quantitative"},
                          "tooltip": [{"field": "h", "title": t["hours_from_drop"]},
                                      {"field": "v", "format": ".2f", "title": t["observed"]}]}}])


def trends_waves(scene, lang, top=14):
    """Calendrier des vagues Google Trends : chaque requete rapportee a son propre maximum."""
    t = T[lang]
    rows = [r for r in scene.get("trends", []) if r["level_measured"]][:top]
    order = [r["query"] for r in rows]
    data = []
    for r in rows:
        mx = max(x["rel"] for x in r["monthly"]) or 1
        data += [{"query": r["query"], "month": x["month"], "share": round(x["rel"] / mx, 3)} for x in r["monthly"]]
    return _spec(
        height=max(160, 18 * len(order)), data={"values": data},
        mark={"type": "rect"},
        encoding={
            "x": {"field": "month", "type": "temporal", "title": None, "axis": {"format": "%Y", "tickCount": "year"}},
            "y": {"field": "query", "type": "nominal", "sort": order, "title": None},
            "color": {"field": "share", "type": "quantitative", "title": t["share_of_peak"],
                      "scale": {"range": ["@seqlo", "@seqhi"], "domain": [0, 1]}},
            "tooltip": [{"field": "query", "title": " "}, {"field": "month", "type": "temporal", "format": "%m/%Y", "title": "date"},
                        {"field": "share", "format": ".0%", "title": t["share_of_peak"]}]})


# ------------------------------------------------------------------ /pol/
def pol_niche(pol, lang):
    """Part des posts de /pol/ ecrits dans les fils Q, par mois (echelle logarithmique)."""
    t = T[lang]
    data = [{"month": x["month"], "share": x["share"]} for x in pol["niche"] if x["share"] > 0]
    return _spec(
        height=220, data={"values": data},
        mark={"type": "line", "strokeWidth": 2, "color": "@series1", "point": {"size": 30, "filled": True}},
        encoding={
            "x": {"field": "month", "type": "temporal", "title": None, "axis": {"format": "%Y", "tickCount": "year"}},
            "y": {"field": "share", "type": "quantitative", "scale": {"type": "log"}, "title": t["pol_niche_axis"],
                  "axis": {"format": ".1~%"}},
            "tooltip": [{"field": "month", "type": "temporal", "format": "%m/%Y", "title": "date"},
                        {"field": "share", "format": ".2%", "title": t["pol_niche_axis"]}]})


def pol_toxicity(pol, lang):
    """Toxicite moyenne (Perspective) par mois : fils et posts Q contre tout /pol/."""
    t = T[lang]
    names = {"all": t["pol_scope_all"], "q": t["pol_scope_q"]}
    order = [names["all"], names["q"]]
    data = [{"month": x["month"], "mean": x["mean"], "scope": names[x["scope"]]} for x in pol["toxicity"]["monthly"]
            if x["scope"] in names]
    return _spec(
        height=220, data={"values": data},
        mark={"type": "line", "strokeWidth": 2, "point": {"size": 30, "filled": True}},
        encoding={
            "x": {"field": "month", "type": "temporal", "title": None, "axis": {"format": "%Y", "tickCount": "year"}},
            "y": {"field": "mean", "type": "quantitative", "scale": {"zero": False}, "title": t["pol_tox_axis"]},
            "color": {"field": "scope", "type": "nominal", "sort": order, "title": None, "legend": _legend(),
                      "scale": {"domain": order, "range": ["@ink3", "@series1"]}},
            "tooltip": [{"field": "scope", "title": " "}, {"field": "month", "type": "temporal", "format": "%m/%Y", "title": "date"},
                        {"field": "mean", "format": ".3f", "title": t["pol_tox_axis"]}]})

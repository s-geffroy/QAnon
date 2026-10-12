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

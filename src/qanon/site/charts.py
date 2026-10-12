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
    return {**BASE, **kw}


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

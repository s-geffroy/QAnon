"""Formatage des nombres et dates selon la langue."""
import datetime as dt
import re
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")  # l'etude date les drops a l'heure de New York

MONTHS = {
    "fr": ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."],
    "en": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
}


def num(lang, x, digits=0):
    s = f"{x:,.{digits}f}"
    if lang == "fr":
        s = s.replace(",", " ").replace(".", ",")
    return s


def pct(lang, x, digits=1):
    s = num(lang, 100 * x, digits)
    return f"{s} %" if lang == "fr" else f"{s}%"


def date(lang, value):
    if isinstance(value, str):
        value = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if isinstance(value, dt.datetime) and value.tzinfo is not None:
        value = value.astimezone(ET)
    m = MONTHS[lang][value.month - 1]
    return f"{value.day} {m} {value.year}" if lang == "fr" else f"{m} {value.day}, {value.year}"


# ------------------------------------------------------------------ typographie francaise
# Espace fine insecable (U+202F) avant ; ! ? et insecable (U+00A0) avant : et a l'interieur des
# guillemets, a la place de l'espace ordinaire saisie dans les textes : la ponctuation haute ne
# se retrouve jamais seule en debut de ligne. Sans espace saisie (adresses, heures), rien ne change.
_FR_RULES = [
    (re.compile("[ \u00a0\u2009](?=[;!?])"), "\u202f"),
    (re.compile(" (?=:)"), "\u00a0"),
    (re.compile("\u00ab[ \u202f]"), "\u00ab\u00a0"),
    (re.compile(" (?=\u00bb)"), "\u00a0"),
    # p < 0,001, n = 140 : l'operateur reste attache a ses deux termes.
    (re.compile("(?<=\\b[pnK]) (?=(?:[<>=\u2264\u2265]|&[lg]t;) ?\\d)"), "\u00a0"),
    (re.compile("(?<=&[lg]t;) (?=\\d)"), "\u00a0"),   # dans le HTML, < et > sont des entites
    (re.compile("(?<=[<>=\u2264\u2265]) (?=\\d)"), "\u00a0"),
]


def fr_typo(text):
    for rx, rep in _FR_RULES:
        text = rx.sub(rep, text)
    return text


# Hors texte : balises, scripts (sauf les donnees des graphiques), styles, code.
_FR_SKIP = re.compile(r"(<script\b[^>]*>.*?</script>|<style\b.*?</style>|<pre\b.*?</pre>|<code\b.*?</code>"
                      r"|<textarea\b.*?</textarea>|<!--.*?-->|<[^>]+>)", re.S | re.I)
_CHART = re.compile(r'(<script type="application/json" data-chart="[^"]*">)(.*?)(</script>)', re.S)


def _fr_json(v):
    if isinstance(v, str):
        return fr_typo(v)
    if isinstance(v, list):
        return [_fr_json(x) for x in v]
    if isinstance(v, dict):
        return {k: _fr_json(x) for k, x in v.items()}
    return v


def fr_html(html):
    """Typographie francaise dans les noeuds de texte d'une page, et dans les chaines des
    specifications de graphiques (domaines et donnees changent ensemble : les couleurs suivent)."""
    import json

    def chart(m):
        spec = _fr_json(json.loads(m.group(2)))
        return m.group(1) + json.dumps(spec, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c") + m.group(3)

    parts = _FR_SKIP.split(html)
    out = []
    for i, part in enumerate(parts):
        if i % 2:
            out.append(_CHART.sub(chart, part) if part.startswith("<script") else part)
        else:
            out.append(fr_typo(part))
    return "".join(out)

import io
import zipfile

from qanon.site import biblio
from qanon.sources.gdelt import aggregate


def gdelt_row(a1="", a2="", root="14", mentions=3, tone=-2.0, gold=1.0, fips="US"):
    p = [""] * 58
    p[6], p[16], p[28], p[30], p[31], p[34], p[51] = a1, a2, root, str(gold), str(mentions), str(tone), fips
    return "\t".join(p)


def test_gdelt_aggregate():
    rows = [gdelt_row("HILLARY CLINTON", "FBI"), gdelt_row("HILLARY CLINTON", root="19"),
            gdelt_row("ONCE", fips="FR"), "short\tline"]
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("20180101.export.CSV", "\n".join(rows) + "\n")
    day, country, names = aggregate(buf.getvalue())
    assert day["events"] == 3 and day["mentions"] == 9
    assert day["us_events"] == 2 and day["us_protest"] == 1 and day["us_fight"] == 1
    assert country["FR"][0] == 1
    assert names == {"HILLARY CLINTON": (2, 6)}   # FBI et ONCE sous le seuil de 2


def test_bibtex_and_citation():
    r = {"id": "doe2020x", "type": "article", "authors": ["Doe, Jane Marie", "Org Inc"], "year": 2020,
         "title": "A title", "container": "Journal", "volume": "3", "issue": "2", "pages": "1-9", "doi": "10.1/x"}
    bib = biblio.bibtex(r)
    assert bib.startswith("@article{doe2020x,") and "journal = {Journal}" in bib and "number = {2}" in bib
    cit = biblio.citation(r, "fr")
    assert cit["authors"] == "Doe, J. M. & Org Inc" and cit["loc"] == "3(2), 1-9"
    assert biblio.csl(r)["issued"] == {"date-parts": [[2020]]}


def test_verification_rate():
    from qanon.analysis.verification import rate
    items = [{"verdict": v} for v in ["fulfilled", "partial", "not_fulfilled", "not_fulfilled", "unverifiable"]]
    r = rate(items)
    assert r["checkable"] == 4 and r["rate"] == 0.25 and r["rate_with_partial"] == 0.5
    assert rate([{"verdict": "unverifiable"}])["rate"] is None


def test_chart_json_survives_script_tag():
    """Le JSON d'un graphe doit se relire tel quel depuis le texte brut du <script>."""
    import json
    import re

    from qanon.site.build import make_env
    spec = {"title": "l'\"année\" & </script><b>", "values": [1, 2]}
    html = make_env().from_string('{% from "macros.html" import chart %}{{ chart("x", spec, "T") }}').render(spec=spec)
    raw = re.search(r'<script type="application/json" data-chart="vis-x">(.*?)</script>', html, re.S).group(1)
    assert json.loads(raw) == spec


def test_wilson_interval():
    from qanon.analysis.verification import wilson
    lo, hi = wilson(39, 140)
    assert 0.20 < lo < 0.22 and 0.35 < hi < 0.37
    assert wilson(0, 0) == (None, None)


def test_changepoints_find_obvious_break():
    import numpy as np
    import pandas as pd

    from qanon.analysis.stats import changepoints
    rng = np.random.default_rng(0)
    start = pd.Timestamp("2018-01-01", tz="America/New_York")
    times = []
    for w in range(40):
        times += [start + pd.Timedelta(weeks=w, hours=int(h)) for h in rng.uniform(0, 160, 50 if w < 20 else 5)]
    d = pd.DataFrame({"et": sorted(times)})
    segs = changepoints(d)["segments"]
    assert len(segs) == 2 and segs[1]["start"] == "2018-05-21"


def test_burstiness_regular_vs_bursty():
    import pandas as pd

    from qanon.analysis.stats import rhythm
    regular = pd.DataFrame({"ts": pd.date_range("2018-01-01", periods=200, freq="h", tz="UTC")})
    assert rhythm(regular)["burstiness"] < -0.9

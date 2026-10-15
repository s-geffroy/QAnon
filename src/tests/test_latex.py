"""Export LaTeX du document de travail : conversions de base, puis document complet
construit a partir de l'etat reel (s'il existe) : citations connues, accolades
equilibrees, aucun caractere que pdflatex ne saurait composer."""
from pathlib import Path

import pytest

from qanon.site import biblio, latex


def test_inline_markup():
    s = latex.inline("**Données.** Un test *simple* [@a2020; @b2021] : 50 % & co_1, voir https://example.org/x_y.")
    assert s == (r"\textbf{Données.} Un test \emph{simple} \parencite{a2020,b2021} : 50 \% \& co\_1, voir "
                 r"\url{https://example.org/x_y}.")


def test_table_from_paper_html():
    html = ("<table class='paper-table'><caption>Tableau 9. Test &amp; essai.</caption><thead><tr><th>Nom</th>"
            "<th class='r'>n</th></tr></thead><tbody><tr><td>a_b</td><td class='r'>1 234</td></tr>"
            "<tr class='tot'><td>Ensemble</td><td class='r'>5</td></tr></tbody></table>")
    t = latex.table(html)
    assert r"\caption*{Tableau 9. Test \& essai.}" in t
    assert r"\begin{tabular}{lr}" in t and r"a\_b & 1 234 \\" in t
    assert r"\midrule" + "\n" + r"\textbf{Ensemble} & \textbf{5} \\" in t


def test_full_document_from_state():
    import sqlite3
    db = Path("/state/qanon.db")
    if not db.exists():
        pytest.skip("pas d'etat reel (conteneur jetable sans volume)")
    from qanon.site.build import Site
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    tex, figures = latex.build(Site(Path("/state"), conn))
    keys = {r["id"] for r in biblio.load()}
    assert latex.cited_keys(tex) <= keys, latex.cited_keys(tex) - keys
    assert tex.count("{") == tex.count("}") + tex.count(r"\{") - tex.count(r"\}")
    assert not latex.stray_unicode(tex), latex.stray_unicode(tex)
    assert "{val:" not in tex and "{table:" not in tex and "{figure:" not in tex
    assert set(figures) == {f"fig-{n}.pdf" for n in ("weekly", "horoscope", "overrep", "models")}
    assert all(b.startswith(b"%PDF") for b in figures.values())

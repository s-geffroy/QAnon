"""Typographie francaise des pages : espaces insecables dans le texte, jamais dans le code."""
from qanon.site import fmt


def test_fr_typo_text():
    assert fmt.fr_typo("Vrai ? Oui : « non » ; fin !") == "Vrai\u202f? Oui\u00a0: «\u00a0non\u00a0»\u202f; fin\u202f!"
    assert fmt.fr_typo("https://x.org a 10:30") == "https://x.org a 10:30"


def test_fr_html_skips_markup_and_code():
    h = ('<p title="a ?">Qui ? <a href="/b?c=1">lien</a> !</p><script>x = a ? b : c;</script>'
         '<pre>a ; b</pre><code>c ? d</code>')
    out = fmt.fr_html(h)
    assert '<p title="a ?">Qui\u202f? <a href="/b?c=1">lien</a>\u202f!</p>' in out
    assert "<script>x = a ? b : c;</script><pre>a ; b</pre><code>c ? d</code>" in out


def test_fr_html_chart_strings():
    h = '<script type="application/json" data-chart="vis-a">{"title":"Taux : bas ?","x":[1,2]}</script>'
    assert fmt.fr_html(h) == ('<script type="application/json" data-chart="vis-a">'
                              '{"title":"Taux\u00a0: bas\u202f?","x":[1,2]}</script>')


def test_fr_typo_operators():
    assert fmt.fr_typo("(p < 0,001, n = 140)") == "(p\u00a0<\u00a00,001, n\u00a0=\u00a0140)"
    assert fmt.fr_html("<p>(p &lt; 0,001)</p>") == "<p>(p\u00a0&lt;\u00a00,001)</p>"


def test_en_html_no_space_before_semicolon():
    assert fmt.en_html('<p>(Linvill et al., 2021 ; Papasavva, 2022)</p><code>a ; b</code>') == \
        '<p>(Linvill et al., 2021; Papasavva, 2022)</p><code>a ; b</code>'

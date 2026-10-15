"""Export LaTeX du document de travail, a partir de la meme source que la page et le PDF
(data/paper/paper-fr.md) : valeurs calculees inserees, tableaux en booktabs (convertis
depuis les tableaux HTML de paper_block, pour n'en garder qu'une definition), figures en
PDF vectoriel, citations biblatex (authoryear) vers bibliography.bib.

Sorties dans data/ : working-paper-fr.tex et working-paper-fr-latex.zip (tex, bib, figures,
mode d'emploi). Compilation : pdflatex, biber, pdflatex, pdflatex."""
import io
import re
import zipfile
from html.parser import HTMLParser

import yaml

from ..pipeline import APP_DIR
from . import biblio

_ESC = {"\\": r"\textbackslash{}", "{": r"\{", "}": r"\}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#",
        "_": r"\_", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}"}
# Caracteres hors du jeu de pdflatex (T1 + utf8) rencontres dans les textes et les valeurs.
UNICODE = {"202F": r"\,", "00A0": "~", "2009": r"\,", "2011": "-", "2212": r"\textminus{}", "00D7": r"\texttimes{}",
           "2264": r"\ensuremath{\leq}", "2265": r"\ensuremath{\geq}", "2248": r"\ensuremath{\approx}",
           "2192": r"\ensuremath{\rightarrow}", "2190": r"\ensuremath{\leftarrow}", "2194": r"\ensuremath{\leftrightarrow}",
           "03B1": r"\ensuremath{\alpha}", "03B2": r"\ensuremath{\beta}", "03B8": r"\ensuremath{\theta}",
           "03BB": r"\ensuremath{\lambda}", "03BC": r"\ensuremath{\mu}", "03C3": r"\ensuremath{\sigma}",
           "03C7": r"\ensuremath{\chi}", "0394": r"\ensuremath{\Delta}", "2032": r"\ensuremath{'}",
           "221E": r"\ensuremath{\infty}", "00B1": r"\ensuremath{\pm}", "2260": r"\ensuremath{\neq}"}


def esc(s):
    return re.sub(r"[\\{}&%$#_~^]", lambda m: _ESC[m.group(0)], s)


_INLINE = re.compile(r"\[(@[^\]]+)\]|\*\*(.+?)\*\*|(?<![*\w])\*(?!\s)(.+?)(?<!\s)\*(?![*\w])|(https?://[^\s)]+[^\s).,;:])")


def inline(s):
    """Texte Markdown d'un paragraphe -> LaTeX : citations, gras, italique, adresses."""
    out, pos = [], 0
    for m in _INLINE.finditer(s):
        out.append(esc(s[pos:m.start()]))
        if m.group(1):
            keys = [x.strip().lstrip("@") for x in m.group(1).split(";")]
            out.append(r"\parencite{" + ",".join(keys) + "}")
        elif m.group(2):
            out.append(r"\textbf{" + inline(m.group(2)) + "}")
        elif m.group(3):
            out.append(r"\emph{" + inline(m.group(3)) + "}")
        else:
            out.append(r"\url{" + m.group(4).replace("%", r"\%").replace("#", r"\#") + "}")
        pos = m.end()
    out.append(esc(s[pos:]))
    return "".join(out)


class _Table(HTMLParser):
    """Tableau HTML de paper_block : legende, en-tete (thead), lignes, cellules alignees a
    droite (class r), ligne de total (tr class tot)."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.caption, self.head, self.rows = "", [], []
        self._in_caption = self._in_head = self._tot = self._right = False
        self._row = self._cell = None

    def handle_starttag(self, tag, attrs):
        cls = (dict(attrs).get("class") or "").split()
        if tag == "caption":
            self._in_caption = True
        elif tag == "thead":
            self._in_head = True
        elif tag == "tr":
            self._row, self._tot = [], "tot" in cls
        elif tag in ("td", "th"):
            self._cell, self._right = "", "r" in cls

    def handle_endtag(self, tag):
        if tag == "caption":
            self._in_caption = False
        elif tag == "thead":
            self._in_head = False
        elif tag in ("td", "th") and self._cell is not None:
            self._row.append((self._cell.strip(), self._right))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            if self._in_head:
                self.head = self._row
            else:
                self.rows.append((self._row, self._tot))
            self._row = None

    def handle_data(self, data):
        if self._in_caption:
            self.caption += data
        elif self._cell is not None:
            self._cell += data


def table(html_text):
    if not html_text.strip():
        return ""
    t = _Table()
    t.feed(html_text)
    n = max(len(t.head), *(len(r) for r, _ in t.rows)) if t.rows else len(t.head)
    align = []
    for j in range(n):
        cells = [r[j][1] for r, _ in t.rows if j < len(r)]
        align.append("r" if cells and sum(cells) > len(cells) / 2 else "l")
    line = lambda cells, bold=False: " & ".join((r"\textbf{" + esc(c) + "}") if bold else esc(c) for c, _ in cells) + r" \\"
    body = []
    for r, tot in t.rows:
        if tot:
            body.append(r"\midrule")
        body.append(line(r, bold=tot))
    return "\n".join([r"\begin{table}[htbp]", r"\centering\small", r"\caption*{" + inline(t.caption.strip()) + "}",
                      r"\begin{adjustbox}{max width=\linewidth}", r"\begin{tabular}{" + "".join(align) + "}", r"\toprule",
                      line(t.head, bold=True), r"\midrule", *body, r"\bottomrule", r"\end{tabular}", r"\end{adjustbox}",
                      r"\end{table}"])


def unicode_decls():
    return "\n".join(f"\\DeclareUnicodeCharacter{{{k}}}{{{v}}}" for k, v in UNICODE.items())


PREAMBLE = r"""%% Document de travail genere par le worker qanon a partir de data/paper/paper-fr.md.
%% Ne pas le modifier a la main : le corriger dans le source, il est regenere a chaque build.
%% Compilation : pdflatex, biber, pdflatex, pdflatex (fichiers du zip dans un meme dossier).
\documentclass[11pt,a4paper]{article}
\usepackage[T1]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage{lmodern}
\usepackage{textcomp}
\usepackage[english,french]{babel}
\usepackage[a4paper,margin=25mm]{geometry}
\usepackage{microtype}
\usepackage{graphicx}
\usepackage{booktabs}
\usepackage{adjustbox}
\usepackage{caption}
\usepackage{csquotes}
\usepackage[backend=biber,style=authoryear,maxcitenames=2,uniquelist=false,uniquename=false]{biblatex}
\addbibresource{bibliography.bib}
\usepackage[hidelinks]{hyperref}
\usepackage{url}
"""


def build(site):
    """(texte LaTeX, {nom de figure: octets PDF}) ; None si le document n'existe pas."""
    from .build import paper_block, paper_fig
    import matplotlib.pyplot as plt
    path = APP_DIR / "data" / "paper" / "paper-fr.md"
    if not path.exists():
        return None
    _, front, body = path.read_text().split("---", 2)
    meta = yaml.safe_load(front)
    vals = site.paper_values()
    body = re.sub(r"\{val:([a-z0-9_]+)\}", lambda m: vals.get(m.group(1), ""), body)
    # Comme pour la page : un tableau ou une figure en tete de paragraphe forme son propre bloc.
    body = re.sub(r"\{(table|figure):([a-z0-9_]+)\}", lambda m: "\n\n" + m.group(0) + "\n\n", body)
    figures, parts = {}, []
    for block in re.split(r"\n\s*\n", body.strip()):
        block = block.strip()
        if not block:
            continue
        m = re.fullmatch(r"\{(table|figure):([a-z0-9_]+)\}", block)
        if m and m.group(1) == "table":
            parts.append(table(paper_block(site, "table", m.group(2))))
        elif m:
            fig, cap = paper_fig(site, m.group(2))
            buf = io.BytesIO()
            fig.savefig(buf, format="pdf")
            plt.close(fig)
            figures[f"fig-{m.group(2)}.pdf"] = buf.getvalue()
            parts.append("\n".join([r"\begin{figure}[htbp]", r"\centering",
                                    rf"\includegraphics[width=\linewidth]{{fig-{m.group(2)}.pdf}}",
                                    r"\caption*{\small " + inline(cap) + "}", r"\end{figure}"]))
        elif block.startswith("### "):
            parts.append(r"\subsection*{" + inline(block[4:]) + "}")
        elif block.startswith("## "):
            parts.append(r"\section*{" + inline(block[3:]) + "}")
        else:
            parts.append(inline(" ".join(block.split("\n"))))
    from .build import SITE_URL, ZENODO_CONCEPT
    head = "\n".join([
        PREAMBLE + unicode_decls(),
        r"\title{" + inline(meta["title"]) + r"\\[4pt]\large " + inline(meta.get("subtitle", "")) + "}",
        r"\author{" + inline(meta["author"]) + "}",
        r"\date{" + inline(f"{meta.get('version', '')} · {meta.get('date', '')}") + "}",
        r"\begin{document}", r"\maketitle",
        r"\begin{center}\small " + r"\url{" + SITE_URL + "} · doi:" + esc(ZENODO_CONCEPT) + r" · Licence CC BY 4.0\end{center}",
        r"\begin{abstract}\begin{otherlanguage}{english}\noindent\textbf{Abstract.} " + inline(meta["abstract_en"].strip())
        + r"\end{otherlanguage}\end{abstract}"])
    tex = head + "\n\n" + "\n\n".join(p for p in parts if p) + "\n\n" + \
        r"\printbibliography[title={Références}]" + "\n" + r"\end{document}" + "\n"
    return tex, figures


README = """Document de travail « Les drops de Q a l'epreuve des faits » : version LaTeX.

Genere automatiquement a partir de data/paper/paper-fr.md (depot s-geffroy/QAnon) ; les
chiffres, tableaux et figures sont ceux du dernier calcul. Licence CC BY 4.0.

Compilation (TeX Live ou MiKTeX, avec biber) :
  pdflatex working-paper-fr
  biber working-paper-fr
  pdflatex working-paper-fr
  pdflatex working-paper-fr
"""


def write(site, d):
    """Ecrit data/working-paper-fr.tex et data/working-paper-fr-latex.zip ; vrai si fait."""
    res = build(site)
    if not res:
        return False
    tex, figures = res
    (d / "working-paper-fr.tex").write_text(tex)
    with zipfile.ZipFile(d / "working-paper-fr-latex.zip", "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("working-paper-fr.tex", tex)
        z.writestr("bibliography.bib", biblio.bibfile())
        z.writestr("LISEZMOI.txt", README)
        for name, data in figures.items():
            z.writestr(name, data)
    return True


def cited_keys(tex):
    return {k.strip() for g in re.findall(r"\\parencite\{([^}]*)\}", tex) for k in g.split(",")}


def stray_unicode(tex):
    """Caracteres que pdflatex (T1 + utf8) ne sait pas composer : ni Latin-1, ni typographie
    courante, ni declares dans UNICODE."""
    ok = set(map(chr, range(0x20, 0x7F))) | set(map(chr, range(0xA0, 0x180))) | {"\n", "\t"} | \
        set("«»‘’“”–—…•€œŒ") | {chr(int(k, 16)) for k in UNICODE}
    return sorted({c for c in tex if c not in ok})


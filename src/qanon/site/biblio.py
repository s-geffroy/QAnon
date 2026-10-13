"""Bibliographie : mise en forme (style auteur-date) et exports BibTeX / CSL-JSON."""
import json
import re

from ..analysis.common import load_yaml

TYPE_ORDER = ["article", "conference", "book", "chapter", "report", "thesis", "primary", "journalism",
              "documentary", "dataset"]
BIBTEX_TYPE = {"article": "article", "conference": "inproceedings", "book": "book", "chapter": "incollection",
               "report": "techreport", "thesis": "phdthesis", "primary": "misc", "journalism": "misc",
               "documentary": "misc", "dataset": "misc"}
CSL_TYPE = {"article": "article-journal", "conference": "paper-conference", "book": "book", "chapter": "chapter",
            "report": "report", "thesis": "thesis", "primary": "document", "journalism": "article-newspaper",
            "documentary": "motion_picture", "dataset": "dataset"}


def load():
    refs = load_yaml("bibliography", "references")
    return sorted(refs, key=lambda r: (TYPE_ORDER.index(r["type"]) if r["type"] in TYPE_ORDER else 99,
                                       -int(r.get("year") or 0), (r.get("authors") or [""])[0]))


def authors_text(names, lang):
    if not names:
        return ""
    def short(n):
        if "," not in n:
            return n
        last, first = [x.strip() for x in n.split(",", 1)]
        initials = " ".join(f"{p[0]}." for p in re.split(r"[\s\-]+", first) if p)
        return f"{last}, {initials}"
    names = [short(n) for n in names]
    if len(names) > 6:
        return f"{', '.join(names[:6])} et al." if lang == "fr" else f"{', '.join(names[:6])}, et al."
    if len(names) == 1:
        return names[0]
    amp = " & "
    return ", ".join(names[:-1]) + amp + names[-1]


def citation(r, lang):
    """Reference en style auteur-date (proche APA), en texte brut + morceaux pour le gabarit."""
    year = r.get("date") or r.get("year") or "s.d."
    parts = {"authors": authors_text(r.get("authors", []), lang), "year": str(year)[:4] if not r.get("date") else r["date"],
             "title": r["title"], "container": r.get("container"), "publisher": r.get("publisher")}
    loc = []
    if r.get("volume"):
        loc.append(str(r["volume"]) + (f"({r['issue']})" if r.get("issue") else ""))
    if r.get("pages"):
        loc.append(str(r["pages"]))
    parts["loc"] = ", ".join(loc)
    if r.get("editors") and not r.get("authors"):
        n = len(r["editors"])
        parts["authors"] = f"{authors_text(r['editors'], lang)} ({'dir.' if lang == 'fr' else ('Ed.' if n == 1 else 'Eds.')})"
    elif r.get("editors") and r.get("container"):
        eds = authors_text(r["editors"], lang)
        label = ("dir." if lang == "fr" else ("Ed." if len(r["editors"]) == 1 else "Eds."))
        parts["container"] = f"{'Dans' if lang == 'fr' else 'In'} {eds} ({label}), {r['container']}"
    return parts


def bibtex(r):
    t = BIBTEX_TYPE.get(r["type"], "misc")
    f = {"author": " and ".join(r.get("authors", [])), "title": "{" + r["title"] + "}", "year": r.get("year")}
    if r["type"] == "article":
        f["journal"] = r.get("container")
    elif r["type"] in ("conference", "chapter"):
        f["booktitle"] = r.get("container")
    elif r["type"] in ("report",):
        f["institution"] = r.get("publisher") or r.get("container")
    elif r["type"] == "thesis":
        f["school"] = r.get("publisher") or r.get("container")
    else:
        f["howpublished"] = r.get("container")
    for k in ("volume", "pages", "publisher", "doi", "url"):
        if r.get(k) and k not in f:
            f["number" if k == "issue" else k] = r[k]
    if r.get("issue"):
        f["number"] = r["issue"]
    if r.get("editors"):
        f["editor"] = " and ".join(r["editors"])
    if r.get("date"):
        f["date"] = r["date"]
    f["langid"] = {"en": "english", "fr": "french", "de": "german", "es": "spanish", "it": "italian", "nl": "dutch",
                 "pt": "portuguese", "ja": "japanese", "cs": "czech"}.get(r.get("lang"), r.get("lang"))
    body = ",\n".join(f"  {k} = {{{v}}}" for k, v in f.items() if v)
    return f"@{t}{{{r['id']},\n{body}\n}}"


def csl(r):
    def person(n):
        if "," in n:
            fam, giv = [x.strip() for x in n.split(",", 1)]
            return {"family": fam, "given": giv}
        return {"literal": n}
    date = r.get("date") or str(r.get("year") or "")
    item = {"id": r["id"], "type": CSL_TYPE.get(r["type"], "document"), "title": r["title"],
            "author": [person(n) for n in r.get("authors", [])],
            "editor": [person(n) for n in r.get("editors", [])] or None,
            "issued": {"date-parts": [[int(x) for x in str(date).split("-") if x.isdigit()]]} if date else None,
            "container-title": r.get("container"), "publisher": r.get("publisher"), "volume": r.get("volume"),
            "issue": r.get("issue"), "page": r.get("pages"), "DOI": r.get("doi"), "URL": r.get("url"),
            "language": r.get("lang")}
    return {k: v for k, v in item.items() if v}


def export(out_dir, refs):
    (out_dir / "bibliography.bib").write_text("\n\n".join(bibtex(r) for r in refs) + "\n")
    (out_dir / "bibliography.json").write_text(json.dumps([csl(r) for r in refs], ensure_ascii=False, indent=1))

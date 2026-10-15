"""Le fichier BibTeX du depot (src/data/bibliography.bib) suit la bibliographie."""
import re

from qanon.pipeline import APP_DIR
from qanon.site import biblio


def test_bib_file_is_up_to_date():
    path = APP_DIR / "data" / "bibliography.bib"
    assert path.read_text() == biblio.bibfile(), (
        "bibliography.bib en retard sur bibliography.yaml : "
        "sudo appctl run worker sh -c 'cd /app && python3 -m qanon.site.biblio' > src/data/bibliography.bib")


def test_bib_entries_are_well_formed():
    text = biblio.bibfile()
    entries = re.findall(r"^@(\w+)\{([^,\s]+),\n(.*?)\n\}$", text, re.S | re.M)
    refs = biblio.load()
    assert len(entries) == len(refs) and len({k for _, k, _ in entries}) == len(refs)
    for kind, key, body in entries:
        assert body.count("{") == body.count("}"), key
        assert not re.search(r"(?<!\\)&", re.sub(r"(?m)^  (?:url|doi) = .*$", "", body)), key


def test_tex_escaping():
    assert biblio.tex("Culture & Society 100% #1 a_b") == r"Culture \& Society 100\% \#1 a\_b"
    assert biblio.tex(r"already \& escaped") == r"already \& escaped"

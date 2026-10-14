"""Lexique de la scene complotiste (data/scene.yaml), avec le glossaire et les
acteurs repris par reference, et son application rapide a de grands corpus.

Un post est d'abord passe au crible d'un automate d'Aho-Corasick (mots-cles
minuscules derives des motifs) ; seuls les motifs dont un mot-cle est present
sont ensuite evalues. Un motif dont on ne sait pas deriver de mot-cle est
evalue sur tous les posts (cas a eviter : signale par les tests)."""
import re
import re._constants as C
import re._parser as P
from dataclasses import dataclass, field

import yaml

from . import db
from .pipeline import APP_DIR

MIN_ANCHOR = 3


@dataclass
class Term:
    id: str
    family: str
    source: str               # scene | glossary | actor
    pattern: str
    label_fr: str = ""
    label_en: str = ""
    ambiguous: bool = False
    sensitive: bool = False
    trends: bool = False
    trends_query: str = ""
    pos: list = field(default_factory=list)
    neg: list = field(default_factory=list)
    rx: re.Pattern = None
    anchors: tuple = ()       # mots-cles explicites (scene.yaml), sinon derives du motif


# ------------------------------------------------------------------ mots-cles
def _anchors(items, icase):
    """Ensemble de chaines (minuscules) dont l'une au moins doit figurer dans toute
    correspondance de la sequence `items` ; None si on ne sait pas le garantir."""
    best, run = None, ""

    def consider(cands):
        nonlocal best
        if cands and (best is None or min(map(len, cands)) > min(map(len, best))):
            best = cands

    for op, av in items:
        if op is C.LITERAL:
            run += chr(av)
            continue
        consider({run.lower()} if run else None)
        run = ""
        if op is C.SUBPATTERN:
            _, add, _, sub = av
            consider(_anchors(sub, icase or bool(add & C.SRE_FLAG_IGNORECASE)))
        elif op is C.BRANCH:
            alts = [_anchors(b, icase) for b in av[1]]
            if all(alts):
                consider(set().union(*alts))
        elif op in (C.MAX_REPEAT, C.MIN_REPEAT) and av[0] >= 1:
            consider(_anchors(av[2], icase))
        elif op is C.AT or op in (C.ASSERT, C.ASSERT_NOT):
            continue
    consider({run.lower()} if run else None)
    return best


def anchors(pattern):
    a = _anchors(P.parse(pattern), False)
    if not a or min(map(len, a)) < 2:
        return ()
    return tuple(sorted(a))


# ------------------------------------------------------------------ chargement
def _scoped(pattern):
    """'(?i)motif' -> '(?i:motif)' : les drapeaux globaux sont interdits au milieu
    d'une alternance (et pour combiner des motifs)."""
    m = re.match(r"^\(\?([aiLmsux]+)\)", pattern)
    return f"(?{m.group(1)}:{pattern[m.end():]})" if m else pattern


_CODE = re.compile(r"^[A-Z0-9_ .+-]{1,2}$")


def actor_name_patterns(patterns, excluded=()):
    """Motifs de noms d'un acteur, sans les codes courts propres a Q (JC, SA, NK, D's...),
    sans les mots exclus (scene.yaml : actor_codes_excluded) ni les motifs qui
    dependent du contexte des drops (lookbehind sur '>')."""
    out = []
    for p in patterns:
        if "(?<=>" in p or "\\bnon " in p:
            continue
        core = re.sub(r"\(\?<?[=!][^()]*\)", "", p).replace("\\b", "")
        core = re.sub(r"\[[^\]]*\]", "", core).replace("\\", "").strip()
        # Codes de deux signes (JC, SA, NK, AM, D's...) : propres a Q. Les sigles (FBI, CIA) restent.
        if _CODE.match(core) or len(core) < 3 or core in excluded:
            continue
        out.append(p)
    return out


def _yaml(name):
    path = APP_DIR / "data" / f"{name}.yaml"
    return yaml.safe_load(path.read_text()) if path.exists() else {}


def load():
    scene = _yaml("scene")
    gl_amb = set(scene.get("glossary_ambiguous", []))
    terms = []
    for g in _yaml("glossary").get("terms", []):
        terms.append(Term(id=f"gl:{g['id']}", family="glossary", source="glossary", pattern=g["pattern"],
                          label_fr=g.get("term", g["id"]), label_en=g.get("term", g["id"]),
                          ambiguous=g["id"] in gl_amb))
    for a in _yaml("actors").get("actors", []):
        pats = actor_name_patterns(a["patterns"], set(scene.get("actor_codes_excluded", [])))
        if pats:
            terms.append(Term(id=f"actor:{a['id']}", family=f"actor:{a['category']}", source="actor",
                              pattern="|".join(f"(?:{p})" for p in pats), label_fr=a["name"], label_en=a["name"]))
    for t in scene.get("terms", []):
        terms.append(Term(source="scene", **{k: v for k, v in t.items() if k != "note"}))
    for t in terms:
        t.rx = re.compile(_scoped(t.pattern))
        t.anchors = tuple(a.lower() for a in t.anchors) or anchors(_scoped(t.pattern))
    return terms


def fingerprint(terms):
    """Empreinte du lexique (ids et motifs) : c'est elle qu'on approuve avant le balayage de /pol/."""
    return db.sha(*sorted(f"{t.id}\t{t.pattern}" for t in terms))[:16]


# ------------------------------------------------------------------ application
class Matcher:
    def __init__(self, terms):
        import ahocorasick
        self.terms = terms
        self.always = [i for i, t in enumerate(terms) if not t.anchors]
        self.A = ahocorasick.Automaton()
        index = {}
        for i, t in enumerate(terms):
            for a in t.anchors:
                index.setdefault(a, []).append(i)
        for a, ids in index.items():
            self.A.add_word(a, tuple(ids))
        if index:
            self.A.make_automaton()
        self.empty = not index

    def candidates(self, text):
        cand = set(self.always)
        if not self.empty:
            for _, ids in self.A.iter(text.lower()):
                cand.update(ids)
        return cand

    def hits(self, text):
        """Indices des termes presents dans le texte."""
        if not text:
            return []
        return [i for i in self.candidates(text) if self.terms[i].rx.search(text)]

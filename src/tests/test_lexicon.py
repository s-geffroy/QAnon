"""Lexique de la scene : chaque motif compile, a ses mots-cles, et respecte ses
exemples ; le crible d'Aho-Corasick ne perd aucune correspondance."""
import pytest

from qanon import lexicon

TERMS = lexicon.load()
SCENE = [t for t in TERMS if t.source == "scene"]


def test_ids_unique_and_families_known():
    import yaml
    from qanon.pipeline import APP_DIR
    fams = set(yaml.safe_load((APP_DIR / "data" / "scene.yaml").read_text())["families"])
    ids = [t.id for t in TERMS]
    assert len(ids) == len(set(ids))
    assert {t.family for t in SCENE} <= fams
    assert all(t.label_fr and t.label_en for t in SCENE)


@pytest.mark.parametrize("t", SCENE, ids=lambda t: t.id)
def test_examples(t):
    assert t.pos and t.neg, "exemples manquants"
    for s in t.pos:
        assert t.rx.search(s), f"{t.id} devrait reconnaitre {s!r}"
    for s in t.neg:
        assert not t.rx.search(s), f"{t.id} ne devrait pas reconnaitre {s!r}"


def test_every_term_has_anchors():
    missing = [t.id for t in TERMS if not t.anchors]
    assert not missing, missing


def test_prefilter_loses_nothing():
    m = lexicon.Matcher(TERMS)
    for t in SCENE:
        for s in t.pos + t.neg:
            brute = {i for i, u in enumerate(TERMS) if u.rx.search(s)}
            assert set(m.hits(s)) == brute, (t.id, s)


def test_actor_codes_are_dropped():
    assert lexicon.actor_name_patterns([r"\bJC\b", r"(?<!/)\bComey\b", r"\bCOMEY\b", r"\bAM\b(?! ET| EST)",
                                        r"(?<=>)Page\b", r"\bSA\b", r"\bD['’]s\b", r"\bFBI\b"]) == \
        [r"(?<!/)\bComey\b", r"\bCOMEY\b", r"\bFBI\b"]
    assert lexicon.actor_name_patterns([r"\bMIL\b", r"\bUSMC\b"], {"MIL"}) == [r"\bUSMC\b"]


def test_anchor_derivation():
    assert lexicon.anchors(r"(?i:\bpizza ?gate\b)") == ("pizza",)
    assert set(lexicon.anchors(r"\bfoo\b|\bbarbaz\b")) == {"foo", "barbaz"}
    assert lexicon.anchors(r"\b\w+\b") == ()


def test_pol_scan_fingerprint_unchanged():
    """Un terme ajoute apres le balayage de /pol/ doit porter post_scan : sinon l'empreinte
    approuvee change, et le balayage attend une nouvelle approbation puis efface ses tables."""
    import yaml
    from qanon.pipeline import APP_DIR
    doc = yaml.safe_load((APP_DIR / "data" / "scene.yaml").read_text())
    assert lexicon.fingerprint(lexicon.scanned(TERMS)) == doc["lexicon_approved"]

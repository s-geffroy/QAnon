"""/pol/ : conversion du HTML, lecture du flux, calibration sur une petite archive synthetique."""
import io
import json
import tarfile

import zstandard

from qanon import db
from qanon.sources import pol


def make_archive(path, threads):
    raw = io.BytesIO()
    data = "\n".join(json.dumps({"posts": t}) for t in threads).encode() + b"\n"
    with tarfile.open(fileobj=raw, mode="w") as tf:
        info = tarfile.TarInfo("pol.ndjson")
        info.size = len(data)
        tf.addfile(info, io.BytesIO(data))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(zstandard.ZstdCompressor().compress(raw.getvalue()))


def post(no, t, com, sub=None, trip=None):
    """Post au format reel de l'archive (verifie sur le fichier Zenodo) : no et time entiers,
    entites en liste de dicts, parfois sous la cle mal orthographiee « entitites »,
    perspectives en dict ou [] quand elles manquent, tripcode dans « trip »."""
    p = {"no": no, "time": t, "com": com, "perspectives": [] if no % 10 == 3 else {"TOXICITY": 0.5}}
    p["entitites" if no % 4 == 3 else "entities"] = [
        {"entity_text": "Soros", "entity_start": 0, "entity_end": 5, "entity_label": "PERSON"}]
    if sub:
        p = {"sub": sub, **p}
    if trip:
        p["trip"] = trip
    return p


def test_text_of_and_thread_time():
    assert pol.text_of('Calm<br>before &gt;&gt;123 <span class="quote">&gt;the storm</span>') == \
        "Calm\nbefore >>123 >the storm"
    line = json.dumps({"posts": [{"archived_on": 1509300000, "no": 1, "time": 1509200000, "tim": 1509200000123}]}).encode()
    assert pol.thread_time(line) == 1509200000
    assert pol.thread_time(b'{"posts": [{"no": "1", "time": "1509200000"}]}') == 1509200000


def test_fields_of_real_archive():
    assert pol.entities_of({"entitites": [{"entity_text": "Q", "entity_label": "PERSON"}]}) == [("Q", "PERSON")]
    assert pol.entities_of({"entities": "[{'entity_text': 'Q', 'entity_start': 0, 'entity_label': 'ORG'}]"}) == [("Q", "ORG")]
    assert pol.entities_of({}) == []
    assert pol.perspectives_of({"perspectives": {"TOXICITY": 0.25}}) == [("TOXICITY", 0.25)]
    assert pol.perspectives_of({"perspectives": []}) == []


def test_q_tripcode_enters_qcorpus():
    from qanon import lexicon
    terms = lexicon.load()
    acc = pol.Scan()
    posts = [post(10, 1509200000, "nothing here"), post(11, 1509200060, "plain words", trip="!ITPb.qbhqo")]
    pol.process_thread(posts, terms, lexicon.Matcher(terms), set(), set(), acc, {"!ITPb.qbhqo"})
    assert [(r[1], r[6]) for r in acc.qcorpus] == [("11", "post:q_trip")]


class Ctx:
    def __init__(self, state):
        self.state, self.cursor, self.out, self.n = state, None, None, 0

    def should_yield(self):
        self.n += 1
        return self.n % 3 == 0

    def save_cursor(self, v):
        self.cursor = v

    def set_output(self, v):
        self.out = v


def test_calibration_resumes(tmp_path):
    threads = []
    for i in range(900):
        t = 1490000000 + i * 1000 if i < 600 else 1509200000 + i     # 600 fils avant, 300 dans la naissance de Q
        threads.append([post(i, t, "WWG1WGA trust the plan" if i % 2 else "nothing", sub="CBTS general" if i == 650 else None)])
    threads.append([post(99999, 1515000000, "after")] )
    make_archive(tmp_path / "cache" / "pol" / "pol.tar.zst", threads)
    ctx = Ctx(tmp_path)
    ctx.conn = db.connect(tmp_path / "t.db")
    for _ in range(500):
        pol._streams.clear() if ctx.n % 7 == 0 else None    # redemarrages simules
        if pol.run_calibrate(ctx) is True:
            break
    st = json.loads(pol.calib_path(tmp_path).read_text())
    assert st["threads"]["birth"] == 300 and st["threads"]["sample"] == 600 // pol.CAL_SAMPLE
    assert st["terms"]["gl:wwg1wga"]["birth"] == 150
    assert st["terms"]["cbts"]["birth"] == 1
    assert 1 <= len(st["terms"]["gl:wwg1wga"]["ex"]) <= pol.N_EX


def _threads(n_threads=3000):
    out = []
    for i in range(n_threads):
        t = 1490000000 + i * 3600 * 7          # ~2,4 ans, presque chronologique
        posts = [post(i * 10, t, "WWG1WGA trust the plan, the storm is coming" if i % 3 == 0 else "Soros owns the banks",
                      sub="CBTS general" if i % 500 == 0 else None)]
        posts += [post(i * 10 + k, t + k * 60, f"reply {k} about the deep state") for k in range(1, 4)]
        out.append(posts)
    return out


def _scan_all(tmp_path, monkeypatch, restarts):
    from qanon import lexicon
    monkeypatch.setattr(pol, "approved", lambda terms: True)
    monkeypatch.setattr(pol, "CHECKPOINT", 400)
    archive = tmp_path / "cache" / "pol" / "pol.tar.zst"
    make_archive(archive, _threads())
    conn = db.connect(tmp_path / "t.db")

    class C(Ctx):
        def __init__(self):
            super().__init__(tmp_path)
            self.conn = conn
        def save_cursor(self, v):
            self.cursor = v
            conn.commit()
    ctx = C()
    pol._streams.clear()
    pol._scan.update(acc=None, ckpt=None)
    for k in range(3000):
        if restarts and k % 5 == 4:          # redemarrage : memoire perdue
            pol._streams.clear()
            pol._scan.update(acc=None, ckpt=None)
        if pol.run_scan(ctx) is True:
            break
    q = lambda sql: [tuple(r) for r in conn.execute(sql).fetchall()]
    return {"total": q("SELECT sum(posts), sum(threads) FROM pol_hour_total"),
            "terms": q("SELECT term, sum(n) FROM pol_hour GROUP BY term ORDER BY term"),
            "uni": q("SELECT token, sum(n) FROM pol_unigram_month GROUP BY token ORDER BY token"),
            "q": q("SELECT count(*), count(DISTINCT reason) FROM pol_qcorpus"),
            "sample": q("SELECT count(*) FROM pol_sample"),
            "tox": q("SELECT scope, sum(n) FROM pol_tox_day GROUP BY scope ORDER BY scope"),
            "ent": q("SELECT sum(n) FROM pol_entity_month"),
            "first": q("SELECT term, ts FROM pol_first ORDER BY term")}


def test_scan_layers_identical_with_restarts(tmp_path, monkeypatch):
    a = _scan_all(tmp_path / "a", monkeypatch, restarts=False)
    b = _scan_all(tmp_path / "b", monkeypatch, restarts=True)
    assert a == b
    assert a["total"] == [(12000, 3000)]
    terms = dict(a["terms"])
    assert terms["gl:wwg1wga"] == 1000 and terms["actor:soros"] == 2000
    assert dict(a["uni"])["reply"] == 9000
    assert a["sample"] == [(len([n for n in range(30000) if n % 100 == 0 and n % 10 < 4]),)]
    assert dict(a["tox"])["all"] == 9000          # les 3000 posts sans perspectives ([]) ne comptent pas
    assert a["ent"] == [(12000,)]


def test_onset_ignores_isolated_hits_and_finds_sustained_rise():
    """Date d'apparition : une occurrence isolee avant Q (« I got a Q anons ») ne compte pas ;
    la premiere semaine anormale et durable, si."""
    import pandas as pd
    from qanon.analysis import polscene
    weeks = pd.date_range("2017-01-02", periods=60, freq="W-MON").strftime("%Y-%m-%d")
    posts = pd.Series(800_000, index=weeks)
    counts = pd.Series(0, index=weeks)
    counts.iloc[5] = 1                       # occurrence isolee
    counts.iloc[50] = 3                      # semaine faible, non confirmee
    counts.iloc[52:56] = [40, 25, 30, 20]    # naissance durable
    on, lam = polscene.onset(counts, posts, base_end=weeks[45])
    assert on == weeks[52]
    assert polscene.onset(pd.Series(0, index=weeks), posts, base_end=weeks[45])[0] is None


def test_keyness_drops_sensitive_and_address_tokens():
    import sqlite3
    from qanon import lexicon
    from qanon.analysis import polscene
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE pol_unigram_month (month TEXT, token TEXT, n INTEGER)")
    conn.executemany("INSERT INTO pol_unigram_month VALUES ('2018-01', ?, ?)",
                     [("the", 10_000_000), ("bread", 2_000), ("http", 500_000), ("zog", 1_000)])
    tok = {"the": 50_000, "bread": 9_000, "http": 30_000, "zog": 5_000}
    top = [x["token"] for x in polscene.keyness(conn, tok, lexicon.load())["top"]]
    assert top[0] == "bread" and "http" not in top and "zog" not in top

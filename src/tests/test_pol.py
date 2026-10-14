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


def post(no, t, com, sub=None):
    p = {"no": str(no), "time": str(t), "com": com, "entities": "[]", "perspectives": "{'TOXICITY': 0.5}"}
    if sub:
        p = {"sub": sub, **p}
    return p


def test_text_of_and_thread_time():
    assert pol.text_of('Calm<br>before &gt;&gt;123 <span class="quote">&gt;the storm</span>') == \
        "Calm\nbefore >>123 >the storm"
    line = json.dumps({"posts": [post(1, 1509200000, "x")]}).encode()
    assert pol.thread_time(line) == 1509200000


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
    assert dict(a["tox"])["all"] == 12000

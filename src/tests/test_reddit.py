"""Collecte Reddit (API simulee) : echantillon d'un jour, et comptage du lexique."""
from qanon import db
from qanon.sources import reddit


class Ctx:
    def __init__(self, conn):
        self.conn, self.cursor, self.out = conn, None, None

    def save_cursor(self, v):
        self.cursor = v
        self.conn.commit()

    def should_yield(self):
        return False

    def set_output(self, v):
        self.out = v


def fake_get(path, **p):
    if path == "/comments/search":
        if p["after"] % 86400 == 0:   # premier creneau : plein (100), donc echantillon incomplet
            return ([{"id": f"c{i}", "created_utc": p["after"] + i, "author": "x", "body": "WWG1WGA trust the plan"}
                     for i in range(98)]
                    + [{"id": "gone", "created_utc": p["after"], "author": "x", "body": "[removed]"},
                       {"id": "bot", "created_utc": p["after"], "author": "AutoModerator", "body": "rules"}])
        return [{"id": f"d{p['after']}", "created_utc": p["after"], "author": "y", "body": "nothing here"}]
    return [{"id": f"p{p['after']}", "created_utc": p["after"], "author": "z", "title": "Q drop decoded",
             "selftext": "[removed]"}]


def test_sample_day_and_scan(tmp_path, monkeypatch):
    conn = db.connect(tmp_path / "t.db")
    monkeypatch.setattr(reddit, "get", fake_get)
    reddit.sample_day(conn, "greatawakening", "2018-03-01")
    conn.commit()
    c = conn.execute("SELECT * FROM reddit_sample_day WHERE kind = 'comments'").fetchone()
    assert (c["n_sampled"], c["n_gone"], c["n_bots"], c["complete"]) == (100, 1, 1, 0)
    p = conn.execute("SELECT * FROM reddit_sample_day WHERE kind = 'posts'").fetchone()
    assert p["n_sampled"] == 2 and p["complete"] == 1
    assert conn.execute("SELECT text FROM reddit_sample WHERE kind = 'posts'").fetchone()[0] == "Q drop decoded"
    ctx = Ctx(conn)
    assert reddit.run_scan(ctx) is True
    n = dict(conn.execute("SELECT term, sum(n) FROM reddit_term_day GROUP BY term").fetchall())
    assert n["gl:wwg1wga"] == 98 and n["gl:trust-the-plan"] == 98 and n["q_drop_term"] == 2
    # Rejoue sans nouvel element : rien ne change ; lexique different : tout est recompte.
    reddit.run_scan(ctx)
    assert dict(conn.execute("SELECT term, sum(n) FROM reddit_term_day GROUP BY term").fetchall()) == n
    ctx.cursor = "autre:999"
    reddit.run_scan(ctx)
    assert dict(conn.execute("SELECT term, sum(n) FROM reddit_term_day GROUP BY term").fetchall()) == n


def test_retry_then_give_up(monkeypatch):
    calls = []

    def busy(path, **p):
        calls.append(1)
        raise reddit.Busy("422")
    monkeypatch.setattr(reddit, "get", busy)
    import pytest
    with pytest.raises(reddit.Busy):
        reddit.get_retry("/x", lambda s: True)
    assert len(calls) == reddit.RETRIES
    calls.clear()
    with pytest.raises(reddit.Busy):
        reddit.get_retry("/x", lambda s: False)   # budget epuise : pas de nouvel essai
    assert len(calls) == 1

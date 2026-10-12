"""Drops de Q : dataset Kaggle jkingsman/qanondrops (agrege depuis qanon.pub)."""
import json

from .. import db
from ..log import log
from .kaggle import download

HANDLE = "jkingsman/qanondrops"


def run(ctx):
    path = download(ctx, HANDLE) / "posts.json"
    raw = path.read_bytes()
    digest = db.sha(raw)
    if db.get_meta(ctx.conn, "out:fetch_qdrops") == digest:
        return True
    posts = json.loads(raw)["posts"]
    rows = []
    for p in posts:
        m = p["post_metadata"]
        src = m.get("source") or {}
        refs = p.get("referenced_posts") or []
        rows.append((
            m["id"], m.get("post_id"), (m.get("author") or "").strip(), m.get("author_id"),
            m.get("tripcode"), src.get("site"), src.get("board"), src.get("link"), m["time"],
            p.get("text") or "", len(p.get("images") or []), len(refs),
            json.dumps(refs, ensure_ascii=False) if refs else None,
        ))
    ctx.conn.execute("DELETE FROM drops")
    ctx.conn.executemany("INSERT INTO drops VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
    ctx.set_output(digest)
    log(f"drops : {len(rows)} charges depuis {HANDLE}")
    return True

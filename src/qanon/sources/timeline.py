"""Chronologie curee : data/timeline.yaml, versionnee dans Git."""
import yaml

from .. import db
from ..log import log
from ..pipeline import APP_DIR

PATH = APP_DIR / "data" / "timeline.yaml"


def run(ctx):
    raw = PATH.read_bytes()
    events = yaml.safe_load(raw)["events"]
    rows = []
    for e in events:
        date = str(e["date"])
        rows.append((f"{date}-{e['id']}", date, e["category"], e["fr"], e["en"], e.get("source")))
    ctx.conn.execute("DELETE FROM events")
    ctx.conn.executemany("INSERT INTO events VALUES (?,?,?,?,?,?)", rows)
    ctx.set_output(db.sha(raw))
    log(f"chronologie : {len(rows)} evenements")
    return True

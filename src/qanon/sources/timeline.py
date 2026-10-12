"""Chronologie curee : data/timeline.yaml, versionnee dans Git."""
import json

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
        meta = {k: str(e[f"source_{k}"]) for k in ("outlet", "date", "title") if e.get(f"source_{k}")}
        rows.append((f"{date}-{e['id']}", date, e["category"], e["fr"], e["en"], e.get("source"),
                     json.dumps(meta, ensure_ascii=False) if meta else None))
    ctx.conn.execute("DELETE FROM events")
    ctx.conn.executemany("INSERT INTO events (id, date, category, label_fr, label_en, source, source_meta) "
                         "VALUES (?,?,?,?,?,?,?)", rows)
    ctx.set_output(db.sha(raw))
    log(f"chronologie : {len(rows)} evenements")
    return True

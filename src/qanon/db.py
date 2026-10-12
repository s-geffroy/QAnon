"""Base SQLite de l'etude, dans le volume /state."""
import hashlib
import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);

-- Etat du pipeline : une ligne par etape, ecrite apres chaque lot.
CREATE TABLE IF NOT EXISTS stages (
    name        TEXT PRIMARY KEY,
    fingerprint TEXT,          -- empreinte des entrees au dernier succes complet
    cursor      TEXT,          -- avancement d'une etape incrementale
    done        INTEGER NOT NULL DEFAULT 0,
    failures    INTEGER NOT NULL DEFAULT 0,
    retry_at    INTEGER NOT NULL DEFAULT 0,
    last_error  TEXT,
    updated_at  INTEGER
);

CREATE TABLE IF NOT EXISTS drops (
    id          INTEGER PRIMARY KEY,   -- ordinal du dataset (1 = le plus ancien)
    post_id     TEXT,
    author      TEXT,
    author_id   TEXT,
    tripcode    TEXT,
    site        TEXT,
    board       TEXT,
    link        TEXT,
    time        INTEGER NOT NULL,      -- epoch UTC
    text        TEXT,
    n_images    INTEGER,
    n_refs      INTEGER,
    refs_json   TEXT
);
CREATE INDEX IF NOT EXISTS drops_time ON drops(time);

CREATE TABLE IF NOT EXISTS tweets (
    id          TEXT PRIMARY KEY,
    time        INTEGER NOT NULL,      -- epoch UTC
    text        TEXT,
    is_retweet  INTEGER,
    is_deleted  INTEGER,
    device      TEXT,
    favorites   INTEGER,
    retweets    INTEGER
);
CREATE INDEX IF NOT EXISTS tweets_time ON tweets(time);

CREATE TABLE IF NOT EXISTS events (
    id          TEXT PRIMARY KEY,
    date        TEXT NOT NULL,         -- AAAA-MM-JJ
    category    TEXT,
    label_fr    TEXT,
    label_en    TEXT,
    source      TEXT
);
"""


def connect(path):
    conn = sqlite3.connect(path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA)
    return conn


def get_meta(conn, key, default=None):
    row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def set_meta(conn, key, value):
    conn.execute(
        "INSERT INTO meta(key, value) VALUES(?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )


def sha(*parts):
    h = hashlib.sha256()
    for p in parts:
        h.update(p if isinstance(p, bytes) else str(p).encode())
        h.update(b"\0")
    return h.hexdigest()[:16]

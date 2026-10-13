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
    source      TEXT,
    source_meta TEXT              -- JSON : media, date, titre de la source
);
"""


# Colonnes ajoutees apres coup a des tables existantes (CREATE IF NOT EXISTS ne
# modifie pas une table deja creee).
MIGRATIONS = [("events", "source_meta", "TEXT")]


def connect(path):
    conn = sqlite3.connect(path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA)
    for table, column, kind in MIGRATIONS:
        if column not in {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {kind}")
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

GDELT_SCHEMA = """
-- GDELT 1.0, fichiers quotidiens d'evenements : agregats par jour d'ajout.
CREATE TABLE IF NOT EXISTS gdelt_day (
    day TEXT PRIMARY KEY, events INTEGER, mentions INTEGER, tone_sum REAL,
    us_events INTEGER, us_protest INTEGER, us_fight INTEGER
);
CREATE TABLE IF NOT EXISTS gdelt_country (
    day TEXT, fips TEXT, events INTEGER, mentions INTEGER, tone_sum REAL, goldstein_sum REAL,
    PRIMARY KEY (day, fips)
);
-- Noms d'acteurs (Actor1Name / Actor2Name) vus au moins MIN_NAME fois dans la journee.
CREATE TABLE IF NOT EXISTS gdelt_name (
    day TEXT, name TEXT, events INTEGER, mentions INTEGER,
    PRIMARY KEY (day, name)
);
CREATE INDEX IF NOT EXISTS gdelt_name_name ON gdelt_name(name);
CREATE TABLE IF NOT EXISTS gdelt_missing (day TEXT PRIMARY KEY, reason TEXT);

CREATE TABLE IF NOT EXISTS pageviews (
    project TEXT, article TEXT, day TEXT, views INTEGER,
    PRIMARY KEY (project, article, day)
);
"""
SCHEMA += GDELT_SCHEMA

SCHEMA += """
-- Evaluation des modeles OpenAI : une reponse par (modele, drop du jeu d'or).
CREATE TABLE IF NOT EXISTS llm_eval (
    model TEXT, drop_id INTEGER, response TEXT, error TEXT,
    in_tok INTEGER, out_tok INTEGER, latency REAL, created_at INTEGER, attempts INTEGER,
    PRIMARY KEY (model, drop_id)
);

-- Annotation du corpus : une ligne par drop.
CREATE TABLE IF NOT EXISTS llm_class (
    drop_id INTEGER PRIMARY KEY, model TEXT, response TEXT, error TEXT,
    in_tok INTEGER, out_tok INTEGER, source TEXT, created_at INTEGER
);
"""

SCHEMA += """
-- Actualite quotidienne (portail Current events de Wikipedia) : wikitexte source, une ligne par jour.
CREATE TABLE IF NOT EXISTS wikinews_raw (day TEXT PRIMARY KEY, wikitext TEXT);

-- Test de l'horoscope : une reponse par (drop, comparaison).
CREATE TABLE IF NOT EXISTS llm_horoscope (
    drop_id INTEGER, kind TEXT, model TEXT, prompt_sha TEXT, truth TEXT, response TEXT, error TEXT,
    in_tok INTEGER, out_tok INTEGER, created_at INTEGER,
    PRIMARY KEY (drop_id, kind)
);

-- Veille bibliographique : publications reperees automatiquement (Crossref, OpenAlex).
CREATE TABLE IF NOT EXISTS biblio_watch (
    key TEXT PRIMARY KEY, source TEXT, doi TEXT, title TEXT, authors TEXT, year INTEGER, date TEXT,
    container TEXT, url TEXT, type TEXT, abstract TEXT, first_seen TEXT, last_seen TEXT
);
"""

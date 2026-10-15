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
-- Pages vues des articles de la scene complotiste (data/scene.yaml), a part :
-- la table pageviews reste celle de l'analyse d'interet publiee. Une ligne par
-- titre : l'article lui-meme et chacune de ses redirections (anciens titres
-- compris), a additionner par article.
CREATE TABLE IF NOT EXISTS wiki_scene_views (
    project TEXT, article TEXT, title TEXT, day TEXT, views INTEGER,
    PRIMARY KEY (project, article, title, day)
);

-- Reddit (Arctic Shift) : volumes exacts, echantillon systematique, comptage du lexique.
CREATE TABLE IF NOT EXISTS reddit_volume (
    sub TEXT, kind TEXT, day TEXT, n INTEGER,     -- kind : posts | comments ; jour UTC
    PRIMARY KEY (sub, kind, day)
);
CREATE TABLE IF NOT EXISTS reddit_sample (
    sub TEXT, kind TEXT, id TEXT, ts INTEGER, text TEXT,   -- sans auteur
    PRIMARY KEY (sub, kind, id)
);
CREATE TABLE IF NOT EXISTS reddit_sample_day (
    sub TEXT, kind TEXT, day TEXT,
    n_sampled INTEGER,   -- elements gardes (ni supprimes, ni robots)
    n_gone INTEGER,      -- [deleted] / [removed]
    n_bots INTEGER,      -- AutoModerator
    complete INTEGER,    -- 1 si les trois creneaux ont ete lus en entier
    PRIMARY KEY (sub, kind, day)
);
-- 4chan /pol/ (Zenodo 3606810), lu une fois : voir qanon/sources/pol.py.
CREATE TABLE IF NOT EXISTS pol_hour (hour INTEGER, term TEXT, n INTEGER, PRIMARY KEY (hour, term));
CREATE TABLE IF NOT EXISTS pol_hour_total (hour INTEGER PRIMARY KEY, posts INTEGER, threads INTEGER);
CREATE TABLE IF NOT EXISTS pol_first (term TEXT PRIMARY KEY, ts INTEGER, post TEXT);
CREATE TABLE IF NOT EXISTS pol_qcorpus (
    thread TEXT, post TEXT, ts INTEGER, subject TEXT, text TEXT, country TEXT, reason TEXT,
    PRIMARY KEY (post)
);
CREATE TABLE IF NOT EXISTS pol_sample (post TEXT PRIMARY KEY, thread TEXT, ts INTEGER, text TEXT, country TEXT);
CREATE TABLE IF NOT EXISTS pol_unigram_month (month TEXT, token TEXT, n INTEGER, PRIMARY KEY (month, token));
CREATE TABLE IF NOT EXISTS pol_entity_month (month TEXT, entity TEXT, label TEXT, n INTEGER, PRIMARY KEY (month, entity, label));
-- Comptes exacts des mois encore ouverts, cumules a chaque point de reprise (la memoire est videe).
CREATE TABLE IF NOT EXISTS pol_unigram_acc (month TEXT, token TEXT, n INTEGER, PRIMARY KEY (month, token));
CREATE TABLE IF NOT EXISTS pol_entity_acc (month TEXT, entity TEXT, label TEXT, n INTEGER, PRIMARY KEY (month, entity, label));
CREATE TABLE IF NOT EXISTS pol_tox_day (
    day TEXT, scope TEXT, attr TEXT, total REAL, n INTEGER, n_high INTEGER,   -- moyenne = total / n ; n_high : score > 0,8
    PRIMARY KEY (day, scope, attr)
);
-- Meme mesure, sous-corpus Q ventile par raison d'entree (thread:cbts, post:promoter...) : passe dediee.
CREATE TABLE IF NOT EXISTS pol_tox_reason (
    day TEXT, reason TEXT, attr TEXT, total REAL, n INTEGER, n_high INTEGER,
    PRIMARY KEY (day, reason, attr)
);

-- Google Trends : valeurs brutes (0-100, normalisees par lot et fenetre), ancre comprise.
CREATE TABLE IF NOT EXISTS trends_raw (
    batch TEXT, window TEXT, query TEXT, date TEXT, value INTEGER, partial INTEGER,
    PRIMARY KEY (batch, window, query, date)
);
CREATE TABLE IF NOT EXISTS reddit_hour (
    sub TEXT, hour INTEGER, n INTEGER,            -- debut de l'heure (epoque UTC), commentaires
    PRIMARY KEY (sub, hour)
);
CREATE TABLE IF NOT EXISTS reddit_hour_day (sub TEXT, day TEXT, n INTEGER, PRIMARY KEY (sub, day));
CREATE TABLE IF NOT EXISTS reddit_term_day (
    sub TEXT, kind TEXT, day TEXT, term TEXT, n INTEGER,   -- elements echantillonnes contenant le terme
    PRIMARY KEY (sub, kind, day, term)
);
"""

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

SCHEMA += """
-- Verification hebdomadaire des liens (une passe par semaine ; voir sources/links.py).
CREATE TABLE IF NOT EXISTS link_check (
    url TEXT PRIMARY KEY, origin TEXT, state TEXT, code INTEGER, archive TEXT, checked_at INTEGER, pass TEXT
);
"""

SCHEMA += """
-- Traductions francaises des paraphrases anglaises (predictions, justifications) ; voir llm/translate.py.
CREATE TABLE IF NOT EXISTS llm_translate (key TEXT PRIMARY KEY, src_sha TEXT, fr TEXT, model TEXT, created_at INTEGER);
"""

SCHEMA += """
-- Test de l'horoscope : reponses d'un second modele (robustesse), meme format que llm_horoscope.
CREATE TABLE IF NOT EXISTS llm_horoscope_check (
    drop_id INTEGER, kind TEXT, model TEXT, prompt_sha TEXT, truth TEXT, response TEXT, error TEXT,
    in_tok INTEGER, out_tok INTEGER, created_at INTEGER,
    PRIMARY KEY (drop_id, kind, model)
);
"""

SCHEMA += """
-- Relectures editoriales (API Editorial Reviewer) : une ligne par revue soumise ; voir review.py.
CREATE TABLE IF NOT EXISTS editorial_review (
    doc TEXT, text_sha TEXT, job_id TEXT PRIMARY KEY, status TEXT, profile TEXT, words INTEGER,
    est_cost REAL, audit TEXT, submitted_at INTEGER, finished_at INTEGER, n_issues INTEGER, counts TEXT, failure TEXT
);
"""

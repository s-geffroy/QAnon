import json

import pandas as pd

ET = "America/New_York"


def load_drops(conn):
    df = pd.read_sql_query("SELECT * FROM drops ORDER BY time", conn)
    df["ts"] = pd.to_datetime(df["time"], unit="s", utc=True)
    df["et"] = df["ts"].dt.tz_convert(ET)
    return df


def load_tweets(conn):
    df = pd.read_sql_query("SELECT * FROM tweets ORDER BY time", conn)
    df["ts"] = pd.to_datetime(df["time"], unit="s", utc=True)
    return df


def load_events(conn):
    return pd.read_sql_query("SELECT * FROM events ORDER BY date", conn)


def write(ctx, name, data):
    """Ecrit un resultat JSON dans /state/results ; renvoie son contenu serialise."""
    text = json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True, default=str)
    (ctx.results / f"{name}.json").write_text(text)
    return text


import re as _re

_URL = _re.compile(r"https?://\S+|www\.\S+")
_REF = _re.compile(r">>\d+|>>>/\S+")
_SIGN = _re.compile(r"^\s*Q\s*$", _re.M)


def clean(text):
    """Texte d'un drop sans liens, renvois (>>123) ni signature 'Q'."""
    t = _URL.sub(" ", text or "")
    t = _REF.sub(" ", t)
    t = _SIGN.sub(" ", t)
    return _re.sub(r"\s+", " ", t).strip()


def month(series_ts):
    """Mois (AAAA-MM) en heure de New York."""
    return series_ts.dt.tz_convert(ET).dt.strftime("%Y-%m")


def load_yaml(name, key):
    import yaml
    from ..pipeline import APP_DIR
    path = APP_DIR / "data" / f"{name}.yaml"
    if not path.exists():
        return []
    return yaml.safe_load(path.read_text())[key]

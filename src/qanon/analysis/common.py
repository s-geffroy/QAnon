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

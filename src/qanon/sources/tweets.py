"""Tweets de @realDonaldTrump : export du Trump Twitter Archive republie sur
Kaggle (codebreaker619/donald-trump-tweets-dataset), horodatage UTC."""
import pandas as pd

from .. import db
from ..log import log
from .kaggle import download

HANDLE = "codebreaker619/donald-trump-tweets-dataset"


def run(ctx):
    path = download(ctx, HANDLE) / "tweets.csv"
    raw = path.read_bytes()
    digest = db.sha(raw)
    if db.get_meta(ctx.conn, "out:fetch_tweets") == digest:
        return True
    df = pd.read_csv(path, dtype={"id": str})
    t = pd.to_datetime(df["date"], utc=True)
    flag = lambda col: (df[col].astype(str).str.lower() == "t").astype(int)
    rows = list(zip(
        df["id"], (t.astype("int64") // 10**9).astype(int), df["text"].fillna(""),
        flag("isRetweet"), flag("isDeleted"), df["device"].fillna(""),
        df["favorites"].fillna(0).astype(int), df["retweets"].fillna(0).astype(int),
    ))
    ctx.conn.execute("DELETE FROM tweets")
    ctx.conn.executemany("INSERT OR REPLACE INTO tweets VALUES (?,?,?,?,?,?,?,?)",
                         [tuple(int(v) if hasattr(v, "item") else v for v in r) for r in rows])
    ctx.set_output(digest)
    log(f"tweets : {len(rows)} charges depuis {HANDLE}")
    return True

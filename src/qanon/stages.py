"""Ordre et dependances des etapes de l'etude."""
from .analysis import descriptive, trump
from .pipeline import Stage
from .site import build, publish
from .sources import qdrops, timeline, tweets

WEEK = 7 * 86400

STAGES = [
    Stage("fetch_qdrops", qdrops.run, refresh=WEEK),
    Stage("fetch_tweets", tweets.run, refresh=WEEK),
    Stage("load_timeline", timeline.run, code=True),
    Stage("analyze_descriptive", descriptive.run, inputs=("fetch_qdrops", "load_timeline"), code=True),
    Stage("analyze_trump", trump.run, inputs=("fetch_qdrops", "fetch_tweets"), code=True),
    Stage("build_site", build.run, inputs=("analyze_descriptive", "analyze_trump"), code=True),
    Stage("publish_site", publish.run, inputs=("build_site",)),
]

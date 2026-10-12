"""Ordre et dependances des etapes de l'etude.

Les etapes longues et incrementales (GDELT) viennent en dernier : chaque cycle a
un budget de temps, et les etapes rapides doivent passer avant."""
from .analysis import actors, descriptive, discourse, interest, news, predictions, trump, verification
from .llm import classify as llm_classify
from .llm import eval as llm_eval
from .pipeline import Stage
from .site import build
from .sources import gdelt, pageviews, qdrops, timeline, tweets

WEEK = 7 * 86400

STAGES = [
    Stage("fetch_qdrops", qdrops.run, refresh=WEEK),
    Stage("fetch_tweets", tweets.run, refresh=WEEK),
    Stage("load_timeline", timeline.run, code=True),
    Stage("fetch_pageviews", pageviews.run),
    Stage("analyze_descriptive", descriptive.run, inputs=("fetch_qdrops", "load_timeline"), code=True),
    Stage("analyze_trump", trump.run, inputs=("fetch_qdrops", "fetch_tweets"), code=True),
    Stage("analyze_discourse", discourse.run, inputs=("fetch_qdrops",), code=True),
    Stage("analyze_actors", actors.run, inputs=("fetch_qdrops",), code=True),
    Stage("analyze_interest", interest.run, inputs=("fetch_qdrops", "fetch_pageviews", "load_timeline"), code=True),
    # Appels payants : les reponses sont gardees en base, une relance ne fait que re-noter.
    Stage("llm_eval", llm_eval.run, inputs=("fetch_qdrops",), code=True),
    Stage("build_site", build.run, code=True,
          inputs=("fetch_qdrops", "analyze_descriptive", "analyze_trump", "analyze_discourse", "analyze_actors",
                  "analyze_interest"),
          optional=("analyze_news", "llm_eval", "analyze_predictions", "analyze_verification")),
    # Plusieurs heures au premier passage : reprend au dernier jour traite.
    Stage("fetch_gdelt", gdelt.run, keep_cursor=True),
    Stage("analyze_news", news.run, inputs=("fetch_qdrops", "fetch_gdelt"), code=True),
    # Payant (~0,60 $ avec gpt-5.6-luna) : ne depend ni du code ni de l'evaluation, pour ne jamais
    # resoumettre le corpus par accident ; seuls les drops non annotes partent.
    Stage("llm_classify", llm_classify.run, inputs=("fetch_qdrops",), keep_cursor=True),
    Stage("analyze_predictions", predictions.run, inputs=("llm_classify",), code=True),
    # Verdicts editoriaux versionnes dans data/verification/ (inclus dans l'empreinte du code).
    Stage("analyze_verification", verification.run, inputs=("analyze_predictions",), code=True),
]

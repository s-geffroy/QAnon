"""Ordre et dependances des etapes de l'etude.

Les etapes longues et incrementales (GDELT) viennent en dernier : chaque cycle a
un budget de temps, et les etapes rapides doivent passer avant."""
from .analysis import actors, descriptive, discourse, interest, news, predictions, prophecies, stats, trump, verification
from .llm import classify as llm_classify
from .llm import eval as llm_eval
from .llm import horoscope
from .llm import translate
from .pipeline import Stage
from .site import build, publish
from .sources import biblio_watch, gdelt, links, pageviews, qdrops, timeline, tweets, wikinews

WEEK = 7 * 86400

STAGES = [
    Stage("fetch_qdrops", qdrops.run, refresh=WEEK),
    Stage("fetch_tweets", tweets.run, refresh=WEEK),
    Stage("load_timeline", timeline.run, code=True),
    Stage("fetch_pageviews", pageviews.run),
    # Chaque semaine : publications nouvelles sur QAnon (Crossref, OpenAlex), publiees avec leur etat.
    Stage("watch_biblio", biblio_watch.run, refresh=WEEK),
    Stage("analyze_descriptive", descriptive.run, inputs=("fetch_qdrops", "load_timeline"), code=True),
    Stage("analyze_trump", trump.run, inputs=("fetch_qdrops", "fetch_tweets"), code=True),
    Stage("analyze_discourse", discourse.run, inputs=("fetch_qdrops",), code=True),
    Stage("analyze_actors", actors.run, inputs=("fetch_qdrops",), code=True),
    Stage("analyze_stats", stats.run, inputs=("fetch_qdrops", "load_timeline"), code=True),
    Stage("analyze_interest", interest.run, inputs=("fetch_qdrops", "fetch_pageviews", "load_timeline"), code=True),
    # Appels payants : les reponses sont gardees en base, une relance ne fait que re-noter.
    Stage("llm_eval", llm_eval.run, inputs=("fetch_qdrops",), code=True),
    Stage("build_site", build.run, code=True,
          inputs=("fetch_qdrops", "analyze_descriptive", "analyze_trump", "analyze_discourse", "analyze_actors",
                  "analyze_interest", "analyze_stats"),
          optional=("analyze_news", "llm_eval", "analyze_predictions", "analyze_verification", "analyze_prophecies",
                    "llm_horoscope", "watch_biblio", "check_links", "llm_translate")),
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
STAGES += [
    Stage("analyze_prophecies", prophecies.run, inputs=("analyze_predictions", "analyze_verification"), code=True),
    # Actualite quotidienne (portail Current events), ~1 200 pages, reprenable jour par jour.
    # Nom de curseur distinct du premier essai (items mal extraits) : la collecte repart de zero.
    Stage("fetch_wikinews_raw", wikinews.run, keep_cursor=True),
    # Payant (~0,60 $) : seules les questions sans reponse sont posees.
    Stage("llm_horoscope", horoscope.run, inputs=("fetch_qdrops", "fetch_wikinews_raw"), code=True),
]
STAGES += [
    # Apres chaque reconstruction du site (dont la veille hebdomadaire) : push gh-pages, si le secret
    # github_token est monte ; sinon publication manuelle (scripts/publish-pages.sh).
    Stage("publish_pages", publish.run, inputs=("build_site",), code=True),
]
STAGES += [
    # Chaque semaine : liens morts, bloques aux robots, copies archivees proposees (~15 min, par lots).
    Stage("check_links", links.run, refresh=WEEK),
]
STAGES += [
    # Payant (~0,10 $) : seules les paraphrases nouvelles ou modifiees sont traduites.
    Stage("llm_translate", translate.run, inputs=("analyze_predictions",), optional=("llm_horoscope",), code=True),
]

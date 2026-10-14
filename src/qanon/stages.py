"""Ordre et dependances des etapes de l'etude.

Les etapes longues et incrementales (GDELT) viennent en dernier : chaque cycle a
un budget de temps, et les etapes rapides doivent passer avant."""
from .analysis import (actors, descriptive, discourse, interest, markov, news, physics, predictions, prophecies, scene,
                       stats, trump, verification)
from .llm import classify as llm_classify
from .llm import eval as llm_eval
from .llm import horoscope
from .llm import translate
from . import review
from .pipeline import Stage
from .site import build, publish
from .sources import biblio_watch, gdelt, links, pageviews, qdrops, reddit, timeline, tweets, wikinews

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
    Stage("check_links", links.run, refresh=WEEK, code=True),
]
STAGES += [
    # Payant (~0,10 $) : seules les paraphrases nouvelles ou modifiees sont traduites.
    Stage("llm_translate", translate.run, inputs=("analyze_predictions",), optional=("llm_horoscope",), code=True),
]
STAGES += [
    # Payant (API Editorial Reviewer, ~0,20 $ / 1 500 mots) : un texte modifie est relu au plus une fois
    # par semaine, sous plafond REVIEW_BUDGET_USD sur 30 jours ; les rapports vont dans /state/reviews.
    Stage("editorial_review", review.run, inputs=("build_site",), code=True),
]
STAGES += [
    # Modeles : chaines de Markov (regimes, themes, compression) et analogies physiques
    # (Hawkes, DFA, avalanches, phases). Decoupes en parties d'une dizaine de secondes.
    Stage("analyze_markov", markov.run, inputs=("fetch_qdrops", "fetch_tweets", "analyze_stats"), code=True),
    Stage("analyze_physics", physics.run, inputs=("fetch_qdrops", "fetch_tweets", "analyze_stats"), code=True),
]
STAGES += [
    # Scene complotiste : pages vues d'articles connexes (table a part), Reddit via Arctic Shift.
    Stage("fetch_pageviews_scene", pageviews.run_scene, code=True),
    Stage("fetch_reddit_volume", reddit.run_volume, code=True),
    # Rejoue toutes les heures sur les nouveaux elements ; un lexique modifie recompte tout.
    Stage("scan_reddit", reddit.run_scan, refresh=3600, keep_cursor=True, code=True),
]
STAGES += [
    # Q et la scene : entropie de transfert, syncretisme, reponse horaire, pics d'attention, diffusion.
    # Rejoue a chaque nouveau comptage Reddit (toutes les heures pendant la collecte).
    Stage("analyze_scene", scene.run, code=True,
          inputs=("fetch_qdrops", "fetch_tweets", "load_timeline", "fetch_pageviews", "fetch_pageviews_scene",
                  "fetch_reddit_volume"),
          optional=("scan_reddit", "fetch_reddit_hour", "fetch_gdelt")),
]
STAGES += [
    # Collectes longues en dernier : elles prennent le budget restant du cycle (sinon les
    # etapes placees apres elles n'auraient jamais leur tour). Heures : 15 s par cycle au plus.
    Stage("fetch_reddit_hour", reddit.run_hour, inputs=("fetch_reddit_volume",), keep_cursor=True),
    # Un a deux jours au premier passage (~36 000 requetes) : reprend aux jours non echantillonnes.
    Stage("fetch_reddit_sample", reddit.run_sample, inputs=("fetch_reddit_volume",), keep_cursor=True),
]

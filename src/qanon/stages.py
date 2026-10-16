"""Ordre et dependances des etapes de l'etude.

Les etapes longues et incrementales (GDELT) viennent en dernier : chaque cycle a
un budget de temps, et les etapes rapides doivent passer avant."""
from .analysis import (actors, descriptive, discourse, interest, markov, news, physics, polscene, predictions,
                       prophecies, scene, stats, trump, verification)
from .llm import classify as llm_classify
from .llm import eval as llm_eval
from .llm import horoscope
from .llm import translate
from . import db
from .analysis.common import load_yaml
from .pipeline import Stage
from .site import build, publish
from .sources import biblio_watch, gdelt, links, pageviews, pol, qdrops, reddit, timeline, trends, tweets, wikinews

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
                    "llm_horoscope", "watch_biblio", "check_links", "llm_translate",
                    "analyze_markov", "analyze_physics", "analyze_scene", "analyze_pol")),
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
    # Passage horaire : rattrape une version de main que l'API GitHub donnait encore en cache au moment du
    # deploiement ; rien n'est pousse si ni la version ni le site n'ont change.
    Stage("publish_pages", publish.run, inputs=("build_site",), refresh=3600, code=True),
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
]
STAGES += [
    # Modeles : chaines de Markov (regimes, themes, compression) et analogies physiques
    # (Hawkes, DFA, avalanches, phases). Decoupes en parties d'une dizaine de secondes.
    Stage("analyze_markov", markov.run, inputs=("fetch_qdrops", "fetch_tweets", "analyze_stats"), code=True),
    Stage("analyze_physics", physics.run, inputs=("fetch_qdrops", "fetch_tweets", "analyze_stats"), code=True),
]
STAGES += [
    # Scene complotiste : pages vues d'articles connexes (table a part), Reddit via Arctic Shift.
    # Ces collectes dependent de leurs listes (scene.yaml), pas de tout le code : un
    # deploiement ne les relance pas.
    Stage("fetch_pageviews_scene", pageviews.run_scene, version=db.sha(*load_yaml("scene", "wikipedia_articles"))),
    Stage("fetch_reddit_volume", reddit.run_volume, version=db.sha(*reddit.subreddits(), reddit.START_YEAR, reddit.END_YEAR)),
    # Google Trends : API non officielle, fragile ; en option pour l'analyse de la scene.
    # Version : liste des requetes et schema de collecte (forme seule + niveau ancre).
    Stage("fetch_trends", trends.run, version=db.sha("forme+niveau", *trends.queries(), *trends.WINDOWS,
                                                      trends.ANCHOR, trends.GEO)),
    # Rejoue toutes les heures sur les nouveaux elements ; un lexique modifie recompte tout.
    Stage("scan_reddit", reddit.run_scan, refresh=3600, keep_cursor=True, code=True),
]
STAGES += [
    # Q et la scene : entropie de transfert, syncretisme, reponse horaire, pics d'attention, diffusion.
    # Rejoue a chaque nouveau comptage Reddit (toutes les heures pendant la collecte).
    Stage("analyze_scene", scene.run, code=True,
          inputs=("fetch_qdrops", "fetch_tweets", "load_timeline", "fetch_pageviews", "fetch_pageviews_scene",
                  "fetch_reddit_volume"),
          optional=("scan_reddit", "fetch_reddit_hour", "fetch_gdelt", "fetch_trends")),
]
STAGES += [
    # Collectes longues en dernier : elles prennent le budget restant du cycle (sinon les
    # etapes placees apres elles n'auraient jamais leur tour). Heures : 15 s par cycle au plus.
    Stage("fetch_reddit_hour", reddit.run_hour, inputs=("fetch_reddit_volume",), keep_cursor=True),
    # 4chan /pol/ : 24 Go, reprenable (le fichier partiel fait foi), puis md5.
    Stage("fetch_pol", pol.run_fetch, version=pol.MD5),
    # Lexique applique a /pol/ jusqu'a fin 2017 (rapport hors des resultats publies), avant
    # l'approbation du lexique pour le balayage complet.
    Stage("calibrate_pol", pol.run_calibrate, inputs=("fetch_pol",), code=True, keep_cursor=True),
    # Balayage complet (~6 h de calcul, 30 s par cycle) : attend l'approbation du lexique.
    # Le curseur porte l'empreinte du lexique ; un autre lexique recommence tout.
    Stage("scan_pol", pol.run_scan, inputs=("calibrate_pol",), keep_cursor=True),
    # Q et /pol/ : lit les couches du balayage (jamais l'archive) ; ~2 min en parties. Apres
    # scan_pol : une etape n'attend que des entrees placees avant elle dans cette liste.
    Stage("analyze_pol", polscene.run, inputs=("fetch_qdrops", "scan_pol"), code=True),
    # Un a deux jours au premier passage (~36 000 requetes) : reprend aux jours non echantillonnes.
    Stage("fetch_reddit_sample", reddit.run_sample, inputs=("fetch_reddit_volume",), keep_cursor=True),
    # Toxicite du sous-corpus Q ventilee par raison (fils Q, promoteurs, noyau Q...) : relit l'archive
    # (~1 h). Demande du 15/10/2026 : seulement une fois l'echantillon Reddit termine.
    Stage("split_pol_tox", pol.run_tox_split, inputs=("scan_pol", "fetch_reddit_sample"), keep_cursor=True),
]

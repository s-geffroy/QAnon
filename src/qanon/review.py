"""Relecture editoriale des textes du site par l'API Editorial Reviewer
(application du VPS, sur le tailnet ; acces autorise par le proprietaire).

L'API relit un texte avec plusieurs modeles de familles differentes et rend des
problemes sources ; elle ne reecrit rien. Pour chaque texte editorial (document
de travail, etat de la recherche, FAQ, kit pedagogique) :
- audit deterministe gratuit (/audit) a chaque changement du texte ;
- revue payante (/reviews, profil « balanced ») seulement si le texte a change
  depuis la derniere revue, au plus une fois par MIN_DAYS jours et par texte, et
  tant que le plafond REVIEW_BUDGET_USD sur 30 jours n'est pas atteint ;
- le travail est suivi par son job_id sur plusieurs cycles, jamais resoumis ;
- les rapports sont gardes dans /state/reviews (ils expirent cote API apres 24 h) ;
- tant que la publication est suspendue (PUBLISH_HOLD), aucun texte nouveau n'est
  soumis, meme a l'audit : la relecture humaine passe d'abord, la revue payante
  ensuite, une seule fois, sur le texte final ;
- l'application Reviewer peut etre arretee (c'est normal) : l'etape attend alors son
  retour (/health interroge au plus toutes les 30 min), sans echec, et reprend seule.
Les revues ne modifient aucun texte : leurs objectifs de revision sont appliques
ou refuses par un humain."""
import datetime as dt
import hashlib
import json
import os
import re
import time
from html import unescape

import requests

from . import db
from .log import log

API = os.environ.get("REVIEWER_URL", "https://app.reviewer.vps.internal/api/v1")
PROFILE = "balanced"
MIN_DAYS = 7
DOWN_RECHECK = 1800              # API arretee : nouvel essai de /health au plus toutes les 30 min
BUDGET_USD = float(os.environ.get("REVIEW_BUDGET_USD", "3"))
COST_PER_1500_WORDS = 0.20       # ordre de grandeur mesure pour « balanced »
CONSTRAINTS = [
    {"level": "MUST", "text": "Ne jamais présenter une affirmation de QAnon comme un fait ; toujours l'attribuer à Q ou au mouvement."},
    {"level": "MUST_NOT", "text": "Nommer ou accuser une personne privée."},
    {"level": "SHOULD", "text": "Rattacher chaque chiffre à sa méthode ou à sa source, et signaler les limites."},
]
DOCS = {
    "paper": {"profile": "academic", "audience": "specialist", "goal": "demonstrate",
              "brief": "Document de travail scientifique présentant une étude statistique des messages de « Q » (QAnon) "
                       "confrontés à l'actualité : données, méthodes, résultats chiffrés, limites."},
    "research": {"profile": "essay", "audience": "general", "goal": "inform",
                 "brief": "Synthèse de l'état de la recherche sur QAnon, question par question, avec appels de "
                          "référence, pour un site de référence bilingue."},
    "faq": {"profile": "general", "audience": "general", "goal": "inform",
            "brief": "Questions fréquentes sur QAnon et sur l'étude, réponses courtes et sourcées pour le grand public."},
    "teaching": {"profile": "general", "audience": "general", "goal": "instruct",
                 "brief": "Fiches pédagogiques pour enseignants (lycée, première année d'université) sur l'analyse "
                          "critique des messages de Q, avec déroulé, questions et éléments de correction."},
}


def plain(html):
    """Texte brut ; les figures (SVG) sont retirees, leurs legendes gardees."""
    h = re.sub(r"<svg.*?</svg>", " ", str(html), flags=re.S)
    # Les blocs (paragraphes, titres, listes, tableaux) restent separes : la relecture juge aussi la structure.
    h = re.sub(r"</(p|h[1-6]|li|tr|caption|figcaption|table|ul|ol)>|<br\s*/?>", "\n\n", h)
    t = unescape(re.sub(r"<[^>]+>", " ", h))
    t = re.sub(r"[ \t]+", " ", t)
    return re.sub(r"\s*\n\s*(\n\s*)+", "\n\n", t).strip()


def texts(site):
    """Texte brut (francais) de chaque document, renvois resolus comme sur le site."""
    import yaml
    from .pipeline import APP_DIR
    out = {}
    pp = site.paper()
    if pp:
        out["paper"] = plain(pp["html"])
    data = yaml.safe_load((APP_DIR / "data" / "research.yaml").read_text())["sections"]
    out["research"] = "\n\n".join(f"{s['title_fr']}\n\n" + "\n\n".join(plain(p) for p in site._prose(s["body_fr"], "fr"))
                                  for s in data)
    faq = yaml.safe_load((APP_DIR / "data" / "faq.yaml").read_text())["questions"]
    out["faq"] = "\n\n".join(f"{q['q_fr']}\n\n" + "\n\n".join(plain(p) for p in site._prose(q["a_fr"], "fr")) for q in faq)
    tpath = APP_DIR / "data" / "teaching.yaml"
    if tpath.exists():
        th = site.page_teaching("fr", site.base("fr"))
        parts = [" ".join(plain(p) for p in th["intro"])]
        for sh in th["sheets"]:
            parts.append("\n".join([sh["title"], *map(plain, sh["goals"]), *map(plain, sh["steps"]),
                                    *map(plain, sh["questions"]), *map(plain, sh["answers"]), *map(plain, sh["caution"])]))
        out["teaching"] = "\n\n".join(parts)
    return out


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def spent_30d(conn):
    since = int(time.time()) - 30 * 86400
    return conn.execute("SELECT coalesce(sum(est_cost), 0) FROM editorial_review WHERE submitted_at >= ?",
                        (since,)).fetchone()[0]


def save(ctx, doc, row_sha, payload):
    d = ctx.state / "reviews" / doc
    d.mkdir(parents=True, exist_ok=True)
    stamp = dt.date.today().isoformat()
    art = payload.get("artifacts") or {}
    (d / f"{stamp}-{row_sha}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1))
    for k, name in (("review_report_md", "rapport"), ("revision_instructions_md", "objectifs")):
        if art.get(k):
            (d / f"{stamp}-{row_sha}-{name}.md").write_text(art[k])


def run(ctx):
    from .site.build import Site
    # API arretee au dernier essai, il y a moins de DOWN_RECHECK : rien a faire, pas meme les textes.
    if db.get_meta(ctx.conn, "review_api_down") == "1" and \
            time.time() - float(db.get_meta(ctx.conn, "review_api_checked") or 0) < DOWN_RECHECK:
        return None
    site = Site(ctx.state, ctx.conn)
    docs = texts(site)
    conn = ctx.conn
    s = requests.Session()
    pending = held = 0
    hold = os.environ.get("PUBLISH_HOLD", "") not in ("", "0")
    up = {}

    def api_up():
        """L'application Reviewer peut etre arretee, et c'est normal : on attend qu'elle revienne
        (une ligne de log a l'arret, une a la reprise), sans echec ni nouvel essai rapproche."""
        if "ok" not in up:
            # Arretee au dernier essai : on ne la reinterroge qu'apres DOWN_RECHECK secondes.
            last = float(db.get_meta(conn, "review_api_checked") or 0)
            if db.get_meta(conn, "review_api_down") == "1" and time.time() - last < DOWN_RECHECK:
                up["ok"] = False
                return False
            db.set_meta(conn, "review_api_checked", str(int(time.time())))
            conn.commit()
            try:
                up["ok"] = s.get(f"{API}/health", timeout=30).status_code == 200
            except requests.RequestException:
                up["ok"] = False
            was_down = db.get_meta(conn, "review_api_down") == "1"
            if up["ok"] == was_down:
                db.set_meta(conn, "review_api_down", "0" if up["ok"] else "1")
                conn.commit()
                log("relecture : API Editorial Reviewer de nouveau disponible" if up["ok"] else
                    "relecture : API Editorial Reviewer arretee (/health ne repond pas) ; revues en attente, "
                    "reprise automatique a son retour")
        return up["ok"]

    for doc, text in docs.items():
        if ctx.should_yield():
            return False
        h = sha(text)
        row = conn.execute("SELECT * FROM editorial_review WHERE doc = ? ORDER BY submitted_at DESC LIMIT 1", (doc,)).fetchone()
        # 1. Travail en cours : on le suit, on ne le resoumet jamais.
        # « expired » de moins de 24 h : peut-etre un faux 404 (liste d'IP), on reprend le suivi.
        if row and (row["status"] in ("queued", "started")
                    or (row["status"] == "expired" and time.time() - row["submitted_at"] < 86400)):
            # API arretee (ou adresse refusee : Traefik repond alors 404 a tout) : le travail en
            # cours est conserve, son suivi reprendra au retour de l'API.
            if not api_up():
                return None
            r = s.get(f"{API}/reviews/{row['job_id']}", timeout=60)
            if r.status_code == 404 and time.time() - row["submitted_at"] < 86400:
                pending += 1
                log(f"relecture {doc} : travail {row['job_id']} introuvable pour l'instant, nouveau suivi au cycle suivant")
                continue
            if r.status_code == 404:
                conn.execute("UPDATE editorial_review SET status = 'expired' WHERE job_id = ?", (row["job_id"],))
                log(f"relecture {doc} : travail {row['job_id']} introuvable (expire ?)")
                continue
            r.raise_for_status()
            js = r.json()
            st = js.get("status")
            if st == "finished":
                issues = (js.get("result") or {}).get("issues") or []
                counts = {k: sum(i.get("status") == k for i in issues) for k in ("CONFIRMED", "PROBABLE", "UNRESOLVED")}
                save(ctx, doc, row["text_sha"], js)
                conn.execute("UPDATE editorial_review SET status = 'finished', finished_at = ?, n_issues = ?, counts = ? "
                             "WHERE job_id = ?", (int(time.time()), len(issues), json.dumps(counts), row["job_id"]))
                log(f"relecture {doc} : {len(issues)} problemes ({counts['CONFIRMED']} confirmes, "
                    f"{counts['PROBABLE']} probables, {counts['UNRESOLVED']} a trancher)")
            elif st == "failed":
                cause = str((js.get("failure") or {}).get("cause"))[:400]
                conn.execute("UPDATE editorial_review SET status = 'failed', finished_at = ?, failure = ? WHERE job_id = ?",
                             (int(time.time()), cause, row["job_id"]))
                log(f"relecture {doc} : echec cote API ({cause[:200]}) ; pas de nouvel essai automatique")
            else:
                conn.execute("UPDATE editorial_review SET status = ? WHERE job_id = ?", (st, row["job_id"]))
                pending += 1
            conn.commit()
            continue
        # 2. Texte inchange depuis la derniere revue (ou dernier echec sur ce texte) : rien a faire.
        if row and row["text_sha"] == h:
            continue
        if hold:
            held += 1
            continue
        if not api_up():
            return None
        # 3. Audit gratuit du nouveau texte.
        audit = s.post(f"{API}/audit", json={"text": text, "language": "fr"}, timeout=120)
        audit.raise_for_status()
        # 4. Revue payante : delai minimal par texte et plafond sur 30 jours.
        if row and time.time() - row["submitted_at"] < MIN_DAYS * 86400:
            continue
        words = len(text.split())
        est = round(COST_PER_1500_WORDS * max(1.0, words / 1500), 2)
        if spent_30d(conn) + est > BUDGET_USD:
            log(f"relecture {doc} : plafond REVIEW_BUDGET_USD={BUDGET_USD} $ atteint sur 30 jours, revue reportee")
            continue
        cfg = DOCS[doc]
        compile_cfg = {"language": "fr", "profile": cfg["profile"], "audience": cfg["audience"],
                       "rhetorical_goal": cfg["goal"], "task_brief": cfg["brief"], "custom_constraints": CONSTRAINTS}
        comp = s.post(f"{API}/prompts/compile", json=compile_cfg, timeout=120)
        comp.raise_for_status()
        sub = s.post(f"{API}/reviews", timeout=120, json={
            "text": text, "writing_instructions": comp.json()["writing_instructions"],
            "config": compile_cfg, "model_profile": PROFILE})
        if sub.status_code == 422:
            raise RuntimeError(f"relecture {doc} : configuration refusee (422) : {sub.text[:300]}")
        sub.raise_for_status()
        job = sub.json()
        conn.execute("INSERT INTO editorial_review (doc, text_sha, job_id, status, profile, words, est_cost, audit, "
                     "submitted_at) VALUES (?,?,?,?,?,?,?,?,?)",
                     (doc, h, job["job_id"], job.get("status", "queued"), PROFILE, words, est, audit.text, int(time.time())))
        conn.commit()
        pending += 1
        log(f"relecture {doc} : revue soumise ({words} mots, ~{est} $, profil {PROFILE})")
    if pending:
        return False
    if held:
        if db.get_meta(conn, "review_hold_logged") != "1":
            db.set_meta(conn, "review_hold_logged", "1")
            conn.commit()
            log(f"relecture : {held} texte(s) modifie(s) en attente, rien n'est soumis tant que PUBLISH_HOLD est pose")
        return None
    db.set_meta(conn, "review_hold_logged", "0")
    rows = conn.execute("SELECT doc, text_sha, status, n_issues FROM editorial_review ORDER BY doc, submitted_at").fetchall()
    ctx.set_output(db.sha(*[tuple(r) for r in rows]))
    return True

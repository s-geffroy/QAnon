"""Evaluation des modeles OpenAI sur le jeu d'or (data/gold.jsonl).

Chaque modele candidat annote les 150 drops du jeu d'or ; les reponses sont
stockees une par une (table llm_eval), donc l'etape est reprenable. On compare :
F1 sur "contient une prediction" (intervalle bootstrap), exactitude du type et de
l'echeance sur les drops positifs, cout reel (jetons x tarif) extrapole au
corpus entier en Batch API, latence. Recommandation : le modele le moins cher
dont le F1 est a 3 points ou moins du meilleur."""
import json
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np

from .. import db
from ..log import log
from ..pipeline import APP_DIR
from ..secrets import read_secret
from .prompt import SCHEMA, SYSTEM, parse, user_message

# Tarifs par million de jetons (standard, batch), page officielle consultee le
# 2026-10-12 : https://developers.openai.com/api/docs/pricing
PRICING_DATE = "2026-10-12"
MODELS = {
    "gpt-5-nano":   {"in": 0.05, "out": 0.40, "batch_in": 0.025, "batch_out": 0.20},
    "gpt-6-luna":   {"in": 0.10, "out": 0.50, "batch_in": 0.05, "batch_out": 0.25},
    "gpt-5.6-luna": {"in": 0.20, "out": 1.20, "batch_in": 0.10, "batch_out": 0.60},
    "gpt-5-mini":   {"in": 0.25, "out": 2.00, "batch_in": 0.125, "batch_out": 1.00},
    "gpt-4.1-mini": {"in": 0.40, "out": 1.60, "batch_in": 0.20, "batch_out": 0.80},
    "gpt-6.1-sol":  {"in": 2.00, "out": 10.00, "batch_in": 1.00, "batch_out": 5.00},
    "gpt-6-astra":  {"in": 10.00, "out": 50.00, "batch_in": 5.00, "batch_out": 25.00},
}
WORKERS = 6

MAX_ATTEMPTS = 3


def gold():
    return [json.loads(line) for line in (APP_DIR / "data" / "gold.jsonl").read_text().splitlines() if line.strip()]


def call(client, model, msg):
    """Un appel ; repli sans reasoning_effort si le modele ne l'accepte pas."""
    kwargs = {"model": model, "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": msg}],
              "response_format": {"type": "json_schema", "json_schema": SCHEMA}, "max_completion_tokens": 4000}
    if not model.startswith("gpt-4"):
        kwargs["reasoning_effort"] = "low"
    t0 = time.monotonic()
    try:
        r = client.chat.completions.create(**kwargs)
    except Exception as exc:
        if "reasoning_effort" in str(exc) and "reasoning_effort" in kwargs:
            kwargs.pop("reasoning_effort")
            r = client.chat.completions.create(**kwargs)
        else:
            raise
    return r.choices[0].message.content, r.usage.prompt_tokens, r.usage.completion_tokens, time.monotonic() - t0


def f1(y, p):
    tp = int((y & p).sum()); fp = int((~y & p).sum()); fn = int((y & ~p).sum())
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    return (2 * prec * rec / (prec + rec) if prec + rec else 0.0), prec, rec


def score(conn, items, corpus_tokens):
    rows = {}
    for r in conn.execute("SELECT * FROM llm_eval"):
        rows.setdefault(r["model"], {})[r["drop_id"]] = r
    ids = [g["drop_id"] for g in items]
    y = np.array([g["is_prediction"] for g in items])
    rng = np.random.default_rng(0)
    boot = rng.integers(0, len(ids), size=(1000, len(ids)))
    out = []
    for model, price in MODELS.items():
        got = rows.get(model, {})
        if len(got) < len(ids):
            continue
        preds, errors, types_ok, dead_ok, n_pos_both = [], 0, 0, 0, 0
        for g in items:
            r = got[g["drop_id"]]
            if r["error"] or not r["response"]:
                errors += 1
                preds.append(False)
                continue
            ans = json.loads(r["response"])
            p = bool(ans["is_prediction"])
            preds.append(p)
            if p and g["is_prediction"] and ans["predictions"] and g["predictions"]:
                n_pos_both += 1
                types_ok += ans["predictions"][0]["event_type"] == g["predictions"][0]["event_type"]
                dead_ok += (ans["predictions"][0]["deadline"] or None) == (g["predictions"][0]["deadline"] or None)
        p = np.array(preds)
        f, prec, rec = f1(y, p)
        fb = [f1(y[b], p[b])[0] for b in boot]
        tin = sum(got[i]["in_tok"] or 0 for i in ids)
        tout = sum(got[i]["out_tok"] or 0 for i in ids)
        # Extrapolation au corpus : jetons d'entree proportionnels a la taille
        # des textes, jetons de sortie moyens par drop.
        scale_in = corpus_tokens["input"] / max(corpus_tokens["gold_input"], 1)
        n_corpus = corpus_tokens["n"]
        corpus_cost = (tin * scale_in * price["batch_in"] + tout / len(ids) * n_corpus * price["batch_out"]) / 1e6
        out.append({
            "model": model, "f1": round(f, 3), "f1_lo": round(float(np.quantile(fb, 0.025)), 3),
            "f1_hi": round(float(np.quantile(fb, 0.975)), 3), "precision": round(prec, 3), "recall": round(rec, 3),
            "errors": errors, "type_acc": round(types_ok / n_pos_both, 3) if n_pos_both else None,
            "deadline_acc": round(dead_ok / n_pos_both, 3) if n_pos_both else None, "n_pos_both": n_pos_both,
            "gold_cost_usd": round((tin * price["in"] + tout * price["out"]) / 1e6, 4),
            "corpus_cost_batch_usd": round(corpus_cost, 2),
            "latency_median_s": round(float(np.median([got[i]["latency"] or 0 for i in ids])), 2),
            "in_tok": tin, "out_tok": tout, **{f"price_{k}": v for k, v in price.items()},
        })
    if out:
        best = max(o["f1"] for o in out)
        ok = [o for o in out if o["f1"] >= best - 0.03 and o["errors"] <= 2]
        rec = min(ok, key=lambda o: o["corpus_cost_batch_usd"]) if ok else None
    else:
        rec = None
    return out, rec


def run(ctx):
    key = read_secret("openai_api_key")
    if not key:
        raise RuntimeError("secret openai_api_key absent : evaluation en attente")
    from openai import OpenAI
    client = OpenAI(api_key=key, max_retries=3, timeout=120)
    items = gold()
    drops = {r["id"]: r for r in ctx.conn.execute("SELECT id, time, text, refs_json FROM drops")}
    msgs = {}
    for g in items:
        d = drops[g["drop_id"]]
        date = time.strftime("%Y-%m-%d", time.gmtime(d["time"]))
        msgs[g["drop_id"]] = user_message(date, d["text"], json.loads(d["refs_json"]) if d["refs_json"] else [])
    # A faire : jamais tente, ou en echec avec moins de MAX_ATTEMPTS essais.
    settled = {(r["model"], r["drop_id"]) for r in ctx.conn.execute(
        "SELECT model, drop_id FROM llm_eval WHERE error IS NULL OR attempts >= ?", (MAX_ATTEMPTS,))}
    todo = [(m, i) for m in MODELS for i in msgs if (m, i) not in settled]

    def one(job):
        model, i = job
        try:
            content, tin, tout, lat = call(client, model, msgs[i])
            parse(content)
            return model, i, content, None, tin, tout, lat
        except Exception as exc:
            return model, i, None, repr(exc)[:300], None, None, None

    with ThreadPoolExecutor(WORKERS) as pool:
        while todo and not ctx.should_yield():
            batch, todo = todo[:WORKERS * 4], todo[WORKERS * 4:]
            res = list(pool.map(one, batch))
            ctx.conn.executemany(
                "INSERT INTO llm_eval VALUES (?,?,?,?,?,?,?,?,1) ON CONFLICT(model, drop_id) DO UPDATE SET "
                "response=excluded.response, error=excluded.error, in_tok=excluded.in_tok, out_tok=excluded.out_tok, "
                "latency=excluded.latency, created_at=excluded.created_at, attempts=attempts+1",
                [(*r, int(time.time())) for r in res])
            ctx.conn.commit()
            errs = [r for r in res if r[3]]
            if errs and len(errs) == len(res):
                raise RuntimeError(f"tous les appels du lot ont echoue, ex. {errs[0][0]} : {errs[0][3]}")
    remaining = len(todo)
    if remaining:
        n = ctx.conn.execute("SELECT count(*) FROM llm_eval WHERE error IS NULL").fetchone()[0]
        log(f"evaluation llm : {n}/{len(MODELS) * len(msgs)} reponses")
        return False
    # Erreurs restantes (une reponse mal formee, un modele indisponible) : on
    # retente au prochain passage ; un modele qui echoue toujours est ecarte.
    failed = ctx.conn.execute("SELECT model, count(*) n, max(error) e FROM llm_eval WHERE error IS NOT NULL "
                              "GROUP BY model").fetchall()
    for f in failed:
        log(f"evaluation llm : {f['model']} : {f['n']} echec(s), ex. {f['e']}")

    corpus_chars = ctx.conn.execute("SELECT sum(length(text)) + sum(coalesce(length(refs_json), 0)), count(*) "
                                    "FROM drops").fetchone()
    gold_chars = sum(len(m) for m in msgs.values())
    ratio_tokens = {"input": corpus_chars[0] + len(SYSTEM) * corpus_chars[1],
                    "gold_input": gold_chars + len(SYSTEM) * len(msgs), "n": corpus_chars[1]}
    table, rec = score(ctx.conn, items, ratio_tokens)
    out = {"pricing_date": PRICING_DATE, "pricing_url": "https://developers.openai.com/api/docs/pricing",
           "n_gold": len(items), "n_positive": int(sum(g["is_prediction"] for g in items)),
           "models": sorted(table, key=lambda o: -o["f1"]), "recommended": rec["model"] if rec else None,
           "failed": [dict(f) for f in failed]}
    from ..analysis.common import write
    ctx.set_output(db.sha(write(ctx, "llm_eval", out)))
    log("evaluation llm : " + " ; ".join(f"{o['model']} F1={o['f1']:.2f} corpus~{o['corpus_cost_batch_usd']}$"
                                         for o in out["models"]) + f" ; recommande : {out['recommended']}")
    return True

"""Annotation de tout le corpus par le modele retenu, via l'API Batch d'OpenAI
(moitie prix, resultat sous 24 h).

Etat dans le curseur (JSON) : identifiant du fichier et du lot soumis. A chaque
passage : soumission si rien n'est en cours, sinon consultation du lot ; quand
il est termine, les reponses sont enregistrees drop par drop (table
llm_class). Les lignes en erreur sont rejouees en appels directs, par petits
paquets. Les drops sans texte ne sont pas soumis."""
import io
import json
import os
import time

from .. import db
from ..log import log
from ..secrets import read_secret
from .eval import MODELS, call
from .prompt import SCHEMA, SYSTEM, parse, user_message

MODEL = os.environ.get("LLM_MODEL", "gpt-5.6-luna")
BUDGET_USD = float(os.environ.get("OPENAI_BUDGET_USD", "15"))


def body(msg):
    b = {"model": MODEL, "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": msg}],
         "response_format": {"type": "json_schema", "json_schema": SCHEMA}, "max_completion_tokens": 4000}
    if not MODEL.startswith("gpt-4"):
        b["reasoning_effort"] = "low"
    return b


def pending(conn):
    rows = conn.execute("SELECT d.id, d.time, d.text, d.refs_json FROM drops d "
                        "LEFT JOIN llm_class c ON c.drop_id = d.id "
                        # Une erreur en appel direct n'est pas rejouee : le drop reste en erreur.
                        "WHERE (c.drop_id IS NULL OR (c.error IS NOT NULL AND c.source = 'batch')) "
                        "AND trim(d.text) != '' "
                        "ORDER BY d.id").fetchall()
    return {r["id"]: user_message(time.strftime("%Y-%m-%d", time.gmtime(r["time"])), r["text"],
                                  json.loads(r["refs_json"]) if r["refs_json"] else []) for r in rows}


def estimate(conn, msgs):
    """Cout estime (USD, tarif Batch) a partir des jetons moyens de l'evaluation."""
    row = conn.execute("SELECT avg(in_tok), avg(out_tok) FROM llm_eval WHERE model = ? AND error IS NULL",
                       (MODEL,)).fetchone()
    in_tok, out_tok = row[0] or 1500, row[1] or 400
    p = MODELS[MODEL]
    return len(msgs) * (in_tok * p["batch_in"] + out_tok * p["batch_out"]) / 1e6


def store(conn, drop_id, content, error, tin, tout, source):
    conn.execute("INSERT OR REPLACE INTO llm_class VALUES (?,?,?,?,?,?,?,?)",
                 (drop_id, MODEL, content, error, tin, tout, source, int(time.time())))


def run(ctx):
    key = read_secret("openai_api_key")
    if not key:
        raise RuntimeError("secret openai_api_key absent : annotation en attente")
    from openai import OpenAI
    client = OpenAI(api_key=key, max_retries=3, timeout=300)
    state = json.loads(ctx.cursor) if ctx.cursor else {}
    conn = ctx.conn

    if not state.get("batch_id"):
        msgs = pending(conn)
        if not msgs:
            return finish(ctx)
        if state.get("retries", 0) >= 1 or len(msgs) <= 50:
            return direct(ctx, client, msgs, state)
        cost = estimate(conn, msgs)
        if cost > BUDGET_USD:
            raise RuntimeError(f"cout estime {cost:.2f} $ > plafond OPENAI_BUDGET_USD={BUDGET_USD} $")
        lines = "\n".join(json.dumps({"custom_id": f"drop-{i}", "method": "POST", "url": "/v1/chat/completions",
                                      "body": body(m)}) for i, m in msgs.items())
        f = client.files.create(file=("qanon_batch.jsonl", io.BytesIO(lines.encode())), purpose="batch")
        b = client.batches.create(input_file_id=f.id, endpoint="/v1/chat/completions", completion_window="24h",
                                  metadata={"project": "qanon", "model": MODEL})
        state.update({"batch_id": b.id, "file_id": f.id, "n": len(msgs), "submitted": int(time.time())})
        ctx.save_cursor(json.dumps(state))
        log(f"annotation : lot {b.id} soumis ({len(msgs)} drops, {MODEL}, cout estime {cost:.2f} $)")
        return None

    b = client.batches.retrieve(state["batch_id"])
    counts = getattr(b, "request_counts", None)
    progress = f"{counts.completed}/{counts.total}" if counts else "?"
    if b.status in ("validating", "in_progress", "finalizing"):
        if state.get("last_status") != [b.status, progress]:
            log(f"annotation : lot {b.id} {b.status} ({progress})")
            state["last_status"] = [b.status, progress]
            ctx.save_cursor(json.dumps(state))
        return None
    if b.status != "completed":
        # failed / expired / cancelled : on oublie le lot, les drops restants
        # seront resoumis (ou traites en direct au deuxieme essai).
        err = getattr(b, "errors", None)
        state = {"retries": state.get("retries", 0) + 1}
        ctx.save_cursor(json.dumps(state))
        raise RuntimeError(f"lot {b.id} termine en '{b.status}' : {str(err)[:300]}")

    ok = bad = 0
    for fid, is_err in ((b.output_file_id, False), (b.error_file_id, True)):
        if not fid:
            continue
        for line in client.files.content(fid).text.splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            drop_id = int(r["custom_id"].split("-")[1])
            resp = (r.get("response") or {})
            body_ = resp.get("body") or {}
            if resp.get("status_code") == 200 and body_.get("choices"):
                content = body_["choices"][0]["message"]["content"]
                try:
                    parse(content)
                    usage = body_.get("usage") or {}
                    store(conn, drop_id, content, None, usage.get("prompt_tokens"), usage.get("completion_tokens"), "batch")
                    ok += 1
                    continue
                except ValueError as exc:
                    error = f"json invalide : {exc}"
            else:
                error = str(r.get("error") or body_.get("error") or resp.get("status_code"))[:300]
            store(conn, drop_id, None, error, None, None, "batch")
            bad += 1
    conn.commit()
    log(f"annotation : lot {b.id} termine, {ok} reponses, {bad} en erreur")
    ctx.save_cursor(json.dumps({"retries": state.get("retries", 0) + (1 if bad else 0), "done_batch": b.id}))
    return False  # au passage suivant : erreurs rejouees en direct, ou fin


def direct(ctx, client, msgs, state):
    """Rejoue des drops en appels directs (erreurs du lot, petits restes) ;
    chaque drop n'est tente qu'une fois de cette facon."""
    n = 0
    for drop_id, msg in msgs.items():
        if ctx.should_yield():
            break
        try:
            content, tin, tout, _ = call(client, MODEL, msg)
            parse(content)
            store(ctx.conn, drop_id, content, None, tin, tout, "direct")
        except Exception as exc:
            store(ctx.conn, drop_id, None, repr(exc)[:300], None, None, "direct")
        ctx.conn.commit()
        n += 1
    left = len(pending(ctx.conn))
    log(f"annotation : {n} drop(s) en appel direct, {left} restant(s)")
    return False if left else finish(ctx)


def finish(ctx):
    n = ctx.conn.execute("SELECT count(*), sum(error IS NULL), sum(in_tok), sum(out_tok) FROM llm_class").fetchone()
    p = MODELS[MODEL]
    cost = ((n[2] or 0) * p["batch_in"] + (n[3] or 0) * p["batch_out"]) / 1e6
    ctx.set_output(db.sha(MODEL, n[0], n[1], n[2]))
    log(f"annotation : terminee, {n[1]}/{n[0]} drops annotes par {MODEL}, cout ~{cost:.2f} $")
    return True

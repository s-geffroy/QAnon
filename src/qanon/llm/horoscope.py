"""Test de l'horoscope : les drops « collent »-ils a l'actualite plus que par hasard ?

Pour un echantillon fixe de drops, le modele recoit, sans aucune date, le texte
du drop et deux listes d'items d'actualite (portail Current events de
Wikipedia, items lies aux Etats-Unis) dans un ordre tire au sort :
- « past » : les 7 jours qui finissent le jour du drop, contre 7 jours tires au hasard ;
- « future » : les 30 jours qui suivent le drop, contre 30 jours tires au hasard.
Il note le lien de chaque liste (0-10) et choisit celle a laquelle le drop se
rapporte, ou aucune. Si les drops annoncaient l'avenir, la liste « future »
serait choisie bien plus souvent que la liste au hasard ; si les « correspondances »
tiennent de l'effet Barnum, les listes au hasard obtiennent elles aussi des notes.

Reprenable : une ligne par (drop, comparaison) dans llm_horoscope ; une relance
ne repose que les questions manquantes. Cout ~0,60 $ avec gpt-5.6-luna."""
import datetime as dt
import hashlib
import json
import math
import os
import re
import time

import numpy as np

from .. import db
from ..analysis.common import ET, clean, load_drops, write
from ..log import log
from ..secrets import read_secret

MODEL = os.environ.get("LLM_MODEL", "gpt-5.6-luna")
N_SAMPLE = 300
N_ITEMS = 40
SEED = 20171028
FIRST, LAST = dt.date(2017, 11, 1), dt.date(2020, 11, 30)   # fenetres d'actualite disponibles jusqu'au 31/01/2021
KINDS = {"past": (-6, 0), "future": (1, 30)}                # bornes en jours relatives au drop
US = re.compile(r"\b(United States|U\.S\.|American|Americans|Trump|White House|Congress|Senate|House of "
                r"Representatives|FBI|CIA|NSA|Justice Department|Department of Justice|Pentagon|Democrat\w*|"
                r"Republican\w*|Supreme Court|Washington|Clinton|Obama|Biden|Mueller|Pelosi|Comey)\b")

SYSTEM = ("You are a careful, sceptical analyst. You compare a short anonymous online message with two lists of "
          "real news items. A link counts only if the message clearly refers to, or specifically anticipates, a "
          "particular item; vague wording that could fit many events does not count. Answer in JSON.")
SCHEMA = {"name": "horoscope", "strict": True, "schema": {
    "type": "object", "additionalProperties": False,
    "required": ["score_a", "score_b", "choice", "best_items", "reason"],
    "properties": {
        "score_a": {"type": "integer", "description": "0 = no specific link to list A, 10 = unambiguous reference"},
        "score_b": {"type": "integer", "description": "same for list B"},
        "choice": {"type": "string", "enum": ["A", "B", "none"]},
        "best_items": {"type": "array", "items": {"type": "integer"}, "description": "up to 3 item numbers of the chosen list"},
        "reason": {"type": "string", "description": "at most 30 words"}}}}


def news_by_day(conn):
    return {dt.date.fromisoformat(r["day"]): [x for x in (r["text"] or "").split("\n") if x]
            for r in conn.execute("SELECT day, text FROM wikinews")}


def window(news, start, days, rng):
    pool = [x for k in range(days) for x in news.get(start + dt.timedelta(days=k), []) if US.search(x)]
    idx = rng.permutation(len(pool))[:N_ITEMS]
    return [pool[i] for i in sorted(idx)]


def sample(d):
    """Echantillon fixe, stratifie par annee : drops d'au moins 15 mots (hors liens et renvois)."""
    d = d.copy()
    d["clean"] = [clean(x) for x in d["text"]]
    d["day"] = d["et"].dt.date
    ok = d[(d["clean"].str.split().str.len() >= 15) & (d["day"] >= FIRST) & (d["day"] <= LAST)]
    rng = np.random.default_rng(SEED)
    years = sorted(ok["et"].dt.year.unique())
    per = N_SAMPLE // len(years)
    picks = []
    for y in years:
        sub = ok[ok["et"].dt.year == y]
        picks += list(rng.choice(sub["id"].to_numpy(), size=min(per, len(sub)), replace=False))
    return ok.set_index("id").loc[sorted(picks)]


def questions(d, news):
    """Questions deterministes : (drop_id, kind) -> message, liste vraie (A ou B)."""
    out = {}
    days = sorted(news)
    for drop_id, row in sample(d).iterrows():
        for kind, (a, b) in KINDS.items():
            rng = np.random.default_rng([SEED, int(drop_id), len(kind)])
            span = b - a + 1
            true_start = row["day"] + dt.timedelta(days=a)
            # Fenetre au hasard : a plus de 180 jours du drop, entierement dans la periode couverte.
            far = [x for x in days if abs((x - row["day"]).days) > 180 and x + dt.timedelta(days=span - 1) <= days[-1]]
            rand_start = far[int(rng.integers(len(far)))]
            true_items, rand_items = window(news, true_start, span, rng), window(news, rand_start, span, rng)
            k = min(len(true_items), len(rand_items))
            if k < 10:
                continue
            true_items, rand_items = true_items[:k], rand_items[:k]
            truth = "A" if rng.random() < 0.5 else "B"
            la, lb = (true_items, rand_items) if truth == "A" else (rand_items, true_items)
            fmt = lambda xs: "\n".join(f"{i + 1}. {x}" for i, x in enumerate(xs))
            msg = (f"MESSAGE:\n{row['clean'][:3000]}\n\nLIST A:\n{fmt(la)}\n\nLIST B:\n{fmt(lb)}\n\n"
                   "Score each list, then choose the list the message specifically refers to or anticipates, "
                   "or 'none'.")
            out[(int(drop_id), kind)] = {"msg": msg, "truth": truth, "rand_start": rand_start.isoformat(),
                                         "items": {"A": la, "B": lb}}
    return out


def call(client, msg):
    r = client.chat.completions.create(
        model=MODEL, messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": msg}],
        response_format={"type": "json_schema", "json_schema": SCHEMA}, max_completion_tokens=2000,
        reasoning_effort="low")
    return r.choices[0].message.content, r.usage.prompt_tokens, r.usage.completion_tokens


def wilson(k, n, z=1.96):
    if not n:
        return None, None
    p = k / n
    c = (p + z * z / (2 * n)) / (1 + z * z / n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return round(c - h, 4), round(c + h, 4)


def binom_p(k, n):
    """p-valeur bilaterale exacte, H0 : p = 1/2."""
    from scipy.stats import binomtest
    return float(binomtest(k, n, 0.5).pvalue) if n else None


def analyse(qs, rows, d):
    res = {}
    texts = d.set_index("id")["text"]
    for kind in KINDS:
        R = [(key, json.loads(r["response"]), r["truth"]) for key, r in rows.items()
             if key[1] == kind and r["response"]]
        if not R:
            continue
        true_s = [a["score_a"] if t == "A" else a["score_b"] for _, a, t in R]
        rand_s = [a["score_b"] if t == "A" else a["score_a"] for _, a, t in R]
        chose_true = sum(a["choice"] == t for _, a, t in R)
        chose_rand = sum(a["choice"] not in (t, "none") for _, a, t in R)
        none = sum(a["choice"] == "none" for _, a, t in R)
        decided = chose_true + chose_rand
        # Exemples d'« horoscope » : liste au hasard jugee liee (note >= 6).
        ex = sorted([(rs, key[0], a) for (key, a, t), rs in zip(R, rand_s) if rs >= 6 and a["choice"] != t],
                    key=lambda x: -x[0])[:6]
        res[kind] = {
            "n": len(R), "chose_true": chose_true, "chose_random": chose_rand, "none": none,
            "share_true_decided": round(chose_true / decided, 4) if decided else None,
            "ci_true_decided": wilson(chose_true, decided), "p_value": binom_p(chose_true, decided),
            "mean_true": round(float(np.mean(true_s)), 2), "mean_random": round(float(np.mean(rand_s)), 2),
            "share_random_ge5": round(float(np.mean([s >= 5 for s in rand_s])), 4),
            "share_true_ge5": round(float(np.mean([s >= 5 for s in true_s])), 4),
            "hist": [{"score": s, "true": int(sum(x == s for x in true_s)), "random": int(sum(x == s for x in rand_s))}
                     for s in range(11)],
            "examples": [{"drop_id": i, "score": s, "reason": a["reason"]} for s, i, a in ex],
        }
    by_year = {}
    for kind in KINDS:
        for (i, k), r in rows.items():
            if k != kind or not r["response"]:
                continue
            y = str(d.set_index("id").loc[i, "et"].year)
            a = json.loads(r["response"])
            b = by_year.setdefault(kind, {}).setdefault(y, {"n": 0, "true": 0, "random": 0})
            b["n"] += 1
            b["true"] += a["choice"] == r["truth"]
            b["random"] += a["choice"] not in (r["truth"], "none")
    return {"model": MODEL, "n_sample": len({k[0] for k in qs}), "n_items": N_ITEMS, "kinds": res, "by_year": by_year,
            "windows": {k: {"from": a, "to": b} for k, (a, b) in KINDS.items()}}


def run(ctx):
    d = load_drops(ctx.conn)
    d = d[d["text"].str.strip() != ""].reset_index(drop=True)
    news = news_by_day(ctx.conn)
    qs = questions(d, news)
    sha = lambda m: hashlib.sha256(m.encode()).hexdigest()[:16]
    done = {(r["drop_id"], r["kind"]): r for r in ctx.conn.execute("SELECT * FROM llm_horoscope")}
    todo = [k for k, q in qs.items() if k not in done or done[k]["prompt_sha"] != sha(q["msg"])
            or (done[k]["error"] and not done[k]["response"])]
    if todo:
        key = read_secret("openai_api_key")
        if not key:
            raise RuntimeError("secret openai_api_key absent : test de l'horoscope en attente")
        from openai import OpenAI
        client = OpenAI(api_key=key, max_retries=3, timeout=120)
        n = 0
        for k in todo:
            if ctx.should_yield():
                log(f"horoscope : {len(qs) - len(todo) + n}/{len(qs)} questions posees")
                return False
            q = qs[k]
            try:
                content, tin, tout = call(client, q["msg"])
                json.loads(content)
                err = None
            except Exception as exc:  # une question en echec est reposee au passage suivant
                content, tin, tout, err = None, None, None, f"{type(exc).__name__}: {exc}"[:500]
            ctx.conn.execute("INSERT OR REPLACE INTO llm_horoscope VALUES (?,?,?,?,?,?,?,?,?,?)",
                             (k[0], k[1], MODEL, sha(q["msg"]), q["truth"], content, err, tin, tout, int(time.time())))
            ctx.conn.commit()
            n += 1
        return False
    rows = {k: done[k] for k in qs if k in done}
    out = analyse(qs, rows, d)
    tok = ctx.conn.execute("SELECT sum(in_tok), sum(out_tok) FROM llm_horoscope").fetchone()
    out["tokens_in"], out["tokens_out"] = tok[0], tok[1]
    ctx.set_output(db.sha(write(ctx, "horoscope", out)))
    f = out["kinds"].get("future", {})
    log(f"horoscope : {out['n_sample']} drops ; futur choisi {f.get('chose_true')} fois, hasard "
        f"{f.get('chose_random')}, aucun {f.get('none')} ; p = {f.get('p_value')}")
    return True

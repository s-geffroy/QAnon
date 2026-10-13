"""Traduction en francais des paraphrases produites en anglais par le modele :
predictions extraites (et donc verdicts, prophéties recyclees) et
justifications du test de l'horoscope.

Par lots de 40 textes, sortie JSON structuree ; une traduction est gardee en
base avec l'empreinte du texte anglais : elle n'est refaite que si celui-ci
change. Cout ~0,10 $ avec gpt-5.6-luna."""
import hashlib
import json
import os
import time

from .. import db
from ..analysis.common import write
from ..log import log
from ..secrets import read_secret

MODEL = os.environ.get("LLM_MODEL", "gpt-5.6-luna")
BATCH = 40
SYSTEM = ("You translate into French short English paraphrases describing what anonymous 'Q' posts (QAnon) claim. "
          "Translate faithfully: keep the attribution to Q (\"Q affirme que…\", \"Q annonce…\", \"Q laisse entendre…\"), "
          "keep names and quoted terms, do not add, soften or endorse anything, do not translate proper names. "
          "Use correct French typography (« », espaces insécables optionnelles). Return JSON.")
SCHEMA = {"name": "translations", "strict": True, "schema": {
    "type": "object", "additionalProperties": False, "required": ["items"],
    "properties": {"items": {"type": "array", "items": {
        "type": "object", "additionalProperties": False, "required": ["id", "fr"],
        "properties": {"id": {"type": "string"}, "fr": {"type": "string"}}}}}}}


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def texts(ctx):
    """Textes a traduire : cle -> texte anglais."""
    out = {}
    preds = json.loads((ctx.results / "predictions_all.json").read_text())["predictions"]
    for p in preds:
        out[f"{p['drop_id']}-{p['k']}"] = p["claim"]
    hp = ctx.results / "horoscope.json"
    if hp.exists():
        for kind, k in json.loads(hp.read_text()).get("kinds", {}).items():
            for e in k.get("examples", []):
                out[f"horo:{kind}:{e['drop_id']}"] = e["reason"]
    return out


def run(ctx):
    src = texts(ctx)
    done = {r["key"]: r for r in ctx.conn.execute("SELECT * FROM llm_translate")}
    todo = [k for k, v in src.items() if k not in done or done[k]["src_sha"] != sha(v)]
    if todo:
        key = read_secret("openai_api_key")
        if not key:
            raise RuntimeError("secret openai_api_key absent : traduction en attente")
        from openai import OpenAI
        client = OpenAI(api_key=key, max_retries=3, timeout=180)
        for i in range(0, len(todo), BATCH):
            if ctx.should_yield():
                log(f"traduction : {len(src) - len(todo) + i}/{len(src)} textes")
                return False
            chunk = todo[i:i + BATCH]
            msg = json.dumps([{"id": k, "en": src[k]} for k in chunk], ensure_ascii=False)
            r = client.chat.completions.create(
                model=MODEL, messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": msg}],
                response_format={"type": "json_schema", "json_schema": SCHEMA}, max_completion_tokens=12000,
                reasoning_effort="low")
            got = {x["id"]: x["fr"].strip() for x in json.loads(r.choices[0].message.content)["items"]}
            for k in chunk:
                if got.get(k):
                    ctx.conn.execute("INSERT OR REPLACE INTO llm_translate VALUES (?,?,?,?,?)",
                                     (k, sha(src[k]), got[k], MODEL, int(time.time())))
            ctx.conn.commit()
        missing = [k for k in todo if not ctx.conn.execute("SELECT 1 FROM llm_translate WHERE key = ?", (k,)).fetchone()]
        if missing:
            log(f"traduction : {len(missing)} textes sans reponse, reposes au cycle suivant")
            return False
    fr = {r["key"]: r["fr"] for r in ctx.conn.execute("SELECT key, fr FROM llm_translate") if r["key"] in src}
    ctx.set_output(db.sha(write(ctx, "translations", {"model": MODEL, "fr": fr})))
    log(f"traduction : {len(fr)} textes traduits en francais")
    return True

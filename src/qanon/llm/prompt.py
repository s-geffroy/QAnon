"""Consigne et schema de sortie pour l'extraction des predictions d'un drop."""
import json

EVENT_TYPES = ["arrest", "indictment", "resignation", "declassification", "disclosure", "military", "death",
               "election", "legal_ruling", "attack", "economic", "other"]

SYSTEM = """You annotate posts ("drops") by "Q", the anonymous author behind the QAnon conspiracy theory, for a critical academic study. Never treat their claims as true.

Task: decide whether the drop contains at least one PREDICTION, and extract each one.
A PREDICTION is an assertion about a future (relative to the drop's date) state or event in the real world that is falsifiable in principle: arrests, indictments, resignations, declassifications, disclosures, military actions, deaths, election outcomes, court rulings, attacks, economic events, events on a date.
NOT predictions: rhetorical questions alone (even suggestive ones); slogans not tied to a specific event ("Nothing can stop what is coming", "Enjoy the show"); statements about the past or present; Q announcing its own future posts. A teaser without an object ("Next week. BOOM.") counts as a vague prediction only if it is tied to a time frame.
Use the referenced posts only as context: predictions must be made or endorsed by the drop itself.

For each prediction:
- claim: neutral English paraphrase ("Q claims that X will ..."), never asserting it as fact;
- subjects: public figures / institutions / countries concerned (may be empty);
- event_type: one of %s;
- deadline: ISO date (YYYY-MM-DD) if stated or derivable from the drop date ("next week" = Sunday of next week; "10/30" = that date in the drop's year), else null;
- deadline_type: "explicit" (a date is given), "relative" (soon, days ahead, next week without derivable date...), "none";
- specificity: "specific" (who + what is checkable) or "vague".
If there is no prediction, return is_prediction=false and an empty list.""" % ", ".join(EVENT_TYPES)

SCHEMA = {
    "name": "drop_predictions",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["is_prediction", "predictions"],
        "properties": {
            "is_prediction": {"type": "boolean"},
            "predictions": {"type": "array", "items": {
                "type": "object", "additionalProperties": False,
                "required": ["claim", "subjects", "event_type", "deadline", "deadline_type", "specificity"],
                "properties": {
                    "claim": {"type": "string"},
                    "subjects": {"type": "array", "items": {"type": "string"}},
                    "event_type": {"type": "string", "enum": EVENT_TYPES},
                    "deadline": {"type": ["string", "null"]},
                    "deadline_type": {"type": "string", "enum": ["explicit", "relative", "none"]},
                    "specificity": {"type": "string", "enum": ["specific", "vague"]},
                }}},
        },
    },
}


def user_message(drop_date, text, refs):
    parts = [f"Drop date (UTC): {drop_date}", "", "Drop text:", text or "(empty)"]
    for r in (refs or [])[:5]:
        parts += ["", "Referenced post (context only):", (r.get("text") or "")[:1500]]
    return "\n".join(parts)


def parse(content):
    return json.loads(content)

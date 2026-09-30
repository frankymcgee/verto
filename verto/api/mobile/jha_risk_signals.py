"""Search vocabulary for incident learning, not a determination of site risk."""

import hashlib
import html
import json
import re


CRITICAL_RISKS = {
    "Uncontrolled Release of Energy": ("stored energy", "stored pressure", "hydraulic pressure", "pneumatic pressure", "uncontrolled release of energy", "unexpected energisation", "unexpected energization"),
    "Entanglement and Crushing": ("entanglement", "entangled", "crushing", "crushed", "crush point", "pinch point", "nip point", "caught between", "caught in", "rotating equipment"),
    "Vehicles and Mobile Equipment": ("mobile plant", "mobile equipment", "vehicle interaction", "vehicle pedestrian", "reversing vehicle", "haul truck", "forklift", "light vehicle"),
    "Lifting Operations": ("lifting operation", "suspended load", "rigging", "crane lift", "lifting gear"),
    "Dropped Objects": ("dropped object", "falling object", "dropped load", "falling load"),
    "Fall from Height": ("fall from height", "falls from height", "working at height", "work at height", "unprotected edge"),
    "Contact with Electricity": ("electric shock", "electrocution", "arc flash", "live conductor", "live electrical", "contact with electricity"),
    "Confined Space": ("confined space", "oxygen deficient", "oxygen deficiency"),
    "Hot Works": ("hot work", "hot works", "welding", "cutting torch"),
    "Working Near Water": ("working near water", "work near water", "drowning", "over water"),
}

MECHANISMS = {
    "Pinch Points": ("pinch point", "pinch points", "pinched", "nip point", "nip points", "crush point", "crush points", "finger crushed", "hand crushed"),
    "Line of Fire": ("line of fire", "lineoffire", "in the path", "suspended load", "recoil", "kickback"),
    "Caught Between": ("caught between", "trapped between", "crushed between", "crushing", "crushed", "pinch point"),
    "Entanglement": ("entanglement", "entangled", "caught in", "rotating equipment", "rotating shaft"),
    "Struck By": ("struck by", "hit by", "falling object", "dropped object", "falling load"),
    "Unexpected Movement": ("unexpected movement", "unexpected start", "unintended movement", "rolled unexpectedly", "unexpected energisation", "unexpected energization"),
    "Stored Energy Release": ("stored energy", "stored pressure", "pressure release", "hose burst", "uncontrolled release of energy"),
    "Loss of Containment": ("loss of containment", "spill", "leak", "chemical release"),
    "Fall": ("fall from height", "falls from height", "fell", "slipped", "tripped"),
    "Electric Contact": ("electric shock", "electrocution", "arc flash", "live conductor"),
}

STOP_WORDS = set("this that with from into then they their there step work task team crew control controls hazard hazards risk risks safety incident near miss using used use before after been were have will would should could when while were what where only also each all for the and are was had has not its our out who how can job one two three".split())


def plain_text(value, limit=10000):
    # Imported rich text is data. Never forward executable markup to the model/UI.
    value = re.sub(r"<[^>]*>", " ", str(value or ""))
    return html.unescape(value).strip()[:limit]


def normalise_text(value):
    return " ".join(re.findall(r"[a-z0-9]+", plain_text(value).lower()))


def tags(value, vocabulary):
    values = value if isinstance(value, (list, tuple)) else re.split(r"[\n,;|]+", str(value or ""))
    if len(values) > 30:
        raise ValueError("Too many risk or mechanism labels.")
    lookup = {normalise_text(label): label for label in vocabulary}
    result = set()
    for label in values:
        if not str(label or "").strip():
            continue
        canonical = lookup.get(normalise_text(label))
        if not canonical:
            raise ValueError(f"Unknown risk/mechanism label: {str(label)[:100]}")
        result.add(canonical)
    return sorted(result)


def detect(value, vocabulary):
    text = f" {normalise_text(value)} "
    return sorted(label for label, aliases in vocabulary.items() if any(
        f" {normalise_text(alias)} " in text
        or f" {normalise_text(alias)}s " in text
        for alias in (label, *aliases)
    ))


def signals(text, critical_risks=(), mechanisms=()):
    return {
        "critical_risks": sorted(set(tags(critical_risks, CRITICAL_RISKS)) | set(detect(text, CRITICAL_RISKS))),
        "mechanisms": sorted(set(tags(mechanisms, MECHANISMS)) | set(detect(text, MECHANISMS))),
    }


def context_terms(text):
    return list(dict.fromkeys(word for word in normalise_text(text).split()
                             if len(word) > 3 and word not in STOP_WORDS))[:8]


def fingerprint(step, hazard):
    payload = [step.get("activity"), hazard.get("hazard_or_energy_source"),
               hazard.get("critical_risk_categories"), hazard.get("exposure_mechanisms")]
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False).encode()).hexdigest()


def rank_incident(incident, query_signals, terms):
    risks = set(tags(incident.get("indexed_critical_risks", incident.get("critical_risks")), CRITICAL_RISKS)) & set(query_signals["critical_risks"])
    mechanisms = set(tags(incident.get("indexed_mechanisms", incident.get("mechanisms")), MECHANISMS)) & set(query_signals["mechanisms"])
    text = f" {normalise_text(incident.get('search_text'))} "
    words = [word for word in terms if f" {word} " in text]
    # Similar event mechanisms outweigh a broad critical-risk category.
    score = 12 * len(mechanisms) + 4 * len(risks) + len(words)
    return score, {"critical_risks": sorted(risks), "mechanisms": sorted(mechanisms), "context_terms": words}

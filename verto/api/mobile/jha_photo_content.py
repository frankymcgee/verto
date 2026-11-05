"""Bounded, tool-free transcription format for photographed paper JHAs."""
import json

MAX_PAGES = 10
MAX_STEPS = 60
MAX_HAZARDS = 300
HAZARD_FIELDS = ("hazard", "controls", "critical_control", "control_owner")


def content_schema():
    def obj(properties):
        return {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}
    return obj({
        "job_description": {"type": "string"},
        "uncertainties": {"type": "array", "items": {"type": "string"}},
        "steps": {"type": "array", "items": obj({
            "page": {"type": "integer"}, "activity": {"type": "string"}, "hold_point": {"type": "string"},
            "hazards": {"type": "array", "items": obj({key: {"type": "string"} for key in HAZARD_FIELDS})},
        })},
    })


def normalise_content(value, page_count, *, for_import=False):
    if isinstance(value, str):
        if len(value) > 500_000:
            raise ValueError("The paper JHA reading is too large.")
        value = json.loads(value)
    if not isinstance(value, dict) or set(value) != {"job_description", "uncertainties", "steps"}:
        raise ValueError("Invalid paper JHA reading.")

    def text(item, limit=2000):
        if not isinstance(item, str) or len(item) > limit:
            raise ValueError("The paper JHA reading contains invalid or oversized text.")
        return item.strip()

    uncertainties = value["uncertainties"]
    steps = value["steps"]
    if not isinstance(uncertainties, list) or len(uncertainties) > 80:
        raise ValueError("Invalid paper JHA clarification list.")
    if not isinstance(steps, list) or len(steps) > MAX_STEPS or (for_import and not steps):
        raise ValueError("Supply between 1 and 60 readable job steps before importing.")
    result = {"job_description": text(value["job_description"], 1000),
              "uncertainties": [text(item, 1000) for item in uncertainties], "steps": []}
    count = 0
    for step in steps:
        if not isinstance(step, dict) or set(step) != {"page", "activity", "hold_point", "hazards"}:
            raise ValueError("Invalid paper JHA work step.")
        page = step["page"]
        if type(page) is not int or not 1 <= page <= page_count:
            raise ValueError("Each step must refer to an uploaded page.")
        activity = text(step["activity"])
        if for_import and not activity:
            raise ValueError("Correct or remove unreadable work steps before importing.")
        hazards = step["hazards"]
        if not isinstance(hazards, list) or len(hazards) > 30:
            raise ValueError("A work step can contain up to 30 hazards.")
        count += len(hazards)
        if count > MAX_HAZARDS:
            raise ValueError("A paper JHA can contain up to 300 hazards.")
        rows = []
        for hazard in hazards:
            if not isinstance(hazard, dict) or set(hazard) != set(HAZARD_FIELDS):
                raise ValueError("Invalid paper JHA hazard or control.")
            row = {key: text(hazard[key], 140 if key == "control_owner" else 2000) for key in HAZARD_FIELDS}
            if for_import and not row["hazard"]:
                raise ValueError("Correct or remove unreadable hazards before importing.")
            rows.append(row)
        result["steps"].append({"page": page, "activity": activity, "hold_point": text(step["hold_point"]), "hazards": rows})
    return result

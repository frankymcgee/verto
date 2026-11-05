"""ICAM classifications shared by Desk, the API and the investigations app.

The child DocType's Select options are the canonical code/label catalogue.
Blank classification remains valid for existing narrative-only investigations.
"""

import json
from pathlib import Path

ICAM_CATEGORIES = (
    "Absent or Failed Defences", "Individual or Team Actions",
    "Task or Environmental Conditions", "Organisational Factors",
)

_schema = json.loads((Path(__file__).parents[1] / "verto/doctype/ehs_icam_factors/ehs_icam_factors.json").read_text(encoding="utf-8"))
_options = next(field["options"] for field in _schema["fields"] if field["fieldname"] == "factor_type").splitlines()
_groups = (
    (ICAM_CATEGORIES[0], ICAM_CATEGORIES[0], "DF"),
    (ICAM_CATEGORIES[1], ICAM_CATEGORIES[1], "IT"),
    (ICAM_CATEGORIES[2], "Task / Environmental Conditions (TE)", "TE"),
    (ICAM_CATEGORIES[2], "Human Factors (HF)", "HF"),
    (ICAM_CATEGORIES[3], ICAM_CATEGORIES[3], None),
)
ICAM_FACTOR_GROUPS = tuple(
    {"category": category, "group": label, "options": [
        option for option in _options if option and (
            option.startswith(prefix) if prefix else not option.startswith(("DF", "IT", "TE", "HF"))
        )
    ]}
    for category, label, prefix in _groups
)
ICAM_FACTOR_CATEGORIES = {
    option: group["category"] for group in ICAM_FACTOR_GROUPS for option in group["options"]
}

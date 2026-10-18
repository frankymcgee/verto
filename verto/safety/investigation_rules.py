"""Evidence and review rules shared by Desk and the investigations app.

This module is independent of Frappe so the causal-graph and approval rules can
be checked without a running site. Analysis remains the investigator's work.
"""

import re

METHODS = ("5 Whys", "ICAM", "5 Whys + ICAM")
STATUSES = ("Draft", "Evidence Gathering", "Analysis", "In Review", "Actions in Progress", "Closed", "Reopened")
EDITABLE_STATUSES = frozenset(("Draft", "Evidence Gathering", "Analysis", "Reopened"))
ICAM_CATEGORIES = (
    "Absent or Failed Defences", "Individual or Team Actions",
    "Task or Environmental Conditions", "Organisational Factors",
)
CONTROL_TYPES = ("Elimination", "Substitution", "Isolation", "Engineering", "Administrative", "PPE")
FINDING_STATUSES = ("Hypothesis", "Supported", "Not supported")
ACTION_STATUSES = ("Open", "In Progress", "Completed", "Verified", "Cancelled")
ROW_TABLES = {"evidence": "E", "timeline": "T", "five_whys": "W", "icam_factors": "F", "actions": "A"}
ID_PATTERN = re.compile(r"^[EWTFA]-[a-zA-Z0-9]{8,24}$")


def refs(value):
    return list(dict.fromkeys(part.strip() for part in re.split(r"[,\n]", str(value or "")) if part.strip()))


def text(value):
    return str(value or "").strip()


def checked(value):
    return value in (True, 1, "1")


def _cycle(nodes, links):
    visited, active = set(), set()

    def visit(node):
        if node in active:
            return True
        if node in visited:
            return False
        active.add(node)
        if any(visit(other) for other in links(nodes[node]) if other in nodes):
            return True
        active.remove(node)
        visited.add(node)
        return False

    return any(visit(node) for node in nodes)


def validate_structure(data):
    errors = []
    ids = set()
    for table, prefix in ROW_TABLES.items():
        rows = data.get(table) or []
        if len(rows) > 200:
            errors.append(f"Keep {table.replace('_', ' ')} to 200 entries per investigation.")
            continue
        for row in rows:
            key = row.get("entry_id")
            if not ID_PATTERN.fullmatch(str(key or "")) or not str(key).startswith(prefix + "-"):
                errors.append(f"Invalid reference in {table.replace('_', ' ')}.")
            if key in ids:
                errors.append(f"Duplicate reference: {key}.")
            ids.add(key)

    if any(len(data.get(table) or []) > 200 for table in ROW_TABLES):
        return errors

    evidence = {row.get("entry_id"): row for row in data.get("evidence") or []}
    whys = {row.get("entry_id"): row for row in data.get("five_whys") or []}
    factors = {row.get("entry_id"): row for row in data.get("icam_factors") or []}
    for table in ("timeline", "five_whys", "icam_factors"):
        for row in data.get(table) or []:
            if any(key not in evidence for key in refs(row.get("evidence_refs"))):
                errors.append(f"{row.get('entry_id')}: select evidence that is still in this investigation.")
    for row in whys.values():
        if row.get("parent_id") and row["parent_id"] not in whys:
            errors.append(f"{row.get('entry_id')}: the preceding why no longer exists.")
        if row.get("finding_status") not in FINDING_STATUSES:
            errors.append("Choose a finding status for each why.")
    if _cycle(whys, lambda row: [row.get("parent_id")] if row.get("parent_id") else []):
        errors.append("The 5 Whys branches must not contain a circular link.")
    for row in factors.values():
        if row.get("category") not in ICAM_CATEGORIES or row.get("finding_status") not in FINDING_STATUSES:
            errors.append("Choose an ICAM category and finding status for each factor.")
        if any(key not in factors for key in refs(row.get("contributes_to"))):
            errors.append(f"{row.get('entry_id')}: a linked ICAM factor no longer exists.")
    if _cycle(factors, lambda row: refs(row.get("contributes_to"))):
        errors.append("The ICAM factor map must not contain a circular link.")
    for row in data.get("actions") or []:
        if any(key not in whys and key not in factors for key in refs(row.get("finding_refs"))):
            errors.append(f"{row.get('entry_id')}: a linked finding no longer exists.")
        if row.get("action_status") not in ACTION_STATUSES:
            errors.append("Choose a valid action status.")
    return list(dict.fromkeys(errors))


def review_readiness(data):
    errors = validate_structure(data)
    for field, label in (
        ("description", "Describe what happened"), ("immediate_response", "Record the immediate response"),
        ("lead_investigator", "Appoint a lead investigator"), ("reviewer", "Appoint a reviewer"),
        ("due_date", "Set an investigation due date"), ("findings_summary", "Summarise the investigation findings"),
        ("lessons_learned", "Record the lessons learned"),
    ):
        if not text(data.get(field)):
            errors.append(label + ".")
    if data.get("lead_investigator") == data.get("reviewer"):
        errors.append("The reviewer must be different from the lead investigator.")
    if data.get("regulatory_review") in (None, "", "Not assessed"):
        errors.append("Record the reportability assessment and its basis.")
    if not text(data.get("reportability_notes")):
        errors.append("Record the basis of the reportability assessment.")
    evidence = {row.get("entry_id"): row for row in data.get("evidence") or []}
    if not any(row.get("verification_status") == "Verified" for row in evidence.values()):
        errors.append("Verify at least one item of evidence.")

    method = data.get("method")
    required_findings = set()
    tables = []
    if method in ("5 Whys", "5 Whys + ICAM"):
        tables.append("five_whys")
        whys = data.get("five_whys") or []
        roots = [row for row in whys if checked(row.get("is_root_cause")) and row.get("finding_status") == "Supported"]
        if not roots:
            errors.append("Identify at least one supported root cause in the 5 Whys analysis.")
        by_id = {row.get("entry_id"): row for row in whys}
        for row in roots:
            required_findings.add(row.get("entry_id"))
            if not text(row.get("root_cause_reason")):
                errors.append(f"{row.get('entry_id')}: explain why the analysis can stop at this cause.")
            if any(other.get("parent_id") == row.get("entry_id") and other.get("finding_status") == "Supported" for other in whys):
                errors.append(f"{row.get('entry_id')}: a supported branch continues beyond this root cause.")
        for row in whys:
            if row.get("finding_status") == "Supported" and row.get("parent_id"):
                if by_id.get(row["parent_id"], {}).get("finding_status") != "Supported":
                    errors.append(f"{row.get('entry_id')}: resolve the preceding why before supporting this cause.")
            if row.get("finding_status") == "Supported" and not checked(row.get("is_root_cause")):
                if not any(other.get("parent_id") == row.get("entry_id") and other.get("finding_status") == "Supported" for other in whys):
                    errors.append(f"{row.get('entry_id')}: continue this supported branch or record its root-cause stopping rationale.")
    if method in ("ICAM", "5 Whys + ICAM"):
        tables.append("icam_factors")
        factors = data.get("icam_factors") or []
        supported = [row for row in factors if row.get("finding_status") == "Supported"]
        if not supported:
            errors.append("Record at least one supported ICAM factor.")
        if not any(row.get("category") == ICAM_CATEGORIES[0] for row in supported):
            errors.append("Identify a supported absent or failed defence in the ICAM analysis.")
        reviews = {row.get("category"): row for row in data.get("category_reviews") or []}
        for category in ICAM_CATEGORIES:
            if not any(row.get("category") == category for row in supported) and not text(reviews.get(category, {}).get("no_finding_reason")):
                errors.append(f"{category}: record a supported factor or explain why none was identified.")
        by_id = {row.get("entry_id"): row for row in factors}
        for row in supported:
            required_findings.add(row.get("entry_id"))
            if any(by_id.get(key, {}).get("finding_status") != "Supported" for key in refs(row.get("contributes_to"))):
                errors.append(f"{row.get('entry_id')}: causal links must point to supported factors.")
            if row.get("category") != ICAM_CATEGORIES[0] and not refs(row.get("contributes_to")):
                errors.append(f"{row.get('entry_id')}: connect this factor to the factors or failed defences it influenced.")

    for table in tables:
        for row in data.get(table) or []:
            key = row.get("entry_id")
            if not text(row.get("description")):
                errors.append(f"{key}: describe the finding.")
            if row.get("finding_status") == "Hypothesis":
                errors.append(f"{key}: resolve the hypothesis before review.")
            if row.get("finding_status") == "Supported":
                selected = refs(row.get("evidence_refs"))
                if not selected or any(evidence.get(ref, {}).get("verification_status") != "Verified" for ref in selected):
                    errors.append(f"{key}: support the finding with verified evidence.")

    covered = set()
    actions = data.get("actions") or []
    for row in actions:
        key = row.get("entry_id")
        if row.get("action_status") == "Cancelled":
            continue
        for field in ("title", "assigned_to_user", "due_date", "control_type", "success_criteria", "verifier", "verification_due_date"):
            if not text(row.get(field)):
                errors.append(f"{key}: set {field.replace('_', ' ')}.")
        if row.get("assigned_to_user") == row.get("verifier"):
            errors.append(f"{key}: assign an independent action verifier.")
        linked = refs(row.get("finding_refs"))
        if not linked or any(ref not in required_findings for ref in linked):
            errors.append(f"{key}: link the action to a supported root cause or ICAM factor.")
        covered.update(linked)
    for key in sorted(required_findings - covered):
        errors.append(f"{key}: link at least one corrective action to this finding.")
    return list(dict.fromkeys(errors))


def closure_readiness(data):
    errors = []
    if not data.get("approved_by"):
        errors.append("Approve the investigation before close-out.")
    if data.get("regulatory_review") in (None, "", "Not assessed", "Review required"):
        errors.append("Complete the reportability assessment before close-out.")
    for row in data.get("actions") or []:
        if row.get("action_status") not in ("Verified", "Cancelled"):
            errors.append(f"{row.get('entry_id')}: complete and verify the action's effectiveness.")
        if row.get("action_status") == "Cancelled" and not text(row.get("cancellation_reason")):
            errors.append(f"{row.get('entry_id')}: record the approved cancellation reason.")
    return errors

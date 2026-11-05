"""Deterministic diagram content for the saved investigation report."""

from datetime import datetime
import re

from verto.safety.investigation_rules import EVENT_TYPES, ICAM_CATEGORIES, checked, refs, text


def event_time_key(value):
    value = text(value)
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d{1,6})?)?)?", value):
        return ""
    try:
        return datetime.fromisoformat(value).isoformat(sep=" ", timespec="microseconds")
    except ValueError:
        return ""


def ordered_timeline(rows):
    # Stable sorting retains entry order for equal timestamps and undated rows.
    return sorted(rows or [], key=lambda row: (not bool(event_time_key(row.get("event_datetime"))), event_time_key(row.get("event_datetime"))))


def event_time_label(value, date_only=False):
    key = event_time_key(value)
    if not key:
        return "Time not set"
    months = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
    day = f"{key[8:10]} {months[int(key[5:7]) - 1]} {key[:4]}"
    fraction = key[20:].rstrip("0")
    clock = key[11:19] + (f".{fraction}" if fraction else "") if key[17:19] != "00" or fraction else key[11:16]
    return f"{day} - {'Date only' if date_only else clock}"


def event_type(row, doc):
    if row.get("event_type") in EVENT_TYPES:
        return row["event_type"]
    moment = text(row.get("event_datetime")).replace("T", " ")[:16]
    incident = text(doc.get("incident_datetime")).replace("T", " ")[:16]
    if not moment or not incident or doc.get("incident_time_precision") == "Date only":
        return EVENT_TYPES[0]
    return "Post event" if moment > incident else "Actual event" if moment == incident else EVENT_TYPES[0]


def _why_layout(rows):
    by_id = {row["entry_id"]: row for row in rows}
    children, positions, visited = {}, {}, set()
    for row in rows:
        children.setdefault(row.get("parent_id"), []).append(row)

    def visit(row):
        if row["entry_id"] in visited:
            return None
        visited.add(row["entry_id"])
        branches = [branch for child in children.get(row["entry_id"], []) if (branch := visit(child))]
        return {"row": row, "branches": branches, "span": max(1, sum(branch["span"] for branch in branches))}

    # Match the editor: preserve sibling entry order and keep whole subtrees
    # together, even when their rows or generated IDs are interleaved.
    roots = [visit(row) for row in rows if row.get("parent_id") not in by_id]
    for row in rows:
        if row["entry_id"] not in visited:
            roots.append(visit(row))

    def place(branch, left, depth):
        positions[branch["row"]["entry_id"]] = {"column": left + (branch["span"] - 1) / 2, "depth": depth}
        for child in branch["branches"]:
            place(child, left, depth + 1)
            left += child["span"]

    columns = 0
    for root in roots:
        if root:
            place(root, columns, 1)
            columns += root["span"]
    return positions, max(1, columns)


def diagram(doc, mode):
    nodes, edges = [], []

    def add(row, lane, kind, title):
        node = {"id": row["entry_id"], "lane": lane, "kind": kind, "title": title,
            "description": text(row.get("description")), "status": row.get("finding_status") or "",
            "evidence": refs(row.get("evidence_refs")), "time": text(row.get("event_datetime"))}
        nodes.append(node)
        return node

    incident = {"entry_id": "incident", "description": doc.get("description") or doc.get("title"),
        "event_datetime": doc.get("incident_datetime")}
    if mode == "timeline":
        add(incident, 3, "Actual event", "Actual event")
        for row in doc.get("timeline") or []:
            kind = event_type(row, doc)
            add(row, 0, kind, kind)
            edges.extend({"from": row["entry_id"], "to": target, "dashed": False} for target in refs(row.get("next_events")))
            edges.extend({"from": source, "to": row["entry_id"], "dashed": False} for source in refs(row.get("previous_events")))
        nodes.sort(key=lambda node: (not bool(event_time_key(node["time"])), event_time_key(node["time"])))
        for index, node in enumerate(nodes):
            node["lane"] = index
            node["date_only"] = node["id"] == "incident" and doc.get("incident_time_precision") == "Date only"
        lanes = [event_time_label(node["time"], node["date_only"]) for node in nodes]
        sequence = [node for node in nodes if event_time_key(node["time"]) and not node["date_only"]]
        by_id = {row["entry_id"]: row for row in doc.get("timeline") or []}
        for current, following in zip(sequence, sequence[1:]):
            if not any(refs(row.get("next_events")) or refs(row.get("previous_events")) for row in by_id.values()):
                edges.append({"from": current["id"], "to": following["id"], "dashed": True})
    elif mode == "whys":
        lanes = []
        rows = doc.get("five_whys") or []
        positions, columns = _why_layout(rows)
        add(incident, 0, "Actual event", "Actual event").update(column=(columns - 1) / 2, depth=0)
        for row in rows:
            position = positions[row["entry_id"]]
            depth = position["depth"]
            kind = "Root cause" if checked(row.get("is_root_cause")) else "Direct factor" if depth == 1 else "Contributing factor"
            add(row, depth, kind, f"Why {depth}" + (" - Root cause" if kind == "Root cause" else "")).update(position)
            edges.append({"from": row.get("parent_id") or "incident", "to": row["entry_id"], "dashed": row.get("finding_status") != "Supported"})
    else:
        lanes = list(reversed(ICAM_CATEGORIES)) + ["Actual event"]
        add(incident, 4, "Actual event", "Actual event")
        for row in doc.get("icam_factors") or []:
            defence = row.get("category") == ICAM_CATEGORIES[0]
            add(row, lanes.index(row["category"]), "Direct factor" if defence else "Contributing factor", row.get("factor_type") or row["category"])
            targets = refs(row.get("contributes_to")) or (["incident"] if defence else [])
            edges.extend({"from": row["entry_id"], "to": target, "dashed": row.get("finding_status") != "Supported"} for target in targets)
    ids = {node["id"] for node in nodes}
    unique = {(edge["from"], edge["to"]): edge for edge in edges if edge["from"] in ids and edge["to"] in ids}
    return {"nodes": nodes, "edges": list(unique.values()), "lanes": lanes}

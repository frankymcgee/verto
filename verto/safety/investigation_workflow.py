"""Deterministic diagram content for the saved investigation report."""

from verto.safety.investigation_rules import EVENT_TYPES, ICAM_CATEGORIES, checked, refs, text


def event_type(row, doc):
    if row.get("event_type") in EVENT_TYPES:
        return row["event_type"]
    moment = text(row.get("event_datetime")).replace("T", " ")[:16]
    incident = text(doc.get("incident_datetime")).replace("T", " ")[:16]
    if not moment or not incident or doc.get("incident_time_precision") == "Date only":
        return EVENT_TYPES[0]
    return "Post event" if moment > incident else "Actual event" if moment == incident else EVENT_TYPES[0]


def diagram(doc, mode):
    nodes, edges = [], []

    def add(row, lane, kind, title):
        nodes.append({"id": row["entry_id"], "lane": lane, "kind": kind, "title": title,
            "description": text(row.get("description")), "status": row.get("finding_status") or "",
            "evidence": refs(row.get("evidence_refs")), "time": text(row.get("event_datetime"))})

    incident = {"entry_id": "incident", "description": doc.get("description") or doc.get("title"),
        "event_datetime": doc.get("incident_datetime")}
    if mode == "timeline":
        lanes = list(EVENT_TYPES)
        add(incident, 3, "Actual event", "Actual event")
        for row in doc.get("timeline") or []:
            kind = event_type(row, doc)
            add(row, lanes.index(kind), kind, kind)
            edges.extend({"from": row["entry_id"], "to": target, "dashed": False} for target in refs(row.get("next_events")))
            edges.extend({"from": source, "to": row["entry_id"], "dashed": False} for source in refs(row.get("previous_events")))
        sequence = sorted((node for node in nodes if node["time"] and node["kind"] not in ("Contributing factor", "Direct factor")
            and not (node["id"] == "incident" and doc.get("incident_time_precision") == "Date only")),
            key=lambda node: node["time"].replace("T", " "))
        by_id = {row["entry_id"]: row for row in doc.get("timeline") or []}
        for current, following in zip(sequence, sequence[1:]):
            if not any(refs(row.get("next_events")) or refs(row.get("previous_events")) for row in by_id.values()):
                edges.append({"from": current["id"], "to": following["id"], "dashed": True})
    elif mode == "whys":
        lanes = ["Actual event", "Direct factors", "Contributing factors"]
        add(incident, 0, "Actual event", "Actual event")
        by_id = {row["entry_id"]: row for row in doc.get("five_whys") or []}
        for row in by_id.values():
            depth, parent, seen = 1, by_id.get(row.get("parent_id")), {row["entry_id"]}
            while parent and parent["entry_id"] not in seen:
                depth += 1
                seen.add(parent["entry_id"])
                parent = by_id.get(parent.get("parent_id"))
            while len(lanes) <= depth:
                lanes.append(f"Why {len(lanes)}")
            kind = "Root cause" if checked(row.get("is_root_cause")) else "Direct factor" if depth == 1 else "Contributing factor"
            add(row, depth, kind, f"Why {depth}" + (" - Root cause" if kind == "Root cause" else ""))
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

import frappe

@frappe.whitelist(allow_guest=True)
def create_project_handover_records(doc, method=None):
    project_name = doc.project_name or doc.name
    team = getattr(doc, "roster_or_shutdown", None)

    # Safety Handover
    if not frappe.db.exists("Safety Handover", {"project": doc.name}):
        frappe.get_doc({
            "doctype": "Safety Handover",
            "project": doc.name
        }).insert(ignore_permissions=True)

    # Lead Safety Handover
    if not frappe.db.exists("Lead Safety Handover", {"project": doc.name}):
        frappe.get_doc({
            "doctype": "Lead Safety Handover",
            "project": doc.name
        }).insert(ignore_permissions=True)

    # GP Project
    gp_project_name = frappe.db.get_value("GP Project", {"title": project_name}, "name")

    if not gp_project_name:
        gp_project = frappe.get_doc({
            "doctype": "GP Project",
            "title": project_name,
            "team": team,
            "progress": 0,
            "status": "Open",
            "readme": f"""<h3>Welcome to the {project_name} page!</h3>
<p>You can add a brief introduction about this project, links, resources, and other important information here.</p>"""
        }).insert(ignore_permissions=True)

        gp_project_name = gp_project.name

    if gp_project_name and getattr(doc, "gameplan_project", None) != gp_project_name:
        doc.db_set("gameplan_project", gp_project_name, update_modified=False)

    # Raven Channel
    raven_channel_name = frappe.db.get_value(
        "Raven Channel",
        {
            "channel_name": project_name,
            "workspace": "Mine Site Support"
        },
        "name"
    )

    if not raven_channel_name:
        raven_channel = frappe.get_doc({
            "doctype": "Raven Channel",
            "channel_name": project_name,
            "workspace": "Mine Site Support",
            "type": "Open"
        }).insert(ignore_permissions=True)

        raven_channel_name = raven_channel.name

    if raven_channel_name and getattr(doc, "raven_channel", None) != raven_channel_name:
        doc.db_set("raven_channel", raven_channel_name, update_modified=False)
        doc.db_set("raven_workspace", "Mine Site Support", update_modified=False)
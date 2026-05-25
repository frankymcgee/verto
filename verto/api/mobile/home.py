import frappe


@frappe.whitelist()
def get_home_summary():
    user = frappe.session.user

    return {
        "user": user,
        "message": "Mobile frontend API is working",
        "cards": [
            {
                "label": "Forms",
                "value": 0,
                "description": "Forms available for completion"
            },
            {
                "label": "Shifts",
                "value": 0,
                "description": "Upcoming shifts"
            },
            {
                "label": "Chat",
                "value": 0,
                "description": "Recent Raven activity"
            }
        ]
    }

# Copyright (c) 2026, Webwire Pty Ltd and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class ShutdownIncidentTracker(Document):
	def validate(self):
		set_risk_rating(self)


RISK_MATRIX = {
    "Almost Certain": {
        "Minor": "MED 16",
        "Moderate": "HIGH 22",
        "Serious": "VERY HIGH 27",
        "Major": "EXTREME 31",
        "Severe": "EXTREME 34",
        "Catastrophic": "EXTREME 36",
    },
    "Highly Likely": {
        "Minor": "MED 11",
        "Moderate": "MED 17",
        "Serious": "HIGH 23",
        "Major": "VERY HIGH 28",
        "Severe": "EXTREME 32",
        "Catastrophic": "EXTREME 35",
    },
    "Likely": {
        "Minor": "LOW 7",
        "Moderate": "MED 12",
        "Serious": "MED 18",
        "Major": "HIGH 24",
        "Severe": "VERY HIGH 29",
        "Catastrophic": "EXTREME 33",
    },
    "Possible": {
        "Minor": "LOW 4",
        "Moderate": "LOW 8",
        "Serious": "MED 13",
        "Major": "MED 19",
        "Severe": "HIGH 25",
        "Catastrophic": "VERY HIGH 30",
    },
    "Unlikely": {
        "Minor": "LOW 2",
        "Moderate": "LOW 5",
        "Serious": "LOW 9",
        "Major": "MED 14",
        "Severe": "MED 20",
        "Catastrophic": "HIGH 26",
    },
    "Highly Unlikely": {
        "Minor": "LOW 1",
        "Moderate": "LOW 3",
        "Serious": "LOW 6",
        "Major": "LOW 10",
        "Severe": "MED 15",
        "Catastrophic": "MED 21",
    },
    "PENDING": {
        "PENDING": "Pending",
    },
}


def set_risk_rating(doc):
    likelihood = doc.get("likelihood")
    consequence = doc.get("consequence")

    if not likelihood or not consequence:
        doc.risk_rating = None
        return

    risk_rating = RISK_MATRIX.get(likelihood, {}).get(consequence)

    if not risk_rating:
        frappe.throw(
            f"Invalid risk matrix combination: Likelihood '{likelihood}' and Consequence '{consequence}'."
        )

    doc.risk_rating = risk_rating
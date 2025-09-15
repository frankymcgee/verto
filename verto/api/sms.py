import re
import frappe
from frappe.core.doctype.sms_settings.sms_settings import send_sms

def _parse_receivers(raw_list: str):
    """Parse lines like:
       '1  Sean Long - +61 4 8858 9315'
       'Sean Long - +61 488 589 315'
       'Sean Long,+61 488 589 315'
       'Sean Long    +61488589315'
       Returns list of (full_name, mobile_no_no_spaces)
    """
    lines = [l.strip() for l in (raw_list or "").splitlines() if l.strip()]
    pairs = []
    for line in lines:
        # Remove a leading index if present (e.g., "1  Name - +61...")
        line = re.sub(r'^\s*\d+\s+', '', line)

        # Try a few separators between name & number
        # "Name - +61...", "Name, +61...", "Name\t+61...", "Name  +61..."
        m = re.search(r'^(?P<name>.+?)\s*(?:-|,|\t|\s{2,})\s*(?P<num>[+0-9][0-9\s]+)$', line)
        if not m:
            # As a fallback, split on the last space-ish chunk that looks like a number
            m = re.search(r'^(?P<name>.+?)\s+(?P<num>[+0-9][0-9\s]+)$', line)
        if not m:
            continue

        full_name = m.group('name').strip()
        mobile = re.sub(r'\s+', '', m.group('num'))  # strip spaces from number
        if full_name and mobile:
            pairs.append((full_name, mobile))
    return pairs

@frappe.whitelist()
def send_personalised_sms_preview(sms_center: str, message: str = None, receiver_list: str = None):
    """Render preview for the first recipient (uses live receiver_list when provided)."""
    doc = frappe.get_doc("SMS Center", sms_center)
    template = (message or doc.message or "").strip()
    raw_list = receiver_list if receiver_list is not None else (doc.receiver_list or "")

    pairs = _parse_receivers(raw_list)
    if not pairs:
        return None

    full_name, mobile = pairs[0]
    ctx = {
        "name": full_name,
        "full_name": full_name,
        "first_name": (full_name.split()[0] if full_name else ""),
        "mobile_no": mobile,
    }

    final_template = "Hi {{ first_name }},\n" + template + "\n\nMine Site Support"
    msg = frappe.render_template(final_template, ctx)

    return {"name": full_name, "mobile_no": mobile, "message": msg}

@frappe.whitelist()
def send_personalised_sms_from_center(sms_center: str, message: str = None, receiver_list: str = None):
    """Send personalised SMS using the live message & receiver list from the form when passed."""
    doc = frappe.get_doc("SMS Center", sms_center)
    template = (message or doc.message or "").strip()
    raw_list = receiver_list if receiver_list is not None else (doc.receiver_list or "")

    pairs = _parse_receivers(raw_list)
    sent = 0

    for full_name, mobile in pairs:
        ctx = {
            "name": full_name,
            "full_name": full_name,
            "first_name": (full_name.split()[0] if full_name else ""),
            "mobile_no": mobile,
        }
        final_template = "Hi {{ first_name }},\n" + template + "\n\nMine Site Support"
        msg = frappe.render_template(final_template, ctx)
        send_sms([mobile], msg)
        sent += 1

    return {"sent": sent}

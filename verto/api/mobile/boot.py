import frappe
from frappe.utils import get_url


SETTINGS_DOCTYPE = "Verto Mobile Settings"


DEFAULT_BOOT = {
    "app_name": "Verto Mobile",
    "app_icon": "/assets/verto/images/verto-icon.png",
    "app_logo": "",
    "favicon": "",
    "default_workspace": "",
    "default_chat_channel": "general",
    "peri_bot_name": "P.E.R.I.",
    "peri_bot_user": "",
    "peri_bot_image": "",
    "fallback_home_route": "/",
}


def require_login():
    if frappe.session.user == "Guest":
        frappe.throw("Login required", frappe.PermissionError)


def doctype_exists(doctype):
    return bool(frappe.db.exists("DocType", doctype))


def get_mobile_settings():
    try:
        return frappe.get_cached_doc(SETTINGS_DOCTYPE)
    except Exception:
        return None


def get_setting(settings, fieldname, default=None):
    if not settings or not settings.meta.has_field(fieldname):
        return default

    value = settings.get(fieldname)

    if value in (None, ""):
        return default

    return value


def get_enabled_rows(settings, fieldname, fields):
    """Return enabled child-table rows as plain dictionaries for mobile boot."""
    if not settings or not settings.meta.has_field(fieldname):
        return []

    rows = []

    for row in settings.get(fieldname) or []:
        if row.meta.has_field("enabled") and not row.get("enabled"):
            continue

        rows.append({
            field: row.get(field)
            for field in fields
            if row.meta.has_field(field)
        })

    return rows


def get_site_base_url():
    """
    Return the current tenant/site base URL.

    frappe.utils.get_url() will use the active request/site context, and can
    also use host_name from site_config when needed.
    """
    return get_url().rstrip("/")


def normalise_asset_url(value):
    """
    Keep relative URLs relative where possible, but also provide a safe value
    that works if a full URL is already stored in settings.
    """
    if not value:
        return ""

    value = str(value).strip()

    if value.startswith(("http://", "https://", "data:")):
        return value

    if not value.startswith("/"):
        value = f"/{value}"

    return value


def absolute_url(value):
    if not value:
        return ""

    value = str(value).strip()

    if value.startswith(("http://", "https://", "data:")):
        return value

    if not value.startswith("/"):
        value = f"/{value}"

    return get_url(value)


def get_user_image(user):
    if not user:
        return ""

    return frappe.db.get_value(
        "User",
        user,
        "user_image",
    ) or ""


def get_peri_bot_image_from_raven(bot_name):
    if not bot_name:
        return ""

    if not frappe.db.exists("DocType", "Raven Bot"):
        return ""

    meta = frappe.get_meta("Raven Bot")

    image_fields = []

    for df in meta.fields:
        fieldname = df.fieldname or ""
        label = df.label or ""
        fieldtype = df.fieldtype or ""

        if fieldtype in ["Attach", "Attach Image", "Image"]:
            image_fields.append(fieldname)
            continue

        lowered = f"{fieldname} {label}".lower()

        if any(keyword in lowered for keyword in ["image", "avatar", "photo", "picture", "icon"]):
            image_fields.append(fieldname)

    image_fields = list(dict.fromkeys(image_fields))

    if not image_fields:
        return ""

    bot_docname = None

    if frappe.db.exists("Raven Bot", bot_name):
        bot_docname = bot_name
    else:
        for fieldname in ["bot_name", "title", "full_name", "name"]:
            if fieldname == "name" or frappe.get_meta("Raven Bot").has_field(fieldname):
                found = frappe.db.get_value(
                    "Raven Bot",
                    {
                        fieldname: bot_name,
                    },
                    "name",
                )

                if found:
                    bot_docname = found
                    break

    if not bot_docname:
        return ""

    fields = ["name"] + image_fields

    bot_doc = frappe.db.get_value(
        "Raven Bot",
        bot_docname,
        fields,
        as_dict=True,
    )

    if not bot_doc:
        return ""

    for fieldname in image_fields:
        if bot_doc.get(fieldname):
            return bot_doc.get(fieldname)

    return ""


@frappe.whitelist()
def get_mobile_boot():
    require_login()

    settings = get_mobile_settings()

    app_icon = normalise_asset_url(
        get_setting(settings, "app_icon", DEFAULT_BOOT["app_icon"])
    )

    app_logo = normalise_asset_url(
        get_setting(settings, "app_logo", DEFAULT_BOOT["app_logo"])
    )

    favicon = normalise_asset_url(
        get_setting(settings, "favicon", DEFAULT_BOOT["favicon"])
    )

    peri_bot_name = get_setting(settings, 
        "peri_bot_name",
        DEFAULT_BOOT["peri_bot_name"],
    )

    configured_peri_bot_image = normalise_asset_url(
        get_setting(settings, "peri_bot_image", DEFAULT_BOOT["peri_bot_image"])
    )

    resolved_peri_bot_image = configured_peri_bot_image or normalise_asset_url(
        get_peri_bot_image_from_raven(peri_bot_name)
    )

    user_details = frappe.db.get_value(
        "User",
        frappe.session.user,
        ["full_name", "user_image"],
        as_dict=True,
    ) or {}

    user_image = normalise_asset_url(
        user_details.get("user_image")
    )

    mobile_configuration = {
        "forms": {
            "generic": get_enabled_rows(
                settings,
                "generic_forms",
                ["doc_type", "label"],
            ),
            "project": get_enabled_rows(
                settings,
                "project_forms",
                ["doc_type", "label"],
            ),
            "project_ccvs": get_enabled_rows(
                settings,
                "project_ccvs",
                ["doc_type", "label"],
            ),
        },
        "project_tools": get_enabled_rows(
            settings,
            "project_tools",
            ["tool_key", "label", "description"],
        ),
    }

    return {
        "site_name": frappe.local.site,
        "base_url": get_site_base_url(),

        # App identity
        "app_name": get_setting(settings, "app_name", DEFAULT_BOOT["app_name"]),
        "app_icon": app_icon,
        "app_icon_url": absolute_url(app_icon),
        "app_logo": app_logo,
        "app_logo_url": absolute_url(app_logo),
        "favicon": favicon,
        "favicon_url": absolute_url(favicon),

        # Mobile routing
        "app_route_base": "/verto-mobile",
        "fallback_home_route": get_setting(settings, 
            "fallback_home_route",
            DEFAULT_BOOT["fallback_home_route"],
        ),

        # Chat/Raven defaults
        "default_workspace": get_setting(settings, 
            "default_workspace",
            DEFAULT_BOOT["default_workspace"],
        ),
        "default_chat_channel": get_setting(settings, 
            "default_chat_channel",
            DEFAULT_BOOT["default_chat_channel"],
        ),
        "peri_bot_name": peri_bot_name,
        "peri_bot_user": get_setting(settings, 
            "peri_bot_user",
            DEFAULT_BOOT["peri_bot_user"],
        ),
        "peri_bot_image": resolved_peri_bot_image,
        "peri_bot_image_url": absolute_url(resolved_peri_bot_image),

        # API helpers
        "api_method_base": "/api/method",
        "api_resource_base": "/api/resource",

        # Administrator-controlled mobile application configuration
        "configuration": mobile_configuration,

        # Current user
        "user": frappe.session.user,
        "user_fullname": user_details.get("full_name") or frappe.session.user,
        "user_image": user_image,
        "user_image_url": absolute_url(user_image),
    }
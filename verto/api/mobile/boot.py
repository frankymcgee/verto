import frappe
from frappe.utils import cint, flt, get_url


SETTINGS_DOCTYPE = "Verto Mobile Settings"


DEFAULT_MAP_SETTINGS = {
    "center_latitude": -32.5279,
    "center_longitude": 115.7189,
    "default_zoom": 6,
    "min_zoom": 0,
    "max_zoom": 19,
    "default_tile_url": "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
    "default_attribution": (
        '&copy; <a href="https://www.openstreetmap.org/copyright">'
        "OpenStreetMap</a> contributors"
    ),
    "satellite_tile_url": (
        "https://server.arcgisonline.com/ArcGIS/rest/services/"
        "World_Imagery/MapServer/tile/{z}/{y}/{x}"
    ),
    "satellite_attribution": "Tiles &copy; Esri and the GIS User Community",
    "labels_tile_url": (
        "https://services.arcgisonline.com/ArcGIS/rest/services/Reference/"
        "World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}"
    ),
    "labels_attribution": "Labels &copy; Esri",
    "terrain_tile_url": (
        "https://server.arcgisonline.com/ArcGIS/rest/services/"
        "World_Terrain_Base/MapServer/tile/{z}/{y}/{x}"
    ),
    "terrain_attribution": "Terrain &copy; Esri",
    "terrain_max_zoom": 13,
    "terrain_opacity": 0.45,
}


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


def get_map_settings():
    """Return validated map configuration from Verto Mobile Settings."""
    settings = get_mobile_settings()

    return {
        "center_latitude": flt(
            get_setting(
                settings,
                "map_center_latitude",
                DEFAULT_MAP_SETTINGS["center_latitude"],
            )
        ),
        "center_longitude": flt(
            get_setting(
                settings,
                "map_center_longitude",
                DEFAULT_MAP_SETTINGS["center_longitude"],
            )
        ),
        "default_zoom": cint(
            get_setting(
                settings,
                "map_default_zoom",
                DEFAULT_MAP_SETTINGS["default_zoom"],
            )
        ),
        "min_zoom": cint(
            get_setting(settings, "map_min_zoom", DEFAULT_MAP_SETTINGS["min_zoom"])
        ),
        "max_zoom": cint(
            get_setting(settings, "map_max_zoom", DEFAULT_MAP_SETTINGS["max_zoom"])
        ),
        "default_tile_url": get_setting(
            settings,
            "map_default_tile_url",
            DEFAULT_MAP_SETTINGS["default_tile_url"],
        ),
        "default_attribution": get_setting(
            settings,
            "map_default_attribution",
            DEFAULT_MAP_SETTINGS["default_attribution"],
        ),
        "satellite_tile_url": get_setting(
            settings,
            "map_satellite_tile_url",
            DEFAULT_MAP_SETTINGS["satellite_tile_url"],
        ),
        "satellite_attribution": get_setting(
            settings,
            "map_satellite_attribution",
            DEFAULT_MAP_SETTINGS["satellite_attribution"],
        ),
        "labels_tile_url": get_setting(
            settings,
            "map_labels_tile_url",
            DEFAULT_MAP_SETTINGS["labels_tile_url"],
        ),
        "labels_attribution": get_setting(
            settings,
            "map_labels_attribution",
            DEFAULT_MAP_SETTINGS["labels_attribution"],
        ),
        "terrain_tile_url": get_setting(
            settings,
            "map_terrain_tile_url",
            DEFAULT_MAP_SETTINGS["terrain_tile_url"],
        ),
        "terrain_attribution": get_setting(
            settings,
            "map_terrain_attribution",
            DEFAULT_MAP_SETTINGS["terrain_attribution"],
        ),
        "terrain_max_zoom": cint(
            get_setting(
                settings,
                "map_terrain_max_zoom",
                DEFAULT_MAP_SETTINGS["terrain_max_zoom"],
            )
        ),
        "terrain_opacity": flt(
            get_setting(
                settings,
                "map_terrain_opacity",
                DEFAULT_MAP_SETTINGS["terrain_opacity"],
            )
        ),
    }


def add_map_settings_to_boot(bootinfo):
    """Expose site map settings to Desk before map controls initialise."""
    bootinfo.verto_map_settings = get_map_settings()


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

        # Current user
        "user": frappe.session.user,
        "user_fullname": user_details.get("full_name") or frappe.session.user,
        "user_image": user_image,
        "user_image_url": absolute_url(user_image),
    }
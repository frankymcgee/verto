from __future__ import annotations

import frappe


VERTO_PLANNER_MANAGER = "Verto Planner Manager"
VERTO_PLANNER_USER = "Verto Planner User"
VERTO_MOBILE_MANAGER = "Verto Mobile Manager"
VERTO_MOBILE_USER = "Verto Mobile User"

ROLE_PROFILE_DEFINITIONS = {
    VERTO_PLANNER_MANAGER: (VERTO_PLANNER_MANAGER,),
    VERTO_PLANNER_USER: (VERTO_PLANNER_USER,),
    VERTO_MOBILE_MANAGER: (VERTO_MOBILE_MANAGER,),
    VERTO_MOBILE_USER: (VERTO_MOBILE_USER,),
}

# Both app cards intentionally use all four roles for now. These sets can be
# narrowed independently when Planner and Mobile permissions become granular.
PLANNER_APP_ROLES = frozenset(ROLE_PROFILE_DEFINITIONS)
MOBILE_APP_ROLES = frozenset(ROLE_PROFILE_DEFINITIONS)
SYSTEM_ACCESS_ROLES = frozenset({"System Manager"})


def can_view_planner_app() -> bool:
    """Return whether the current user can see the Verto Planner app card."""
    return _current_user_has_any_role(PLANNER_APP_ROLES)


def can_view_mobile_app() -> bool:
    """Return whether the current user can see the Verto Mobile app card."""
    return _current_user_has_any_role(MOBILE_APP_ROLES)


def _current_user_has_any_role(allowed_roles: frozenset[str]) -> bool:
    user = frappe.session.user

    if not user or user == "Guest":
        return False
    if user == "Administrator":
        return True

    roles = set(frappe.get_roles(user))
    return bool(roles.intersection(allowed_roles | SYSTEM_ACCESS_ROLES))


def ensure_access_roles_and_profiles() -> dict:
    """Create Verto access roles and matching Role Profiles idempotently.

    Existing profiles are never reset: the required Verto role is appended if
    missing, while any additional roles configured by an administrator remain.
    """

    results = {
        "roles_created": [],
        "roles_updated": [],
        "profiles_created": [],
        "profiles_updated": [],
    }

    for role_name in ROLE_PROFILE_DEFINITIONS:
        state = _ensure_role(role_name)
        if state:
            results[f"roles_{state}"].append(role_name)

    for profile_name, required_roles in ROLE_PROFILE_DEFINITIONS.items():
        state = _ensure_role_profile(profile_name, required_roles)
        if state:
            results[f"profiles_{state}"].append(profile_name)

    if any(results.values()):
        frappe.clear_cache()

    return results


def _ensure_role(role_name: str) -> str | None:
    if not frappe.db.exists("Role", role_name):
        frappe.get_doc(
            {
                "doctype": "Role",
                "role_name": role_name,
                "desk_access": 1,
                "disabled": 0,
                "is_custom": 1,
            }
        ).insert(ignore_permissions=True)
        return "created"

    role = frappe.get_doc("Role", role_name)
    changed = False

    for fieldname, value in {
        "desk_access": 1,
        "disabled": 0,
        "is_custom": 1,
    }.items():
        if role.get(fieldname) != value:
            role.set(fieldname, value)
            changed = True

    if changed:
        role.save(ignore_permissions=True)
        return "updated"

    return None


def _ensure_role_profile(
    profile_name: str,
    required_roles: tuple[str, ...],
) -> str | None:
    if not frappe.db.exists("Role Profile", profile_name):
        frappe.get_doc(
            {
                "doctype": "Role Profile",
                "role_profile": profile_name,
                "roles": [{"role": role_name} for role_name in required_roles],
            }
        ).insert(ignore_permissions=True)
        return "created"

    profile = frappe.get_doc("Role Profile", profile_name)
    existing_roles = {row.role for row in profile.roles if row.role}
    missing_roles = [
        role_name for role_name in required_roles if role_name not in existing_roles
    ]

    if not missing_roles:
        return None

    for role_name in missing_roles:
        profile.append("roles", {"role": role_name})

    profile.save(ignore_permissions=True)
    return "updated"

"""Database-backed coverage for whiteboard privacy, publishing and concurrent saves."""

import copy
import json
from urllib.parse import parse_qs, urlsplit

import frappe
from frappe.tests import IntegrationTestCase

from verto.api import whiteboard


def workbook():
    return {"type": "verto-whiteboard", "version": 1, "activePageId": "page-one", "pages": [{
        "id": "page-one", "title": "Page 1", "bounds": {"x": 0, "y": 0, "width": 1600, "height": 900},
        "scene": {"elements": [], "appState": {}, "files": {}},
    }]}


class TestWhiteboard(IntegrationTestCase):
    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")
        self.owner_user = "whiteboard-owner@example.test"
        self.reader_user = "whiteboard-reader@example.test"
        self.portal_user = "whiteboard-portal@example.test"
        for email in (self.owner_user, self.reader_user, self.portal_user):
            if not frappe.db.exists("User", email):
                frappe.get_doc({
                    "doctype": "User", "email": email, "first_name": "Whiteboard test", "send_welcome_email": 0,
                    "user_type": "Website User" if email == self.portal_user else "System User",
                    "roles": [] if email == self.portal_user else [{"role": "Desk User"}],
                }).insert(ignore_permissions=True)
        frappe.set_user(self.owner_user)
        self.board = whiteboard.create_whiteboard("Office test board", json.dumps(workbook()))

    def tearDown(self):
        frappe.set_user("Administrator")
        super().tearDown()

    def share(self, visibility):
        self.board = whiteboard.update_whiteboard_sharing(
            self.board["name"], visibility, self.board["revision"],
        )
        return parse_qs(urlsplit(self.board["display_url"]).fragment).get("token", [None])[0]

    def test_workspace_readers_cannot_edit_or_change_sharing(self):
        frappe.set_user(self.reader_user)
        snapshot = whiteboard.get_whiteboard(self.board["name"])
        self.assertFalse(snapshot["can_edit"])
        self.assertNotIn("display_url", snapshot)
        self.assertIn(self.board["name"], [row.name for row in whiteboard.get_whiteboards()])
        with self.assertRaises(frappe.PermissionError):
            whiteboard.save_whiteboard(json.dumps(workbook()), snapshot["revision"], self.board["name"])
        with self.assertRaises(frappe.PermissionError):
            whiteboard.update_whiteboard_sharing(self.board["name"], "Public link", snapshot["revision"])
        self.assertFalse(frappe.has_permission("Verto Whiteboard", "write", doc=self.board["name"]))

    def test_private_board_is_filtered_from_lists_and_direct_reads(self):
        self.share("Private")
        frappe.set_user(self.reader_user)
        self.assertNotIn(self.board["name"], [row.name for row in whiteboard.get_whiteboards()])
        with self.assertRaises(frappe.PermissionError):
            whiteboard.get_whiteboard(self.board["name"])
        self.assertFalse(frappe.has_permission("Verto Whiteboard", "read", doc=self.board["name"]))

    def test_guest_requires_opt_in_and_exact_token_even_for_unchanged_revision(self):
        token = self.share("Public link")
        frappe.set_user("Guest")
        for wrong in (None, "wrong", "é" * 43):
            with self.assertRaises(frappe.PermissionError):
                whiteboard.get_whiteboard(self.board["name"], token=wrong, revision=self.board["revision"])
        snapshot = whiteboard.get_whiteboard(self.board["name"], token=token)
        self.assertEqual(snapshot["state"], workbook())
        self.assertFalse(snapshot["can_edit"])
        self.assertNotIn("display_url", snapshot)
        self.assertNotIn("public_token", snapshot)
        self.assertFalse(frappe.has_permission("Verto Whiteboard", "read", doc=self.board["name"]))
        with self.assertRaises(frappe.PermissionError):
            whiteboard.save_whiteboard(json.dumps(workbook()), self.board["revision"], self.board["name"])
        with self.assertRaises(frappe.PermissionError):
            whiteboard.get_whiteboards()
        self.assertEqual(frappe.local.response_headers["Cache-Control"], "no-store")

    def test_revoked_links_stay_revoked_when_published_again(self):
        old_token = self.share("Public link")
        self.share("Workspace")
        frappe.set_user("Guest")
        with self.assertRaises(frappe.PermissionError):
            whiteboard.get_whiteboard(self.board["name"], token=old_token)
        frappe.set_user(self.owner_user)
        new_token = self.share("Public link")
        self.assertNotEqual(old_token, new_token)
        frappe.set_user("Guest")
        with self.assertRaises(frappe.PermissionError):
            whiteboard.get_whiteboard(self.board["name"], token=old_token)
        self.assertEqual(whiteboard.get_whiteboard(self.board["name"], token=new_token)["name"], self.board["name"])

    def test_portal_account_is_not_a_workspace_reader(self):
        frappe.set_user(self.portal_user)
        with self.assertRaises(frappe.PermissionError):
            whiteboard.get_whiteboard(self.board["name"])
        with self.assertRaises(frappe.PermissionError):
            whiteboard.create_whiteboard("Portal board", json.dumps(workbook()))

    def test_stale_save_cannot_overwrite_newer_content(self):
        changed = workbook()
        changed["pages"][0]["title"] = "Newer content"
        result = whiteboard.save_whiteboard(json.dumps(changed), self.board["revision"], self.board["name"])
        self.assertGreater(result["revision"], self.board["revision"])
        with self.assertRaises(frappe.TimestampMismatchError):
            whiteboard.save_whiteboard(json.dumps(workbook()), self.board["revision"], self.board["name"])
        self.assertEqual(whiteboard.get_whiteboard(self.board["name"])["state"], changed)

    def test_personal_state_is_scoped_to_the_current_user_and_legacy_writes_are_blocked(self):
        initial = whiteboard.get_whiteboard()
        whiteboard.save_whiteboard(json.dumps(workbook()), initial["revision"])
        with self.assertRaises(frappe.ValidationError):
            whiteboard.save_user_whiteboard_state(json.dumps({"type": "excalidraw", "elements": []}))
        self.assertEqual(whiteboard.get_whiteboard()["state"], workbook())
        frappe.set_user(self.reader_user)
        self.assertNotEqual(whiteboard.get_whiteboard()["state"], workbook())
        frappe.set_user("Guest")
        with self.assertRaises(frappe.PermissionError):
            whiteboard.get_whiteboard()

    def test_unchanged_poll_omits_scene_data(self):
        result = whiteboard.get_whiteboard(self.board["name"], revision=self.board["revision"])
        self.assertTrue(result["not_modified"])
        self.assertNotIn("state", result)

    def test_invalid_page_data_is_rejected_without_changing_the_board(self):
        invalids = []
        for change in (lambda s: s.update(activePageId="missing"),
                       lambda s: s["pages"].append(copy.deepcopy(s["pages"][0])),
                       lambda s: s["pages"][0]["bounds"].update(width=-1)):
            state = workbook()
            change(state)
            invalids.append(state)
        for state in invalids:
            with self.assertRaises(frappe.ValidationError):
                whiteboard.save_whiteboard(json.dumps(state), self.board["revision"], self.board["name"])
        self.assertEqual(whiteboard.get_whiteboard(self.board["name"])["state"], workbook())

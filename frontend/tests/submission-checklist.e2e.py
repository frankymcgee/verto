"""Production mobile form checklist coverage, including real native validity."""
import argparse
from functools import partial
from http.server import ThreadingHTTPServer
import importlib.util
import json
import os
from pathlib import Path
import re
from threading import Thread
from urllib.parse import unquote, urlparse

from playwright.sync_api import expect, sync_playwright

spec = importlib.util.spec_from_file_location("checklist_fixture", Path(__file__).with_name("timesheets.e2e.py"))
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)
RESULTS = fixture.RESULTS
SCHEMA = {"mobile_doctype": "field-interaction", "doctype": "Field Interaction", "title": "Field Interaction", "fields": [
    {"fieldname": "notes", "label": "Notes", "fieldtype": "Data"},
    {"fieldname": "quantity", "label": "Quantity", "fieldtype": "Int", "required": True},
    {"fieldname": "email", "label": "Email", "fieldtype": "Email"},
    {"fieldname": "review_tab", "label": "Review", "fieldtype": "Tab Break"},
    {"fieldname": "signature", "label": "Supervisor signature", "fieldtype": "Signature", "required": True},
    {"fieldname": "rows", "label": "Observations", "fieldtype": "Table", "required": True, "child_fields": [
        {"fieldname": "detail", "label": "Observation detail", "fieldtype": "Data", "required": True},
    ]},
]}
VALUES = {"notes": "Keep my notes", "quantity": 0, "email": "invalid-email", "rows": [{"detail": "First row"}, {"detail": ""}]}


def queued_count(page):
    return page.evaluate("""() => new Promise((resolve, reject) => {
        const request = indexedDB.open('verto-mobile-offline-db');
        request.onerror = () => reject(request.error);
        request.onsuccess = () => {
            const db = request.result;
            const read = db.transaction('offline_queue').objectStore('offline_queue').count();
            read.onsuccess = () => { resolve(read.result); db.close(); };
            read.onerror = () => { reject(read.error); db.close(); };
        };
    })""")


def check_form(browser, origin, engine, width, edit):
    context = fixture.context_for(browser, width)
    page = context.new_page()
    saves = []
    attachments = []
    normal_api = fixture.api_fixture([])

    def api(route):
        method = urlparse(route.request.url).path.rsplit("/", 1)[-1]
        message = None
        if method.endswith("get_form_schema"): message = SCHEMA
        elif method.endswith("get_prefill_values"): message = {"values": VALUES}
        elif method.endswith("get_mobile_doc_for_edit"):
            message = {"doctype": "Field Interaction", "name": "FORM-1", "schema": SCHEMA, "values": VALUES, "can_write": True, "files": [], "docstatus": 0}
        elif method.endswith("get_offline_bootstrap"): message = {"user": fixture.USER, "schemas": {"field-interaction": SCHEMA}}
        elif method.endswith("sync_action"):
            payload = fixture.form_values(route.request)
            values = json.loads(payload["values"])
            saves.append(values)
            message = {"ok": True, "result": {"doctype": "Field Interaction", "name": "FORM-1", "route": "/forms", "values": values, "files": []}}
        elif method == "upload_file":
            metadata = json.loads(unquote(route.request.headers["x-verto-attachment"]))
            attachments.append({"name": metadata["file_name"], "content": route.request.post_data_buffer.decode()})
            message = {"file_url": "/private/files/site-note.txt"}
        if message is None: normal_api(route)
        else: route.fulfill(content_type="application/json", body=json.dumps({"message": message}))

    page.route("**/api/method/**", api)
    mode = "edit" if edit else "new"
    try:
        page.goto(f"{origin}/verto-mobile/{'edit/field-interaction/FORM-1' if edit else 'new/field-interaction'}")
        submit = page.get_by_role("button", name="Save Changes" if edit else "Submit", exact=True)
        expect(submit).to_be_enabled()
        page.locator('input[type="file"]').set_input_files({"name": "site-note.txt", "mimeType": "text/plain", "buffer": b"Retain this attachment"})
        submit.click()
        checklist = page.locator('form [aria-label="Submission checklist"]')
        expect(checklist).to_contain_text("3 items need attention")
        expect(checklist).to_contain_text("Review · Observations · Row 2")
        expect(page.get_by_label("Notes", exact=True)).to_have_value("Keep my notes")
        expect(page.get_by_text("site-note.txt", exact=True)).to_be_visible()
        assert not saves, "An incomplete form was sent to the server"
        assert queued_count(page) == 0, "An incomplete form entered the offline queue"
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), "Checklist overflowed viewport"
        page.screenshot(path=str(RESULTS / f"{engine}-checklist-{mode}-{width}.png"))

        checklist.get_by_role("button", name=re.compile("Observation detail")).click()
        dialog = page.get_by_role("dialog")
        expect(dialog.locator('h2:not(.sr-only)').filter(has_text="Edit row")).to_be_visible()
        detail = dialog.get_by_role("textbox", name=re.compile("^Observation detail"))
        expect(detail).to_have_value("")
        dialog.get_by_role("button", name="Save Row", exact=True).click()
        expect(dialog.locator('[aria-label="Submission checklist"]')).to_contain_text("1 item needs attention")
        assert not saves
        detail.fill("Updated second row")
        dialog.get_by_role("button", name="Save Row", exact=True).click()
        if edit:
            expect(dialog.get_by_text("Other form items need attention.", exact=False)).to_be_visible()
            detail.fill("Latest second row")
            dialog.get_by_role("button", name="Keep row and review form", exact=True).click()
        expect(dialog).not_to_be_visible()
        assert not saves, "Saving a row queued an incomplete parent form"
        assert queued_count(page) == 0, "The incomplete parent was queued while reviewing a row"
        expect(checklist).to_contain_text("2 items need attention")

        checklist.get_by_role("button", name=re.compile("Supervisor signature")).click()
        canvas = page.locator('[data-form-field="signature"] canvas')
        expect(canvas).to_be_in_viewport()
        canvas.scroll_into_view_if_needed()
        rect = canvas.bounding_box()
        page.mouse.move(rect["x"] + 20, rect["y"] + 40)
        page.mouse.down()
        page.mouse.move(rect["x"] + 50, rect["y"] + 65, steps=4)
        page.mouse.move(rect["x"] + 90, rect["y"] + 30, steps=4)
        page.mouse.up()
        expect(checklist).to_contain_text("1 item needs attention")
        checklist.get_by_role("button", name=re.compile("Email")).click()
        expect(page.get_by_label("Email", exact=True)).to_be_focused()
        page.get_by_label("Email", exact=True).fill("crew@example.test")
        expect(checklist).to_contain_text("No missing required items")
        submit.click()
        if edit: expect(page.get_by_text("Saved successfully.", exact=True)).to_be_visible()
        else: expect(page).to_have_url(f"{origin}/verto-mobile/forms")
        assert len(saves) == 1, f"Expected one save, received {len(saves)}"
        values = saves[0]
        assert values["rows"] == [{"detail": "First row"}, {"detail": "Latest second row" if edit else "Updated second row"}], values["rows"]
        assert values["quantity"] == 0 and values["notes"] == "Keep my notes" and values["signature"].startswith("data:image/png"), "Parent values or signature were lost"
        assert attachments == [{"name": "site-note.txt", "content": "Retain this attachment"}], attachments
        print(f"{engine} {width}px {mode}: cross-tab checklist, exact row, native email validity and retained attachment; one valid save", flush=True)
    finally:
        context.close()


def check_long_form(browser, origin, engine):
    context = fixture.context_for(browser, 440)
    page = context.new_page()
    normal_api = fixture.api_fixture([])

    def api(route):
        method = urlparse(route.request.url).path.rsplit("/", 1)[-1]
        if method.endswith("get_form_schema"):
            schema = {**SCHEMA, "fields": [{"fieldname": f"answer_{i}", "label": f"Answer {i}", "fieldtype": "Data", "required": True} for i in range(30)]}
            route.fulfill(content_type="application/json", body=json.dumps({"message": schema}))
        elif method.endswith("get_prefill_values"):
            route.fulfill(content_type="application/json", body=json.dumps({"message": {"values": {}}}))
        else: normal_api(route)

    page.route("**/api/method/**", api)
    try:
        page.goto(f"{origin}/verto-mobile/new/field-interaction")
        page.get_by_role("button", name="Submit", exact=True).click()
        checklist = page.locator('form [aria-label="Submission checklist"]')
        expect(checklist).to_contain_text("30 items need attention")
        expect(checklist.get_by_role("heading", name="Submission checklist", exact=True)).to_be_in_viewport()
        expect(checklist.get_by_role("button", name=re.compile("^Answer 0"))).to_be_in_viewport()
        assert queued_count(page) == 0
        page.screenshot(path=str(RESULTS / f"{engine}-checklist-long-form.png"))
        print(f"{engine} long form: checklist heading and first item remain visible with 30 missing answers", flush=True)
    finally:
        context.close()


def main(engines):
    RESULTS.mkdir(exist_ok=True)
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(fixture.layout.Handler, directory=str(fixture.layout.PUBLIC)))
    Thread(target=server.serve_forever, daemon=True).start()
    try:
        with sync_playwright() as playwright:
            for engine in engines:
                options = {"headless": True}
                if engine == "chromium":
                    options["args"] = ["--no-sandbox"]
                    if os.environ.get("CHROMIUM_BINARY"): options["executable_path"] = os.environ["CHROMIUM_BINARY"]
                browser = getattr(playwright, engine).launch(**options)
                try:
                    for width in (320, 440, 1280):
                        for edit in (False, True): check_form(browser, f"http://127.0.0.1:{server.server_port}", engine, width, edit)
                    check_long_form(browser, f"http://127.0.0.1:{server.server_port}", engine)
                finally:
                    browser.close()
    finally:
        server.shutdown()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--browser", action="append", choices=("chromium", "webkit"))
    main(parser.parse_args().browser or ("chromium", "webkit"))

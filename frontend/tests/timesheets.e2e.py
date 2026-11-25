"""Production-build phone/desktop coverage for hours confirmation and exceptions."""
import argparse
from email import message_from_bytes
from functools import partial
from http.server import ThreadingHTTPServer
import importlib.util
import json
import os
from pathlib import Path
from threading import Thread
from urllib.parse import urlparse

from playwright.sync_api import expect, sync_playwright

spec = importlib.util.spec_from_file_location("timesheet_layout_fixture", Path(__file__).with_name("mobile-shell-layout.e2e.py"))
layout = importlib.util.module_from_spec(spec)
spec.loader.exec_module(layout)
RESULTS = Path(__file__).resolve().parent.parent / "test-results"
USER = "layout@example.test"
VALUES = {"duration": 45000, "date": "2026-10-05", "start_time": "06:00:00", "end_time": "18:30:00", "comments": "Keep these notes"}
SCHEMA = {"mobile_doctype": "daily-timesheet", "doctype": "Daily Timesheet", "title": "Daily Timesheet", "fields": [
    {"fieldname": "date", "label": "Work date", "fieldtype": "Date", "read_only": True},
    {"fieldname": "start_time", "label": "Start", "fieldtype": "Time", "read_only": True},
    {"fieldname": "end_time", "label": "End", "fieldtype": "Time", "read_only": True},
    {"fieldname": "duration", "label": "Duration", "fieldtype": "Float", "read_only": True},
    {"fieldname": "comments", "label": "Comments", "fieldtype": "Data"},
]}
REPORT = {"week_start": "2026-10-05", "week_end": "2026-10-11", "generated_at": "2026-10-12 12:00:00", "warnings": ["Checks cover readable records."],
    "projects": [{"value": "PROJ-1", "label": "Shutdown"}], "categories": [{"value": "missing", "label": "Missing hours", "count": 1}],
    "items": [{"id": "missing:SHIFT-1:2026-10-05", "employee": "EMP-1", "employee_name": "Missing advisor", "project": "PROJ-1", "project_name": "Shutdown",
               "date": "2026-10-05", "title": "Allocated shift has no hours", "hours": None, "categories": ["missing"], "severity": "review", "internal_approved": False,
               "issues": [{"code": "missing_hours", "message": "No accessible valid hours for allocated Day Shift."}],
               "links": [{"doctype": "Shift Assignment", "name": "SHIFT-1", "label": "Open allocation"}]}]}


def form_values(request):
    message = message_from_bytes(b"Content-Type: " + request.headers["content-type"].encode() + b"\r\n\r\n" + request.post_data_buffer)
    return {part.get_param("name", header="content-disposition"): part.get_payload(decode=True).decode() for part in message.get_payload()}


def api_fixture(saves):
    def api(route):
        method = urlparse(route.request.url).path.rsplit("/", 1)[-1]
        message = None
        if method.endswith("get_logged_user"): message = USER
        elif method == "frappe.ping": message = "pong"
        elif method.endswith("get_mobile_boot"):
            message = {"user": USER, "user_fullname": "Timesheet reviewer", "csrf_token": "fixture", "app_name": "Verto",
                       "navigation_access": {"has_employee_profile": True, "employee_id": "EMP-1", "can_review_timesheets": True},
                       "push_config": {"configured": False}, "theme_preference": "Light"}
        elif method.endswith("get_offline_bootstrap"): message = {"user": USER, "schemas": {"daily-timesheet": SCHEMA}}
        elif method.endswith("get_form_schema"): message = SCHEMA
        elif method.endswith("get_prefill_values"): message = {"values": VALUES}
        elif method.endswith("get_mobile_doc_for_edit"):
            message = {"doctype": "Daily Timesheet", "name": "DAILY-1", "schema": SCHEMA, "values": VALUES, "can_write": True, "files": [], "docstatus": 0}
        elif method.endswith("process_field_change"): message = {"values": {}}
        elif method.endswith("get_timesheet_exceptions"): message = REPORT
        elif method.endswith("get_mobile_form_options"): message = []
        elif method.endswith("sync_action"):
            values = json.loads(form_values(route.request)["values"])
            saves.append(values)
            message = {"ok": True, "result": {"doctype": "Daily Timesheet", "name": "DAILY-1", "route": "/forms", "values": values, "files": []}}
        elif method.endswith("queue_submitted_form_review"): message = {"queued": True}
        if message is None: layout.mock_api(route)
        else: route.fulfill(content_type="application/json", body=json.dumps({"message": message}))
    return api


def context_for(browser, width):
    context = browser.new_context(viewport={"width": width, "height": 956}, has_touch=width < 600, is_mobile=width < 600, service_workers="block", locale="en-AU")
    context.route("**/socket.io/**", lambda route: route.abort())
    context.route("**/verto-mobile.webmanifest", lambda route: route.fulfill(content_type="application/manifest+json", body="{}"))
    return context


def check_confirmation(browser, origin, engine, width, edit):
    context = context_for(browser, width)
    page = context.new_page()
    saves = []
    page.route("**/api/method/**", api_fixture(saves))
    mode = "edit" if edit else "new"
    try:
        page.goto(f"{origin}/verto-mobile/{'edit/daily-timesheet/DAILY-1' if edit else 'new/daily-timesheet'}")
        submit = page.get_by_role("button", name="Save Changes" if edit else "Submit", exact=True)
        expect(submit).to_be_enabled()
        submit.click()
        dialog = page.get_by_role("dialog")
        expect(dialog).to_be_visible()
        expect(dialog.get_by_text("12.50 hours", exact=True)).to_be_visible()
        assert not saves, "Opening a confirmation saved the document"
        page.keyboard.press("Escape")
        expect(dialog).not_to_be_visible()
        expect(page.get_by_label("Comments", exact=True)).to_have_value("Keep these notes")
        submit.click()
        expect(dialog).to_be_visible()
        dialog.get_by_role("button", name="Review hours", exact=True).click()
        assert not saves, "Cancelling wrote a timesheet"
        submit.click()
        expect(dialog).to_be_visible()
        dialog.evaluate("async el => { await Promise.all(el.getAnimations({subtree:true}).map(animation => animation.finished)); }")
        page.screenshot(path=str(RESULTS / f"{engine}-timesheet-{mode}-{width}.png"))
        button = dialog.get_by_role("button", name=f"{'Save' if edit else 'Submit'} 12.50 hours", exact=True)
        button.evaluate("button => { button.click(); button.click(); }")
        page.wait_for_function("document.querySelector('[role=dialog]') === null")
        if edit: expect(page.get_by_text("Saved successfully.", exact=True)).to_be_visible()
        else: expect(page).to_have_url(f"{origin}/verto-mobile/forms")
        assert len(saves) == 1 and saves[0]["duration"] == 45000, saves
        assert saves[0]["comments"] == "Keep these notes"
        print(f"{engine} {width}px {mode}: Escape/cancel preserved form; exact hours saved once", flush=True)
    finally:
        context.close()


def check_queue(browser, origin, engine, width):
    context = context_for(browser, width)
    page = context.new_page()
    page.route("**/api/method/**", api_fixture([]))
    try:
        page.goto(f"{origin}/verto-mobile/timesheet-exceptions")
        expect(page.get_by_role("main").get_by_role("heading", name="Timesheet exceptions", exact=True)).to_be_visible()
        expect(page.get_by_role("heading", name="Missing advisor", exact=True)).to_be_visible()
        expect(page.get_by_role("button", name="Refresh queue", exact=True)).to_be_enabled()
        expect(page.get_by_role("link", name="Open allocation", exact=True)).to_have_attribute("href", "/app/shift-assignment/SHIFT-1")
        page.get_by_label("Employee or record", exact=True).fill("Nobody")
        expect(page.get_by_text("No exceptions match these filters.", exact=True)).to_be_visible()
        page.get_by_label("Employee or record", exact=True).fill("Missing advisor")
        expect(page.get_by_role("heading", name="Missing advisor", exact=True)).to_be_visible()
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), "Queue overflowed the viewport"
        page.screenshot(path=str(RESULTS / f"{engine}-timesheet-exceptions-{width}.png"))
        print(f"{engine} {width}px: exceptions visible, filterable and linked without horizontal overflow", flush=True)
    finally:
        context.close()


def check_offline_confirmation(browser, origin, engine):
    context = context_for(browser, 440)
    page = context.new_page()
    saves = []
    page.route("**/api/method/**", api_fixture(saves))
    try:
        page.goto(f"{origin}/verto-mobile/timesheet-exceptions")
        page.wait_for_function("localStorage.getItem('verto:offline-actor') === 'layout@example.test'")
        page.goto(f"{origin}/verto-mobile/edit/daily-timesheet/DAILY-1")
        submit = page.get_by_role("button", name="Save Changes", exact=True)
        expect(submit).to_be_enabled()
        context.set_offline(True)
        submit.click()
        dialog = page.get_by_role("dialog")
        expect(dialog.get_by_text("12.50 hours", exact=True)).to_be_visible()
        dialog.get_by_role("button", name="Review hours", exact=True).click()
        submit.click()
        dialog.get_by_role("button", name="Save 12.50 hours", exact=True).click()
        expect(page.get_by_text("Saved on this device and waiting to sync.", exact=True)).to_be_visible()
        entries = page.evaluate("""() => new Promise((resolve,reject) => {
            const request = indexedDB.open('verto-mobile-offline-db');
            request.onsuccess = () => {
                const db=request.result;
                const read=db.transaction('offline_queue').objectStore('offline_queue').getAll();
                read.onsuccess=()=>{resolve(read.result);db.close();};read.onerror=()=>reject(read.error);
            };request.onerror=()=>reject(request.error);
        })""")
        assert len(entries) == 1 and entries[0]["values"]["duration"] == 45000, entries
        assert not saves, "Offline confirmation sent an online write"
        print(f"{engine}: offline confirmation retained exact hours and queued one update", flush=True)
    finally:
        context.close()


def main(engines):
    RESULTS.mkdir(exist_ok=True)
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(layout.Handler, directory=str(layout.PUBLIC)))
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
                    origin = f"http://127.0.0.1:{server.server_port}"
                    for width in (440, 1280):
                        for edit in (False, True): check_confirmation(browser, origin, engine, width, edit)
                        check_queue(browser, origin, engine, width)
                    check_offline_confirmation(browser, origin, engine)
                finally:
                    browser.close()
    finally:
        server.shutdown(); server.server_close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--browser", action="append", choices=("chromium", "webkit"))
    main(parser.parse_args().browser or ("chromium", "webkit"))

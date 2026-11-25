"""Real-browser checks for photo evidence, upload receipts and handover drafts.

Uses the production mobile build and local API fixtures; no site data or AI calls.
"""
import argparse
from email import message_from_bytes
import base64
from functools import partial
from http.server import ThreadingHTTPServer
import importlib.util
import json
import os
from pathlib import Path
import re
import struct
import zlib
from threading import Thread
from urllib.parse import unquote, urlparse

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("mobile_layout_fixture", Path(__file__).with_name("mobile-shell-layout.e2e.py"))
layout = importlib.util.module_from_spec(spec)
spec.loader.exec_module(layout)
RESULTS = ROOT / "frontend/test-results"
USER = "layout@example.test"


class Handler(layout.Handler):
    def do_POST(self):
        if urlparse(self.path).path != "/api/method/upload_file":
            self.send_error(404)
            return
        metadata = json.loads(unquote(self.headers["X-Verto-Attachment"]))
        content = self.rfile.read(int(self.headers["Content-Length"]))
        state = self.server.photo_state
        rejected = "-annotated-" in metadata["file_name"] and state["reject_copy"]
        if rejected:
            state["failures"].append(metadata)
            message = "The annotated copy needs a retry."
        else:
            state["uploads"].append((metadata, content))
            message = {"file_url": "/private/files/" + metadata["file_name"]}
        self.send_response(403 if rejected else 200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"message": message}).encode())


def form_values(request):
    message = message_from_bytes(b"Content-Type: " + request.headers["content-type"].encode() + b"\r\n\r\n" + request.post_data_buffer)
    return {part.get_param("name", header="content-disposition"): part.get_payload(decode=True).decode() for part in message.get_payload()}


def fixture_image():
    def chunk(kind, content):
        return struct.pack(">I", len(content)) + kind + content + struct.pack(">I", zlib.crc32(kind + content))
    pixels = (b"\0" + bytes((20, 80, 120)) * 640) * 480
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 640, 480, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(pixels)) + chunk(b"IEND", b"")


def check_photos(browser, server, origin, engine, width):
    context = browser.new_context(viewport={"width": width, "height": 956}, has_touch=width < 600,
                                  is_mobile=width < 600, service_workers="block", locale="en-AU")
    page = context.new_page()
    failures, uploads, actions = [], [], []
    state = {"failures": failures, "uploads": uploads, "reject_copy": True}
    server.photo_state = state

    def api(route):
        method = urlparse(route.request.url).path.rsplit("/", 1)[-1]
        message = None
        if method.endswith("get_logged_user"): message = USER
        elif method == "frappe.ping": message = "pong"
        elif method.endswith("get_form_schema"):
            message = {"mobile_doctype": "field-interaction", "doctype": "Field Interaction", "title": "Field Interaction", "fields": []}
        elif method.endswith("get_prefill_values"): message = {"values": {}}
        elif method.endswith("sync_action"):
            payload = form_values(route.request); actions.append(payload)
            message = {"ok": True, "result": {"doctype": "Field Interaction", "name": "FI-BROWSER-1", "route": "/forms"}}
        elif method == "upload_file":
            # Verify bytes received over HTTP. WebKit's protocol represents
            # intercepted postData as UTF-8, which cannot preserve image bytes.
            route.continue_()
            return
        elif method.endswith("queue_submitted_form_review"): message = {"queued": True}
        elif method.endswith("get_mobile_form_options"): message = []
        if message is None: layout.mock_api(route)
        else: route.fulfill(content_type="application/json", body=json.dumps({"message": message}))

    page.route("**/api/method/**", api)
    page.route("**/socket.io/**", lambda route: route.abort())
    page.route("**/verto-mobile.webmanifest", lambda route: route.fulfill(content_type="application/manifest+json", body="{}"))
    try:
        page.goto(f"{origin}/verto-mobile/new/field-interaction")
        original = fixture_image()
        page.get_by_label("Add attachments or photos").set_input_files({"name": "site.png", "mimeType": "image/png", "buffer": original})
        page.get_by_role("button", name="Annotate", exact=True).click()
        canvas = page.get_by_label("Photo annotation canvas")
        expect(canvas).to_be_visible()
        page.wait_for_function("document.querySelector('canvas')?.width === 640")
        baseline = canvas.evaluate("canvas => canvas.toDataURL()")
        def draw():
            canvas.scroll_into_view_if_needed()
            canvas.evaluate("""async canvas => {
              let previous='';
              for(let i=0;i<40;i++) {
                await new Promise(requestAnimationFrame);
                const box=JSON.stringify(canvas.getBoundingClientRect());
                if(box===previous) return;
                previous=box;
              }
            }""")
            box = canvas.bounding_box()
            start = {"x": box["x"] + box["width"] * .2, "y": box["y"] + box["height"] * .3}
            end = {"x": box["x"] + box["width"] * .7, "y": box["y"] + box["height"] * .6}
            if engine == "chromium" and width < 600:
                session = context.new_cdp_session(page)
                session.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{**start, "id": 1}]})
                session.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [{**end, "id": 1}]})
                session.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
                session.detach()
            else:
                page.mouse.move(**start); page.mouse.down(); page.mouse.move(**end, steps=5); page.mouse.up()

        draw()
        expect(page.get_by_text("site.png · 1 marks", exact=True)).to_be_visible()
        assert canvas.evaluate("canvas => canvas.toDataURL()") != baseline
        page.get_by_role("button", name="Undo", exact=True).click()
        assert canvas.evaluate("canvas => canvas.toDataURL()") == baseline
        page.get_by_role("button", name="Circle", exact=True).click(); draw()
        page.get_by_role("button", name="Note", exact=True).click()
        page.get_by_placeholder("Enter a note, then tap the photo").fill("Barrier needs attention")
        box = canvas.bounding_box()
        canvas.click(position={"x": box["width"] * .1, "y": box["height"] * .1})
        expect(page.get_by_text("site.png · 2 marks", exact=True)).to_be_visible()
        page.screenshot(path=str(RESULTS / f"{engine}-photo-annotation-{width}.png"))
        page.get_by_role("button", name="Add annotated copy", exact=True).click()
        expect(canvas).not_to_be_visible()
        expect(page.get_by_role("button", name="Annotate", exact=True)).to_have_count(2)
        page.get_by_role("button", name="Submit", exact=True).click()
        page.wait_for_url("**/forms")
        assert len(actions) == 1 and len(uploads) == 1 and len(failures) == 1
        assert uploads[0][1] == original, "Original evidence bytes were changed"
        page.goto(f"{origin}/verto-mobile/failed-uploads")
        expect(page.get_by_text("1 of 2 attachments uploaded")).to_be_visible()
        expect(page.get_by_text("The annotated copy needs a retry.")).to_be_visible()
        expect(page.get_by_text("Needs attention", exact=True)).to_be_visible()
        if width >= 1024:
            geometry = page.evaluate("""() => ({content:document.querySelector('.mobile-shell-content').getBoundingClientRect().width,
              sidebar:document.querySelector('.bottom-tabs').getBoundingClientRect().x})""")
            assert geometry["content"] > width - 400 and geometry["sidebar"] < 1, geometry
        state["reject_copy"] = False
        page.get_by_role("button", name="Retry upload", exact=True).click()
        expect(page.get_by_text("Confirmed by server", exact=True).first).to_be_visible()
        expect(page.get_by_text("2 of 2 attachments uploaded")).to_be_visible()
        assert len(actions) == 1 and len(uploads) == 2, "Retry replayed accepted evidence or document"
        assert uploads[1][1].startswith(b"\xff\xd8\xff"), "Annotated copy must be a JPEG"
        annotated = page.evaluate("""async data => {
          const bytes = Uint8Array.from(atob(data), character => character.charCodeAt(0));
          const image = await createImageBitmap(new Blob([bytes], {type:'image/jpeg'}));
          const canvas = document.createElement('canvas'); canvas.width=image.width; canvas.height=image.height;
          const ctx=canvas.getContext('2d'); ctx.drawImage(image,0,0);
          return {width:image.width,height:image.height,footer:[...ctx.getImageData(320,image.height-4,1,1).data]};
        }""", base64.b64encode(uploads[1][1]).decode())
        assert annotated["width"] == 640 and annotated["height"] > 480
        assert annotated["footer"][:3] == [255, 255, 255], "Missing copy-label footer"
        print(f"{engine} {width}px: original retained, annotation exported, partial progress and retry confirmed", flush=True)
    finally:
        if not (len(actions) == 1 and len(uploads) == 2):
            print('Photo failure state', page.url, page.evaluate("""() => Object.fromEntries(['.mobile-shell-frame','.mobile-shell-content','.mobile-shell-main','.mobile-shell-page','article','article button','.bottom-tabs'].map(s=>{
              const e=document.querySelector(s); if(!e)return[s,null];const r=e.getBoundingClientRect(),c=getComputedStyle(e);
              return[s,{x:r.x,y:r.y,width:r.width,height:r.height,order:c.order,position:c.position,scrollX:scrollX,scrollY:scrollY}];
            }))"""), flush=True)
        page.screenshot(path=str(RESULTS / f"{engine}-photo-queue-{width}.png"))
        context.close()


def check_handover(browser, origin, engine):
    context = browser.new_context(viewport={"width": 440, "height": 956}, is_mobile=True, has_touch=True, service_workers="block")
    page = context.new_page()
    saves, generations = [], []
    values = {"project": "PROJ-1", "table_hhdr": [{"date": "2026-11-24 06:00:00", "shift_findings": "Advisor original notes", "actions": "", "signoff": ""}]}
    schema = {"mobile_doctype": "safety-handover", "doctype": "Safety Handover", "title": "Safety Handover", "fields": [
        {"fieldname": "project", "fieldtype": "Data", "label": "Project", "read_only": True},
        {"fieldname": "table_hhdr", "fieldtype": "Table", "label": "Handover", "options": "Handover Information", "child_fields": [
            {"fieldname": "date", "fieldtype": "Datetime", "label": "Date & Time"},
            {"fieldname": "shift_findings", "fieldtype": "Text Editor", "label": "Shift Findings"},
            {"fieldname": "actions", "fieldtype": "Text Editor", "label": "Actions & Owners"},
            {"fieldname": "signoff", "fieldtype": "Signature", "label": "Sign-off"}]}]}

    def api(route):
        method = urlparse(route.request.url).path.rsplit("/", 1)[-1]
        message = None
        if method.endswith("get_logged_user"): message = USER
        elif method == "frappe.ping": message = "pong"
        elif method.endswith("get_mobile_doc_for_edit"):
            message = {"schema": schema, "doctype": "Safety Handover", "name": "HANDOVER-1", "can_write": True, "values": values, "files": []}
        elif method.endswith("prepare_handover_draft"):
            generations.append(route.request.post_data_json)
            message = {"fields": {"shift_findings": "Suggested replacement [S1]", "actions": "Check the barrier [S1]"},
                "sources": [{"id": "S1", "doctype": "Field Interaction", "name": "FI-1", "recorded_at": "2026-11-24 02:00:00", "time_basis": "submission timestamp", "url": "/app/field-interaction/FI-1"}],
                "warnings": ["Date-only records may include other shifts."],
                "scope": {"period_start": "2026-11-23 18:00:00", "period_end": "2026-11-24 06:00:00", "timezone": "Australia/Perth"}}
        elif method.endswith("sync_action"):
            saved = json.loads(form_values(route.request)["values"]); saves.append(saved)
            message = {"ok": True, "result": {"doctype": "Safety Handover", "name": "HANDOVER-1", "values": saved, "files": [], "docstatus": 0}}
        if message is None: layout.mock_api(route)
        else: route.fulfill(content_type="application/json", body=json.dumps({"message": message}))

    page.route("**/api/method/**", api)
    page.route("**/socket.io/**", lambda route: route.abort())
    page.route("**/verto-mobile.webmanifest", lambda route: route.fulfill(content_type="application/manifest+json", body="{}"))
    try:
        page.goto(f"{origin}/verto-mobile/edit/safety-handover/HANDOVER-1")
        page.get_by_role("button", name=re.compile(r"2026-11-24.*Edit", re.S)).click()
        page.get_by_role("button", name="Prepare handover draft", exact=True).click()
        expect(page.get_by_text("Check the barrier [S1]", exact=True)).to_be_visible()
        assert not saves, "Generation wrote the handover"
        assert generations[0]["period_start"] == "2026-11-23 18:00:00"
        page.get_by_role("button", name="Use draft in row", exact=True).click()
        page.get_by_role("button", name="Save Row", exact=True).click()
        expect(page.get_by_text("Saved successfully.", exact=True)).to_be_visible()
        assert len(saves) == 1
        row = saves[0]["table_hhdr"][0]
        assert "Advisor original notes" in row["shift_findings"] and "Suggested replacement" not in row["shift_findings"], row
        assert not row["signoff"], "Applying a draft must not sign the row"
        assert 'href="/desk/field-interaction/FI-1"' in row["actions"]
        print(f"{engine}: handover prepared without writes; reviewed row saved with source links and existing notes", flush=True)
    finally:
        page.screenshot(path=str(RESULTS / f"{engine}-handover-draft.png"))
        context.close()


def main(engines):
    RESULTS.mkdir(exist_ok=True)
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(Handler, directory=str(layout.PUBLIC)))
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
                    for width in (440, 1280): check_photos(browser, server, origin, engine, width)
                    check_handover(browser, origin, engine)
                finally: browser.close()
    finally:
        server.shutdown(); server.server_close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--browser", action="append", choices=("chromium", "webkit"))
    args = parser.parse_args()
    main(args.browser or ("chromium", "webkit"))

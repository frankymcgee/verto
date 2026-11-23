"""Measure the built mobile shell in real browser engines, without a Frappe site."""

from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from threading import Thread
from urllib.parse import urlparse

from playwright.sync_api import expect, sync_playwright


PUBLIC = Path(__file__).resolve().parents[2] / "verto/public"
RESULTS = Path(__file__).resolve().parent.parent / "test-results"
FLOW = """<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><style>
html,body,#app{height:100%;margin:0}#app{display:flex;flex-direction:column}
</style></head><body><div id="app"></div><script>
const host=document.createElement('div');host.style.cssText='height:100%;min-height:0';
document.querySelector('#app').append(host);const root=host.attachShadow({mode:'open'});
root.innerHTML=`<style>.chat{display:flex;flex-direction:column;height:100%;font:16px sans-serif}
article{flex:1;overflow:auto}footer{padding:12px}textarea{box-sizing:border-box;width:100%}</style>
<div class="chat"><article>Local Flow layout fixture</article><footer>
<textarea aria-label="Message PERI"></textarea></footer></div>`;
host.toggleAttribute('data-panel',false);
</script></body></html>"""


class Handler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        if urlparse(self.path).path.startswith("/flow/"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(FLOW.encode())
        else:
            super().do_GET()

    def translate_path(self, path):
        path = urlparse(path).path
        if path.startswith("/verto-mobile/"):
            return str(PUBLIC / "verto-mobile/index.html")
        if path.startswith("/assets/verto/"):
            return str(PUBLIC / path.removeprefix("/assets/verto/"))
        return super().translate_path(path)


def mock_api(route):
    method = urlparse(route.request.url).path.rsplit("/", 1)[-1]
    message = {}
    if method.endswith("get_mobile_boot"):
        message = {
            "user": "layout@example.test", "user_fullname": "Layout test",
            "csrf_token": "fixture", "app_name": "Verto layout test",
            "theme_preference": "Light", "peri_chat_version": "Flow", "peri_flow_agent": "PERI",
            "navigation_access": {"has_employee_profile": True, "employee_id": "FIXTURE"},
            "push_config": {"configured": False, "public_key": ""},
            "pwa_metadata": {"app_name": "Verto layout test", "short_name": "Verto"},
        }
    elif method.endswith("open_peri_chat"):
        message = {"url": "/flow/s/layout-fixture", "session": "layout-fixture", "agent": "PERI"}
    elif method.endswith("get_user_theme"):
        message = {"user": "layout@example.test", "theme": "Light"}
    elif method.endswith("get_my_missing_hours_reminders"):
        message = {"reminders": []}
    route.fulfill(content_type="application/json", body=json.dumps({"message": message}))


def check_layout(browser, origin, engine, width, height, shortfall):
    mobile = width < 1024
    context = browser.new_context(
        viewport={"width": width, "height": height},
        is_mobile=mobile, has_touch=mobile, service_workers="block", locale="en-AU",
    )
    page = context.new_page()
    label = f"{engine}-{'phone' if mobile else 'desktop'}-dvh-shortfall-{shortfall}"
    page.route("**/api/method/**", mock_api)
    page.route("**/socket.io/**", lambda route: route.abort())
    page.route("**/verto-mobile.webmanifest", lambda route: route.fulfill(content_type="application/manifest+json", body="{}"))

    def stylesheet(route):
        css = (PUBLIC / "verto-mobile/assets/index.css").read_text()
        # Reproduce a PWA reporting a dvh shorter than its fixed containing box.
        # The screenshot showed about 62 CSS pixels below the nav. With the old
        # independent 100dvh heights, this case leaves exactly that gap.
        if shortfall:
            css = css.replace("100dvh", f"calc(100vh - {shortfall}px)")
        route.fulfill(content_type="text/css", body=css)

    page.route("**/assets/verto/verto-mobile/assets/index.css", stylesheet)
    try:
        page.goto(f"{origin}/verto-mobile/chat/peri")
        expect(page.frame_locator("iframe.flow-chat-frame").get_by_role("textbox", name="Message PERI")).to_be_visible()
        if mobile:
            # Keep the home-indicator reservation inside the nav in this test.
            page.add_style_tag(content=".mobile-shell--flow { --verto-footer-safe-bottom: 34px !important; }")

        def measure():
            return page.evaluate("""() => {
              const box = selector => {
                const r=document.querySelector(selector).getBoundingClientRect();
                return {top:r.top,bottom:r.bottom,height:r.height};
              };
              return {viewport:innerHeight,shell:box('.mobile-shell'),frame:box('.mobile-shell-frame'),nav:box('.bottom-tabs')};
            }""")

        geometry = measure()
        for key in ("shell", "frame", "nav"):
            assert abs(geometry[key]["bottom"] - height) <= 1, (label, key, geometry)
        print(label, json.dumps(geometry), flush=True)
        page.screenshot(path=str(RESULTS / f"{label}.png"))

        # Sync/offline notices must consume space above the nav, never below it.
        context.set_offline(True)
        expect(page.locator(".mobile-shell-content [role='status']").first).to_be_visible()
        geometry = measure()
        assert abs(geometry["nav"]["bottom"] - height) <= 1, (label, "offline notice", geometry)
        context.set_offline(False)

        if mobile:
            # Resize with the real shadow composer focused. Both the frame and
            # nav must follow the smaller bounds, including the keyboard branch.
            page.frame_locator("iframe.flow-chat-frame").get_by_role("textbox", name="Message PERI").fill("Keyboard layout check")
            page.set_viewport_size({"width": width, "height": 480})
            expect(page.locator(".mobile-shell")).to_have_css("height", "480px")
            geometry = measure()
            assert abs(geometry["frame"]["bottom"] - 480) <= 1, (label, geometry)
            assert abs(geometry["nav"]["bottom"] - 480) <= 1, (label, geometry)
    finally:
        page.screenshot(path=str(RESULTS / f"{label}-last-state.png"))
        context.close()


def main():
    RESULTS.mkdir(exist_ok=True)
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(Handler, directory=str(PUBLIC)))
    Thread(target=server.serve_forever, daemon=True).start()
    try:
        with sync_playwright() as playwright:
            for engine in ("chromium", "webkit"):
                browser = getattr(playwright, engine).launch()
                try:
                    for width, height in ((440, 956), (1440, 900)):
                        for shortfall in (0, 62):
                            check_layout(browser, f"http://127.0.0.1:{server.server_port}", engine, width, height, shortfall)
                finally:
                    browser.close()
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()

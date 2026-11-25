"""Measure the built mobile shell in real browser engines, without a Frappe site."""

import argparse
import os
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import re
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


def check_layout(browser, origin, engine, width, height, shortfall, ios_standalone=False):
    mobile = width < 1024
    context = browser.new_context(
        viewport={"width": width, "height": height},
        is_mobile=mobile, has_touch=mobile, service_workers="block", locale="en-AU",
        **({"user_agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) AppleWebKit/605.1.15 Version/27.0.1 Mobile/15E148 Safari/604.1"} if ios_standalone else {}),
    )
    if ios_standalone:
        # Model the measured phone: lvh=956 but innerHeight/visualViewport=894.
        # This is a regression model, not a claim to run an installed iOS app.
        context.add_init_script("""(() => {
          Object.defineProperty(navigator, 'standalone', {value:true});
          const viewport=window.visualViewport;
          const nativeHeight=Object.getOwnPropertyDescriptor(VisualViewport.prototype, 'height').get;
          const reportedHeight=() => {const h=nativeHeight.call(viewport); return h>600 ? h-62 : h};
          Object.defineProperty(viewport, 'height', {get:reportedHeight});
          Object.defineProperty(window, 'innerHeight', {get:reportedHeight});
        })()""")
    page = context.new_page()
    label = f"{engine}-{'phone' if mobile else 'desktop'}-dvh-shortfall-{shortfall}"
    if ios_standalone:
        label += "-ios-standalone"
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
              return {viewport:innerHeight,shell:box('.mobile-shell'),frame:box('.mobile-shell-frame'),nav:box('.bottom-tabs'),main:box('.mobile-shell-main')};
            }""")

        if ios_standalone:
            # Model the shorter native fixed containing block using a transformed
            # body. Removing the fix must reproduce the measured 62px gap.
            page.add_style_tag(content="""
              body {transform:translate(0);}
              html.verto-flow-active:not(.verto-flow-standalone-ios),
              html.verto-flow-active:not(.verto-flow-standalone-ios) body {
                height:calc(100vh - 62px) !important;
              }
            """)
            expect(page.locator('html')).to_have_class(re.compile(r'\bverto-flow-standalone-ios\b'))
            page.evaluate("document.documentElement.classList.remove('verto-flow-standalone-ios')")
            assert abs(measure()["nav"]["bottom"] - (height - 62)) <= 1, (label, "unpatched model", measure())
            page.evaluate("document.documentElement.classList.add('verto-flow-standalone-ios')")
            expect(page.locator('body')).to_have_css('position', 'relative')

        geometry = measure()
        for key in ("shell", "frame", "nav"):
            assert abs(geometry[key]["bottom"] - height) <= 1, (label, key, geometry)
        print(label, json.dumps(geometry), flush=True)
        page.screenshot(path=str(RESULTS / f"{label}.png"))

        # Sync notices float without shrinking the page or covering the composer.
        before_notice = measure()["main"]
        context.set_offline(True)
        notice = page.locator('[data-sonner-toast][data-type="warning"]:not([data-removed="true"])')
        expect(notice).to_contain_text('Offline mode')
        geometry = measure()
        assert abs(geometry["nav"]["bottom"] - height) <= 1, (label, "offline notice", geometry)
        assert all(abs(before_notice[key] - geometry["main"][key]) <= 1 for key in before_notice), (label, "notice moved the page", geometry)
        composer = page.frame_locator("iframe.flow-chat-frame").get_by_role("textbox", name="Message PERI")
        composer_top = composer.bounding_box()["y"]
        page.wait_for_function("""top => {
          const toast=document.querySelector('[data-sonner-toast][data-type="warning"]:not([data-removed="true"])');
          return toast && toast.getBoundingClientRect().bottom <= top-4;
        }""", arg=composer_top)
        context.set_offline(False)

        if mobile:
            # Resize with the real shadow composer focused. Both the frame and
            # nav must follow the smaller bounds, including the keyboard branch.
            composer.click()
            composer.fill("Keyboard layout check")
            page.set_viewport_size({"width": width, "height": 480})
            expect(page.locator(".mobile-shell")).to_have_css("height", "480px")
            geometry = measure()
            assert abs(geometry["frame"]["bottom"] - 480) <= 1, (label, geometry)
            assert abs(geometry["nav"]["bottom"] - 480) <= 1, (label, geometry)
            # Restore the idle app after the keyboard closes.
            page.set_viewport_size({"width": width, "height": height})
            expect(page.locator(".mobile-shell")).to_have_css("height", f"{height}px")
            assert abs(measure()["nav"]["bottom"] - height) <= 1, (label, "keyboard closed", measure())
    finally:
        page.screenshot(path=str(RESULTS / f"{label}-last-state.png"))
        context.close()


def main(engines=("chromium", "webkit")):
    RESULTS.mkdir(exist_ok=True)
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(Handler, directory=str(PUBLIC)))
    Thread(target=server.serve_forever, daemon=True).start()
    try:
        with sync_playwright() as playwright:
            for engine in engines:
                launch_options = {}
                if engine == "chromium" and os.environ.get("CHROMIUM_BINARY"):
                    launch_options["executable_path"] = os.environ["CHROMIUM_BINARY"]
                browser = getattr(playwright, engine).launch(**launch_options)
                try:
                    for width, height in ((440, 956), (1440, 900)):
                        for shortfall in (0, 62):
                            check_layout(browser, f"http://127.0.0.1:{server.server_port}", engine, width, height, shortfall)
                    check_layout(browser, f"http://127.0.0.1:{server.server_port}", engine, 440, 956, 62, ios_standalone=True)
                finally:
                    browser.close()
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--browser", action="append", choices=("chromium", "webkit"))
    args = parser.parse_args()
    main(tuple(args.browser) if args.browser else ("chromium", "webkit"))

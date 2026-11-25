"""Real browser coverage for non-blocking Frappe sync notifications."""
import argparse
from functools import partial
from http.server import ThreadingHTTPServer
import importlib.util
import json
import os
from pathlib import Path
from threading import Thread
from urllib.parse import urlparse

from playwright.sync_api import expect, sync_playwright

spec = importlib.util.spec_from_file_location("sync_status_fixture", Path(__file__).with_name("timesheets.e2e.py"))
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)
RESULTS = Path(__file__).resolve().parent.parent / "test-results"
NOTICE = '[data-sonner-toast]:not([data-removed="true"])'


def check_status(browser, origin, engine, width):
    context = fixture.context_for(browser, width)
    page = context.new_page()
    pending = []
    normal_api = fixture.api_fixture([])

    def api(route):
        method = urlparse(route.request.url).path.rsplit("/", 1)[-1]
        if method.endswith("get_offline_bootstrap"):
            pending.append(route)
        else:
            normal_api(route)

    page.route("**/api/method/**", api)
    try:
        page.goto(f"{origin}/verto-mobile/forms", wait_until="domcontentloaded")
        notice = page.locator(NOTICE)
        expect(notice).to_have_count(1)
        expect(notice).to_contain_text("Preparing offline data")
        notice.evaluate("el => el.dataset.fixtureNotice='same'")
        geometry = page.locator('.mobile-shell-main').bounding_box()
        page.wait_for_function("""() => {
            const toast=document.querySelector('[data-sonner-toast]');
            const nav=document.querySelector('.bottom-tabs');
            const rect=toast?.getBoundingClientRect();
            return rect && rect.x>=0 && rect.right<=innerWidth &&
              (innerWidth>=1024 || rect.bottom<=nav.getBoundingClientRect().top-4);
        }""")
        assert "Preparing offline data" not in page.locator('.mobile-shell-content').inner_text(), "A status bar still occupies the page"
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), "Toast overflowed the phone viewport"

        if width < 1024:
            page.evaluate("""() => {
                const dock=document.createElement('div');dock.className='jha-voice-dock';
                dock.innerHTML='<button aria-label="Microphone fixture" style="width:84px;height:84px">Mic</button><p>Voice controls</p>';
                dock.querySelector('button').onclick=()=>dock.dataset.pressed='yes';
                document.querySelector('.mobile-shell-main').append(dock);
            }""")
            page.wait_for_function("document.querySelector('[data-sonner-toast]').getBoundingClientRect().bottom <= document.querySelector('.jha-voice-dock').getBoundingClientRect().top - 4")
            page.get_by_role('button', name='Microphone fixture').click()
            expect(page.locator('.jha-voice-dock')).to_have_attribute('data-pressed', 'yes')
            page.locator('.jha-voice-dock').evaluate('el=>el.remove()')

        assert len(pending) == 1
        pending.pop().fulfill(status=403, content_type="application/json", body=json.dumps({"message": "Offline data unavailable for this account."}))
        expect(notice).to_contain_text('Offline data refresh failed')
        expect(notice).to_have_count(1)
        expect(notice).to_have_attribute('data-fixture-notice', 'same')
        # Persistent errors remain actionable beyond the short success lifetime.
        page.wait_for_timeout(4300)
        expect(notice).to_be_visible()
        page.screenshot(path=str(RESULTS / f'{engine}-sync-error-{width}.png'))
        notice.get_by_role('button', name='Retry', exact=True).click()
        expect(notice).to_contain_text('Preparing offline data')
        expect(notice).to_have_count(1)
        page.wait_for_function("document.querySelector('[data-sonner-toast]')?.textContent.includes('Preparing offline data')")
        assert len(pending) == 1
        pending.pop().fulfill(content_type="application/json", body=json.dumps({"message": {"user": fixture.USER, "schemas": {}}}))
        expect(notice).to_contain_text('Offline data ready')
        expect(notice).to_have_count(1)
        expect(notice).to_have_attribute('data-fixture-notice', 'same')
        after = page.locator('.mobile-shell-main').bounding_box()
        assert all(abs(geometry[key]-after[key]) < 1 for key in ('x','y','width','height')), (geometry, after)
        page.locator('body').evaluate("async el => { await Promise.all(el.getAnimations({subtree:true}).filter(animation => animation.effect?.getTiming().iterations !== Infinity).map(animation => animation.finished.catch(()=>{}))); }")
        page.screenshot(path=str(RESULTS / f'{engine}-sync-ready-{width}.png'))
        expect(notice).to_have_count(0, timeout=6000)
        # A normal queue poll must not re-announce the same successful refresh.
        page.wait_for_timeout(1200)
        expect(notice).to_have_count(0)
        print(f'{engine} {width}px: one toast, retry, finite success, stable layout and reachable controls', flush=True)
    finally:
        context.close()


def main(engines):
    RESULTS.mkdir(exist_ok=True)
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(fixture.layout.Handler, directory=str(fixture.layout.PUBLIC)))
    Thread(target=server.serve_forever, daemon=True).start()
    try:
        with sync_playwright() as playwright:
            for engine in engines:
                options = {'headless': True}
                if engine == 'chromium':
                    options['args'] = ['--no-sandbox']
                    if os.environ.get('CHROMIUM_BINARY'): options['executable_path'] = os.environ['CHROMIUM_BINARY']
                browser = getattr(playwright, engine).launch(**options)
                try:
                    for width in (320, 440, 1280):
                        check_status(browser, f'http://127.0.0.1:{server.server_port}', engine, width)
                finally:
                    browser.close()
    finally:
        server.shutdown(); server.server_close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--browser', action='append', choices=('chromium', 'webkit'))
    main(parser.parse_args().browser or ('chromium', 'webkit'))

"""Real Chromium regressions for HTML handling and whiteboard dependency overrides.

Install all four app dependencies and Playwright/Chromium first. DOMPurify is
intentionally real here: a simulated DOM or a mocked sanitizer cannot validate XSS.
"""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


class SecurityBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix=".security-smoke-", dir=ROOT)
        cls.addClassCleanup(cls.tmp.cleanup)
        folder = Path(cls.tmp.name)
        entry = folder / "entry.ts"
        entry.write_text("\n".join([
            'export * from "../frontend/src/lib/chatHtml";',
            'export * from "../planner/src/utils/plainText";',
            'export { parseMermaidToExcalidraw } from "@excalidraw/mermaid-to-excalidraw";',
            'export { default as mermaid } from "mermaid";',
            'export { default as katex } from "katex";',
        ]))
        cls.bundle = folder / "security.js"
        subprocess.run([
            str(ROOT / "frontend/node_modules/.bin/esbuild"), str(entry),
            "--bundle", "--platform=browser", "--format=iife",
            "--global-name=VertoSecurity", f"--outfile={cls.bundle}",
        ], cwd=ROOT, check=True, text=True)
        cls.playwright = sync_playwright().start()
        cls.addClassCleanup(cls.playwright.stop)
        options = {"headless": True, "args": ["--no-sandbox"]}
        if os.environ.get("CHROMIUM_BINARY"):
            options["executable_path"] = os.environ["CHROMIUM_BINARY"]
        cls.browser = cls.playwright.chromium.launch(**options)
        cls.addClassCleanup(cls.browser.close)

    def setUp(self):
        self.page = self.browser.new_page()
        self.page.route("**/*", lambda route: route.abort())
        self.page.set_content('<main class="for-login"></main>')
        self.page.add_script_tag(path=str(self.bundle))
        self.addCleanup(self.page.close)

    def test_planner_text_preserves_lines_and_decodes_entities_once(self):
        result = self.page.evaluate("""() => {
            const { htmlToPlainText } = VertoSecurity;
            const text = htmlToPlainText('<p>Fish &amp; chips&nbsp;<b>today</b></p><div>Next<br>line</div><li>Last</li>');
            const encoded = htmlToPlainText('<p>&amp;lt;img src=x onerror=alert(1)&amp;gt;</p>');
            return { text, encoded };
        }""")
        self.assertEqual(result["text"], "Fish & chips today\nNext\nline\nLast")
        self.assertEqual(result["encoded"], "&lt;img src=x onerror=alert(1)&gt;")

    def test_planner_malformed_markup_and_active_content_remain_inert(self):
        result = self.page.evaluate("""() => {
            window.xss = 0;
            const attacks = [
                '<scr<script>ipt>window.xss=1</scr</script>ipt>',
                '<img src=x onerror="window.xss=1"><p>Keep this note</p>',
                '<svg onload="window.xss=1"><script>window.xss=1</script></svg>',
                '&lt;img src=x onerror="window.xss=1"&gt;',
            ];
            for (const attack of attacks) {
                const note = document.createElement('div');
                // Same text context as the annual hover card's Vue interpolation.
                note.textContent = VertoSecurity.htmlToPlainText(attack);
                document.body.append(note);
            }
            return { xss: window.xss, active: document.querySelectorAll('body > div img,body > div svg,body > div script').length,
                notes: [...document.querySelectorAll('body > div')].map(n => n.textContent) };
        }""")
        self.assertEqual(result["xss"], 0)
        self.assertEqual(result["active"], 0)
        self.assertIn("Keep this note", result["notes"])

    def test_chat_entity_decoding_never_parses_untrusted_html(self):
        result = self.page.evaluate("""() => {
            const original = document.createElement;
            document.createElement = () => { throw new Error('Decoder attempted DOM parsing'); };
            try {
                return VertoSecurity.decodeHtmlDeep('&amp;lt;/textarea&amp;gt;&amp;lt;img src=x onerror=alert(1)&amp;gt;');
            } finally { document.createElement = original; }
        }""")
        self.assertEqual(result, '</textarea><img src=x onerror=alert(1)>')

    def test_chat_sanitizes_final_decoded_html_and_encodes_attribute_values(self):
        result = self.page.evaluate("""() => {
            const { decodeHtmlDeep, escapeHtml, sanitiseMessageHtml } = VertoSecurity;
            window.xss = 0;
            const dirty = '&lt;/textarea&gt;&lt;img src=x onerror="window.xss=1"&gt;' +
                '<script>window.xss=1</script><svg onload="window.xss=1"></svg>' +
                '<a href="javascript:window.xss=1">Bad link</a><strong>Keep formatting</strong>' +
                '<a href="https://example.test">Safe link</a>';
            const target = document.createElement('div');
            target.innerHTML = sanitiseMessageHtml(decodeHtmlDeep(dirty));
            document.body.append(target);
            const encoded = escapeHtml('" onerror="window.xss=1');
            const image = document.createElement('div');
            image.innerHTML = sanitiseMessageHtml(`<img src="/safe.png" alt="${encoded}">`);
            return { xss: window.xss, active: target.querySelectorAll('script,svg,[onerror],[onload]').length,
                badHref: target.querySelector('a').getAttribute('href'), strong: target.querySelector('strong').textContent,
                safeLink: target.querySelectorAll('a')[1].getAttribute('rel'),
                alt: image.querySelector('img').getAttribute('alt'), injected: image.querySelector('[onerror]') !== null };
        }""")
        self.assertEqual(result, {"xss": 0, "active": 0, "badHref": None, "strong": "Keep formatting",
                                  "safeLink": "noopener noreferrer", "alt": '" onerror="window.xss=1', "injected": False})

    def test_install_instructions_use_the_same_plain_text_in_modal_and_alert(self):
        source = (ROOT / "verto/public/js/mobile_install_prompt.js").read_text()
        messages = []
        for modal in [False, True]:
            page = self.browser.new_page()
            try:
                page.set_content('<main class="for-login"></main>')
                page.evaluate("""modal => {
                    Object.defineProperty(navigator, 'userAgent', { value: 'iPhone', configurable: true });
                    window.alert = text => { window.instructionText = text; };
                    if (modal) window.frappe = { msgprint: html => {
                        const content = document.createElement('div');
                        content.innerHTML = html;
                        window.instructionText = content.textContent;
                        window.instructionTags = [...content.querySelectorAll('*')].map(n => n.tagName);
                    } };
                }""", modal)
                page.add_script_tag(content=source)
                page.locator("#mobile-install-button").click()
                messages.append(page.evaluate("window.instructionText"))
                if modal:
                    self.assertEqual(page.evaluate("window.instructionTags"), ["DIV"])
            finally:
                page.close()
        self.assertEqual(messages[0], messages[1])
        self.assertIn("\n1. Open this site in Safari.\n2.", messages[0])
        self.assertNotIn("<b>", messages[0])

    def test_whiteboard_diagram_conversion_keeps_generated_ids_and_geometry(self):
        diagrams = [
            "sequenceDiagram\nbox Operations\nparticipant A as Worker\nparticipant B as Supervisor\nend\nloop Each shift\nA->>B: Review JHA\nend",
            "classDiagram\nclass Worker {\n+String name\n}\nclass Project\nWorker --> Project",
            "erDiagram\nEMPLOYEE ||--o{ SHIFT : works\nEMPLOYEE {\nstring name\n}",
        ]
        for diagram in diagrams:
            with self.subTest(diagram=diagram.splitlines()[0]):
                result = self.page.evaluate("""async diagram => {
                    const { elements, files } = await VertoSecurity.parseMermaidToExcalidraw(diagram);
                    return { count: elements.length, ids: elements.map(e => e.id).filter(Boolean),
                        generatedIds: [...elements.flatMap(e => e.groupIds || []), ...elements.map(e => e.groupId).filter(Boolean), ...Object.keys(files || {})],
                        validImages: elements.filter(e => e.type === 'image').every(e =>
                            e.width > 0 && e.height > 0 && files?.[e.fileId]?.dataURL.startsWith('data:image/svg+xml;base64,')),
                        validGeometry: elements.every(e => Number.isFinite(e.x) && Number.isFinite(e.y)) };
                }""", diagram)
                self.assertGreater(result["count"], 0)
                self.assertEqual(len(result["ids"]), len(set(result["ids"])))
                self.assertTrue(result["validGeometry"])
                self.assertTrue(result["validImages"])
                # The converter supports editable skeletons and SVG image fallback.
                # Both paths generate IDs through its scoped Nano ID dependency.
                self.assertTrue(result["generatedIds"])
                for group in result["generatedIds"]:
                    self.assertRegex(group, r"^[A-Za-z0-9_-]{21}$")

    def test_katex_and_mermaid_math_render_with_trust_disabled(self):
        result = self.page.evaluate(r"""async () => {
            const { katex, mermaid, parseMermaidToExcalidraw } = VertoSecurity;
            const math = katex.renderToString(String.raw`\frac{x^2}{2}`, { throwOnError: true, trust: false });
            const unsafe = katex.renderToString(String.raw`\href{javascript:alert(1)}{Click}`, { trust: false });
            mermaid.initialize({ startOnLoad: false, securityLevel: 'strict', forceLegacyMathML: true });
            const { svg } = await mermaid.render('math-smoke', 'flowchart LR\nA["$$x^2$$"] --> B["Done"]');
            const converted = await parseMermaidToExcalidraw('flowchart LR\nA["$$x^2$$"] --> B["Done"]');
            return { version: katex.version, mathml: math.includes('<math'), math: svg.includes('katex'),
                unsafeLink: /href=["']javascript:/i.test(unsafe), converted: converted.elements.length };
        }""")
        self.assertEqual(result["version"], "0.18.2")
        self.assertTrue(result["mathml"])
        self.assertTrue(result["math"])
        self.assertFalse(result["unsafeLink"])
        self.assertGreater(result["converted"], 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)

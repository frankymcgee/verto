// @vitest-environment node
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({ plugins: vi.fn() }))
vi.mock('workbox-precaching', () => ({ addPlugins: mocks.plugins, cleanupOutdatedCaches: vi.fn(), precacheAndRoute: vi.fn() }))
let handlers, cache, entries
const root = 'https://example.test/verto-mobile/'
const appHtml = '<div id="app"></div><script type="module" src="/assets/verto/verto-mobile/assets/index.js"></script>'
const html = value => new Response(value, { headers: { 'Content-Type': 'text/html' } })
beforeEach(async () => {
  vi.resetModules(); vi.clearAllMocks()
  handlers = new Map()
  entries = new Map([[root, html(appHtml)]])
  const key = value => typeof value === 'string' ? value : value.url
  cache = {
    match: vi.fn(async request => entries.get(key(request))?.clone()),
    put: vi.fn(async (request, response) => { entries.set(key(request), response) }),
  }
  vi.stubGlobal('self', {
    location: new URL(root), __WB_MANIFEST: [], skipWaiting: vi.fn(),
    addEventListener: (type, handler) => handlers.set(type, handler),
    clients: { matchAll: vi.fn(async () => []), claim: vi.fn() },
  })
  vi.stubGlobal('caches', { open: vi.fn(async () => cache) })
  vi.stubGlobal('fetch', vi.fn())
  await import('../src/verto-sw')
})
afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals() })

async function navigate(path = 'new/field-interaction') {
  let response
  handlers.get('fetch')({ request: { method: 'GET', mode: 'navigate', url: `${root}${path}` },
    respondWith: pending => { response = pending },
  })
  return response
}
async function activate() {
  let work
  handlers.get('message')({ data: { type: 'SKIP_WAITING' }, waitUntil: pending => { work = pending } })
  await work
}

describe('Service worker offline shell and updates', () => {
  it('ignores a portal page cached by an earlier version and falls back to the working root shell', async () => {
    entries.set(`${root}new/field-interaction`, html('<html>Old Wi-Fi login</html>'))
    fetch.mockRejectedValueOnce(new TypeError('Network unavailable'))
    expect(await (await navigate()).text()).toBe(appHtml)
  })

  it('keeps the last working shell when a Wi-Fi login page or proxy error is returned', async () => {
    fetch.mockResolvedValueOnce(html('<html>Wi-Fi login</html>'))
    expect(await (await navigate()).text()).toBe(appHtml)
    expect(cache.put).not.toHaveBeenCalled()
    fetch.mockResolvedValueOnce(new Response('Gateway error', { status: 502 }))
    expect(await (await navigate()).text()).toBe(appHtml)
    expect(cache.put).not.toHaveBeenCalled()
    expect(fetch.mock.calls[0][1].redirect).toBe('manual')
  })

  it('falls back to the saved app promptly when the network stalls', async () => {
    vi.useFakeTimers()
    fetch.mockImplementationOnce((_request, { signal }) => new Promise((_resolve, reject) => {
      signal.addEventListener('abort', () => reject(new DOMException('Timed out', 'AbortError')))
    }))
    const response = navigate()
    await vi.advanceTimersByTimeAsync(8000)
    expect(await (await response).text()).toBe(appHtml)
  })

  it('refuses to cache portal HTML in place of JavaScript or styles', async () => {
    const [plugin] = mocks.plugins.mock.calls[0][0]
    for (const file of ['index.js', 'index.css']) {
      expect(await plugin.cacheWillUpdate({ request: new Request(`${root}${file}`), response: html('<html>Wi-Fi login</html>') })).toBeNull()
    }
    const bundle = new Response('export {}', { headers: { 'Content-Type': 'text/javascript' } })
    expect(await plugin.cacheWillUpdate({ request: new Request(`${root}index.js`), response: bundle })).toBe(bundle)
  })

  it('waits to activate while any tab has a new, edited or voice form open', async () => {
    expect(self.skipWaiting).not.toHaveBeenCalled()
    for (const path of ['new/form', 'edit/form/FORM-1', 'voice-jha/WORK-1']) {
      self.clients.matchAll.mockResolvedValueOnce([{ url: `${root}forms` }, { url: `${root}${path}` }])
      await activate()
      expect(self.skipWaiting).not.toHaveBeenCalled()
    }
    self.clients.matchAll.mockResolvedValueOnce([{ url: `${root}forms` }])
    await activate()
    expect(self.skipWaiting).toHaveBeenCalledOnce()
  })
})

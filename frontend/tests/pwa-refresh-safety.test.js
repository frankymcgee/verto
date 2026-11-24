// @vitest-environment node
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { ref } from 'vue'

const mocks = vi.hoisted(() => ({ check: vi.fn() }))
vi.mock('../src/lib/connection', () => ({
  checkServerConnection: (...args) => mocks.check(...args), serverReachable: mocks.reachable,
}))
let worker, registration, updates, forms
beforeEach(async () => {
  vi.resetModules(); vi.useFakeTimers(); vi.clearAllMocks()
  mocks.reachable ??= ref(true)
  mocks.reachable.value = true
  mocks.check.mockResolvedValue(true)
  vi.stubGlobal('window', Object.assign(new EventTarget(), {
    location: { hostname: 'example.test', origin: 'https://example.test', protocol: 'https:', pathname: '/verto-mobile/', reload: vi.fn() },
    setTimeout, clearTimeout, setInterval, clearInterval,
  }))
  vi.stubGlobal('document', Object.assign(new EventTarget(), { hidden: false, visibilityState: 'visible' }))
  registration = Object.assign(new EventTarget(), { update: vi.fn(async () => {}), waiting: { postMessage: vi.fn() }, scope: 'https://example.test/verto-mobile' })
  worker = Object.assign(new EventTarget(), { controller: {}, register: vi.fn(async () => registration), getRegistrations: vi.fn(async () => []) })
  Object.defineProperty(navigator, 'serviceWorker', { configurable: true, value: worker })
  forms = await import('../src/pwa/formActivity')
  updates = await import('../src/pwa/registerServiceWorker')
})
afterEach(() => { delete navigator.serviceWorker; vi.clearAllTimers(); vi.useRealTimers(); vi.unstubAllGlobals() })

describe('App refresh safety', () => {
  it.each(['/new/field-interaction', '/edit/daily-timesheet/TS-1', '/voice-jha/WORK-1'])(
    'defers controller reloads and update activation for the whole editor visit: %s', async path => {
      forms.setFormPath(path)
      await updates.registerVertoServiceWorker()
      worker.dispatchEvent(new Event('controllerchange'))
      window.dispatchEvent(new Event('online'))
      window.dispatchEvent(new Event('focus'))
      await vi.advanceTimersByTimeAsync(15 * 60_000)
      await updates.updateVertoServiceWorkerAndReload()
      expect(window.location.reload).not.toHaveBeenCalled()
      expect(registration.update).not.toHaveBeenCalled()
      expect(registration.waiting.postMessage).not.toHaveBeenCalled()
      forms.setFormPath('/forms')
      await flushPromises()
      expect(window.location.reload).toHaveBeenCalledOnce()
      worker.dispatchEvent(new Event('controllerchange'))
      await flushPromises()
      expect(window.location.reload).toHaveBeenCalledOnce()
    },
  )

  it('keeps a requested reload pending behind a captive portal until the server is reachable', async () => {
    mocks.check.mockResolvedValue(false)
    mocks.reachable.value = false
    await updates.requestAppReload()
    expect(window.location.reload).not.toHaveBeenCalled()
    mocks.check.mockResolvedValue(true)
    mocks.reachable.value = true
    await flushPromises()
    expect(window.location.reload).toHaveBeenCalledOnce()
  })

  it('rechecks the active route after an in-flight connectivity check completes', async () => {
    let done
    mocks.check.mockReturnValueOnce(new Promise(resolve => { done = resolve }))
    const pending = updates.requestAppReload()
    forms.setFormPath('/new/field-interaction')
    done(true)
    await pending
    expect(window.location.reload).not.toHaveBeenCalled()
    forms.setFormPath('/forms')
    await flushPromises()
    expect(window.location.reload).toHaveBeenCalledOnce()
  })
})

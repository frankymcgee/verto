import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import QrScanner from '../src/pages/QrScanner.vue'
import Home from '../src/pages/Home.vue'

const mocks = vi.hoisted(() => ({ api: vi.fn(), replace: vi.fn(), push: vi.fn(), browser: vi.fn(), decode: vi.fn() }))
vi.mock('../src/lib/api', () => ({ apiRequest: mocks.api }))
vi.mock('../src/lib/appBrowser', () => ({ openAppBrowser: mocks.browser }))
vi.mock('vue-router', () => ({ useRouter: () => ({ replace: mocks.replace, push: mocks.push }) }))
vi.mock('jsqr', () => ({ default: mocks.decode }))
let wrapper, stop, getUserMedia
const deferred = () => { let resolve; const promise = new Promise(yes => { resolve = yes }); return { promise, resolve } }
const frame = { data: new Uint8ClampedArray(16), width: 2, height: 2 }
beforeEach(() => {
  vi.useFakeTimers(); vi.clearAllMocks()
  stop = vi.fn(); getUserMedia = vi.fn().mockResolvedValue({ getTracks: () => [{ stop }] })
  vi.stubGlobal('isSecureContext', true)
  Object.defineProperty(navigator, 'mediaDevices', { configurable: true, value: { getUserMedia } })
  vi.spyOn(HTMLMediaElement.prototype, 'play').mockResolvedValue()
  vi.spyOn(HTMLMediaElement.prototype, 'pause').mockImplementation(() => {})
  vi.spyOn(HTMLMediaElement.prototype, 'srcObject', 'set').mockImplementation(() => {})
  vi.spyOn(HTMLMediaElement.prototype, 'readyState', 'get').mockReturnValue(4)
  Object.defineProperty(HTMLVideoElement.prototype, 'videoWidth', { configurable: true, get: () => 1280 })
  Object.defineProperty(HTMLVideoElement.prototype, 'videoHeight', { configurable: true, get: () => 720 })
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue({ drawImage: vi.fn(), getImageData: () => frame })
  mocks.decode.mockReturnValue(null); mocks.replace.mockResolvedValue()
})
afterEach(() => { wrapper?.unmount(); wrapper = null; vi.restoreAllMocks(); vi.unstubAllGlobals(); vi.useRealTimers() })
async function open() { wrapper = mount(QrScanner); await flushPromises() }
async function scan(value) { mocks.decode.mockReturnValueOnce({ data: value }); await vi.advanceTimersByTimeAsync(200); await flushPromises() }

describe('Project Tools QR camera', () => {
  it('is available from a project’s tools and opens the in-app scanner', async () => {
    mocks.api.mockResolvedValue({ message: { grouped_tasks: [{ scope_name: 'P-1', project: 'P-1',
      project_details: { project_name: 'Demo project' }, parent_groups: [] }] } })
    wrapper = mount(Home, { global: { stubs: { MobileSheet: { props: ['open'], template: '<div v-if="open"><slot /></div>' } } } })
    await flushPromises()
    await wrapper.findAll('button').find(button => button.text().includes('P-1')).trigger('click')
    await wrapper.findAll('button').find(button => button.text() === 'Project Tools').trigger('click')
    await wrapper.findAll('button').find(button => button.text().includes('Scan QR code')).trigger('click')
    expect(mocks.push).toHaveBeenCalledWith('/scan-qr')
  })
  it('uses an inline rear-camera preview with no microphone and stops on close', async () => {
    await open()
    expect(getUserMedia).toHaveBeenCalledWith(expect.objectContaining({ audio: false, video: expect.objectContaining({ facingMode: { ideal: 'environment' } }) }))
    expect(wrapper.find('video').attributes()).toHaveProperty('playsinline')
    await wrapper.find('button').trigger('click')
    expect(stop).toHaveBeenCalledOnce(); expect(mocks.replace).toHaveBeenCalledWith('/')
    const calls = mocks.decode.mock.calls.length
    await vi.advanceTimersByTimeAsync(1000); expect(mocks.decode).toHaveBeenCalledTimes(calls)
  })
  it('decodes and opens a mobile form once without a native BarcodeDetector', async () => {
    await open(); await scan('/verto-mobile/edit/take-5/T-1')
    expect(mocks.replace).toHaveBeenCalledOnce()
    expect(mocks.replace).toHaveBeenCalledWith('/edit/take-5/T-1')
    expect(stop).toHaveBeenCalledOnce(); mocks.api.mockClear()
    await vi.advanceTimersByTimeAsync(1000); expect(mocks.replace).toHaveBeenCalledOnce()
  })
  it('resolves a Desk QR to its permission-checked mobile form', async () => {
    mocks.api.mockResolvedValue({ message: { kind: 'mobile', url: '/verto-mobile/edit/field-interaction/FI-1' } })
    await open(); await scan('/app/field-interaction/FI-1')
    expect(mocks.api.mock.calls[0][0]).toContain('doctype=field-interaction&name=FI-1')
    expect(mocks.api.mock.calls[0][1]).toEqual({ cache: 'no-store' })
    expect(mocks.replace).toHaveBeenCalledWith('/edit/field-interaction/FI-1')
  })
  it('opens readable Desk-only documents in the existing in-app drawer', async () => {
    mocks.api.mockResolvedValue({ message: { kind: 'desk', url: '/app/task/T-1' } })
    await open(); await scan('/app/task/T-1')
    expect(mocks.browser).toHaveBeenCalledWith({ url: '/app/task/T-1', title: 'Scanned document' })
    expect(mocks.replace).not.toHaveBeenCalled(); expect(stop).toHaveBeenCalledOnce()
  })
  it('opens PDF documents in-app and allows scanning another document', async () => {
    await open(); await scan('/private/files/permit.pdf')
    expect(mocks.browser).toHaveBeenCalledWith({ url: '/private/files/permit.pdf', title: 'Scanned document' })
    expect(wrapper.text()).toContain('Scan again'); expect(stop).toHaveBeenCalledOnce()
  })
  it('rejects another tenant and does not navigate or query it', async () => {
    await open(); await scan('https://another-site.test/verto-mobile/jha/JHA-1')
    expect(wrapper.find('[role=alert]').text()).toContain('another site')
    expect(mocks.api).not.toHaveBeenCalled(); expect(mocks.replace).not.toHaveBeenCalled(); expect(stop).toHaveBeenCalledOnce()
  })
  it('shows a permission error and lets the user retry', async () => {
    getUserMedia.mockRejectedValueOnce(new DOMException('Denied', 'NotAllowedError'))
    await open(); expect(wrapper.find('[role=alert]').text()).toContain('Camera access was denied')
    await wrapper.findAll('button').find(button => button.text() === 'Scan again').trigger('click'); await flushPromises()
    expect(wrapper.text()).toContain('Keep the QR code steady'); expect(getUserMedia).toHaveBeenCalledTimes(2)
  })
  it('stops a stream that arrives after the user has closed the page', async () => {
    const pending = deferred(); getUserMedia.mockReturnValueOnce(pending.promise)
    await open(); wrapper.unmount(); wrapper = null
    pending.resolve({ getTracks: () => [{ stop }] }); await flushPromises()
    expect(stop).toHaveBeenCalledOnce(); expect(mocks.decode).not.toHaveBeenCalled()
  })
  it('stops the camera when the app goes into the background', async () => {
    await open(); window.dispatchEvent(new Event('pagehide')); await flushPromises()
    expect(stop).toHaveBeenCalledOnce(); expect(wrapper.text()).toContain('Camera paused')
    const calls = mocks.decode.mock.calls.length
    await vi.advanceTimersByTimeAsync(1000); expect(mocks.decode).toHaveBeenCalledTimes(calls)
  })
  it('discards a document lookup after navigation away', async () => {
    const pending = deferred(); mocks.api.mockReturnValueOnce(pending.promise)
    await open(); await scan('/app/task/T-1'); wrapper.unmount(); wrapper = null
    pending.resolve({ message: { kind: 'desk', url: '/app/task/T-1' } }); await flushPromises()
    expect(mocks.browser).not.toHaveBeenCalled(); expect(mocks.replace).not.toHaveBeenCalled()
  })
})

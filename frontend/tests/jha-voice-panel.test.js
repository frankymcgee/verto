import { afterEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import JhaVoicePanel from '../src/components/JhaVoicePanel.vue'
import { monitorRemoteVoice } from '../src/lib/remoteVoiceActivity'

vi.mock('../src/lib/mobileBoot', () => ({ useMobileBoot: () => ({ periBotImageUrl: { __v_isRef: true, value: '/files/peri.png' } }) }))
let wrapper, scrollArea
afterEach(() => {
  wrapper?.unmount(); wrapper = null
  scrollArea?.remove(); scrollArea = null
  vi.restoreAllMocks(); vi.unstubAllGlobals()
})
const props = { connected: true, connecting: false, disconnecting: false, canConnect: false,
  consent: true, talking: false, busy: false, level: 0, status: 'Connected', step: 'Step 2 · Fit pump' }

describe('compact PERI voice panel', () => {
  it('keeps the central mic beside the configured avatar in a sticky panel', async () => {
    wrapper = mount(JhaVoicePanel, { props })
    expect(wrapper.classes()).toContain('voice-panel-sticky')
    expect(wrapper.find('img[alt="PERI"]').attributes('src')).toBe('/files/peri.png')
    expect(wrapper.find('[aria-label="Hold to talk to PERI"]').classes()).toContain('h-28')
    expect(wrapper.text()).toContain('Step 2 · Fit pump')
    await wrapper.find('[aria-label="Hold to talk to PERI"]').trigger('pointerdown', { pointerId: 1 })
    expect(wrapper.emitted('talkStart')).toHaveLength(1)
    await wrapper.find('[aria-label="Hold to talk to PERI"]').trigger('pointerup', { pointerId: 1 })
    expect(wrapper.emitted('talkStop')).toHaveLength(1)
  })
  it('reserves the actual dock overlap and updates it on layout changes without leaving resize listeners behind', async () => {
    scrollArea = document.createElement('main')
    scrollArea.className = 'mobile-shell-main'
    document.body.append(scrollArea)
    let scrollBottom = 732, dockTop = 560
    const rectangles = vi.spyOn(Element.prototype, 'getBoundingClientRect').mockImplementation(function () {
      return { bottom: this === scrollArea ? scrollBottom : 0, top: this.classList.contains('jha-voice-dock') ? dockTop : 0 }
    })
    const computeStyle = getComputedStyle.bind(window)
    vi.stubGlobal('getComputedStyle', element => element.classList.contains('jha-voice-dock') ? { position: 'fixed' } : computeStyle(element))
    const observers = []
    vi.stubGlobal('ResizeObserver', class {
      constructor(callback) { this.callback = callback; observers.push(this) }
      observe = vi.fn()
      disconnect = vi.fn()
    })
    wrapper = mount(JhaVoicePanel, { props, attachTo: scrollArea })
    await wrapper.vm.$nextTick()
    const dock = wrapper.find('.jha-voice-dock').element
    const observer = observers.find(item => item.observe.mock.calls.some(([element]) => element === dock))
    expect(observer.observe).toHaveBeenCalledWith(scrollArea)
    // The bottom tabs are outside the scroller, so their height is excluded.
    expect(wrapper.emitted('clearanceChange').at(-1)).toEqual([172])
    dockTop = 524
    observer.callback()
    expect(wrapper.emitted('clearanceChange').at(-1)).toEqual([208])
    scrollBottom = 900; dockTop = 704
    window.dispatchEvent(new Event('resize'))
    expect(wrapper.emitted('clearanceChange').at(-1)).toEqual([196])
    await wrapper.setProps({ connected: false })
    expect(wrapper.emitted('clearanceChange').at(-1)).toEqual([0])
    expect(observer.disconnect).toHaveBeenCalledOnce()
    await wrapper.setProps({ connected: true })
    expect(wrapper.emitted('clearanceChange').at(-1)).toEqual([196])
    wrapper.unmount(); wrapper = null
    const measurements = rectangles.mock.calls.length
    window.dispatchEvent(new Event('resize'))
    expect(rectangles).toHaveBeenCalledTimes(measurements)
    expect(observers.every(item => item.disconnect.mock.calls.length === 1)).toBe(true)
  })
  it('shows speech only when received audio has activity, with a quiet thinking state', async () => {
    wrapper = mount(JhaVoicePanel, { props: { ...props, busy: true } })
    expect(wrapper.text()).toContain('Thinking')
    expect(wrapper.find('.voice-bars').attributes('data-speaking')).toBe('false')
    await wrapper.setProps({ level: 0.6 })
    expect(wrapper.text()).toContain('Speaking')
    expect(wrapper.find('.voice-bars').attributes('data-speaking')).toBe('true')
    await wrapper.setProps({ level: 0, busy: false })
    expect(wrapper.text()).toContain('Ready to listen')
    await wrapper.find('img').trigger('error')
    expect(wrapper.find('img').exists()).toBe(false)
    expect(wrapper.find('.peri-avatar').text()).toBe('P')
  })
  it('monitors the remote stream without playing duplicate audio and releases its resources', () => {
    let frame, samples = 160
    const analyser = { fftSize: 0, getByteTimeDomainData: vi.fn(array => array.fill(samples)), disconnect: vi.fn() }
    const source = { connect: vi.fn(), disconnect: vi.fn() }
    const close = vi.fn(async () => {})
    const update = vi.fn()
    vi.stubGlobal('AudioContext', class {
      createMediaStreamSource = vi.fn(() => source)
      createAnalyser = vi.fn(() => analyser)
      resume = vi.fn(async () => {})
      close = close
    })
    vi.stubGlobal('requestAnimationFrame', vi.fn(callback => { frame = callback; return 7 }))
    vi.stubGlobal('cancelAnimationFrame', vi.fn())
    const stop = monitorRemoteVoice(new MediaStream(), update)
    frame(100)
    expect(update.mock.calls.at(-1)[0]).toBeGreaterThan(0)
    samples = 128
    frame(400)
    expect(update.mock.calls.at(-1)[0]).toBe(0)
    expect(source.connect).toHaveBeenCalledOnce()
    expect(source.connect).toHaveBeenCalledWith(analyser)
    stop()
    expect(cancelAnimationFrame).toHaveBeenCalledWith(7)
    expect(source.disconnect).toHaveBeenCalledOnce()
    expect(analyser.disconnect).toHaveBeenCalledOnce()
    expect(close).toHaveBeenCalledOnce()
  })
})

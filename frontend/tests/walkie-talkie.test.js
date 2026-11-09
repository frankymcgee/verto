import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { useWalkieTalkie } from '../src/composables/useWalkieTalkie'
import WalkieTalkie from '../src/pages/WalkieTalkie.vue'
import Home from '../src/pages/Home.vue'

const mocks = vi.hoisted(() => ({ api: vi.fn(), push: vi.fn(), rooms: [], tracks: [],
  route: { params: { project: 'PROJ-1' } } }))
vi.mock('../src/lib/api', () => ({ apiRequest: mocks.api }))
vi.mock('vue-router', () => ({ useRoute: () => mocks.route, useRouter: () => ({ push: mocks.push }) }))
vi.mock('livekit-client', () => ({
  Track: { Kind: { Audio: 'audio' }, Source: { Microphone: 'microphone' } },
  RoomEvent: Object.fromEntries(['TrackSubscribed', 'TrackUnsubscribed', 'ParticipantConnected',
    'ParticipantDisconnected', 'AudioPlaybackStatusChanged', 'Reconnecting', 'Disconnected'].map(key => [key, key])),
  Room: class {
    constructor() {
      this.events = new Map()
      this.remoteParticipants = new Map()
      this.localParticipant = { name: 'Worker', permissions: { canPublish: true },
        publishTrack: vi.fn(async track => { expect(track.mediaStreamTrack.enabled).toBe(false) }),
        unpublishTrack: vi.fn().mockResolvedValue(undefined) }
      this.connect = vi.fn().mockResolvedValue(undefined)
      this.disconnect = vi.fn().mockResolvedValue(undefined)
      this.startAudio = vi.fn().mockResolvedValue(undefined)
      mocks.rooms.push(this)
    }
    on(event, callback) { this.events.set(event, callback); return this }
  },
  LocalAudioTrack: class {
    constructor(media) {
      this.mediaStreamTrack = media
      this.mute = vi.fn(async () => { media.enabled = false })
      this.unmute = vi.fn(async () => { media.enabled = true })
      this.stop = vi.fn(() => { media.enabled = false; media.stop() })
      mocks.tracks.push(this)
    }
  },
}))

const deferred = () => { let resolve; const promise = new Promise(yes => { resolve = yes }); return { promise, resolve } }
let radio, wrapper, microphone, getUserMedia
const calls = action => mocks.api.mock.calls.filter(([url, options]) =>
  url.endsWith('floor_action') && JSON.parse(options.body).action === action)

beforeEach(() => {
  vi.useFakeTimers()
  vi.clearAllMocks()
  mocks.rooms.length = 0
  mocks.tracks.length = 0
  vi.stubGlobal('isSecureContext', true)
  microphone = { enabled: true, stop: vi.fn() }
  getUserMedia = vi.fn().mockResolvedValue({ getAudioTracks: () => [microphone], getTracks: () => [microphone] })
  Object.defineProperty(navigator, 'mediaDevices', { configurable: true, value: { getUserMedia } })
  mocks.api.mockImplementation(async (url, options = {}) => {
    if (url.includes('get_channels')) return { message: { channels: [{ name: 'RADIO-1', channel_name: 'Site team', project: 'PROJ-1' }] } }
    if (url.endsWith('join_channel')) return { message: { session_id: 'session-1', identity: 'worker-1', url: 'wss://radio.test', token: 'token',
      heartbeat_seconds: 3, lease_seconds: 10, max_transmission_seconds: 60 } }
    if (url.endsWith('leave_channel')) return { message: { left: true } }
    const action = JSON.parse(options.body || '{}').action
    return { message: { granted: action === 'claim', floor: action === 'claim' ? { identity: 'worker-1', display_name: 'Worker' } : null } }
  })
  radio = useWalkieTalkie()
})
afterEach(async () => {
  wrapper?.unmount(); wrapper = null
  await radio.disconnect()
  vi.useRealTimers()
  vi.unstubAllGlobals()
})
async function join() { await radio.join('RADIO-1'); await flushPromises() }

describe('Project radio push-to-talk', () => {
  it('joins in listening mode without capturing or publishing the microphone', async () => {
    await join()
    expect(radio.connected.value).toBe(true)
    expect(getUserMedia).not.toHaveBeenCalled()
    expect(mocks.rooms[0].localParticipant.publishTrack).not.toHaveBeenCalled()
    expect(mocks.api.mock.calls.every(([, options]) => options.cache === 'no-store')).toBe(true)
  })

  it('publishes muted first and stops capture synchronously on release', async () => {
    await join(); await radio.hold()
    expect(radio.talking.value).toBe(true)
    expect(getUserMedia).toHaveBeenCalledWith(expect.objectContaining({ video: false }))
    expect(microphone.enabled).toBe(true)
    const released = radio.release()
    expect(microphone.enabled).toBe(false)
    expect(microphone.stop).toHaveBeenCalled()
    expect(radio.talking.value).toBe(false)
    await released
    expect(calls('release')).toHaveLength(1)
  })

  it('never opens the mic when another participant owns the floor', async () => {
    await join()
    mocks.api.mockResolvedValueOnce({ message: { granted: false, floor: { identity: 'other', display_name: 'Supervisor' } } })
    await radio.hold()
    expect(getUserMedia).not.toHaveBeenCalled()
    expect(radio.status.value).toBe('Supervisor is talking')
  })

  it('releases a late floor grant after the user has let go', async () => {
    await join()
    const pending = deferred(); mocks.api.mockReturnValueOnce(pending.promise)
    const held = radio.hold(); await flushPromises()
    const released = radio.release()
    pending.resolve({ message: { granted: true, floor: { identity: 'worker-1', display_name: 'Worker' } } })
    await held; await released
    expect(getUserMedia).not.toHaveBeenCalled()
    expect(calls('release').length).toBeGreaterThan(0)
  })

  it('stops a microphone that arrives after release without publishing it', async () => {
    await join()
    const pending = deferred(); getUserMedia.mockReturnValueOnce(pending.promise)
    const held = radio.hold(); await flushPromises()
    const released = radio.release()
    pending.resolve({ getAudioTracks: () => [microphone], getTracks: () => [microphone] })
    await held; await released
    expect(microphone.stop).toHaveBeenCalled()
    expect(microphone.enabled).toBe(false)
    expect(mocks.rooms[0].localParticipant.publishTrack).not.toHaveBeenCalled()
  })

  it('disconnects immediately on heartbeat failure and clears the mic', async () => {
    await join(); await radio.hold()
    mocks.api.mockRejectedValueOnce(new Error('Offline'))
    await vi.advanceTimersByTimeAsync(3000)
    expect(radio.connected.value).toBe(false)
    expect(microphone.enabled).toBe(false)
    expect(mocks.rooms[0].disconnect).toHaveBeenCalled()
    expect(radio.error.value).toContain('Connection lost')
  })

  it('stops capture if the control API hangs beyond the local lease watchdog', async () => {
    await join(); await radio.hold()
    const pending = deferred(); mocks.api.mockReturnValueOnce(pending.promise)
    await vi.advanceTimersByTimeAsync(8000)
    expect(microphone.enabled).toBe(false)
    expect(radio.connected.value).toBe(false)
    pending.resolve({ message: { granted: true, floor: null } }); await flushPromises()
    expect(radio.connected.value).toBe(false)
  })

  it('enforces the configured transmission maximum while heartbeats succeed', async () => {
    await join(); await radio.hold()
    mocks.api.mockImplementation(async (url, options) => ({ message: url.endsWith('floor_action')
      ? { granted: JSON.parse(options.body).action !== 'release', floor: { identity: 'worker-1', display_name: 'Worker' } }
      : { left: true } }))
    await vi.advanceTimersByTimeAsync(60000)
    expect(radio.talking.value).toBe(false)
    expect(microphone.enabled).toBe(false)
    expect(radio.error.value).toContain('Transmission limit')
  })

  it('does not reconnect or capture after a late join result', async () => {
    const pending = deferred(); mocks.api.mockReturnValueOnce(pending.promise)
    const joined = radio.join('RADIO-1'); await flushPromises()
    await radio.disconnect()
    pending.resolve({ message: { session_id: 'late-session' } }); await joined
    expect(radio.connected.value).toBe(false)
    expect(mocks.rooms).toHaveLength(0)
    expect(getUserMedia).not.toHaveBeenCalled()
  })

  it('shows a microphone error and releases the floor when permission is denied', async () => {
    await join()
    getUserMedia.mockRejectedValueOnce(new DOMException('Microphone denied', 'NotAllowedError'))
    await radio.hold()
    expect(radio.error.value).toContain('Microphone denied')
    expect(radio.talking.value).toBe(false)
    expect(calls('release')).toHaveLength(1)
  })
})

describe('Project radio mobile page', () => {
  it('loads project-scoped channels and disconnects capture when the page hides', async () => {
    wrapper = mount(WalkieTalkie); await flushPromises()
    expect(mocks.api.mock.calls[0][0]).toContain('project=PROJ-1')
    await wrapper.findAll('button').find(button => button.text() === 'Join channel').trigger('click'); await flushPromises()
    const ptt = wrapper.find('button[aria-pressed]')
    await ptt.trigger('pointerdown', { button: 0, pointerId: 1 }); await flushPromises()
    expect(microphone.enabled).toBe(true)
    window.dispatchEvent(new Event('pagehide')); await flushPromises()
    expect(microphone.enabled).toBe(false)
    expect(wrapper.text()).toContain('Disconnected')
  })

  it('releases on pointer cancellation and supports keyboard hold-to-talk', async () => {
    wrapper = mount(WalkieTalkie); await flushPromises()
    await wrapper.findAll('button').find(button => button.text() === 'Join channel').trigger('click'); await flushPromises()
    const ptt = wrapper.find('button[aria-pressed]')
    await ptt.trigger('keydown', { key: ' ' }); await flushPromises()
    expect(microphone.enabled).toBe(true)
    await ptt.trigger('keyup', { key: ' ' }); await flushPromises()
    expect(microphone.enabled).toBe(false)
    await ptt.trigger('pointerdown', { button: 0, pointerId: 1 }); await flushPromises()
    await ptt.trigger('pointercancel'); await flushPromises()
    expect(microphone.enabled).toBe(false)
  })

  it('opens the project radio from an enabled Project Tools selection', async () => {
    mocks.api.mockResolvedValue({ message: { grouped_tasks: [{ scope_name: 'PROJ-1', project: 'PROJ-1',
      project_details: { project_name: 'Demo project' }, parent_groups: [] }],
      project_tools: [{ key: 'walkie talkie', label: 'Walkie Talkie', description: 'Project radio' }] } })
    wrapper = mount(Home, { global: { stubs: { MobileSheet: { props: ['open'], template: '<div v-if="open"><slot /></div>' } } } })
    await flushPromises()
    await wrapper.findAll('button').find(button => button.text().includes('PROJ-1')).trigger('click')
    await wrapper.findAll('button').find(button => button.text() === 'Project Tools').trigger('click')
    await wrapper.findAll('button').find(button => button.text().includes('Walkie Talkie')).trigger('click')
    expect(mocks.push).toHaveBeenCalledWith({ name: 'walkie-talkie', params: { project: 'PROJ-1' } })
  })
})

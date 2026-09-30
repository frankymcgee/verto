import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { apiRequest } from '../src/lib/api'
import VoiceJha from '../src/pages/VoiceJha.vue'

vi.mock('../src/lib/api', () => ({ apiRequest: vi.fn() }))
vi.mock('vue-router', () => ({ useRoute: () => ({ params: { workSummary: 'WS-1' } }), useRouter: () => ({ back: vi.fn() }) }))

let wrapper, connections, track, snapshot
const config = { engine: 'realtime', engines: [
  { id: 'realtime', label: 'GPT Realtime', model: 'gpt-realtime-2.1', voice: 'marin' },
  { id: 'live', label: 'GPT Live', model: 'gpt-live-1', voice: 'quartz' },
] }
const button = (text) => wrapper.findAll('button').find(item => item.text() === text)
const channel = () => connections.at(-1).channel
const sent = () => channel().send.mock.calls.map(([raw]) => JSON.parse(raw))
const receive = async (event) => { channel().onmessage({ data: JSON.stringify(event) }); await flushPromises() }

async function connect(engine = 'live') {
  await wrapper.find('select').setValue(engine)
  await wrapper.find('input[type=checkbox]').setValue(true)
  await button('Connect Voice with PERI').trigger('click')
  await flushPromises()
  channel().readyState = 'open'
  channel().onopen()
  await flushPromises()
}

beforeEach(async () => {
  vi.clearAllMocks()
  connections = []
  track = { enabled: true, stop: vi.fn() }
  snapshot = { name: 'JHA-1', status: 'Voice Discussion in Progress', work_steps: [{ sequence: 1, activity: 'Fit pump' }], hazards_and_controls: [], participants: [], incident_learning: [] }
  vi.stubGlobal('RTCPeerConnection', class {
    constructor() { connections.push(this); this.iceGatheringState = 'complete'; this.connectionState = 'new' }
    createDataChannel() { this.channel = { readyState: 'connecting', send: vi.fn(), close: vi.fn() }; return this.channel }
    addTrack() {}
    async createOffer() { return { type: 'offer', sdp: 'v=0\noffer' } }
    async setLocalDescription(offer) { this.localDescription = offer }
    async setRemoteDescription() {}
    close() { this.connectionState = 'closed' }
  })
  Object.defineProperty(navigator, 'mediaDevices', { configurable: true, value: { getUserMedia: vi.fn(async () => ({ getAudioTracks: () => [track], getTracks: () => [track] })) } })
  apiRequest.mockImplementation(async (url, options) => {
    if (url.includes('bootstrap')) return { message: { work_summary: 'WS-1', title: 'Pump service', realtime_enabled: true, voice_configuration: config, existing_jha: snapshot } }
    if (url.includes('start_voice_jha_call')) {
      const engine = options.body.get('voice_engine')
      return { message: { sdp: 'v=0\nanswer', engine, model: engine === 'live' ? 'gpt-live-1' : 'gpt-realtime-2.1', jha: snapshot } }
    }
    if (url.includes('execute_voice_jha_tool')) {
      snapshot = { ...snapshot, hazards_and_controls: [{ name: 'H-1', work_step_sequence: 1, hazard_or_energy_source: 'Pinch points', existing_controls: 'Alignment tool' }] }
      return { message: { ok: true, result: { saved: true }, jha: snapshot } }
    }
    throw Error('Unexpected API request')
  })
  wrapper = mount(VoiceJha, { global: { stubs: { JhaFacilitationProgress: true, JhaReviewSignoff: true } } })
  await flushPromises()
})
afterEach(() => { wrapper?.unmount(); vi.useRealTimers(); vi.unstubAllGlobals() })

describe('Voice JHA engine selection and connection', () => {
  it('offers both engines, requires consent, and shows the Australian Live default', async () => {
    expect(wrapper.findAll('option').map(option => option.text())).toEqual(['GPT Realtime', 'GPT Live'])
    expect(button('Connect Voice with PERI').attributes('disabled')).toBeDefined()
    await wrapper.find('select').setValue('live')
    expect(wrapper.text()).toContain('GPT Live · gpt-live-1 · quartz')
    expect(navigator.mediaDevices.getUserMedia).not.toHaveBeenCalled()
  })
  it('preserves the Realtime greeting and restricted tool-result protocol', async () => {
    await connect('realtime')
    expect(sent()[0].type).toBe('response.create')
    expect(track.enabled).toBe(false)
    await receive({ type: 'response.function_call_arguments.done', name: 'record_hazard_and_control', call_id: 'rt-1', arguments: '{}' })
    expect(sent().slice(-2).map(e => e.type)).toEqual(['conversation.item.create', 'response.create'])
    expect(wrapper.text()).toContain('Pinch points')
    await receive({ type: 'response.function_call_arguments.done', name: 'record_hazard_and_control', call_id: 'rt-1', arguments: '{}' })
    expect(apiRequest.mock.calls.filter(([url]) => url.includes('execute_voice_jha_tool'))).toHaveLength(1)
  })
  it('waits for Live session startup, keeps push-to-talk muted, and renders both transcript speakers', async () => {
    await connect()
    expect(sent()).toEqual([])
    expect(wrapper.find('select').attributes('disabled')).toBeDefined()
    expect(wrapper.find('[aria-label="Hold to talk to PERI"]').exists()).toBe(false)
    await receive({ type: 'session.started', session: { id: 'live_1' } })
    expect(sent().map(e => e.type)).toEqual(['session.instructions.append'])
    const talk = wrapper.find('[aria-label="Hold to talk to PERI"]')
    expect(track.enabled).toBe(false)
    await talk.trigger('pointerdown', { pointerId: 1 })
    expect(track.enabled).toBe(true)
    await talk.trigger('pointerup', { pointerId: 1 })
    expect(track.enabled).toBe(false)
    await receive({ type: 'session.input_transcript.delta', event_id: 'in-1', delta: 'Fit the', start_ms: 10, end_ms: 20 })
    await receive({ type: 'session.output_transcript.delta', event_id: 'out-1', delta: 'Which hazard?', start_ms: 15, end_ms: 30 })
    await receive({ type: 'session.input_transcript.delta', event_id: 'in-2', delta: ' pump', start_ms: 21, end_ms: 35 })
    expect(wrapper.text()).toContain('Fit the pump')
    expect(wrapper.text()).toContain('Which hazard?')
    expect(sent().filter(e => e.type === 'response.create')).toHaveLength(0)
  })
  it('uses Live function items to update the same draft and continues after empty completion output', async () => {
    await connect()
    await receive({ type: 'session.started' })
    await receive({ type: 'response.event', delegation_id: 'd', event: { type: 'response.created', response: { id: 'r' } } })
    await receive({ type: 'response.event', delegation_id: 'd', event: { type: 'response.output_item.done', item: { type: 'function_call', name: 'record_hazard_and_control', call_id: 'live-call', arguments: '{}' } } })
    expect(sent().at(-1).type).toBe('response.item.create')
    expect(wrapper.text()).toContain('Pinch points')
    expect(wrapper.text()).toContain('Alignment tool')
    await receive({ type: 'response.event', delegation_id: 'd', event: { type: 'response.completed', response: { id: 'r', output: [] } } })
    expect(sent().at(-1).type).toBe('response.create')
    const request = apiRequest.mock.calls.find(([url]) => url.includes('execute_voice_jha_tool'))
    expect(request[1].body.get('jha_name')).toBe('JHA-1')
    expect(request[1].body.get('call_id')).toBe('live-call')
  })
  it('closes Live gracefully and switches to Realtime on the existing draft', async () => {
    await connect()
    await receive({ type: 'session.started' })
    await button('Disconnect Voice').trigger('click')
    await flushPromises()
    expect(sent().at(-1).type).toBe('session.close')
    expect(track.stop).not.toHaveBeenCalled()
    await receive({ type: 'session.closed' })
    expect(track.stop).toHaveBeenCalled()
    expect(wrapper.find('select').exists()).toBe(true)
    await connect('realtime')
    const starts = apiRequest.mock.calls.filter(([url]) => url.includes('start_voice_jha_call'))
    expect(starts.map(([, options]) => options.body.get('voice_engine'))).toEqual(['live', 'realtime'])
    expect(starts.map(([, options]) => options.body.get('jha_name'))).toEqual(['JHA-1', 'JHA-1'])
  })
  it('keeps the saved draft visible after a Live session error', async () => {
    await connect()
    await receive({ type: 'session.started' })
    await receive({ type: 'error', error: { message: 'Live model access unavailable' } })
    expect(wrapper.text()).toContain('Live model access unavailable')
    expect(wrapper.text()).toContain('Fit pump')
    expect(track.enabled).toBe(false)
  })
  it('waits for pending backend work before closing and rejects tools after close starts', async () => {
    await connect()
    await receive({ type: 'session.started' })
    await receive({ type: 'response.event', delegation_id: 'd', event: { type: 'response.created', response: { id: 'r' } } })
    await button('Disconnect Voice').trigger('click')
    await flushPromises()
    expect(sent().some(e => e.type === 'session.close')).toBe(false)
    await receive({ type: 'response.event', delegation_id: 'd', event: { type: 'response.completed', response: { id: 'r', output: [] } } })
    expect(sent().at(-1).type).toBe('session.close')
    await receive({ type: 'response.event', delegation_id: 'd', event: { type: 'response.output_item.done', item: { type: 'function_call', name: 'record_hazard_and_control', call_id: 'late', arguments: '{}' } } })
    expect(apiRequest.mock.calls.filter(([url]) => url.includes('execute_voice_jha_tool'))).toHaveLength(0)
    await receive({ type: 'session.closed' })
    expect(track.stop).toHaveBeenCalled()
  })
  it('releases the microphone and reports an unconfirmed close after timeout', async () => {
    await connect()
    await receive({ type: 'session.started' })
    vi.useFakeTimers()
    await button('Disconnect Voice').trigger('click')
    await flushPromises()
    await vi.advanceTimersByTimeAsync(15_000)
    expect(track.stop).toHaveBeenCalled()
    expect(wrapper.text()).toContain('did not confirm that the Live session finished')
  })
})

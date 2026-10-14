import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { apiRequest } from '../src/lib/api'
import VoiceJha from '../src/pages/VoiceJha.vue'

vi.mock('../src/lib/api', () => ({ apiRequest: vi.fn() }))
vi.mock('vue-router', () => ({ useRoute: () => ({ params: { workSummary: 'WS-1' } }), useRouter: () => ({ back: vi.fn() }) }))

let wrapper, connections, track, snapshot, configuredEngine
const configuration = () => ({ engine: configuredEngine, engine_label: configuredEngine === 'live' ? 'GPT Live' : 'GPT Realtime', model: configuredEngine === 'live' ? 'gpt-live-1' : 'gpt-realtime-2.1', voice: configuredEngine === 'live' ? 'quartz' : 'marin' })
const button = (text) => wrapper.findAll('button').find(item => item.text() === text)
const channel = () => connections.at(-1).channel
const sent = () => channel().send.mock.calls.map(([raw]) => JSON.parse(raw))
const receive = async (event) => { channel().onmessage({ data: JSON.stringify(event) }); await flushPromises() }

async function connect(engine = 'live') {
  // Simulate an administrator changing the server setting after page load.
  configuredEngine = engine
  await wrapper.find('input[type=checkbox]').setValue(true)
  await button('Connect Voice with PERI').trigger('click')
  await flushPromises()
  channel().readyState = 'open'
  channel().onopen()
  await flushPromises()
}

beforeEach(async () => {
  vi.clearAllMocks()
  configuredEngine = 'live'
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
    if (url.includes('bootstrap')) return { message: { work_summary: 'WS-1', title: 'Pump service', realtime_enabled: true, voice_configuration: configuration(), existing_jha: snapshot } }
    if (url.includes('start_voice_jha_call')) {
      expect(options.body.has('voice_engine')).toBe(false)
      const config = configuration()
      return { message: { sdp: 'v=0\nanswer', engine: config.engine, model: config.model, configuration: config, jha: snapshot } }
    }
    if (url.includes('execute_voice_jha_tool')) {
      if (options.body.get('tool_name') === 'mark_ready_for_human_review') {
        snapshot = { ...snapshot, status: 'Ready for Team Review' }
      } else if (options.body.get('tool_name') === 'record_hazard_and_control') {
        snapshot = { ...snapshot, hazards_and_controls: [{ name: 'H-1', work_step_sequence: 1, hazard_or_energy_source: 'Pinch points', existing_controls: 'Alignment tool' }] }
      }
      return { message: { ok: true, result: { saved: true }, jha: snapshot } }
    }
    if (url.includes('get_jha_review_state')) return { message: snapshot }
    if (url.includes('get_jha_fieldwork')) return { message: { controls: [], ccv_options: [], shift_reviews: [], today: '2026-10-14' } }
    if (url.includes('begin_jha_shift_review')) return { message: { name: 'SHIFT-1', jha: snapshot.name, revision: 1,
      shift_date: '2026-10-14', shift: 'Day', status: 'In Progress', checks: {} } }
    if (url.includes('begin_jha_change') || url.includes('begin_shift_change')) {
      snapshot = { ...snapshot, name: 'JHA-2', previous_jha: 'JHA-1', revision: 2,
        status: 'Incomplete - Actions Required', change_management_stage: 'Describe Change',
        facilitation: { stage: 'Change Request' }, review_completed: 0 }
      return { message: snapshot }
    }
    throw Error('Unexpected API request')
  })
  wrapper = mount(VoiceJha, { global: { stubs: { JhaFacilitationProgress: true, JhaReviewSignoff: true } } })
  await flushPromises()
})
afterEach(() => { wrapper?.unmount(); vi.useRealTimers(); vi.unstubAllGlobals() })

describe('Voice JHA configured engine connection', () => {
  it.each(['live', 'realtime'])('runs a %s shift review against the signed revision with consent and its own tool context', async engine => {
    snapshot = { ...snapshot, status: 'Signed', revision: 1 }
    wrapper.unmount()
    wrapper = mount(VoiceJha, { global: { stubs: { JhaReviewSignoff: true, JhaFieldwork: true } } })
    await flushPromises()
    wrapper.findComponent({ name: 'JhaFieldwork' }).vm.$emit('startReview', { shift_date: '2026-10-14', shift: 'Day' })
    await flushPromises()
    expect(navigator.mediaDevices.getUserMedia).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('Shift review with PERI')
    await connect(engine)
    if (engine === 'live') await receive({ type: 'session.started' })
    const start = apiRequest.mock.calls.find(([url]) => url.includes('start_voice_jha_call'))
    expect(start[1].body.get('shift_review')).toBe('SHIFT-1')
    expect(start[1].body.get('jha_name')).toBe('JHA-1')
    expect(JSON.stringify(sent())).toContain('start-of-shift review')
    expect(wrapper.text()).toContain('Signed')
    const item = { name: 'record_jha_shift_check', call_id: 'shift-answer', arguments: '{"category":"crew","changed":false,"notes":""}' }
    if (engine === 'live') {
      await receive({ type: 'response.event', delegation_id: 'shift', event: { type: 'response.created', response: { id: 'shift-response' } } })
      await receive({ type: 'response.event', delegation_id: 'shift', event: { type: 'response.output_item.done', item: { ...item, type: 'function_call' } } })
    } else await receive({ ...item, type: 'response.function_call_arguments.done' })
    const request = apiRequest.mock.calls.find(([url]) => url.includes('execute_voice_jha_tool'))
    expect(request[1].body.get('shift_review')).toBe('SHIFT-1')
    expect(request[1].body.get('jha_name')).toBe('JHA-1')
    expect(button('Disconnect Voice')).toBeDefined()
  })
  it('hands a changed shift review to a new revision and clears the old tool context', async () => {
    snapshot = { ...snapshot, status: 'Signed', revision: 1 }
    wrapper.unmount()
    wrapper = mount(VoiceJha, { global: { stubs: { JhaReviewSignoff: true, JhaFieldwork: true } } })
    await flushPromises()
    const fields = wrapper.findComponent({ name: 'JhaFieldwork' })
    fields.vm.$emit('startReview', { shift_date: '2026-10-14', shift: 'Day' }); await flushPromises()
    await connect('realtime')
    fields.vm.$emit('reviewChanges', { name: 'SHIFT-1', jha: 'JHA-1', status: 'Change Required' })
    await flushPromises()
    const change = apiRequest.mock.calls.find(([url]) => url.includes('begin_shift_change'))
    expect(change[1].body.get('shift_review')).toBe('SHIFT-1')
    expect(track.stop).toHaveBeenCalledOnce()
    const starts = apiRequest.mock.calls.filter(([url]) => url.includes('start_voice_jha_call'))
    expect(starts.map(([, options]) => options.body.get('shift_review'))).toEqual(['SHIFT-1', null])
    expect(starts.at(-1)[1].body.get('jha_name')).toBe('JHA-2')
  })
  it('has no engine selector and still requires consent before connecting', async () => {
    expect(wrapper.find('select').exists()).toBe(false)
    expect(button('Connect Voice with PERI').attributes('disabled')).toBeDefined()
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
    expect(wrapper.find('select').exists()).toBe(false)
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
  it('closes Live gracefully and applies changed server settings on the same draft', async () => {
    await connect()
    await receive({ type: 'session.started' })
    await button('Disconnect Voice').trigger('click')
    await flushPromises()
    expect(sent().at(-1).type).toBe('session.close')
    expect(track.stop).not.toHaveBeenCalled()
    await receive({ type: 'session.closed' })
    expect(track.stop).toHaveBeenCalled()
    expect(wrapper.find('select').exists()).toBe(false)
    await connect('realtime')
    const starts = apiRequest.mock.calls.filter(([url]) => url.includes('start_voice_jha_call'))
    expect(starts.map(([, options]) => options.body.get('voice_engine'))).toEqual([null, null])
    expect(starts.map(([, options]) => options.body.get('jha_name'))).toEqual(['JHA-1', 'JHA-1'])
    expect(sent()[0].type).toBe('response.create')
    expect(wrapper.find('[data-testid="jha-voice-panel"]').exists()).toBe(true)
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

  it.each(['live', 'realtime'])('keeps %s speech, audio and transcripts working through print/download until disconnect', async (engine) => {
    // Exercise the real review component so printing/downloading is part of the
    // connected flow, including its review-state update back to this page.
    wrapper.unmount()
    wrapper = mount(VoiceJha, { global: { stubs: { JhaFacilitationProgress: true, SignatureField: true } } })
    await flushPromises()
    await connect(engine)
    if (engine === 'live') await receive({ type: 'session.started' })

    const pc = connections.at(-1)
    const audio = wrapper.find('audio').element
    const remoteStream = new MediaStream()
    vi.spyOn(audio, 'play').mockResolvedValue()
    pc.ontrack({ streams: [remoteStream] })
    expect(audio.srcObject).toBe(remoteStream)

    const execute = async (name, id) => {
      const item = { type: 'function_call', name, call_id: id, arguments: '{}' }
      if (engine === 'live') {
        await receive({ type: 'response.event', delegation_id: 'review', event: { type: 'response.created', response: { id } } })
        await receive({ type: 'response.event', delegation_id: 'review', event: { type: 'response.output_item.done', item } })
        await receive({ type: 'response.event', delegation_id: 'review', event: { type: 'response.completed', response: { id, output: [] } } })
        // Finish the no-tool continuation before the eventual explicit close.
        await receive({ type: 'response.event', delegation_id: 'review', event: { type: 'response.created', response: { id: `${id}-continued` } } })
        await receive({ type: 'response.event', delegation_id: 'review', event: { type: 'response.completed', response: { id: `${id}-continued`, output: [] } } })
      } else {
        await receive({ ...item, type: 'response.function_call_arguments.done' })
      }
    }
    const talk = wrapper.find('[aria-label="Hold to talk to PERI"]')
    await talk.trigger('pointerdown', { pointerId: 1 })
    expect(track.enabled).toBe(true)
    await execute('mark_ready_for_human_review', 'ready')

    expect(wrapper.text()).toContain('Ready for Team Review')
    expect(wrapper.find('audio').exists()).toBe(true)
    expect(wrapper.find('audio').element).toBe(audio)
    expect(audio.srcObject).toBe(remoteStream)
    expect(wrapper.find('[aria-label="Release to send voice to PERI"]').element).toBe(talk.element)
    await talk.trigger('pointerup', { pointerId: 1 })
    expect(track.enabled).toBe(false)
    expect(button('Disconnect Voice')).toBeDefined()
    expect(track.stop).not.toHaveBeenCalled()

    const open = vi.spyOn(window, 'open').mockReturnValue(null)
    try {
      await button('Print JHA').trigger('click')
      await button('Download PDF').trigger('click')
      expect(open.mock.calls.map(([url]) => new URL(url, 'https://verto.test').pathname)).toEqual([
        '/printview', '/api/method/frappe.utils.print_format.download_pdf',
      ])
      for (const [url] of open.mock.calls) {
        const query = new URL(url, 'https://verto.test').searchParams
        expect(query.get('name')).toBe('JHA-1')
        expect(query.get('format')).toBe('Digital JHA Workpack')
      }
    } finally {
      open.mockRestore()
    }

    await talk.trigger('pointerdown', { pointerId: 1 })
    expect(track.enabled).toBe(true)
    await talk.trigger('pointerup', { pointerId: 1 })
    expect(track.enabled).toBe(false)

    if (engine === 'live') {
      await receive({ type: 'session.input_transcript.delta', event_id: 'review-in', delta: 'How do we print it?', start_ms: 100, end_ms: 200 })
      await receive({ type: 'session.output_transcript.delta', event_id: 'review-out', delta: 'Use Print JHA.', start_ms: 250, end_ms: 300 })
    } else {
      await receive({ type: 'conversation.item.input_audio_transcription.completed', transcript: 'How do we print it?' })
      await receive({ type: 'response.output_audio_transcript.delta', delta: 'Use Print JHA.' })
      expect(wrapper.text()).toContain('Use Print JHA.')
      await receive({ type: 'response.output_audio_transcript.done', transcript: 'Use Print JHA.' })
    }
    expect(wrapper.text()).toContain('How do we print it?')
    expect(wrapper.text()).toContain('Use Print JHA.')
    await execute('get_current_jha_state', 'read-after-ready')
    expect(apiRequest.mock.calls.filter(([url]) => url.includes('execute_voice_jha_tool'))).toHaveLength(2)
    expect(sent().some(event => event.type === 'session.close')).toBe(false)
    expect(pc.channel.close).not.toHaveBeenCalled()
    expect(wrapper.find('audio').element).toBe(audio)

    // Ending while the talk button is held must also mute/release the track.
    await talk.trigger('pointerdown', { pointerId: 2 })
    expect(track.enabled).toBe(true)
    await button('Disconnect Voice').trigger('click')
    await flushPromises()
    expect(track.enabled).toBe(false)
    if (engine === 'live') {
      expect(sent().at(-1).type).toBe('session.close')
      expect(button('Disconnect Voice').attributes('disabled')).toBeDefined()
      expect(track.stop).not.toHaveBeenCalled()
      await receive({ type: 'session.closed' })
    }
    expect(track.stop).toHaveBeenCalledOnce()
    expect(pc.channel.close).toHaveBeenCalledOnce()
    expect(pc.connectionState).toBe('closed')
    expect(audio.srcObject).toBeNull()
    expect(button('Disconnect Voice')).toBeUndefined()
    expect(wrapper.find('[aria-label="Hold to talk to PERI"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('How do we print it?')
    expect(button('Print JHA')).toBeDefined()
    expect(button('Download PDF')).toBeDefined()
  })

  it.each(['Signed', 'Review Required - Work Changed'])('retains the connected facilitator when human review changes the status to %s', async (status) => {
    await connect('realtime')
    wrapper.findComponent({ name: 'JhaReviewSignoff' }).vm.$emit('updated', { status })
    await flushPromises()
    const talk = wrapper.find('[aria-label="Hold to talk to PERI"]')
    await talk.trigger('pointerdown', { pointerId: 1 })
    expect(track.enabled).toBe(true)
    await talk.trigger('pointerup', { pointerId: 1 })
    expect(track.enabled).toBe(false)
    expect(button('Disconnect Voice')).toBeDefined()
    expect(track.stop).not.toHaveBeenCalled()
    await button('Disconnect Voice').trigger('click')
    expect(track.stop).toHaveBeenCalledOnce()
    expect(button('Connect Voice with PERI')).toBeUndefined()
  })

  it('releases a ready-for-review Live call when leaving the page', async () => {
    await connect()
    await receive({ type: 'session.started' })
    wrapper.findComponent({ name: 'JhaReviewSignoff' }).vm.$emit('updated', { status: 'Ready for Team Review' })
    await flushPromises()
    const pc = connections.at(-1)
    const voiceChannel = channel()
    wrapper.unmount()
    wrapper = null
    expect(JSON.parse(voiceChannel.send.mock.calls.at(-1)[0])).toMatchObject({ type: 'session.close', event_id: 'jha-leave' })
    expect(track.stop).toHaveBeenCalledOnce()
    expect(voiceChannel.close).toHaveBeenCalledOnce()
    expect(pc.connectionState).toBe('closed')
  })

  it('opens a signed JHA change revision and connects PERI to that revision after consent', async () => {
    snapshot = { ...snapshot, status: 'Signed', revision: 1 }
    wrapper.unmount()
    wrapper = mount(VoiceJha, { global: { stubs: { JhaFacilitationProgress: true, SignatureField: true } } })
    await flushPromises()
    await button('Request a JHA Change').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('Change review · Revision 2')
    expect(navigator.mediaDevices.getUserMedia).not.toHaveBeenCalled()
    await connect('live')
    await receive({ type: 'session.started' })
    const starts = apiRequest.mock.calls.filter(([url]) => url.includes('start_voice_jha_call'))
    expect(starts.at(-1)[1].body.get('jha_name')).toBe('JHA-2')
    expect(wrapper.text()).toContain('Change review with PERI')
    wrapper.findComponent({ name: 'JhaReviewSignoff' }).vm.$emit('updated', { name: 'JHA-1', status: 'Signed' })
    await flushPromises()
    expect(wrapper.text()).toContain('Change review · Revision 2')
  })

  it('finishes the old call before reconnecting to a requested change revision', async () => {
    wrapper.unmount()
    wrapper = mount(VoiceJha, { global: { stubs: { JhaFacilitationProgress: true, SignatureField: true } } })
    await flushPromises()
    await connect('live')
    await receive({ type: 'session.started' })
    snapshot = { ...snapshot, status: 'Ready for Team Review' }
    wrapper.findComponent({ name: 'JhaReviewSignoff' }).vm.$emit('updated', { name: 'JHA-1', status: 'Ready for Team Review' })
    await flushPromises()
    await button('Request a JHA Change').trigger('click')
    await flushPromises()
    expect(sent().at(-1).type).toBe('session.close')
    expect(apiRequest.mock.calls.some(([url]) => url.includes('begin_jha_change'))).toBe(false)
    await receive({ type: 'session.closed' })
    expect(track.stop).toHaveBeenCalledOnce()
    expect(connections).toHaveLength(2)
    expect(wrapper.text()).toContain('Change review · Revision 2')
    const starts = apiRequest.mock.calls.filter(([url]) => url.includes('start_voice_jha_call'))
    expect(starts.map(([, options]) => options.body.get('jha_name'))).toEqual(['JHA-1', 'JHA-2'])
  })
})

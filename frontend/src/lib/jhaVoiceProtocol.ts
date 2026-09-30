export type VoiceEngine = 'realtime' | 'live'
export type VoiceToolCall = { call_id: string; name: string; arguments: string }
type VoiceEvent = Record<string, any>

export function voiceGreeting(engine: VoiceEngine): VoiceEvent {
  const instructions = 'Greet the crew now in English, briefly identify the Work Summary, and resume the persisted facilitation stage and current step in your instructions. Ask the next missing question, then pause and listen. Do not restart a confirmed or completed phase.'
  return engine === 'live'
    ? { type: 'session.instructions.append', event_id: 'jha-greeting', delegation_id: null, content: instructions + ' Delegate to the backend to verify the current JHA and obtain the next workflow question before asking it.' }
    : { type: 'response.create', response: { instructions } }
}

export function voiceToolResult(engine: VoiceEngine, callId: string, result: any): VoiceEvent {
  return {
    type: engine === 'live' ? 'response.item.create' : 'conversation.item.create',
    event_id: `jha-result-${callId}`,
    item: { type: 'function_call_output', call_id: callId, output: JSON.stringify(result) },
  }
}

type LiveResponse = {
  id: string
  delegation: string
  calls: Set<string>
  pending: number
  completed: boolean
  continued: boolean
  failed: boolean
}

// Live forwards an empty output array at response.completed. Keep the completed
// function items ourselves and continue only after every result has been sent.
export class LiveJhaToolLoop {
  private responses = new Map<string, LiveResponse>()
  private activeResponses = new Map<string, string>()
  private seenCalls = new Set<string>()
  private awaitingContinuations = new Set<string>()
  private idleWaiters = new Set<(finished: boolean) => void>()
  private queue = Promise.resolve()
  private closed = false

  constructor(
    private execute: (call: VoiceToolCall) => Promise<Record<string, any>>,
    private send: (event: VoiceEvent) => boolean,
    private reportError: (message: string) => void,
  ) {}

  close() {
    this.closed = true
    this.resolveIdleWaiters(false)
  }
  drain() { return this.queue }

  // Finishing a local tool is not the end of delegated work: Live must receive
  // every result and complete the backend continuation before session.close.
  waitForIdle(): Promise<boolean> {
    if (this.closed) return Promise.resolve(false)
    if (this.isIdle()) return Promise.resolve(true)
    return new Promise(resolve => this.idleWaiters.add(resolve))
  }

  private isIdle() {
    return !this.awaitingContinuations.size && [...this.responses.values()].every(
      state => !state.pending && (state.completed || state.failed),
    )
  }

  private resolveIdleWaiters(finished: boolean) {
    for (const resolve of this.idleWaiters) resolve(finished)
    this.idleWaiters.clear()
  }

  private updateIdle() {
    if (!this.closed && this.isIdle()) this.resolveIdleWaiters(true)
  }

  handle(envelope: VoiceEvent) {
    if (this.closed) return
    if (envelope.type === 'session.delegation.created' && envelope.delegation?.target === 'responses') {
      const delegation = envelope.delegation
      this.awaitingContinuations.add(String(delegation.id))
      if (delegation.response_id) this.activeResponses.set(String(delegation.id), String(delegation.response_id))
      return
    }
    if (envelope.type !== 'response.event') return
    const event = envelope.event || {}
    const delegation = String(envelope.delegation_id || '')
    const id = String(event.response?.id || event.response_id || this.activeResponses.get(delegation) || '')
    if (!id) return
    if (event.type === 'response.created') this.awaitingContinuations.delete(delegation)
    this.activeResponses.set(delegation, id)
    let state = this.responses.get(id)
    if (!state) {
      state = { id, delegation, calls: new Set(), pending: 0, completed: false, continued: false, failed: false }
      this.responses.set(id, state)
    }
    if (event.type === 'response.output_item.done' && event.item?.type === 'function_call') {
      const call = event.item
      if (!call.call_id || !call.name || this.seenCalls.has(call.call_id)) return
      this.seenCalls.add(call.call_id)
      state.calls.add(call.call_id)
      state.pending += 1
      const current = state
      // Apply JHA mutations in order, including calls from overlapping delegations.
      this.queue = this.queue.then(async () => {
        try {
          if (this.closed || current.failed) return
          let result: Record<string, any>
          try { result = await this.execute(call) }
          catch (error) { result = { ok: false, error: error instanceof Error ? error.message : 'The JHA tool failed.' } }
          if (this.closed) return
          if (!this.send(voiceToolResult('live', call.call_id, result))) {
            current.failed = true
            this.reportError('The voice connection closed before the tool result could be delivered. Reconnect to check the saved draft.')
          }
        } finally {
          current.pending -= 1
          this.continueResponses()
          this.updateIdle()
        }
      })
    } else if (event.type === 'response.completed') {
      state.completed = true
      this.continueResponses()
    } else if (event.type === 'response.failed' || event.type === 'response.incomplete' || event.type === 'error') {
      state.failed = true
      this.awaitingContinuations.delete(delegation)
      this.reportError(String(event.response?.error?.message || event.error?.message || 'PERI could not complete the Live backend request.'))
    }
    this.updateIdle()
  }

  private continueResponses() {
    if (this.closed || [...this.responses.values()].some(state => state.pending)) return
    for (const state of this.responses.values()) {
      if (state.failed || state.continued || !state.completed || !state.calls.size) continue
      state.continued = true
      this.awaitingContinuations.add(state.delegation)
      if (!this.send({ type: 'response.create', event_id: `jha-continue-${state.id}` })) {
        state.failed = true
        this.awaitingContinuations.delete(state.delegation)
        this.reportError('The voice connection closed before PERI could continue. Reconnect to resume the saved draft.')
      }
    }
  }
}

export type LiveTranscriptFragment = {
  role: 'Crew' | 'PERI'; text: string; start_ms: number; end_ms: number
}

export function liveTranscriptEntries(fragments: LiveTranscriptFragment[]) {
  const groups: LiveTranscriptFragment[] = []
  const current: Partial<Record<'Crew' | 'PERI', LiveTranscriptFragment>> = {}
  // Arrival order need not match the timeline; speakers can overlap. Preserve
  // every fragment's spaces and repeated words, and group each speaker separately.
  for (const fragment of [...fragments].sort((a, b) => a.start_ms - b.start_ms)) {
    const previous = current[fragment.role]
    if (previous && fragment.start_ms - previous.end_ms <= 1500) {
      previous.text += fragment.text
      previous.end_ms = Math.max(previous.end_ms, fragment.end_ms)
    } else {
      const group = { ...fragment }
      groups.push(group)
      current[fragment.role] = group
    }
  }
  return groups.sort((a, b) => a.start_ms - b.start_ms).slice(-30)
}

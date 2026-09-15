<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Badge, Button, Checkbox } from 'frappe-ui'

import { apiRequest } from '../lib/api'
import JhaReviewSignoff from '../components/JhaReviewSignoff.vue'

type FrappeResponse<T> = { message: T }

type JhaSnapshot = {
  name: string
  status: string
  revision?: number
  project?: string
  work_summary?: string
  work_summary_title?: string
  work_order_number?: string
  work_area?: string
  ai_bot?: string
  modified?: string
  created?: boolean
  voice_session_reference?: string
  voice_model?: string
  voice_started_at?: string
  voice_transcription_consent_confirmed?: number | boolean
  voice_transcription_consent_confirmed_by?: string
  voice_transcription_consent_confirmed_at?: string
  work_steps?: any[]
  hazards_and_controls?: any[]
  participants?: any[]
  [key: string]: any
}

type VoiceJhaBootstrap = {
  work_summary: string
  title: string
  project?: string
  work_area?: string
  work_order_number?: string
  description?: string
  peri_bot?: string
  realtime_enabled: boolean
  prototype_stage?: string
  notice?: string
  existing_jha?: JhaSnapshot | null
  voice_configuration?: Record<string, any>
}

type VoiceCallResponse = {
  sdp: string
  model: string
  configuration?: Record<string, any>
  session_reference?: string
  consent_confirmed_at?: string
  jha: JhaSnapshot
}

type VoiceToolResponse = {
  ok: boolean
  replayed?: boolean
  tool_name: string
  result: Record<string, any>
  jha?: JhaSnapshot
}

type TranscriptEntry = {
  role: 'Crew' | 'PERI'
  text: string
}

const route = useRoute()
const router = useRouter()

const loading = ref(true)
const creating = ref(false)
const refreshing = ref(false)
const connecting = ref(false)
const error = ref('')
const context = ref<VoiceJhaBootstrap | null>(null)
const jha = ref<JhaSnapshot | null>(null)
const consentConfirmed = ref(false)
const voiceConnected = ref(false)
const pushToTalkActive = ref(false)
const voiceStatus = ref('Not connected')
const voiceModel = ref('')
const transcript = ref<TranscriptEntry[]>([])
const pendingPeriTranscript = ref('')
const remoteAudio = ref<HTMLAudioElement | null>(null)
const toolActivity = ref('')
const processingToolCalls = ref(0)
const completenessIssues = ref<string[]>([])

let peerConnection: RTCPeerConnection | null = null
let localStream: MediaStream | null = null
let dataChannel: RTCDataChannel | null = null
let manualDisconnect = false
const processedToolCalls = new Set<string>()

const workSummary = computed(() => String(route.params.workSummary || ''))
const workStepCount = computed(() => jha.value?.work_steps?.length || 0)
const hazardCount = computed(() => jha.value?.hazards_and_controls?.length || 0)
const participantCount = computed(() => jha.value?.participants?.length || 0)
const reviewStage = computed(() => [
  'Ready for Team Review',
  'Signed',
  'Review Required - Work Changed',
].includes(String(jha.value?.status || '')))
const canConnectVoice = computed(() => Boolean(
  jha.value?.name &&
  context.value?.realtime_enabled &&
  consentConfirmed.value &&
  !connecting.value &&
  !voiceConnected.value &&
  !reviewStage.value
))
const voiceConfigSummary = computed(() => {
  const config = context.value?.voice_configuration
  if (!config) return ''
  return [config.realtime_model, config.voice].filter(Boolean).join(' · ')
})

function handleReviewUpdated(value: Record<string, any>) {
  if (!jha.value) return
  jha.value = { ...jha.value, ...value }
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const data = await apiRequest<FrappeResponse<VoiceJhaBootstrap>>(
      `/api/method/verto.api.mobile.voice_jha.get_voice_jha_bootstrap?work_summary=${encodeURIComponent(workSummary.value)}`
    )
    context.value = data.message
    jha.value = data.message?.existing_jha || null
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Could not load the Work Summary.'
  } finally {
    loading.value = false
  }
}

async function createOrResumeDraft() {
  creating.value = true
  error.value = ''
  try {
    const payload = new FormData()
    payload.append('work_summary', workSummary.value)
    const data = await apiRequest<FrappeResponse<JhaSnapshot>>(
      '/api/method/verto.api.mobile.voice_jha.create_voice_jha_draft',
      { method: 'POST', body: payload }
    )
    jha.value = data.message
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Could not create or resume the Digital JHA draft.'
  } finally {
    creating.value = false
  }
}

async function refreshJha() {
  if (!jha.value?.name) {
    await load()
    return
  }

  refreshing.value = true
  error.value = ''
  try {
    const data = await apiRequest<FrappeResponse<JhaSnapshot>>(
      `/api/method/verto.api.mobile.voice_jha.get_voice_jha_snapshot?jha_name=${encodeURIComponent(jha.value.name)}`
    )
    jha.value = data.message
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Could not refresh the Digital JHA.'
  } finally {
    refreshing.value = false
  }
}

function appendTranscript(role: TranscriptEntry['role'], text: unknown) {
  const value = String(text || '').trim()
  if (!value) return
  transcript.value.push({ role, text: value })
  if (transcript.value.length > 30) {
    transcript.value = transcript.value.slice(-30)
  }
}

function sendRealtimeEvent(event: Record<string, any>) {
  if (!dataChannel || dataChannel.readyState !== 'open') return false
  dataChannel.send(JSON.stringify(event))
  return true
}

function setMicrophoneEnabled(enabled: boolean) {
  if (!localStream) return
  localStream.getAudioTracks().forEach((track) => {
    track.enabled = enabled
  })
}

function setPushToTalkIdleStatus() {
  if (!voiceConnected.value) return
  if (processingToolCalls.value) {
    voiceStatus.value = 'PERI is updating the draft…'
  } else if (pushToTalkActive.value) {
    voiceStatus.value = 'Talking to PERI… release to send'
  } else {
    voiceStatus.value = 'Connected · hold to talk'
  }
}

function startPushToTalk(event?: PointerEvent) {
  if (!voiceConnected.value || connecting.value || reviewStage.value || pushToTalkActive.value) return
  event?.preventDefault()
  const target = event?.currentTarget as HTMLElement | null
  if (target && event) {
    try { target.setPointerCapture?.(event.pointerId) } catch { /* pointer capture is best effort */ }
  }
  pushToTalkActive.value = true
  setMicrophoneEnabled(true)
  voiceStatus.value = 'Talking to PERI… release to send'
}

function stopPushToTalk(event?: PointerEvent) {
  if (!pushToTalkActive.value) return
  event?.preventDefault()
  setMicrophoneEnabled(false)
  pushToTalkActive.value = false
  voiceStatus.value = 'PERI is considering…'
}

function toolActivityMessage(toolName: string, result: Record<string, any>) {
  if (result?.message) return String(result.message)
  if (toolName === 'record_work_step') return 'Draft work step updated.'
  if (toolName === 'record_hazard_and_control') return 'Draft hazard/control updated.'
  if (toolName === 'record_participant') return 'JHA participant updated.'
  if (toolName === 'run_jha_completeness_check') return 'Draft completeness check completed.'
  if (toolName === 'mark_ready_for_human_review') return 'Draft review status checked.'
  return 'PERI accessed the structured draft.'
}

async function executeRealtimeTool(event: any) {
  const callId = String(event.call_id || '').trim()
  const toolName = String(event.name || '').trim()
  if (!callId || !toolName || !jha.value?.name || processedToolCalls.has(callId)) return

  processedToolCalls.add(callId)
  processingToolCalls.value += 1
  voiceStatus.value = 'PERI is updating the draft…'

  let toolOutput: Record<string, any>
  try {
    const payload = new FormData()
    payload.append('jha_name', jha.value.name)
    payload.append('tool_name', toolName)
    payload.append('arguments', String(event.arguments || '{}'))
    payload.append('call_id', callId)

    const data = await apiRequest<FrappeResponse<VoiceToolResponse>>(
      '/api/method/verto.api.mobile.voice_jha_tools.execute_voice_jha_tool',
      { method: 'POST', body: payload }
    )

    if (data.message?.jha) jha.value = data.message.jha
    toolOutput = data.message?.result || { ok: Boolean(data.message?.ok) }
    toolActivity.value = toolActivityMessage(toolName, toolOutput)

    if (Array.isArray(toolOutput.issues)) {
      completenessIssues.value = toolOutput.issues.map((item: unknown) => String(item))
    } else if (toolName === 'record_work_step' || toolName === 'record_hazard_and_control' || toolName === 'record_participant') {
      completenessIssues.value = []
    }
  } catch (err) {
    const message = err instanceof Error ? err.message : 'The JHA draft tool failed.'
    toolOutput = { ok: false, error: message }
    toolActivity.value = `Draft update not applied: ${message}`
  } finally {
    processingToolCalls.value = Math.max(0, processingToolCalls.value - 1)
  }

  sendRealtimeEvent({
    type: 'conversation.item.create',
    item: {
      type: 'function_call_output',
      call_id: callId,
      output: JSON.stringify(toolOutput),
    },
  })
  sendRealtimeEvent({ type: 'response.create' })
}

async function handleRealtimeEvent(raw: string) {
  let event: any
  try {
    event = JSON.parse(raw)
  } catch {
    return
  }

  if (event.type === 'session.created' || event.type === 'session.updated') {
    setPushToTalkIdleStatus()
    return
  }
  if (event.type === 'input_audio_buffer.speech_started') {
    if (pushToTalkActive.value) voiceStatus.value = 'Talking to PERI… release to send'
    return
  }
  if (event.type === 'input_audio_buffer.speech_stopped') {
    voiceStatus.value = 'PERI is considering…'
    return
  }
  if (event.type === 'conversation.item.input_audio_transcription.completed') {
    appendTranscript('Crew', event.transcript)
    return
  }
  if (event.type === 'response.output_audio_transcript.delta') {
    pendingPeriTranscript.value += String(event.delta || '')
    voiceStatus.value = 'PERI is speaking…'
    return
  }
  if (event.type === 'response.output_audio_transcript.done') {
    appendTranscript('PERI', event.transcript || pendingPeriTranscript.value)
    pendingPeriTranscript.value = ''
    return
  }
  if (event.type === 'response.function_call_arguments.done') {
    await executeRealtimeTool(event)
    return
  }
  if (event.type === 'response.done' || event.type === 'response.output_audio.done' || event.type === 'response.audio.done') {
    if (!processingToolCalls.value) setPushToTalkIdleStatus()
    return
  }
  if (event.type === 'error') {
    const message = event.error?.message || 'The realtime voice session reported an error.'
    error.value = String(message)
    voiceStatus.value = 'Voice error'
  }
}

function configureDataChannel(channel: RTCDataChannel) {
  dataChannel = channel

  channel.onopen = () => {
    setMicrophoneEnabled(false)
    voiceConnected.value = true
    pushToTalkActive.value = false
    voiceStatus.value = 'Connected · starting PERI…'
    sendRealtimeEvent({
      type: 'response.create',
      response: {
        instructions: 'Briefly greet the crew and identify the Work Summary. Then follow the configured field-JHA facilitation sequence: confirm the complete planned job-step list first, or build that list with the crew if no planned steps exist. Do not start by collecting participant names or roles; collect the development team near the end of the JHA.',
      },
    })
  }

  channel.onmessage = (event) => {
    void handleRealtimeEvent(String(event.data || ''))
  }

  channel.onerror = () => {
    error.value = 'The PERI realtime data channel reported an error.'
    voiceStatus.value = 'Voice error'
  }
}

function cleanupVoice(status = 'Not connected') {
  setMicrophoneEnabled(false)
  pushToTalkActive.value = false

  if (dataChannel) {
    dataChannel.onopen = null
    dataChannel.onmessage = null
    dataChannel.onerror = null
    try { dataChannel.close() } catch { /* already closed */ }
  }
  dataChannel = null

  if (peerConnection) {
    peerConnection.ontrack = null
    peerConnection.onconnectionstatechange = null
    try { peerConnection.close() } catch { /* already closed */ }
  }
  peerConnection = null

  if (localStream) localStream.getTracks().forEach((track) => track.stop())
  localStream = null
  if (remoteAudio.value) remoteAudio.value.srcObject = null

  voiceConnected.value = false
  connecting.value = false
  pendingPeriTranscript.value = ''
  processingToolCalls.value = 0
  voiceStatus.value = status
}

function disconnectVoice() {
  manualDisconnect = true
  cleanupVoice('Disconnected')
  window.setTimeout(() => { manualDisconnect = false }, 0)
}

async function connectVoice() {
  if (!jha.value?.name || !consentConfirmed.value || reviewStage.value) return
  if (!navigator.mediaDevices?.getUserMedia || typeof RTCPeerConnection === 'undefined') {
    error.value = 'This browser does not support the microphone/WebRTC features required for PERI voice.'
    return
  }

  connecting.value = true
  error.value = ''
  voiceStatus.value = 'Requesting microphone…'
  transcript.value = []
  pendingPeriTranscript.value = ''
  toolActivity.value = ''
  completenessIssues.value = []
  processedToolCalls.clear()
  manualDisconnect = false
  pushToTalkActive.value = false

  try {
    localStream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
    })

    // Privacy-first: no microphone audio is transmitted during connection setup.
    setMicrophoneEnabled(false)

    voiceStatus.value = 'Connecting to PERI…'
    const pc = new RTCPeerConnection()
    peerConnection = pc

    pc.ontrack = (event) => {
      if (!remoteAudio.value) return
      const stream = event.streams?.[0] || new MediaStream([event.track])
      remoteAudio.value.srcObject = stream
      remoteAudio.value.play().catch(() => {})
    }

    pc.onconnectionstatechange = () => {
      if (peerConnection !== pc) return
      if (pc.connectionState === 'connected') {
        voiceConnected.value = true
        setMicrophoneEnabled(false)
        pushToTalkActive.value = false
        voiceStatus.value = 'Connected · hold to talk'
      } else if (pc.connectionState === 'failed') {
        if (!manualDisconnect) error.value = 'The PERI voice connection failed.'
        cleanupVoice('Connection failed')
      } else if (pc.connectionState === 'disconnected' || pc.connectionState === 'closed') {
        if (!manualDisconnect) cleanupVoice('Disconnected')
      }
    }

    configureDataChannel(pc.createDataChannel('oai-events'))
    localStream.getTracks().forEach((track) => pc.addTrack(track, localStream as MediaStream))

    const offer = await pc.createOffer()
    await pc.setLocalDescription(offer)
    const offerSdp = pc.localDescription?.sdp
    if (!offerSdp) throw new Error('Could not create the WebRTC offer.')

    const payload = new FormData()
    payload.append('jha_name', jha.value.name)
    payload.append('sdp', offerSdp)
    payload.append('consent_confirmed', '1')

    const data = await apiRequest<FrappeResponse<VoiceCallResponse>>(
      '/api/method/verto.api.mobile.voice_jha.start_voice_jha_call',
      { method: 'POST', body: payload }
    )

    if (!data.message?.sdp) throw new Error('PERI did not return a WebRTC answer.')
    await pc.setRemoteDescription({ type: 'answer', sdp: data.message.sdp })

    jha.value = data.message.jha
    voiceModel.value = data.message.model || ''
    setMicrophoneEnabled(false)
    voiceStatus.value = 'Connecting audio…'
  } catch (err) {
    const message = err instanceof DOMException && err.name === 'NotAllowedError'
      ? 'Microphone access was not granted. Allow microphone access to use PERI voice.'
      : err instanceof Error ? err.message : 'Could not connect voice with PERI.'
    error.value = message
    cleanupVoice('Not connected')
  } finally {
    connecting.value = false
  }
}

onMounted(load)
onBeforeUnmount(() => {
  manualDisconnect = true
  cleanupVoice('Disconnected')
})
</script>

<template>
  <section class="min-h-full bg-surface-gray-1 px-[var(--verto-page-x,0.75rem)] py-[var(--verto-page-y,0.75rem)]">
    <div class="mx-auto w-full max-w-3xl space-y-3">
      <div class="flex items-center justify-between gap-3">
        <Button variant="subtle" theme="gray" size="sm" @click="router.back()">Back</Button>
        <Button v-if="jha" variant="subtle" theme="gray" size="sm" :loading="refreshing" :disabled="refreshing || voiceConnected || connecting" @click="refreshJha">Refresh</Button>
      </div>

      <section v-if="loading" class="rounded-7 border border-outline-gray-1 bg-surface-base p-4 shadow-sm">
        <div class="space-y-3"><div class="h-5 w-40 rounded-4 bg-surface-gray-3" /><div class="h-8 w-3/4 rounded-4 bg-surface-gray-2" /><div class="h-24 rounded-7 bg-surface-gray-2" /></div>
      </section>

      <section v-else-if="error && !context" class="rounded-7 border border-red-200 bg-red-50 p-4 shadow-sm">
        <p class="text-sm-medium text-red-800">Could not open this Work Summary.</p><p class="mt-1 text-sm text-red-700">{{ error }}</p>
      </section>

      <template v-else-if="context">
        <section class="rounded-7 border border-outline-gray-1 bg-surface-base p-4 shadow-sm">
          <div class="flex flex-wrap items-center gap-2">
            <Badge variant="subtle">Develop JHA with PERI</Badge>
            <Badge v-if="jha?.status" variant="subtle">{{ jha.status }}</Badge>
            <Badge v-if="context.work_order_number" variant="subtle">WO: {{ context.work_order_number }}</Badge>
          </div>
          <h1 class="mt-3 text-xl-semibold text-ink-gray-9">{{ context.title }}</h1>
          <p class="mt-1 text-sm text-ink-gray-5">{{ context.project }}<span v-if="context.work_area"> · {{ context.work_area }}</span></p>
          <div class="mt-4 rounded-7 border border-amber-200 bg-amber-50 p-3">
            <p class="text-sm-medium text-amber-900">Human review remains mandatory.</p>
            <p class="mt-1 text-sm leading-5 text-amber-800">PERI can record confirmed discussion points into this draft JHA. It cannot approve, submit, sign, authorise work or declare the job safe.</p>
          </div>
        </section>

        <section v-if="!jha" class="rounded-7 border border-outline-gray-1 bg-surface-base p-4 shadow-sm">
          <p class="text-base-semibold text-ink-gray-9">Start the JHA</p>
          <p class="mt-1 text-sm leading-5 text-ink-gray-6">A Digital JHA draft will be created and linked to this assigned Work Summary before the voice discussion begins.</p>
          <div class="mt-4 rounded-7 bg-surface-gray-1 p-3">
            <p class="text-xs-semibold uppercase tracking-wide text-ink-gray-5">AI facilitator</p>
            <p class="mt-1 text-sm-medium text-ink-gray-8">{{ context.peri_bot || 'PERI bot configuration required' }}</p>
            <p v-if="voiceConfigSummary" class="mt-1 text-xs text-ink-gray-5">{{ voiceConfigSummary }}</p>
          </div>
          <Button variant="solid" theme="gray" size="lg" class="mt-4 w-full justify-center" :loading="creating" :disabled="creating || !context.peri_bot" @click="createOrResumeDraft">Start JHA with PERI</Button>
        </section>

        <template v-else>
          <section class="rounded-7 border border-outline-gray-1 bg-surface-base p-4 shadow-sm">
            <div class="flex items-start justify-between gap-3">
              <div class="min-w-0"><p class="text-xs-semibold uppercase tracking-wide text-ink-gray-5">Digital JHA</p><p class="mt-1 truncate text-base-semibold text-ink-gray-9">{{ jha.name }}</p></div>
              <Badge variant="subtle">Rev {{ jha.revision || 1 }}</Badge>
            </div>
            <div class="mt-4 grid grid-cols-3 gap-2">
              <div class="rounded-7 bg-surface-gray-1 p-3 text-center"><p class="text-lg-semibold text-ink-gray-9">{{ workStepCount }}</p><p class="mt-0.5 text-xs text-ink-gray-5">Steps</p></div>
              <div class="rounded-7 bg-surface-gray-1 p-3 text-center"><p class="text-lg-semibold text-ink-gray-9">{{ hazardCount }}</p><p class="mt-0.5 text-xs text-ink-gray-5">Hazards</p></div>
              <div class="rounded-7 bg-surface-gray-1 p-3 text-center"><p class="text-lg-semibold text-ink-gray-9">{{ participantCount }}</p><p class="mt-0.5 text-xs text-ink-gray-5">People</p></div>
            </div>

            <div v-if="jha.work_steps?.length" class="mt-4 space-y-2">
              <p class="text-xs-semibold uppercase tracking-wide text-ink-gray-5">Recorded work steps</p>
              <div v-for="step in jha.work_steps" :key="step.name || step.source_step_identifier || step.sequence" class="rounded-7 border border-outline-gray-1 bg-surface-gray-1 p-3">
                <p class="text-sm-medium text-ink-gray-8">{{ step.sequence }}. {{ step.activity }}</p>
                <p v-if="step.hold_or_pause_point" class="mt-1 text-xs text-amber-700">Hold / pause point</p>
              </div>
            </div>

            <div v-if="jha.hazards_and_controls?.length" class="mt-4 space-y-2">
              <p class="text-xs-semibold uppercase tracking-wide text-ink-gray-5">Recorded hazards & controls</p>
              <div v-for="hazard in jha.hazards_and_controls" :key="hazard.name || hazard.source_hazard_identifier" class="rounded-7 border border-outline-gray-1 bg-surface-gray-1 p-3">
                <p class="text-sm-medium text-ink-gray-8">Step {{ hazard.work_step_sequence }} · {{ hazard.hazard_or_energy_source }}</p>
                <p v-if="hazard.credible_consequence" class="mt-1 text-xs text-ink-gray-6">Consequence: {{ hazard.credible_consequence }}</p>
                <p v-if="hazard.existing_controls || hazard.additional_controls" class="mt-1 text-xs text-ink-gray-6">Controls: {{ [hazard.existing_controls, hazard.additional_controls].filter(Boolean).join(' · ') }}</p>
              </div>
            </div>
          </section>

          <JhaReviewSignoff
            :jha="jha"
            @updated="handleReviewUpdated"
          />

          <section v-if="!reviewStage" class="rounded-7 border border-outline-gray-1 bg-surface-base p-4 shadow-sm">
            <div class="flex items-start justify-between gap-3">
              <div><p class="text-base-semibold text-ink-gray-9">Voice discussion</p><p class="mt-1 text-sm text-ink-gray-5">Push-to-talk structured JHA development with PERI</p></div>
              <Badge variant="subtle">{{ voiceConnected ? (processingToolCalls ? 'Updating draft' : (pushToTalkActive ? 'Talking' : 'Mic muted')) : voiceStatus }}</Badge>
            </div>

            <div v-if="!voiceConnected" class="mt-4 rounded-7 border border-outline-gray-1 bg-surface-gray-1 p-3">
              <label class="flex cursor-pointer items-start gap-3">
                <Checkbox class="mt-0.5 shrink-0" size="md" :model-value="consentConfirmed" :disabled="connecting" @update:model-value="(checked) => consentConfirmed = Boolean(checked)" />
                <span class="text-sm leading-5 text-ink-gray-7">I confirm everyone present has agreed to microphone use and transcription for this JHA discussion.</span>
              </label>
              <p class="mt-3 text-xs leading-4 text-ink-gray-5">This confirmation is recorded against the Digital JHA. Raw audio is not stored by this Verto workflow. Once connected, crew audio is transmitted only while the push-to-talk button is held.</p>
            </div>

            <div v-if="voiceConnected" class="mt-4 rounded-7 border border-green-200 bg-green-50 p-3">
              <p class="text-sm-medium text-green-900">PERI is connected · push-to-talk privacy mode</p>
              <p class="mt-1 text-sm text-green-800">{{ voiceStatus }}<span v-if="voiceModel"> · {{ voiceModel }}</span></p>
              <p class="mt-1 text-xs leading-4 text-green-700">The microphone track is muted whenever the button below is not being held. Your browser/device may still show that microphone permission is active while the PERI session remains connected.</p>
            </div>

            <div v-if="voiceConnected" class="mt-4 flex flex-col items-center">
              <button
                type="button"
                class="flex h-28 w-28 touch-none select-none flex-col items-center justify-center rounded-full border-2 shadow-sm transition active:scale-95"
                :class="pushToTalkActive ? 'border-red-500 bg-red-50 text-red-700' : 'border-outline-gray-3 bg-surface-gray-1 text-ink-gray-8'"
                :aria-pressed="pushToTalkActive"
                :aria-label="pushToTalkActive ? 'Release to send voice to PERI' : 'Hold to talk to PERI'"
                @pointerdown="startPushToTalk"
                @pointerup="stopPushToTalk"
                @pointercancel="stopPushToTalk"
                @lostpointercapture="stopPushToTalk"
                @contextmenu.prevent
              >
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="h-8 w-8" aria-hidden="true">
                  <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z" />
                  <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
                  <path d="M12 19v3" />
                  <path d="M8 22h8" />
                </svg>
                <span class="mt-2 text-sm-medium">{{ pushToTalkActive ? 'Release' : 'Hold to talk' }}</span>
              </button>
              <p class="mt-2 text-center text-xs text-ink-gray-5">Press and hold while speaking. Release when finished.</p>
            </div>

            <div v-if="toolActivity" class="mt-3 rounded-7 border border-blue-200 bg-blue-50 p-3">
              <p class="text-xs-semibold uppercase tracking-wide text-blue-700">Latest draft activity</p>
              <p class="mt-1 text-sm text-blue-900">{{ toolActivity }}</p>
            </div>

            <div v-if="completenessIssues.length" class="mt-3 rounded-7 border border-amber-200 bg-amber-50 p-3">
              <p class="text-sm-medium text-amber-900">Outstanding completeness items</p>
              <ul class="mt-2 space-y-1 pl-4 text-sm text-amber-800 list-disc">
                <li v-for="issue in completenessIssues" :key="issue">{{ issue }}</li>
              </ul>
            </div>

            <p class="mt-4 text-xs leading-4 text-ink-gray-5">PERI can only write to the draft through the restricted fields shown above. No submit, approval, acknowledgement, signature or work-authorisation tool is available.</p>

            <Button v-if="!voiceConnected" variant="solid" theme="gray" size="lg" class="mt-4 w-full justify-center" :loading="connecting" :disabled="!canConnectVoice" @click="connectVoice">Connect Voice with PERI</Button>
            <Button v-else variant="subtle" theme="gray" size="lg" class="mt-4 w-full justify-center" @click="disconnectVoice">Disconnect Voice</Button>
            <audio ref="remoteAudio" autoplay playsinline class="hidden" />
          </section>

          <section v-if="transcript.length || pendingPeriTranscript" class="rounded-7 border border-outline-gray-1 bg-surface-base p-4 shadow-sm">
            <div class="flex items-center justify-between gap-3"><p class="text-base-semibold text-ink-gray-9">Live transcript preview</p><Badge variant="subtle">Session preview</Badge></div>
            <div class="mt-3 max-h-80 space-y-2 overflow-y-auto">
              <div v-for="(entry, index) in transcript" :key="`${entry.role}-${index}`" class="rounded-7 bg-surface-gray-1 p-3">
                <p class="text-xs-semibold uppercase tracking-wide text-ink-gray-5">{{ entry.role }}</p><p class="mt-1 text-sm leading-5 text-ink-gray-8">{{ entry.text }}</p>
              </div>
              <div v-if="pendingPeriTranscript" class="rounded-7 bg-surface-gray-1 p-3"><p class="text-xs-semibold uppercase tracking-wide text-ink-gray-5">PERI</p><p class="mt-1 text-sm leading-5 text-ink-gray-8">{{ pendingPeriTranscript }}</p></div>
            </div>
          </section>
        </template>

        <section v-if="error" class="rounded-7 border border-red-200 bg-red-50 p-3 shadow-sm"><p class="text-sm text-red-700">{{ error }}</p></section>
      </template>
    </div>
  </section>
</template>

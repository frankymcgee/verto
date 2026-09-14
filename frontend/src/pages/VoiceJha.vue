<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Badge, Button, Checkbox } from 'frappe-ui'

import { apiRequest } from '../lib/api'

type FrappeResponse<T> = {
  message: T
}

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
}

type VoiceCallResponse = {
  sdp: string
  model: string
  session_reference?: string
  consent_confirmed_at?: string
  jha: JhaSnapshot
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
const voiceStatus = ref('Not connected')
const voiceModel = ref('')
const transcript = ref<TranscriptEntry[]>([])
const pendingPeriTranscript = ref('')
const remoteAudio = ref<HTMLAudioElement | null>(null)

let peerConnection: RTCPeerConnection | null = null
let localStream: MediaStream | null = null
let dataChannel: RTCDataChannel | null = null
let manualDisconnect = false

const workSummary = computed(() => String(route.params.workSummary || ''))
const workStepCount = computed(() => jha.value?.work_steps?.length || 0)
const hazardCount = computed(() => jha.value?.hazards_and_controls?.length || 0)
const participantCount = computed(() => jha.value?.participants?.length || 0)
const canConnectVoice = computed(() => Boolean(
  jha.value?.name &&
  context.value?.realtime_enabled &&
  consentConfirmed.value &&
  !connecting.value &&
  !voiceConnected.value
))

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
      {
        method: 'POST',
        body: payload,
      }
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
  if (!value) {
    return
  }

  transcript.value.push({ role, text: value })
  if (transcript.value.length > 20) {
    transcript.value = transcript.value.slice(-20)
  }
}

function handleRealtimeEvent(raw: string) {
  let event: any
  try {
    event = JSON.parse(raw)
  } catch {
    return
  }

  if (event.type === 'session.created' || event.type === 'session.updated') {
    voiceStatus.value = 'Connected · listening'
    return
  }

  if (event.type === 'input_audio_buffer.speech_started') {
    voiceStatus.value = 'Listening to crew…'
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

  if (event.type === 'response.done' || event.type === 'response.audio.done') {
    voiceStatus.value = 'Connected · listening'
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
    voiceConnected.value = true
    voiceStatus.value = 'Connected · starting PERI…'

    channel.send(JSON.stringify({
      type: 'response.create',
      response: {
        instructions: 'Briefly greet the crew, identify the Work Summary, remind them this is a draft JHA discussion requiring human review, then ask them to describe the job in their own words.',
      },
    }))
  }

  channel.onmessage = (event) => {
    handleRealtimeEvent(String(event.data || ''))
  }

  channel.onerror = () => {
    error.value = 'The PERI realtime data channel reported an error.'
    voiceStatus.value = 'Voice error'
  }
}

function cleanupVoice(status = 'Not connected') {
  if (dataChannel) {
    dataChannel.onopen = null
    dataChannel.onmessage = null
    dataChannel.onerror = null
    try {
      dataChannel.close()
    } catch {
      // already closed
    }
  }
  dataChannel = null

  if (peerConnection) {
    peerConnection.ontrack = null
    peerConnection.onconnectionstatechange = null
    try {
      peerConnection.close()
    } catch {
      // already closed
    }
  }
  peerConnection = null

  if (localStream) {
    localStream.getTracks().forEach((track) => track.stop())
  }
  localStream = null

  if (remoteAudio.value) {
    remoteAudio.value.srcObject = null
  }

  voiceConnected.value = false
  connecting.value = false
  pendingPeriTranscript.value = ''
  voiceStatus.value = status
}

function disconnectVoice() {
  manualDisconnect = true
  cleanupVoice('Disconnected')
  window.setTimeout(() => {
    manualDisconnect = false
  }, 0)
}

async function connectVoice() {
  if (!jha.value?.name || !consentConfirmed.value) {
    return
  }

  if (!navigator.mediaDevices?.getUserMedia || typeof RTCPeerConnection === 'undefined') {
    error.value = 'This browser does not support the microphone/WebRTC features required for PERI voice.'
    return
  }

  connecting.value = true
  error.value = ''
  voiceStatus.value = 'Requesting microphone…'
  transcript.value = []
  pendingPeriTranscript.value = ''
  manualDisconnect = false

  try {
    localStream = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      },
    })

    voiceStatus.value = 'Connecting to PERI…'

    const pc = new RTCPeerConnection()
    peerConnection = pc

    pc.ontrack = (event) => {
      if (!remoteAudio.value) {
        return
      }

      const stream = event.streams?.[0] || new MediaStream([event.track])
      remoteAudio.value.srcObject = stream
      remoteAudio.value.play().catch(() => {
        // The connect action is user initiated, but some mobile browsers may still
        // delay playback until their media pipeline is ready.
      })
    }

    pc.onconnectionstatechange = () => {
      if (peerConnection !== pc) {
        return
      }

      if (pc.connectionState === 'connected') {
        voiceConnected.value = true
        voiceStatus.value = 'Connected · listening'
      } else if (pc.connectionState === 'failed') {
        if (!manualDisconnect) {
          error.value = 'The PERI voice connection failed.'
        }
        cleanupVoice('Connection failed')
      } else if (pc.connectionState === 'disconnected' || pc.connectionState === 'closed') {
        if (!manualDisconnect) {
          cleanupVoice('Disconnected')
        }
      }
    }

    configureDataChannel(pc.createDataChannel('oai-events'))
    localStream.getTracks().forEach((track) => pc.addTrack(track, localStream as MediaStream))

    const offer = await pc.createOffer()
    await pc.setLocalDescription(offer)

    const offerSdp = pc.localDescription?.sdp
    if (!offerSdp) {
      throw new Error('Could not create the WebRTC offer.')
    }

    const payload = new FormData()
    payload.append('jha_name', jha.value.name)
    payload.append('sdp', offerSdp)
    payload.append('consent_confirmed', '1')

    const data = await apiRequest<FrappeResponse<VoiceCallResponse>>(
      '/api/method/verto.api.mobile.voice_jha.start_voice_jha_call',
      {
        method: 'POST',
        body: payload,
      }
    )

    if (!data.message?.sdp) {
      throw new Error('PERI did not return a WebRTC answer.')
    }

    await pc.setRemoteDescription({
      type: 'answer',
      sdp: data.message.sdp,
    })

    jha.value = data.message.jha
    voiceModel.value = data.message.model || ''
    voiceStatus.value = 'Connecting audio…'
  } catch (err) {
    const message = err instanceof DOMException && err.name === 'NotAllowedError'
      ? 'Microphone access was not granted. Allow microphone access to use PERI voice.'
      : err instanceof Error
        ? err.message
        : 'Could not connect voice with PERI.'

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
        <Button variant="subtle" theme="gray" size="sm" @click="router.back()">
          Back
        </Button>

        <Button
          v-if="jha"
          variant="subtle"
          theme="gray"
          size="sm"
          :loading="refreshing"
          :disabled="refreshing || voiceConnected || connecting"
          @click="refreshJha"
        >
          Refresh
        </Button>
      </div>

      <section v-if="loading" class="rounded-7 border border-outline-gray-1 bg-surface-base p-4 shadow-sm">
        <div class="space-y-3">
          <div class="h-5 w-40 rounded-4 bg-surface-gray-3" />
          <div class="h-8 w-3/4 rounded-4 bg-surface-gray-2" />
          <div class="h-24 rounded-7 bg-surface-gray-2" />
        </div>
      </section>

      <section
        v-else-if="error && !context"
        class="rounded-7 border border-red-200 bg-red-50 p-4 shadow-sm"
      >
        <p class="text-sm-medium text-red-800">Could not open this Work Summary.</p>
        <p class="mt-1 text-sm text-red-700">{{ error }}</p>
      </section>

      <template v-else-if="context">
        <section class="rounded-7 border border-outline-gray-1 bg-surface-base p-4 shadow-sm">
          <div class="flex flex-wrap items-center gap-2">
            <Badge variant="subtle">Develop JHA with PERI</Badge>
            <Badge v-if="jha?.status" variant="subtle">{{ jha.status }}</Badge>
            <Badge v-if="context.work_order_number" variant="subtle">WO: {{ context.work_order_number }}</Badge>
          </div>

          <h1 class="mt-3 text-xl-semibold text-ink-gray-9">
            {{ context.title }}
          </h1>

          <p class="mt-1 text-sm text-ink-gray-5">
            {{ context.project }}<span v-if="context.work_area"> · {{ context.work_area }}</span>
          </p>

          <div class="mt-4 rounded-7 border border-amber-200 bg-amber-50 p-3">
            <p class="text-sm-medium text-amber-900">Human review remains mandatory.</p>
            <p class="mt-1 text-sm leading-5 text-amber-800">
              PERI can help the crew develop and document a draft JHA. It does not authorise work, approve the JHA, or sign on behalf of any participant.
            </p>
          </div>
        </section>

        <section v-if="!jha" class="rounded-7 border border-outline-gray-1 bg-surface-base p-4 shadow-sm">
          <p class="text-base-semibold text-ink-gray-9">Start the JHA</p>
          <p class="mt-1 text-sm leading-5 text-ink-gray-6">
            PERI will use this assigned Work Summary as the controlled starting context. A Digital JHA draft will be created and linked to this work before the voice discussion begins.
          </p>

          <div class="mt-4 rounded-7 bg-surface-gray-1 p-3">
            <p class="text-xs-semibold uppercase tracking-wide text-ink-gray-5">AI facilitator</p>
            <p class="mt-1 text-sm-medium text-ink-gray-8">
              {{ context.peri_bot || 'PERI bot configuration required' }}
            </p>
          </div>

          <Button
            variant="solid"
            theme="gray"
            size="lg"
            class="mt-4 w-full justify-center"
            :loading="creating"
            :disabled="creating || !context.peri_bot"
            @click="createOrResumeDraft"
          >
            Start JHA with PERI
          </Button>
        </section>

        <template v-else>
          <section class="rounded-7 border border-outline-gray-1 bg-surface-base p-4 shadow-sm">
            <div class="flex items-start justify-between gap-3">
              <div class="min-w-0">
                <p class="text-xs-semibold uppercase tracking-wide text-ink-gray-5">Digital JHA</p>
                <p class="mt-1 truncate text-base-semibold text-ink-gray-9">{{ jha.name }}</p>
              </div>

              <Badge variant="subtle">Rev {{ jha.revision || 1 }}</Badge>
            </div>

            <div class="mt-4 grid grid-cols-3 gap-2">
              <div class="rounded-7 bg-surface-gray-1 p-3 text-center">
                <p class="text-lg-semibold text-ink-gray-9">{{ workStepCount }}</p>
                <p class="mt-0.5 text-xs text-ink-gray-5">Steps</p>
              </div>
              <div class="rounded-7 bg-surface-gray-1 p-3 text-center">
                <p class="text-lg-semibold text-ink-gray-9">{{ hazardCount }}</p>
                <p class="mt-0.5 text-xs text-ink-gray-5">Hazards</p>
              </div>
              <div class="rounded-7 bg-surface-gray-1 p-3 text-center">
                <p class="text-lg-semibold text-ink-gray-9">{{ participantCount }}</p>
                <p class="mt-0.5 text-xs text-ink-gray-5">People</p>
              </div>
            </div>
          </section>

          <section class="rounded-7 border border-outline-gray-1 bg-surface-base p-4 shadow-sm">
            <div class="flex items-start justify-between gap-3">
              <div>
                <p class="text-base-semibold text-ink-gray-9">Voice discussion</p>
                <p class="mt-1 text-sm text-ink-gray-5">Live crew conversation with PERI</p>
              </div>
              <Badge variant="subtle">{{ voiceConnected ? 'Microphone live' : voiceStatus }}</Badge>
            </div>

            <div v-if="!voiceConnected" class="mt-4 rounded-7 border border-outline-gray-1 bg-surface-gray-1 p-3">
              <label class="flex cursor-pointer items-start gap-3">
                <Checkbox
                  class="mt-0.5 shrink-0"
                  size="md"
                  :model-value="consentConfirmed"
                  :disabled="connecting"
                  @update:model-value="(checked) => consentConfirmed = Boolean(checked)"
                />
                <span class="text-sm leading-5 text-ink-gray-7">
                  I confirm everyone present has agreed to microphone use and transcription for this JHA discussion.
                </span>
              </label>

              <p class="mt-3 text-xs leading-4 text-ink-gray-5">
                This confirmation is recorded against the Digital JHA with your user and timestamp. Verto does not store raw audio in this workflow.
              </p>
            </div>

            <div v-if="voiceConnected" class="mt-4 rounded-7 border border-green-200 bg-green-50 p-3">
              <p class="text-sm-medium text-green-900">Microphone and transcription are active.</p>
              <p class="mt-1 text-sm text-green-800">
                {{ voiceStatus }}<span v-if="voiceModel"> · {{ voiceModel }}</span>
              </p>
            </div>

            <div class="mt-4 space-y-2 text-sm text-ink-gray-6">
              <p>PERI will ask the crew to describe the work, then work through steps, hazards, consequences and controls.</p>
              <p>PERI cannot approve, sign, submit or authorise the JHA or the work.</p>
              <p class="text-xs text-ink-gray-5">This pilot voice milestone is discussion-only; structured JHA rows are not yet written automatically from the conversation.</p>
            </div>

            <Button
              v-if="!voiceConnected"
              variant="solid"
              theme="gray"
              size="lg"
              class="mt-4 w-full justify-center"
              :loading="connecting"
              :disabled="!canConnectVoice"
              @click="connectVoice"
            >
              Connect Voice with PERI
            </Button>

            <Button
              v-else
              variant="subtle"
              theme="gray"
              size="lg"
              class="mt-4 w-full justify-center"
              @click="disconnectVoice"
            >
              Disconnect Voice
            </Button>

            <audio ref="remoteAudio" autoplay playsinline class="hidden" />
          </section>

          <section
            v-if="transcript.length || pendingPeriTranscript"
            class="rounded-7 border border-outline-gray-1 bg-surface-base p-4 shadow-sm"
          >
            <div class="flex items-center justify-between gap-3">
              <p class="text-base-semibold text-ink-gray-9">Live transcript preview</p>
              <Badge variant="subtle">Not saved yet</Badge>
            </div>

            <div class="mt-3 max-h-80 space-y-2 overflow-y-auto">
              <div
                v-for="(entry, index) in transcript"
                :key="`${entry.role}-${index}`"
                class="rounded-7 bg-surface-gray-1 p-3"
              >
                <p class="text-xs-semibold uppercase tracking-wide text-ink-gray-5">{{ entry.role }}</p>
                <p class="mt-1 text-sm leading-5 text-ink-gray-8">{{ entry.text }}</p>
              </div>

              <div v-if="pendingPeriTranscript" class="rounded-7 bg-surface-gray-1 p-3">
                <p class="text-xs-semibold uppercase tracking-wide text-ink-gray-5">PERI</p>
                <p class="mt-1 text-sm leading-5 text-ink-gray-8">{{ pendingPeriTranscript }}</p>
              </div>
            </div>
          </section>
        </template>

        <section
          v-if="error"
          class="rounded-7 border border-red-200 bg-red-50 p-3 shadow-sm"
        >
          <p class="text-sm text-red-700">{{ error }}</p>
        </section>
      </template>
    </div>
  </section>
</template>

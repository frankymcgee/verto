<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Button } from 'frappe-ui'
import { apiRequest } from '../lib/api'
import { useWalkieTalkie } from '../composables/useWalkieTalkie'

type Channel = { name: string; channel_name: string; project: string }
const route = useRoute()
const router = useRouter()
const channels = ref<Channel[]>([])
const selected = ref('')
const loading = ref(true)
const loadError = ref('')
const { connected, joining, talking, claiming, floor, error, audioBlocked, participants, status,
  join, disconnect, hold, release, startAudio } = useWalkieTalkie()
let loadGeneration = 0

async function loadChannels() {
  const attempt = ++loadGeneration
  await disconnect()
  loading.value = true
  loadError.value = ''
  channels.value = []
  selected.value = ''
  try {
    const response = await apiRequest<{ message: { channels: Channel[] } }>(
      `/api/method/verto.api.mobile.walkie_talkie.get_channels?project=${encodeURIComponent(String(route.params.project))}`,
      { cache: 'no-store' },
    )
    if (attempt !== loadGeneration) return
    channels.value = response.message.channels
    selected.value = channels.value[0]?.name || ''
  } catch {
    if (attempt === loadGeneration) loadError.value = 'Could not load project channels. Check your connection and project access.'
  } finally {
    if (attempt === loadGeneration) loading.value = false
  }
}

function pointerDown(event: PointerEvent) {
  if (event.button !== 0) return
  ;(event.currentTarget as HTMLElement).setPointerCapture?.(event.pointerId)
  void hold()
}
function hide() { if (document.hidden) void disconnect() }
function blur() { void release() }
function pageHide() { void disconnect() }
function keyDown(event: KeyboardEvent) {
  if ((event.key === ' ' || event.key === 'Enter') && !event.repeat) { event.preventDefault(); void hold() }
}
function keyUp(event: KeyboardEvent) {
  if (event.key === ' ' || event.key === 'Enter') { event.preventDefault(); void release() }
}

watch(() => route.params.project, loadChannels)
onMounted(() => {
  void loadChannels()
  document.addEventListener('visibilitychange', hide)
  window.addEventListener('blur', blur)
  window.addEventListener('pagehide', pageHide)
  window.addEventListener('offline', pageHide)
})
onBeforeUnmount(() => {
  loadGeneration++
  void disconnect()
  document.removeEventListener('visibilitychange', hide)
  window.removeEventListener('blur', blur)
  window.removeEventListener('pagehide', pageHide)
  window.removeEventListener('offline', pageHide)
})
</script>

<template>
  <section class="mx-auto max-w-2xl space-y-5 px-[var(--verto-page-x,0.75rem)] py-[var(--verto-page-y,0.75rem)] pb-8">
    <div class="flex items-center justify-between gap-3">
      <div>
        <h1 class="text-xl-semibold text-ink-gray-9">Walkie Talkie</h1>
        <p class="text-sm text-ink-gray-6">{{ route.params.project }}</p>
      </div>
      <Button variant="subtle" @click="router.push('/')">Home</Button>
    </div>
    <p class="text-sm text-ink-gray-6">Join your team’s channel, then hold the button to talk. One person can speak at a time. Audio is live and is not recorded.</p>
    <p v-if="loading" role="status" class="text-sm text-ink-gray-6">Loading channels…</p>
    <div v-else-if="loadError" class="space-y-3">
      <p role="alert" class="text-sm text-ink-red-4">{{ loadError }}</p>
      <Button @click="loadChannels">Try again</Button>
    </div>
    <p v-else-if="!channels.length" class="rounded-7 border border-outline-gray-1 bg-surface-base p-4 text-sm text-ink-gray-6">No channels are available for this project. Ask your administrator to create a Verto Walkie Talkie channel and check your membership.</p>
    <div v-else class="space-y-5 rounded-7 border border-outline-gray-1 bg-surface-base p-5">
      <label class="block space-y-2 text-sm-medium text-ink-gray-9">
        <span>Channel</span>
        <select v-model="selected" :disabled="connected || joining" class="w-full rounded-6 border border-outline-gray-2 bg-surface-base p-2 text-ink-gray-9">
          <option v-for="channel in channels" :key="channel.name" :value="channel.name">{{ channel.channel_name }}</option>
        </select>
      </label>
      <div class="flex items-center justify-between gap-3">
        <p role="status" aria-live="polite" class="text-sm-medium text-ink-gray-9">{{ joining ? 'Joining…' : status }}</p>
        <Button v-if="connected || joining" variant="subtle" @click="disconnect">Disconnect</Button>
        <Button v-else variant="solid" @click="join(selected)">Join channel</Button>
      </div>
      <Button v-if="audioBlocked" @click="startAudio">Enable audio</Button>
      <div class="flex justify-center py-5">
        <button type="button" :disabled="!connected" :aria-pressed="talking"
          class="flex h-44 w-44 touch-none select-none items-center justify-center rounded-full border-4 px-5 text-center text-lg-semibold transition-colors disabled:opacity-40"
          :class="talking ? 'border-outline-red-3 bg-surface-red-2 text-ink-red-4' : 'border-outline-gray-3 bg-surface-gray-2 text-ink-gray-9'"
          style="-webkit-touch-callout: none"
          @pointerdown.prevent="pointerDown" @pointerup.prevent="release" @pointercancel="release"
          @lostpointercapture="release" @contextmenu.prevent @keydown="keyDown" @keyup="keyUp" @blur="release">
          {{ talking ? 'Release to stop' : claiming ? 'Connecting mic…' : 'Hold to talk' }}
        </button>
      </div>
      <p v-if="error" role="alert" class="break-words text-sm text-ink-red-4">{{ error }}</p>
      <div v-if="connected" class="space-y-2 text-sm text-ink-gray-6">
        <p class="text-sm-medium text-ink-gray-9">In this channel ({{ participants.length }})</p>
        <ul class="list-inside list-disc"><li v-for="(name, index) in participants" :key="index">{{ name }}</li></ul>
      </div>
    </div>
    <p class="text-xs text-ink-gray-6">Keep this page open to listen. Leaving the page, locking your phone or switching apps disconnects the radio. An internet connection is required.</p>
  </section>
</template>

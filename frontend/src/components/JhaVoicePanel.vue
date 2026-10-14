<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { Button, Checkbox } from 'frappe-ui'
import { useMobileBoot } from '../lib/mobileBoot'

const props = defineProps<{
  connected: boolean; connecting: boolean; disconnecting: boolean; canConnect: boolean
  consent: boolean; talking: boolean; busy: boolean; level: number; status: string
  step?: string; latestSpeech?: string; changing?: boolean
}>()
const emit = defineEmits<{
  connect: []; disconnect: []; consent: [value: boolean]
  talkStart: [event: PointerEvent]; talkStop: [event: PointerEvent]
  clearanceChange: [pixels: number]
}>()
const { periBotImageUrl } = useMobileBoot()
const dock = ref<HTMLElement | null>(null)
const imageFailed = ref(false)
const speaking = computed(() => props.connected && props.level > 0)
const activity = computed(() => props.disconnecting ? 'Ending call' : props.connecting ? 'Connecting' :
  speaking.value ? 'Speaking' : props.talking ? 'Listening' : props.busy ? 'Thinking' : props.connected ? 'Ready to listen' : 'Not connected')
const bars = [0.45, 0.8, 1, 0.65, 0.9, 0.5]

watch(dock, (element, _previous, onCleanup) => {
  const scrollArea = element?.closest<HTMLElement>('.mobile-shell-main')
  if (!element || !scrollArea) {
    emit('clearanceChange', 0)
    return
  }

  // Navigation sits outside the scroller. Reserve only the area the fixed dock
  // covers inside it, including the gap beneath the dock, at its rendered size.
  const measure = () => emit('clearanceChange', getComputedStyle(element).position === 'fixed'
    ? Math.max(0, Math.ceil(scrollArea.getBoundingClientRect().bottom - element.getBoundingClientRect().top))
    : 0)
  const observer = new ResizeObserver(measure)
  observer.observe(element)
  observer.observe(scrollArea)
  window.addEventListener('resize', measure)
  window.visualViewport?.addEventListener('resize', measure)
  measure()
  onCleanup(() => {
    observer.disconnect()
    window.removeEventListener('resize', measure)
    window.visualViewport?.removeEventListener('resize', measure)
  })
}, { flush: 'post' })

onBeforeUnmount(() => emit('clearanceChange', 0))
</script>

<template>
  <section data-testid="jha-voice-panel" class="voice-panel rounded-7 border border-outline-gray-2 bg-surface-base p-3 shadow-sm"
    :class="{ 'voice-panel-sticky': connected || connecting || disconnecting }">
    <div class="mb-2 flex items-center justify-between gap-2">
      <p class="truncate text-sm-medium text-ink-gray-8">{{ changing ? 'Change review with PERI' : 'Develop JHA with PERI' }}</p>
      <p v-if="step" class="max-w-[60%] truncate text-xs text-ink-gray-5">{{ step }}</p>
    </div>
    <div v-if="connected" ref="dock" class="voice-controls jha-voice-dock">
      <div class="flex min-w-0 flex-col items-center gap-1.5" role="status" :aria-label="`PERI: ${activity}`">
        <div class="peri-avatar" :class="{ 'peri-speaking': speaking, 'peri-thinking': busy && !speaking }">
          <img v-if="periBotImageUrl && !imageFailed" :src="periBotImageUrl" alt="PERI" class="h-full w-full rounded-full object-cover" @error="imageFailed = true" />
          <span v-else class="text-base-semibold" aria-hidden="true">P</span>
        </div>
        <div class="voice-bars" :data-speaking="speaking" aria-hidden="true">
          <span v-for="(bar, index) in bars" :key="index" :style="{ height: `${4 + (speaking ? level * bar * 22 : 0)}px` }" />
        </div>
        <p class="text-center text-xs text-ink-gray-6">{{ activity }}</p>
      </div>
      <button type="button" class="flex h-28 w-28 touch-none select-none flex-col items-center justify-center rounded-full border-2 shadow-sm transition active:scale-95"
        :class="talking ? 'border-red-500 bg-red-50 text-red-700' : 'border-outline-gray-3 bg-surface-gray-1 text-ink-gray-8'"
        :disabled="disconnecting" :aria-pressed="talking"
        :aria-label="talking ? 'Release to send voice to PERI' : 'Hold to talk to PERI'"
        @pointerdown="emit('talkStart', $event)" @pointerup="emit('talkStop', $event)"
        @pointercancel="emit('talkStop', $event)" @lostpointercapture="emit('talkStop', $event)" @contextmenu.prevent>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="h-8 w-8" aria-hidden="true">
          <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z" /><path d="M19 10v2a7 7 0 0 1-14 0v-2" /><path d="M12 19v3" /><path d="M8 22h8" />
        </svg>
        <span class="mt-2 text-sm-medium">{{ talking ? 'Release' : 'Hold to talk' }}</span>
      </button>
      <div class="flex min-w-0 flex-col items-center gap-2">
        <Button variant="subtle" theme="gray" size="sm" class="h-auto whitespace-normal py-2" :loading="disconnecting" :disabled="disconnecting" @click="emit('disconnect')">Disconnect Voice</Button>
        <span class="text-center text-xs text-ink-gray-5">{{ talking ? 'Mic on' : 'Mic muted' }}</span>
      </div>
    </div>
    <template v-else>
      <label class="flex cursor-pointer items-start gap-3 rounded-7 bg-surface-gray-1 p-3">
        <Checkbox size="md" :model-value="consent" :disabled="connecting" @update:model-value="emit('consent', Boolean($event))" />
        <span class="text-sm leading-5 text-ink-gray-7">Everyone present agrees to microphone use and transcription for this JHA discussion.</span>
      </label>
      <p class="mt-2 text-xs text-ink-gray-5">Raw audio is not stored by Verto. Crew audio is sent only while you hold the mic button.</p>
      <Button variant="solid" size="lg" class="mt-3 w-full justify-center" :loading="connecting" :disabled="!canConnect" @click="emit('connect')">Connect Voice with PERI</Button>
    </template>
    <p v-if="connected && latestSpeech" class="mt-2 line-clamp-2 border-t border-outline-gray-1 pt-2 text-sm leading-5 text-ink-gray-7" aria-live="off">{{ latestSpeech }}</p>
    <p class="sr-only">{{ status }}</p>
  </section>
</template>

<style scoped>
.voice-panel-sticky { position: sticky; top: 0; z-index: 30; }
.voice-controls { display: grid; grid-template-columns: minmax(0, 1fr) 7rem minmax(0, 1fr); align-items: center; gap: .5rem; }
.peri-avatar { width: 3.5rem; height: 3.5rem; border-radius: 50%; display: grid; place-items: center; color: #165ba6; background: #e8f3ff; box-shadow: 0 0 0 3px #dceaff; transition: box-shadow 150ms; }
.peri-speaking { box-shadow: 0 0 0 4px #86d9bd, 0 0 0 8px #d8f5e9; }
.peri-thinking { animation: peri-think 1.6s ease-in-out infinite; }
.voice-bars { display: flex; height: 26px; align-items: center; justify-content: center; gap: 3px; }
.voice-bars span { width: 3px; border-radius: 5px; background: #8c9bad; transition: height 70ms linear; }
.voice-bars[data-speaking="true"] span { background: #159371; }
@keyframes peri-think { 50% { opacity: .55; } }
@media (prefers-reduced-motion: reduce) { .peri-thinking { animation: none; } .voice-bars span { transition: none; } }
</style>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { Button } from 'frappe-ui'
import MobileSheet from './MobileSheet.vue'
import { drawPhotoMarks, exportAnnotatedPhoto, photoPoint, type PhotoMark } from '../lib/photoAnnotation'

const props = defineProps<{ file: File }>()
const emit = defineEmits<{ close: []; save: [file: File] }>()
const canvas = ref<HTMLCanvasElement>()
const image = new Image()
const marks = ref<PhotoMark[]>([])
const tool = ref<PhotoMark['tool']>('arrow')
const color = ref('#ffeb3b')
const note = ref('')
const ready = ref(false)
const saving = ref(false)
const error = ref('')
let active: PhotoMark | null = null
let pointer: number | null = null
let url = ''
let disposed = false

function render() {
  const element = canvas.value
  const ctx = element?.getContext('2d')
  if (!element || !ctx || !ready.value) return
  ctx.clearRect(0, 0, element.width, element.height)
  ctx.drawImage(image, 0, 0, element.width, element.height)
  drawPhotoMarks(ctx, active ? [...marks.value, active] : marks.value, element.width, element.height)
}

function start(event: PointerEvent) {
  if (!ready.value || saving.value || pointer !== null || marks.value.length >= 100 || (event.pointerType === 'mouse' && event.button !== 0)) return
  if (tool.value === 'note' && !note.value.trim()) { error.value = 'Enter a note, then tap the photo to place it.'; return }
  const element = canvas.value!
  error.value = ''
  const point = photoPoint(event.clientX, event.clientY, element.getBoundingClientRect())
  active = { tool: tool.value, start: point, end: point, color: color.value, text: note.value.trim() }
  pointer = event.pointerId
  element.setPointerCapture(event.pointerId)
  render()
}

function move(event: PointerEvent) {
  if (!active || pointer !== event.pointerId) return
  active.end = photoPoint(event.clientX, event.clientY, canvas.value!.getBoundingClientRect())
  render()
}

function finish(event: PointerEvent, cancelled = false) {
  if (pointer !== event.pointerId) return
  if (active && !cancelled) {
    move(event)
    const distance = Math.hypot(active.end.x - active.start.x, active.end.y - active.start.y)
    if (active.tool === 'note' || distance > 0.003) marks.value.push(active)
  }
  active = null
  pointer = null
  if (canvas.value?.hasPointerCapture(event.pointerId)) canvas.value.releasePointerCapture(event.pointerId)
  render()
}

function undo() { marks.value.pop(); render() }
function clear() { marks.value = []; render() }
async function save() {
  if (!ready.value || saving.value || !marks.value.length || pointer !== null) return
  saving.value = true
  error.value = ''
  try {
    const file = await exportAnnotatedPhoto(canvas.value!, props.file)
    if (!disposed) emit('save', file)
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Could not save the annotated photo.'
  } finally { saving.value = false }
}

onMounted(() => {
  image.onload = () => {
    if (disposed || !canvas.value) return
    const ratio = Math.min(1, 2560 / Math.max(image.naturalWidth, image.naturalHeight))
    canvas.value.width = Math.max(1, Math.round(image.naturalWidth * ratio))
    canvas.value.height = Math.max(1, Math.round(image.naturalHeight * ratio))
    if (!canvas.value.getContext('2d')) { error.value = 'Photo annotation is not supported by this browser.'; return }
    ready.value = true
    render()
  }
  image.onerror = () => { error.value = 'This photo cannot be opened for annotation. You can still attach the original. Try a JPEG or PNG copy.' }
  url = URL.createObjectURL(props.file)
  image.src = url
})
onBeforeUnmount(() => { disposed = true; image.onload = null; image.onerror = null; if (url) URL.revokeObjectURL(url) })
</script>

<template>
  <MobileSheet :open="true" title="Annotate photo" :dismissible="!saving" @update:open="!$event && !saving && emit('close')">
    <section class="drawer-panel flex max-h-[92dvh] flex-col bg-surface-base">
      <header class="space-y-2 border-b border-outline-gray-1 p-4">
        <div class="flex items-center justify-between gap-2">
          <h2 class="text-lg-semibold text-ink-gray-9">Annotate photo</h2>
          <Button type="button" variant="subtle" :disabled="saving" @click="emit('close')">Cancel</Button>
        </div>
        <p class="text-sm text-ink-gray-6">Drag to draw an arrow or circle. Add a note and tap to place it. The original photo is kept.</p>
      </header>
      <div class="min-h-0 flex-1 space-y-3 overflow-y-auto p-4">
        <div class="flex flex-wrap items-center gap-2" aria-label="Annotation tools">
          <Button v-for="choice in (['arrow', 'circle', 'note'] as const)" :key="choice" type="button" :variant="tool === choice ? 'solid' : 'subtle'" :aria-pressed="tool === choice" :disabled="saving" @click="tool = choice">{{ choice[0].toUpperCase() + choice.slice(1) }}</Button>
          <label class="text-sm text-ink-gray-7">Colour
            <select v-model="color" :disabled="saving" class="rounded border border-outline-gray-2 bg-surface-base p-2">
              <option value="#ffeb3b">Yellow</option><option value="#ff3030">Red</option><option value="#ffffff">White</option><option value="#4ade80">Green</option>
            </select>
          </label>
          <Button type="button" variant="subtle" :disabled="saving || !marks.length" @click="undo">Undo</Button>
          <Button type="button" variant="subtle" :disabled="saving || !marks.length" @click="clear">Clear marks</Button>
        </div>
        <label v-if="tool === 'note'" class="block text-sm text-ink-gray-7">Note
          <input v-model="note" maxlength="200" :disabled="saving" class="mt-1 block w-full rounded border border-outline-gray-2 bg-surface-base p-2 text-base" placeholder="Enter a note, then tap the photo" />
        </label>
        <p v-if="error" role="alert" class="text-sm text-red-700">{{ error }}</p>
        <p v-else-if="!ready" role="status" class="text-sm text-ink-gray-6">Opening photo…</p>
        <div class="flex justify-center rounded bg-gray-900 p-1">
          <canvas ref="canvas" class="block h-auto max-h-[54dvh] max-w-full touch-none select-none object-contain" aria-label="Photo annotation canvas" @pointerdown.prevent="start" @pointermove.prevent="move" @pointerup.prevent="finish($event)" @pointercancel="finish($event, true)" />
        </div>
        <p class="break-words text-xs text-ink-gray-5">{{ file.name }} · {{ marks.length }} marks</p>
      </div>
      <footer class="border-t border-outline-gray-1 p-4 pb-[calc(env(safe-area-inset-bottom)+1rem)]">
        <Button type="button" variant="solid" class="w-full" :loading="saving" :disabled="!ready || saving || !marks.length" @click="save">Add annotated copy</Button>
      </footer>
    </section>
  </MobileSheet>
</template>

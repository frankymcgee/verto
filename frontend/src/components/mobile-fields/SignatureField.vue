<template>
  <div class="space-y-2">
    <div class="flex items-start justify-between gap-3">
      <div class="min-w-0">
        <label class="block text-sm font-medium text-ink-gray-8">
          {{ label }}
          <span
            v-if="required"
            class="text-red-500"
          >*</span>
        </label>

        <p
          v-if="description"
          class="mt-1 text-sm text-ink-gray-5"
        >
          {{ description }}
        </p>
      </div>

      <Button
        v-if="!disabled"
        variant="subtle"
        theme="gray"
        size="sm"
        type="button"
        @click="clearSignature"
      >
        Clear
      </Button>
    </div>

    <div
      class="overflow-hidden rounded-xl border border-outline-gray-2 bg-surface-white"
      :class="disabled ? 'opacity-75' : ''"
    >
      <canvas
        ref="canvasEl"
        class="block h-40 w-full touch-none bg-white"
        :class="disabled ? 'cursor-not-allowed' : 'cursor-crosshair'"
        @pointerdown="startDrawing"
        @pointermove="draw"
        @pointerup="stopDrawing"
        @pointercancel="stopDrawing"
        @pointerleave="stopDrawing"
      />

      <div class="flex items-center justify-between border-t border-outline-gray-1 bg-surface-gray-1 px-3 py-2">
        <p class="text-xs text-ink-gray-5">
          {{ modelValue ? 'Signature captured' : 'Sign inside the box' }}
        </p>

        <p
          v-if="disabled"
          class="text-xs text-ink-gray-5"
        >
          Read only
        </p>
      </div>
    </div>

    <p
      v-if="required && !modelValue"
      class="text-xs text-ink-gray-5"
    >
      Signature is required.
    </p>
  </div>
</template>

<script setup lang="ts">
import {
  nextTick,
  onMounted,
  ref,
  watch,
} from 'vue'
import { Button } from 'frappe-ui'

const props = defineProps<{
  modelValue?: string | null
  label?: string
  description?: string
  required?: boolean
  disabled?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
  change: []
}>()

const canvasEl = ref<HTMLCanvasElement | null>(null)

let context: CanvasRenderingContext2D | null = null
let drawing = false
let lastX = 0
let lastY = 0
let hasDrawn = false
let resizeObserver: ResizeObserver | null = null

function getCanvasScale() {
  return window.devicePixelRatio || 1
}

function getCanvasPoint(event: PointerEvent) {
  const canvas = canvasEl.value

  if (!canvas) {
    return { x: 0, y: 0 }
  }

  const rect = canvas.getBoundingClientRect()
  const scaleX = canvas.width / rect.width
  const scaleY = canvas.height / rect.height

  return {
    x: (event.clientX - rect.left) * scaleX,
    y: (event.clientY - rect.top) * scaleY,
  }
}

function prepareContext() {
  const canvas = canvasEl.value

  if (!canvas) {
    return
  }

  context = canvas.getContext('2d')

  if (!context) {
    return
  }

  context.lineCap = 'round'
  context.lineJoin = 'round'
  context.strokeStyle = '#111827'
  context.lineWidth = 2.5 * getCanvasScale()
}

function resizeCanvas() {
  const canvas = canvasEl.value

  if (!canvas) {
    return
  }

  const existingValue = props.modelValue || ''
  const rect = canvas.getBoundingClientRect()
  const scale = getCanvasScale()

  canvas.width = Math.max(1, Math.floor(rect.width * scale))
  canvas.height = Math.max(1, Math.floor(rect.height * scale))

  prepareContext()

  if (existingValue) {
    drawImageFromValue(existingValue)
  }
}

function drawImageFromValue(value: string) {
  const canvas = canvasEl.value

  if (!canvas || !value) {
    return
  }

  const image = new Image()

  image.onload = () => {
    if (!context || !canvas) {
      return
    }

    context.clearRect(0, 0, canvas.width, canvas.height)
    context.drawImage(image, 0, 0, canvas.width, canvas.height)
    hasDrawn = true
  }

  image.src = value
}

function updateModelFromCanvas() {
  const canvas = canvasEl.value

  if (!canvas || !hasDrawn) {
    emit('update:modelValue', '')
    emit('change')
    return
  }

  emit('update:modelValue', canvas.toDataURL('image/png'))
  emit('change')
}

function startDrawing(event: PointerEvent) {
  if (props.disabled) {
    return
  }

  const canvas = canvasEl.value

  if (!canvas || !context) {
    return
  }

  canvas.setPointerCapture?.(event.pointerId)

  const point = getCanvasPoint(event)

  drawing = true
  hasDrawn = true
  lastX = point.x
  lastY = point.y

  context.beginPath()
  context.moveTo(lastX, lastY)
}

function draw(event: PointerEvent) {
  if (!drawing || props.disabled || !context) {
    return
  }

  const point = getCanvasPoint(event)

  context.lineTo(point.x, point.y)
  context.stroke()

  lastX = point.x
  lastY = point.y
}

function stopDrawing() {
  if (!drawing) {
    return
  }

  drawing = false
  context?.closePath()
  updateModelFromCanvas()
}

function clearSignature() {
  const canvas = canvasEl.value

  if (!canvas || !context) {
    return
  }

  context.clearRect(0, 0, canvas.width, canvas.height)
  hasDrawn = false

  emit('update:modelValue', '')
  emit('change')
}

onMounted(async () => {
  await nextTick()

  resizeCanvas()

  if (canvasEl.value) {
    resizeObserver = new ResizeObserver(() => {
      resizeCanvas()
    })

    resizeObserver.observe(canvasEl.value)
  }
})

watch(
  () => props.modelValue,
  (value) => {
    if (!value) {
      const canvas = canvasEl.value

      if (canvas && context) {
        context.clearRect(0, 0, canvas.width, canvas.height)
      }

      hasDrawn = false
      return
    }

    drawImageFromValue(value)
  }
)
</script>
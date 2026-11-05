<script setup lang="ts">
import { ref } from 'vue'
type Marker = { x: number; y: number; label: string }
const props = defineProps<{ src: string; markers: Marker[]; editable?: boolean }>()
const emit = defineEmits<{ 'update:markers': [value: Marker[]] }>()
const label = ref('')
function mark(event: MouseEvent) {
  if (!props.editable || !label.value.trim() || props.markers.length >= 20) return
  const bounds = (event.currentTarget as HTMLElement).getBoundingClientRect()
  if (!bounds.width || !bounds.height) return
  const x = Math.max(0, Math.min(1, (event.clientX - bounds.left) / bounds.width))
  const y = Math.max(0, Math.min(1, (event.clientY - bounds.top) / bounds.height))
  emit('update:markers', [...props.markers, { x, y, label: label.value.trim() }]); label.value = ''
}
</script>
<template>
  <div class="space-y-2">
    <label v-if="editable" class="block text-sm">Marker note<input v-model="label" maxlength="180" placeholder="Enter a note, then tap the photo" class="mt-1 w-full rounded-7 border p-2" /></label>
    <div class="relative inline-block max-w-full align-top" :class="editable && label ? 'cursor-crosshair' : ''" @click="mark">
      <img :src="src" loading="lazy" alt="Work step supporting photo" class="block max-h-96 max-w-full rounded-7" />
      <span v-for="(marker, index) in markers" :key="index" class="pointer-events-none absolute flex h-6 w-6 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full border-2 border-white bg-red-600 text-xs font-bold text-white shadow" :style="{ left: `${marker.x * 100}%`, top: `${marker.y * 100}%` }">{{ index + 1 }}</span>
    </div>
    <p v-if="editable" class="text-xs text-ink-gray-6">Add up to 20 markers. You can also attach notes below without placing a marker.</p>
    <ol v-if="markers.length" class="list-inside list-decimal space-y-1 text-sm"><li v-for="(marker, index) in markers" :key="index">{{ marker.label }} <button v-if="editable" type="button" class="ml-2 text-red-700 underline" :aria-label="`Remove marker ${index + 1}`" @click="emit('update:markers', markers.filter((_, i) => i !== index))">Remove</button></li></ol>
  </div>
</template>

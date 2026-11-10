<template>
  <Rating
    v-model="mood"
    class="mood-rating"
    :max="moods.length"
    :step="1"
    size="lg"
    :label="label"
    :description="description"
    :required="required"
    :disabled="disabled"
  >
    <template #icon="{ index, value, previewValue }">
      <span
        class="text-3xl leading-none transition-transform"
        :class="index === (previewValue ?? value) ? 'scale-110' : 'opacity-40'"
      >
        {{ moods[index - 1] }}
      </span>
    </template>
  </Rating>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Rating } from 'frappe-ui'

const props = defineProps<{
  modelValue?: number | string | null
  label?: string
  description?: string
  required?: boolean
  disabled?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: number]
}>()

const moods = ['😞', '🙁', '😐', '🙂', '😊']

// Frappe documents store ratings as fractions (0..1); Rating uses 0..max.
const mood = computed({
  get() {
    const fraction = Number(props.modelValue)
    return Number.isFinite(fraction)
      ? Math.round(Math.max(0, Math.min(1, fraction)) * moods.length)
      : 0
  },
  set(value: number) {
    if (!props.disabled) emit('update:modelValue', value / moods.length)
  },
})
</script>

<style scoped>
.mood-rating :deep([data-slot='star']) {
  width: 2.75rem;
  height: 2.75rem;
}
</style>

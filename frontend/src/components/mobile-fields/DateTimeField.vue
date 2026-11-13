<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { DatePicker, TimePicker } from 'frappe-ui'
import { useTimePickerTouch } from '../../lib/useTimePickerTouch'
import type { DateTimeFieldType } from '../../lib/dateTimeFields'

const props = defineProps<{
  modelValue?: string | null
  fieldtype: DateTimeFieldType
  label?: string
  description?: string
  required?: boolean
  disabled?: boolean
  max?: string
}>()

const emit = defineEmits<{ 'update:modelValue': [value: string] }>()

const value = computed(() => props.modelValue ?? '')
const combined = computed(() => props.fieldtype === 'Datetime')
const pendingDate = ref('')
const date = computed(() => value.value.slice(0, 10) || pendingDate.value)
const time = computed(() => combined.value ? value.value.slice(11, 16) : value.value.slice(0, 5))
const timeDisabled = computed(() => props.disabled || (combined.value && !date.value))
const datePickerOpen = ref(false)
const timePickerOpen = ref(false)
const { handleTimePickerBlur } = useTimePickerTouch(timePickerOpen)

watch(value, () => { pendingDate.value = '' })

function updateDate(next: string) {
  if (props.disabled) return
  if (combined.value && next && !time.value) {
    pendingDate.value = next
    return
  }
  pendingDate.value = ''
  // Keep the same local datetime format as the original form input.
  const updated = combined.value && next ? `${next}T${time.value}` : next
  if (updated !== value.value) emit('update:modelValue', updated)
}

function updateTime(next: string) {
  if (timeDisabled.value || next === time.value) return
  const updated = combined.value ? `${date.value}T${next}` : next
  if (updated !== value.value) emit('update:modelValue', updated)
}

function openRequiredPicker() {
  if (props.fieldtype === 'Time' || pendingDate.value) timePickerOpen.value = true
  else datePickerOpen.value = true
}

function clearDate() {
  datePickerOpen.value = false
  updateDate('')
}

function clearTime() {
  timePickerOpen.value = false
  updateTime('')
}
</script>

<template>
  <fieldset class="mobile-date-time-field min-w-0" :disabled="disabled">
    <legend v-if="combined && label" class="mb-1 text-sm-medium text-ink-gray-8">
      {{ label }}
    </legend>
    <div class="flex gap-2">
      <DatePicker
        v-if="fieldtype !== 'Time'"
        v-model:open="datePickerOpen"
        :model-value="date"
        :typeable="false"
        open-on-click
        size="lg"
        class="mobile-date-time-trigger min-w-0 flex-1"
        :label="combined ? 'Date' : label"
        :description="combined ? undefined : description"
        :required="required"
        :disabled="disabled"
        :max="max"
        @update:model-value="updateDate"
      >
        <template #suffix>
          <button
            v-if="!required && date && !disabled"
            type="button"
            class="pointer-events-auto me-1 flex size-6 items-center justify-center rounded hover:bg-surface-gray-3"
            :aria-label="`Clear ${label || 'date'}`"
            @mousedown.prevent
            @click="clearDate"
          >
            <span class="lucide-x size-4" aria-hidden="true" />
          </button>
          <span class="lucide-chevron-down size-4" aria-hidden="true" />
        </template>
      </DatePicker>
      <TimePicker
        v-if="fieldtype !== 'Date'"
        v-model:open="timePickerOpen"
        :model-value="time"
        :interval="15"
        :typeable="false"
        open-on-click
        size="lg"
        class="mobile-date-time-trigger min-w-0 flex-1"
        :label="combined ? 'Time' : label"
        :description="combined ? undefined : description"
        :required="required"
        :disabled="timeDisabled"
        @update:model-value="updateTime"
        @blur.capture="handleTimePickerBlur"
      >
        <template #suffix>
          <button
            v-if="!combined && !required && time && !disabled"
            type="button"
            class="pointer-events-auto me-1 flex size-6 items-center justify-center rounded hover:bg-surface-gray-3"
            :aria-label="`Clear ${label || 'time'}`"
            @mousedown.prevent
            @click="clearTime"
          >
            <span class="lucide-x size-4" aria-hidden="true" />
          </button>
          <span class="lucide-chevron-down size-4" aria-hidden="true" />
        </template>
      </TimePicker>
    </div>
    <!-- Read-only picker inputs are skipped by native form validation. -->
    <select
      v-if="required || pendingDate"
      :value="value ? 'selected' : ''"
      class="sr-only"
      required
      :disabled="disabled"
      tabindex="-1"
      aria-hidden="true"
      @invalid.prevent="openRequiredPicker"
    >
      <option value="" />
      <option value="selected" />
    </select>
    <p v-if="combined && description" class="mt-1 text-sm text-ink-gray-5">{{ description }}</p>
  </fieldset>
</template>

<style scoped>
.mobile-date-time-field :deep(.mobile-date-time-trigger input[readonly]:enabled) {
  cursor: pointer;
}

.mobile-date-time-field :deep(.mobile-date-time-trigger input[readonly] + div) {
  pointer-events: none;
}
</style>

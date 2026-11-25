<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { Button, Dialog } from 'frappe-ui'
import { DialogDescription } from 'reka-ui'

const open = ref(false)
const values = ref<Record<string, unknown>>({})
const action = ref('Submit')
let pending: ((confirmed: boolean) => void) | null = null
const hours = computed(() => {
  const duration = Number(values.value.duration)
  return (Number.isFinite(duration) ? duration / 3600 : 0).toFixed(2)
})
const details = computed(() => [
  ['Work date', values.value.date],
  ['Start time', values.value.start_time],
  ['End time', values.value.end_time],
  ['Shift', values.value.shift],
  ['Project', values.value.project || values.value.project_id],
].filter(([, value]) => value !== undefined && value !== null && value !== ''))

function finish(confirmed: boolean) {
  const resolve = pending
  pending = null
  open.value = false
  resolve?.(confirmed)
}
function confirm(snapshot: Record<string, unknown>, label = 'Submit'): Promise<boolean> {
  if (pending) return Promise.resolve(false)
  values.value = { ...snapshot }
  action.value = label
  open.value = true
  return new Promise(resolve => { pending = resolve })
}
watch(open, value => { if (!value) finish(false) }, { flush: 'sync' })
onBeforeUnmount(() => finish(false))
defineExpose({ confirm })
</script>

<template>
  <Dialog v-model:open="open" title="Check your shift hours" size="sm" :show-close-button="true">
    <DialogDescription class="text-sm text-ink-gray-6">Confirm the hours for this shift before saving your timesheet.</DialogDescription>
    <p class="my-5 text-center text-3xl-semibold text-ink-gray-9" data-timesheet-hours>{{ hours }} hours</p>
    <dl v-if="details.length" class="space-y-2 rounded-7 bg-surface-gray-1 p-3 text-sm">
      <div v-for="[label, value] in details" :key="String(label)" class="flex justify-between gap-4">
        <dt class="shrink-0 text-ink-gray-6">{{ label }}</dt>
        <dd class="min-w-0 break-words text-right text-ink-gray-9">{{ value }}</dd>
      </div>
    </dl>
    <template #actions>
      <div class="flex flex-wrap justify-end gap-2">
        <Button variant="subtle" @click="finish(false)">Review hours</Button>
        <Button variant="solid" @click="finish(true)">{{ action }} {{ hours }} hours</Button>
      </div>
    </template>
  </Dialog>
</template>

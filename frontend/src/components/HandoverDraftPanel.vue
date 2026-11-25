<script setup lang="ts">
import { toDeskUrl } from '../lib/deskRoute'
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { Button, Checkbox } from 'frappe-ui'
import DateTimeField from './mobile-fields/DateTimeField.vue'
import { apiRequest } from '../lib/api'
import { defaultHandoverPeriod, type HandoverDraft } from '../lib/handoverDraft'

const props = defineProps<{
  handoverDoctype: string; project: string; docname?: string; rowDate?: string; coverage?: string
  fieldLabels: Record<string, string>; disabled?: boolean
}>()
const emit = defineEmits<{ apply: [draft: HandoverDraft, replace: boolean]; busy: [busy: boolean] }>()
const start = ref('')
const end = ref('')
const preparing = ref(false)
const draft = ref<HandoverDraft | null>(null)
const replace = ref(false)
const error = ref('')
const notice = ref('')
const hasText = computed(() => draft.value && Object.values(draft.value.fields).some(value => value.trim()))
let request = 0
let alive = true

watch(() => props.rowDate, value => {
  if (!start.value && !end.value) {
    const period = defaultHandoverPeriod(value || '')
    start.value = period.start; end.value = period.end
  }
}, { immediate: true })
watch(() => [props.project, props.coverage, start.value, end.value], () => {
  request += 1; draft.value = null; notice.value = ''; replace.value = false
})
onBeforeUnmount(() => { alive = false; request += 1; emit('busy', false) })

async function prepare() {
  if (preparing.value || props.disabled || !props.project || !start.value || !end.value) return
  const current = ++request
  preparing.value = true; emit('busy', true)
  error.value = ''; notice.value = ''; draft.value = null
  try {
    const result = await apiRequest<{ message: HandoverDraft }>('/api/method/verto.api.mobile.handover_draft.prepare_handover_draft', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ handover_doctype: props.handoverDoctype, project: props.project, docname: props.docname || null,
        period_start: start.value.replace('T', ' '), period_end: end.value.replace('T', ' '), coverage: props.coverage || '' }),
    })
    if (alive && current === request) draft.value = result.message
  } catch (err) {
    if (alive && current === request) error.value = err instanceof Error ? err.message : 'Could not prepare the handover draft.'
  } finally { if (alive) { preparing.value = false; emit('busy', false) } }
}
function apply() {
  if (!draft.value || props.disabled || preparing.value) return
  emit('apply', draft.value, replace.value)
  notice.value = 'Review the row below, including the incident count and shift safety summary. Existing text is kept unless replacement was selected. Save the row when ready.'
}
</script>

<template>
  <section class="space-y-3 rounded border border-outline-gray-2 bg-surface-gray-1 p-3" aria-label="PERI handover draft">
    <h3 class="text-base-semibold text-ink-gray-9">Draft with PERI</h3>
    <p class="text-sm text-ink-gray-6">Prepare suggestions from accessible project records and previous actions. Review the text before saving your handover.</p>
    <p v-if="!project" class="text-sm text-ink-gray-6">Select the project on the handover first.</p>
    <div class="grid gap-3 sm:grid-cols-2">
      <DateTimeField v-model="start" fieldtype="Datetime" label="Records from" :disabled="disabled || preparing" />
      <DateTimeField v-model="end" fieldtype="Datetime" label="Records to" :disabled="disabled || preparing" />
    </div>
    <p class="text-xs text-ink-gray-5">Times use your site's timezone. Adjust the suggested 12-hour period to match the shift.</p>
    <Button type="button" variant="subtle" :loading="preparing" :disabled="disabled || preparing || !project || !start || !end" @click="prepare">Prepare handover draft</Button>
    <p v-if="error" role="alert" class="whitespace-pre-wrap text-sm text-red-700">{{ error }}</p>
    <p v-if="notice" role="status" class="text-sm text-ink-gray-7">{{ notice }}</p>
    <div v-if="draft" class="space-y-3">
      <p class="text-xs text-ink-gray-6">{{ draft.sources.length }} sources · {{ draft.scope.period_start }} to {{ draft.scope.period_end }} · {{ draft.scope.timezone }}</p>
      <details v-if="draft.warnings.length" class="rounded border border-outline-gray-2 p-2 text-sm text-ink-gray-7">
        <summary class="cursor-pointer">{{ draft.warnings.length }} notes about source coverage</summary>
        <ul class="mt-2 list-disc space-y-1 pl-5"><li v-for="warning in draft.warnings" :key="warning">{{ warning }}</li></ul>
      </details>
      <div v-for="(text, name) in draft.fields" :key="name">
        <template v-if="text.trim() && fieldLabels[name]">
          <h4 class="text-sm-semibold text-ink-gray-8">{{ fieldLabels[name] }}</h4>
          <p class="whitespace-pre-wrap break-words text-sm text-ink-gray-7">{{ text }}</p>
        </template>
      </div>
      <details v-if="draft.sources.length" class="text-sm text-ink-gray-7">
        <summary class="cursor-pointer">Source records</summary>
        <ul class="mt-2 space-y-2"><li v-for="source in draft.sources" :key="source.id">
          <a :href="toDeskUrl(source.url)" target="_blank" rel="noopener noreferrer" class="break-words text-blue-600">[{{ source.id }}] {{ source.doctype }} · {{ source.name }}</a>
          <p class="text-xs text-ink-gray-5">{{ source.recorded_at }} · {{ source.time_basis }}</p>
        </li></ul>
      </details>
      <template v-if="hasText">
        <Checkbox v-model="replace" label="Replace existing text in the suggested fields" :disabled="disabled || preparing" />
        <p class="text-xs text-ink-gray-5">Existing text is kept unless you choose to replace it.</p>
        <Button type="button" variant="solid" :disabled="disabled || preparing" @click="apply">Use draft in row</Button>
      </template>
    </div>
  </section>
</template>

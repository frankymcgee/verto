<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { Button } from 'frappe-ui'
import { apiRequest } from '../lib/api'
import JhaIncidentLearning from './JhaIncidentLearning.vue'

const props = defineProps<{ jha: Record<string, any>; online: boolean; busy?: boolean; voiceBriefing?: Record<string, any> | null }>()
const emit = defineEmits<{
  briefing: [state: Record<string, any> | null, selected: boolean]
  discuss: []; requestChange: []
}>()
const state = ref<Record<string, any> | null>(null)
const loading = ref(false)
const error = ref('')
let generation = 0
onBeforeUnmount(() => { generation += 1 })
const current = computed(() => props.jha.status === 'Signed' && !props.jha.replacement_jha)
const active = computed(() => state.value?.active_step)
const learning = computed(() => state.value?.incident_learning)
const incidents = computed(() => learning.value?.incidents || [])
watch(() => props.voiceBriefing, (value) => {
  if (value && value.jha === props.jha.name && Number(value.revision) === Number(props.jha.revision)) state.value = value
})
const controlPrompt = computed(() => {
  const hazard = active.value?.hazards?.find((row: any) => row.critical_control || row.existing_controls || row.additional_controls)
  const control = hazard?.critical_control || hazard?.existing_controls || hazard?.additional_controls
  return control ? `Is “${control}” in place and effective for this step today? Confirm the other recorded controls, owners and hold points with the crew too.`
    : 'Are the controls for this step in place and effective today? Check them with the crew, including critical-control owners and hold points.'
})

watch([() => props.jha.name, () => props.jha.status, () => props.jha.replacement_jha, () => props.online], async () => {
  const token = ++generation
  state.value = null; error.value = ''; emit('briefing', null, false)
  if (!current.value || !props.online) { loading.value = false; return }
  loading.value = true
  try {
    const data = await apiRequest<any>(`/api/method/verto.api.mobile.voice_jha_steps.get_jha_step_briefing?jha_name=${encodeURIComponent(props.jha.name)}`, { cache: 'no-store' })
    if (token !== generation) return
    state.value = data.message
    emit('briefing', state.value, false)
  } catch (err) { if (token === generation) error.value = err instanceof Error ? err.message : 'Could not check the current step.' }
  finally { if (token === generation) loading.value = false }
}, { immediate: true })

async function selectStep(event: Event) {
  const picker = event.target as HTMLSelectElement
  const step = picker.value
  // The displayed choice remains the saved selection if a request fails.
  picker.value = active.value?.step_row || ''
  if (!step || props.busy || loading.value || !props.online || !state.value?.can_select) return
  const token = ++generation
  loading.value = true; error.value = ''
  try {
    const body = new FormData()
    body.append('jha_name', props.jha.name); body.append('step_row', step)
    body.append('request_id', crypto.randomUUID())
    const data = await apiRequest<any>('/api/method/verto.api.mobile.voice_jha_steps.select_jha_active_step', { method: 'POST', body })
    if (token !== generation) return
    state.value = data.message
    picker.value = active.value?.step_row || ''
    emit('briefing', state.value, true)
  } catch (err) { if (token === generation) error.value = err instanceof Error ? err.message : 'Could not select this step.' }
  finally { if (token === generation) loading.value = false }
}
</script>

<template>
  <section v-if="current" class="rounded-7 border border-blue-200 bg-surface-base p-4 shadow-sm" data-testid="jha-active-step">
    <label for="jha-active-step" class="text-base-semibold text-ink-gray-9">Where are you up to?</label>
    <p class="mt-1 text-sm leading-5 text-ink-gray-6">Select your current step for PERI’s incident lessons and control check.</p>
    <select id="jha-active-step" aria-label="Active JHA step" class="mt-3 w-full rounded-4 border border-outline-gray-3 bg-surface-base p-3 text-sm text-ink-gray-9"
      :value="active?.step_row || ''" :disabled="!online || busy || loading || !state?.can_select" @change="selectStep">
      <option value="" disabled>Select the active step…</option>
      <option v-for="step in jha.work_steps || []" :key="step.name" :value="step.name">{{ step.sequence }}. {{ step.activity }}</option>
    </select>
    <p v-if="!online" role="status" class="mt-2 text-sm text-amber-800">Connect to check the current revision and incident evidence before selecting a step.</p>
    <p v-else-if="loading" role="status" class="mt-2 text-sm text-ink-gray-6">Checking step and incident lessons…</p>
    <p v-if="error" role="alert" class="mt-2 text-sm text-red-700">{{ error }}</p>
    <template v-if="active && online">
      <p class="mt-3 text-sm-medium text-blue-900">Active: {{ active.sequence }}. {{ active.activity }}</p>
      <p class="mt-1 text-xs text-ink-gray-5">Selected by {{ active.selected_by }} · {{ active.selected_at }}</p>
      <div class="mt-3 rounded-7 bg-amber-50 p-3" role="status" aria-live="polite">
        <p class="text-sm-medium text-amber-900">{{ incidents.length ? `${incidents.length} relevant incident lesson${incidents.length === 1 ? '' : 's'}` : learning?.status === 'unavailable' ? 'Incident evidence is unavailable' : 'No relevant incidents found in the accessible dataset' }}</p>
        <p v-if="!incidents.length" class="mt-1 text-sm text-amber-900">Continue assessing this step’s hazards and controls with the crew.</p>
        <p v-if="learning?.search_limited" class="mt-1 text-xs text-amber-800">This search considered a limited set of matching records.</p>
        <article v-for="incident in incidents" :key="incident.name" class="mt-2 text-sm leading-5 text-ink-gray-8">
          <a :href="incident.record_url" target="_blank" rel="noopener" class="font-medium text-blue-700 underline">{{ incident.source_reference }} · {{ incident.incident_date }}</a>
          <p class="mt-1 line-clamp-3">{{ incident.incident_summary }}</p>
        </article>
      </div>
      <details v-if="incidents.length" class="mt-2">
        <summary class="cursor-pointer py-2 text-sm text-blue-700">Investigation findings, actions and lessons</summary>
        <JhaIncidentLearning :searches="[learning]" />
      </details>
      <p class="mt-3 text-sm-medium leading-5 text-ink-gray-9">{{ controlPrompt }}</p>
      <details class="mt-2 rounded-7 bg-surface-gray-1 p-3">
        <summary class="cursor-pointer text-sm-medium text-ink-gray-8">This step’s recorded controls & hold point</summary>
        <article v-for="hazard in active.hazards" :key="hazard.name" class="mt-3 text-sm leading-5 text-ink-gray-7">
          <p class="font-medium">{{ hazard.hazard_or_energy_source }}</p>
          <p>{{ [hazard.existing_controls, hazard.additional_controls].filter(Boolean).join(' · ') || 'No controls recorded.' }}</p>
          <p v-if="hazard.critical_control">Critical control: {{ hazard.critical_control }} · Owner: {{ hazard.control_owner || 'Not recorded' }}</p>
        </article>
        <p v-for="control in active.critical_controls" :key="control.name" class="mt-2 text-sm text-amber-900">{{ control.control }} · Field verification: {{ control.status }}</p>
        <p class="mt-2 text-sm text-ink-gray-7">Hold / pause point: {{ active.hold_or_pause_point ? 'Recorded — check the signed JHA before continuing.' : 'None recorded.' }}</p>
      </details>
      <div class="mt-3 flex flex-wrap gap-2">
        <Button variant="subtle" :disabled="busy || loading || !state?.can_select" @click="emit('discuss')">Ask PERI about this step</Button>
        <Button variant="subtle" :disabled="busy || !state?.can_select" @click="emit('requestChange')">Review/change JHA</Button>
      </div>
    </template>
  </section>
</template>

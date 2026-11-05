<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { Button } from 'frappe-ui'
import { apiRequest } from '../lib/api'
const props = defineProps<{ jha: Record<string, any>; busy?: boolean }>()
const emit = defineEmits<{ updated: [] }>()
const state = ref<any>(null), error = ref(''), message = ref(''), saving = ref(false), mode = ref(''), online = ref(navigator.onLine)
const title = ref(''), selected = ref(''), differences = ref(''), confirmed = ref(false)
const deviations = ref(''), improvements = ref(''), followUp = ref(''), lesson = ref('')
const reviewing = ref<any>(null), decision = ref('Approved'), reviewNotes = ref(''), guidance = ref('')
let alive = true, generation = 0, requestId = crypto.randomUUID()
const chosen = computed(() => state.value?.templates.find((item: any) => item.name === selected.value))
async function load() {
  const version = ++generation, name = props.jha.name
  state.value = null
  if (!online.value) return
  try {
    const result = await apiRequest<any>(`/api/method/verto.api.mobile.voice_jha_learning.get_jha_job_learning?jha_name=${encodeURIComponent(name)}`, { cache: 'no-store' })
    if (alive && version === generation && name === props.jha.name) state.value = result.message
  } catch (err) { if (alive && version === generation) error.value = err instanceof Error ? err.message : 'Could not load job learning.' }
}
function start(value: string, item?: any) {
  mode.value = value; confirmed.value = false; error.value = ''; message.value = ''; requestId = crypto.randomUUID()
  title.value = props.jha.work_summary_title || ''; differences.value = ''; reviewing.value = item || null
  decision.value = item?.status === 'Approved' ? 'Retired' : 'Approved'; reviewNotes.value = ''; guidance.value = ''; deviations.value = ''; improvements.value = ''; followUp.value = ''; lesson.value = ''
}
async function submit() {
  if (!confirmed.value || saving.value || props.busy || !online.value) return
  const name = props.jha.name
  saving.value = true; error.value = ''; message.value = ''
  let method = '', fields: Record<string, string> = {}
  if (mode.value === 'template') { method = 'propose_jha_template'; fields = { title: title.value, request_id: requestId } }
  else if (mode.value === 'select') { method = 'select_jha_template'; fields = { template_name: selected.value, differences: differences.value, request_id: requestId } }
  else if (mode.value === 'closeout') { method = 'record_jha_closeout'; fields = { deviations: deviations.value, control_improvements: improvements.value, follow_up: followUp.value, lesson: lesson.value, request_id: requestId } }
  else if (mode.value === 'review-template') { method = 'review_jha_template'; fields = { template_name: reviewing.value.name, decision: decision.value, notes: reviewNotes.value } }
  else if (mode.value === 'review-closeout') { method = 'review_jha_closeout'; fields = { closeout_name: reviewing.value.name, decision: decision.value, notes: reviewNotes.value, future_guidance: guidance.value } }
  if (!method) { saving.value = false; return }
  try {
    const body = new FormData()
    Object.entries({ jha_name: name, confirmation: '1', ...fields }).forEach(([key, value]) => body.append(key, value))
    await apiRequest(`/api/method/verto.api.mobile.voice_jha_learning.${method}`, { method: 'POST', body })
    if (!alive || name !== props.jha.name) return
    message.value = mode.value === 'select' ? 'Template guidance selected. PERI will compare it with this job during the step discussion.' : 'Job-learning record saved.'
    mode.value = ''; await load(); emit('updated')
  } catch (err) { if (alive) error.value = err instanceof Error ? err.message : 'Could not save job learning.' }
  finally { saving.value = false }
}
function connectionChanged() { online.value = navigator.onLine; void load() }
watch(() => [props.jha.name, props.jha.status], () => { mode.value = ''; error.value = ''; message.value = ''; void load() }, { immediate: true })
onMounted(() => { window.addEventListener('online', connectionChanged); window.addEventListener('offline', connectionChanged) })
onBeforeUnmount(() => { alive = false; generation++; window.removeEventListener('online', connectionChanged); window.removeEventListener('offline', connectionChanged) })
</script>

<template>
  <details class="rounded-7 border border-outline-gray-1 bg-surface-base" data-testid="jha-job-learning">
    <summary class="cursor-pointer p-3 text-sm-medium">Job templates and closeout lessons</summary>
    <div class="space-y-3 px-3 pb-3">
      <p v-if="!online" class="text-sm text-amber-800">Connect to select templates or submit and review closeout lessons.</p>
      <p v-if="error" role="alert" class="text-sm text-red-700">{{ error }}</p><p v-if="message" role="status" class="text-sm text-blue-800">{{ message }}</p>
      <template v-if="state">
        <p class="text-xs text-ink-gray-6">Approved templates and reviewed lessons stay within this project. PERI checks their applicability with the crew. Each new JHA needs its own discussion, review and signatures.</p>
        <div class="flex flex-wrap gap-2"><Button v-if="state.can_select" size="sm" :disabled="busy || saving" @click="start('select')">Use Job Template</Button><Button v-if="state.can_propose" size="sm" :disabled="busy || saving" @click="start('template')">Propose Reusable Template</Button><Button v-if="state.can_closeout" size="sm" :disabled="busy || saving" @click="start('closeout')">Record Job Closeout</Button><Button size="sm" :disabled="saving" @click="load">Refresh Learning</Button></div>
        <p v-if="state.template_use" class="rounded-7 bg-blue-50 p-3 text-sm">Selected guidance: {{ state.template_use.job_template }} · Differences to discuss: {{ state.template_use.details }}</p>
        <form v-if="mode" class="space-y-3 rounded-7 border p-3" @submit.prevent="submit">
          <label v-if="mode === 'template'" class="block text-sm">Template name<input v-model="title" required maxlength="140" class="mt-1 block w-full rounded-7 border p-2" /></label>
          <template v-if="mode === 'select'">
            <label class="block text-sm">Approved template<select v-model="selected" required class="mt-1 block w-full rounded-7 border p-2"><option value="">Select a template</option><option v-for="item in state.templates.filter((row: any) => row.status === 'Approved')" :key="item.name" :value="item.name">{{ item.title }} · {{ item.name }}</option></select></label>
            <div v-if="chosen" class="space-y-2 rounded-7 bg-surface-gray-1 p-3 text-sm"><p v-for="step in chosen.content.steps" :key="step.sequence">{{ step.sequence }}. {{ step.activity }}</p><p v-for="(hazard, index) in chosen.content.hazards" :key="index">Step {{ hazard.work_step_sequence }} · {{ hazard.hazard_or_energy_source }} · {{ [hazard.existing_controls, hazard.additional_controls].filter(Boolean).join(' · ') }}</p></div>
            <label class="block text-sm">What differs on this job?<textarea v-model="differences" required maxlength="4000" rows="3" placeholder="Scope, equipment, area, crew or conditions. Record what PERI needs to check, even if no differences are known yet." class="mt-1 block w-full rounded-7 border p-2" /></label>
            <p class="text-xs text-ink-gray-6">The template provides interview guidance. PERI records only steps and controls confirmed for this job.</p>
          </template>
          <template v-if="mode === 'closeout'">
            <label class="block text-sm">Did the work differ from the JHA?<textarea v-model="deviations" required maxlength="4000" rows="3" placeholder="Describe deviations, or record none observed." class="mt-1 block w-full rounded-7 border p-2" /></label>
            <label class="block text-sm">Which controls worked, or need improvement?<textarea v-model="improvements" required maxlength="4000" rows="3" class="mt-1 block w-full rounded-7 border p-2" /></label>
            <label class="block text-sm">What follow-up remains, and who needs to act?<textarea v-model="followUp" required maxlength="4000" rows="3" placeholder="Actions and owners, or no follow-up identified." class="mt-1 block w-full rounded-7 border p-2" /></label>
            <label class="block text-sm">Proposed lesson for future jobs<textarea v-model="lesson" maxlength="4000" rows="3" class="mt-1 block w-full rounded-7 border p-2" /></label>
            <p class="text-xs text-ink-gray-6">Closeout records observations. Follow-up actions remain open under your site's process. A human reviewer decides which lessons can guide future jobs.</p>
          </template>
          <template v-if="mode.startsWith('review-')">
            <p class="text-sm-medium">Review {{ reviewing.name }}</p><label class="block text-sm">Decision<select v-model="decision" class="mt-1 block w-full rounded-7 border p-2"><template v-if="reviewing.status === 'Approved'"><option>Retired</option></template><template v-else><option>Approved</option><option>Rejected</option></template></select></label>
            <label class="block text-sm">Review notes<textarea v-model="reviewNotes" required maxlength="4000" rows="3" class="mt-1 block w-full rounded-7 border p-2" /></label>
            <label v-if="mode === 'review-closeout' && decision === 'Approved'" class="block text-sm">Reviewed guidance for future jobs (optional)<textarea v-model="guidance" maxlength="2000" rows="3" placeholder="Only this reviewed text will be shared with PERI on relevant future jobs in this project. Omit personal information." class="mt-1 block w-full rounded-7 border p-2" /></label>
          </template>
          <label class="flex items-start gap-2 text-sm"><input v-model="confirmed" type="checkbox" required class="mt-1" />{{ mode.startsWith('review-') ? 'I have reviewed this record and confirm my decision.' : 'I have checked the information and confirm this record.' }}</label>
          <div class="flex gap-2"><Button type="submit" variant="solid" :loading="saving" :disabled="!confirmed || saving || busy">{{ mode.startsWith('review-') ? 'Confirm Review' : 'Save' }}</Button><Button :disabled="saving" @click="mode = ''">Cancel</Button></div>
        </form>
        <details v-if="state.templates.length" class="rounded-7 border p-3 text-sm"><summary class="cursor-pointer font-medium">Project templates · {{ state.templates.length }}</summary><article v-for="item in state.templates" :key="item.name" class="mt-3 space-y-1"><p class="font-medium">{{ item.title }} · {{ item.status }}</p><p>{{ item.name }} · Source {{ item.jha }} revision {{ item.revision }}</p><details><summary class="cursor-pointer">View proposed steps and controls</summary><p v-for="step in item.content.steps" :key="step.sequence">{{ step.sequence }}. {{ step.activity }}</p><p v-for="(hazard, i) in item.content.hazards" :key="i">Step {{ hazard.work_step_sequence }} · {{ hazard.hazard_or_energy_source }} · {{ hazard.existing_controls }} · {{ hazard.additional_controls }}</p></details><p v-if="item.reviewed_by">{{ item.reviewed_by }} · {{ item.reviewed_at }} · {{ item.review_notes }}</p><Button v-if="state.can_review && item.jha === jha.name && item.status === 'Pending Review'" size="sm" :disabled="busy || saving" @click="start('review-template', item)">Review Template</Button><Button v-if="state.can_review && item.jha === jha.name && item.status === 'Approved'" size="sm" :disabled="busy || saving" @click="start('review-template', item)">Retire Template</Button></article></details>
        <details v-if="state.closeouts.length" class="rounded-7 border p-3 text-sm"><summary class="cursor-pointer font-medium">Closeout records · {{ state.closeouts.length }}</summary><article v-for="item in state.closeouts" :key="item.name" class="mt-3 space-y-1"><p class="font-medium">{{ item.name }} · {{ item.status }}</p><p>Deviations: {{ item.deviations }}</p><p>Controls: {{ item.control_improvements }}</p><p>Follow-up: {{ item.follow_up }}</p><p>Proposed lesson: {{ item.lesson }}</p><p>{{ item.recorded_by }} · {{ item.recorded_at }}</p><p v-if="item.reviewed_by">Review: {{ item.reviewed_by }} · {{ item.reviewed_at }} · {{ item.review_notes }}</p><p v-if="item.future_guidance" class="text-blue-800">Reviewed guidance: {{ item.future_guidance }}</p><Button v-if="state.can_review && item.status === 'Pending Review'" size="sm" :disabled="busy || saving" @click="start('review-closeout', item)">Review Closeout</Button></article></details>
        <details v-if="state.lessons.length" class="rounded-7 border p-3 text-sm"><summary class="cursor-pointer font-medium">Reviewed lessons relevant to this job</summary><p v-for="item in state.lessons" :key="item.name" class="mt-2">{{ item.name }} · {{ item.future_guidance }} · Reviewed {{ item.reviewed_at }}</p></details>
      </template>
    </div>
  </details>
</template>

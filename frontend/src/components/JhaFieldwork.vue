<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { Button } from 'frappe-ui'
import { apiRequest } from '../lib/api'

const props = defineProps<{ jha: Record<string, any>; voiceReview?: Record<string, any> | null; busy?: boolean }>()
const emit = defineEmits<{
  startReview: [value: { shift_date: string; shift: string; existing?: Record<string, any> }]
  reviewUpdated: [value: Record<string, any>]
  reviewChanges: [value: Record<string, any>]
}>()
const state = ref<any>(null), error = ref(''), saving = ref(''), loading = ref(false)
const selected = ref(''), ccv = ref(''), result = ref('Verified'), notes = ref(''), evidence = ref(''), confirmed = ref(false)
const shiftDate = ref(''), shift = ref('Day')
let generation = 0, alive = true, requestId = ''
const visible = computed(() => ['Ready for Team Review', 'Signed', 'Review Required - Work Changed', 'Superseded'].includes(props.jha.status))
const controls = computed<any[]>(() => state.value?.controls || [])
const unresolved = computed(() => controls.value.filter(row => row.status !== 'Verified').length)
const failed = computed(() => controls.value.some(row => ['Failed', 'Recheck Required'].includes(row.status)))
const reviews = computed<any[]>(() => {
  const saved = state.value?.shift_reviews || []
  return props.voiceReview?.jha === props.jha.name
    ? [props.voiceReview, ...saved.filter((row: any) => row.name !== props.voiceReview?.name)] : saved
})
const categories: Record<string, string> = { crew: 'Crew and roles', equipment: 'Equipment and isolations', environment: 'Environment and nearby work', method: 'Scope and work method', controls: 'Hazards, controls and hold points' }

async function load() {
  const name = props.jha.name, version = ++generation
  if (!visible.value || !name) { state.value = null; return }
  loading.value = true; error.value = ''
  try {
    const data = await apiRequest<any>(`/api/method/verto.api.mobile.voice_jha_fieldwork.get_jha_fieldwork?jha_name=${encodeURIComponent(name)}`, { cache: 'no-store' })
    if (!alive || version !== generation || name !== props.jha.name) return
    state.value = data.message
    shiftDate.value ||= data.message.today
  } catch (err) { if (alive && version === generation) { state.value = null; error.value = err instanceof Error ? err.message : 'Could not check JHA field records.' } }
  finally { if (version === generation) loading.value = false }
}

function editControl(name: string) {
  selected.value = name; ccv.value = ''; result.value = 'Verified'; notes.value = ''; evidence.value = ''; confirmed.value = false
  requestId = crypto.randomUUID()
}

async function upload(event: Event) {
  const input = event.target as HTMLInputElement, file = input.files?.[0]
  if (!file) return
  const name = props.jha.name, version = generation
  saving.value = 'upload'; error.value = ''
  try {
    const body = new FormData()
    body.append('file', file, file.name); body.append('file_name', file.name)
    body.append('doctype', 'Digital Job Hazard Analysis'); body.append('docname', name); body.append('is_private', '1')
    const data = await apiRequest<any>('/api/method/upload_file', { method: 'POST', body })
    if (alive && version === generation && name === props.jha.name) evidence.value = data.message.file_url
  } catch (err) { if (alive && name === props.jha.name) error.value = err instanceof Error ? err.message : 'Evidence upload failed.' }
  finally { saving.value = ''; input.value = '' }
}

async function saveControl() {
  if (!confirmed.value || saving.value) return
  const name = props.jha.name, version = generation
  saving.value = selected.value; error.value = ''
  try {
    const body = new FormData()
    Object.entries({ jha_name: name, hazard_row: selected.value, result: result.value, ccv: ccv.value, notes: notes.value,
      evidence: evidence.value, confirmation: '1', request_id: requestId }).forEach(([key, value]) => body.append(key, value))
    await apiRequest('/api/method/verto.api.mobile.voice_jha_fieldwork.record_jha_control_verification', { method: 'POST', body })
    if (!alive || version !== generation || name !== props.jha.name) return
    selected.value = ''; await load()
  } catch (err) { if (alive && name === props.jha.name) error.value = err instanceof Error ? err.message : 'Could not record verification.' }
  finally { saving.value = '' }
}

async function confirmReview(review: any) {
  const name = props.jha.name
  saving.value = review.name; error.value = ''
  try {
    const body = new FormData()
    body.append('jha_name', name); body.append('shift_review', review.name); body.append('confirmation', '1')
    const data = await apiRequest<any>('/api/method/verto.api.mobile.voice_jha_revalidation.confirm_jha_shift_review', { method: 'POST', body })
    if (!alive || name !== props.jha.name) return
    emit('reviewUpdated', data.message); await load()
  } catch (err) { if (alive && name === props.jha.name) error.value = err instanceof Error ? err.message : 'Could not confirm shift review.' }
  finally { saving.value = '' }
}

watch(() => [props.jha.name, props.jha.status], () => {
  state.value = null; selected.value = ''; shiftDate.value = ''; void load()
}, { immediate: true })
onBeforeUnmount(() => { alive = false; generation++ })
</script>

<template>
  <section v-if="visible" class="space-y-3" data-testid="jha-fieldwork">
    <div class="flex items-center justify-between gap-3 text-sm">
      <a :href="`/verto-mobile/jha/${encodeURIComponent(jha.name)}?revision=${jha.revision || 1}`" class="font-medium text-blue-700 underline">Check revision status</a>
      <Button size="sm" variant="subtle" :loading="loading" :disabled="Boolean(saving)" @click="load">Refresh field checks</Button>
    </div>
    <p v-if="error" role="alert" class="rounded-7 bg-red-50 p-3 text-sm text-red-800">{{ error }}</p>
    <p v-if="failed" role="alert" class="rounded-7 border border-red-200 bg-red-50 p-3 text-sm text-red-800">A critical control has failed or its CCV evidence has changed. Hold affected work and follow the site's escalation and reassessment process.</p>
    <details v-if="state" class="rounded-7 border border-outline-gray-1 bg-surface-base">
      <summary class="cursor-pointer p-3 text-sm-medium">Critical-control checks · {{ unresolved }} outstanding / {{ controls.length }}</summary>
      <div class="space-y-3 px-3 pb-3">
        <p class="text-xs text-ink-gray-6">Checks apply to revision {{ jha.revision || 1 }}. Pending, failed or changed CCV evidence needs attention. These records do not release site permits or authorise work.</p>
        <a v-if="state.ccv_create_path && state.can_verify" :href="state.ccv_create_path" target="_blank" rel="noopener" class="block text-sm text-blue-700 underline">Complete a CCV for this job</a>
        <p v-if="!controls.length" class="text-sm text-ink-gray-6">No critical controls are recorded on this revision.</p>
        <article v-for="control in controls" :key="control.name" class="rounded-7 border border-outline-gray-2 p-3">
          <p class="text-sm-medium">Step {{ control.step }} · {{ control.control }}</p>
          <p class="mt-1 text-xs text-ink-gray-6">Owner: {{ control.owner || 'Not recorded' }} · {{ control.status }}</p>
          <p v-if="control.latest" class="mt-1 text-xs text-ink-gray-6">{{ control.latest.verifier_name }} · {{ control.latest.verified_at }}<span v-if="control.latest.ccv"> · {{ control.latest.ccv }}</span></p>
          <p v-if="control.latest?.notes" class="mt-1 text-sm">{{ control.latest.notes }}</p>
          <a v-if="control.latest?.evidence" :href="control.latest.evidence" target="_blank" rel="noopener" class="mt-1 block text-sm text-blue-700 underline">View supporting evidence</a>
          <Button v-if="state.can_verify && selected !== control.name" class="mt-2" size="sm" :disabled="busy || Boolean(saving)" @click="editControl(control.name)">Record field check</Button>
          <form v-if="selected === control.name" class="mt-3 space-y-3" @submit.prevent="saveControl">
            <label class="block text-sm">Check result<select v-model="result" class="mt-1 block w-full rounded-7 border p-2"><option>Verified</option><option>Failed</option></select></label>
            <label class="block text-sm">Supporting CCV<select v-model="ccv" :required="result === 'Verified'" class="mt-1 block w-full rounded-7 border p-2"><option value="">Select a CCV</option><option v-for="option in state.ccv_options" :key="option.name" :value="option.name">{{ option.ccv_selected }} · {{ option.name }} · {{ option.safety_category }}</option></select></label>
            <p class="text-xs text-ink-gray-6">Verified needs a completed, signed CCV for this job with Good Controls. A failed check can be recorded immediately without a CCV.</p>
            <label class="block text-sm">Observations / required action<textarea v-model="notes" :required="result === 'Failed'" maxlength="4000" rows="3" class="mt-1 block w-full rounded-7 border p-2" /></label>
            <label class="block text-sm">Supporting photo or file<input type="file" :disabled="Boolean(saving)" class="mt-1 block w-full text-sm" @change="upload" /></label>
            <p v-if="evidence" class="text-xs text-ink-gray-6">Evidence uploaded.</p>
            <label class="flex items-start gap-2 text-sm"><input v-model="confirmed" type="checkbox" class="mt-1" />I performed this on-site check and confirm the recorded result.</label>
            <div class="flex gap-2"><Button type="submit" variant="solid" :loading="Boolean(saving)" :disabled="!confirmed || Boolean(saving)">Save field check</Button><Button :disabled="Boolean(saving)" @click="selected = ''">Cancel</Button></div>
          </form>
          <details v-if="control.history.length > 1" class="mt-2 text-xs text-ink-gray-6"><summary class="cursor-pointer">Earlier checks</summary><p v-for="item in control.history.slice(1)" :key="item.name" class="mt-1">{{ item.result }} · {{ item.verifier_name }} · {{ item.verified_at }} · {{ item.notes }}</p></details>
        </article>
      </div>
    </details>
    <details v-if="state && (state.can_revalidate || reviews.length)" class="rounded-7 border border-outline-gray-1 bg-surface-base">
      <summary class="cursor-pointer p-3 text-sm-medium">Start-of-shift review<span v-if="reviews[0]"> · {{ reviews[0].shift_date }} {{ reviews[0].shift }} · {{ reviews[0].status }}</span></summary>
      <div class="space-y-3 px-3 pb-3">
        <p class="text-xs text-ink-gray-6">PERI checks changes to crew, equipment, environment, method and controls. A person confirms the final review. This does not renew permits or authorise work.</p>
        <form v-if="state.can_revalidate" class="space-y-3" @submit.prevent="emit('startReview', { shift_date: shiftDate, shift })">
          <div class="grid grid-cols-2 gap-2"><label class="text-sm">Shift start date<input v-model="shiftDate" type="date" required :max="state.today" class="mt-1 block w-full rounded-7 border p-2" /></label><label class="text-sm">Shift<select v-model="shift" class="mt-1 block w-full rounded-7 border p-2"><option>Day</option><option>Night</option></select></label></div>
          <Button type="submit" variant="solid" :disabled="busy || Boolean(saving)">Review Shift with PERI</Button>
        </form>
        <article v-for="review in reviews" :key="review.name" class="rounded-7 bg-surface-gray-1 p-3">
          <p class="text-sm-medium">{{ review.shift_date }} · {{ review.shift }} · {{ review.status === 'No Change' ? 'Unchanged conditions recorded' : review.status }}</p>
          <p v-for="(check, category) in review.checks" :key="category" class="mt-1 text-xs text-ink-gray-6">{{ categories[category] }}: {{ check.changed ? 'Changed' : 'Unchanged' }}<span v-if="check.notes"> · {{ check.notes }}</span></p>
          <p v-if="review.confirmed_by" class="mt-2 text-xs text-ink-gray-6">Confirmed by {{ review.confirmed_by }} · {{ review.confirmed_at }}</p>
          <Button v-if="review.status === 'In Progress' && state.can_revalidate" class="mt-2" :disabled="busy" @click="emit('startReview', { shift_date: review.shift_date, shift: review.shift, existing: review })">Resume Shift with PERI</Button>
          <Button v-if="review.status === 'Awaiting Confirmation' && state.can_revalidate" class="mt-2" variant="solid" :loading="saving === review.name" :disabled="busy || Boolean(saving)" @click="confirmReview(review)">Confirm No Changes</Button>
          <Button v-if="review.status === 'Change Required' && !review.replacement_jha" class="mt-2" variant="solid" :disabled="busy || Boolean(saving)" @click="emit('reviewChanges', review)">Review Changes with PERI</Button>
          <p v-if="review.replacement_jha" class="mt-2 text-xs text-ink-gray-6">Change review: {{ review.replacement_jha }}</p>
        </article>
      </div>
    </details>
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { Button } from 'frappe-ui'
import { apiRequest } from '../lib/api'
import JhaPhotoMarkers from './JhaPhotoMarkers.vue'

const props = defineProps<{ jha: Record<string, any>; busy?: boolean }>()
const emit = defineEmits<{ updated: [value: Record<string, any>]; requestChange: [] }>()
const state = ref<any>(null), error = ref(''), saving = ref(false), online = ref(navigator.onLine), editing = ref(false)
const step = ref(''), kind = ref('Permit'), reference = ref(''), details = ref(''), evidence = ref(''), permit = ref('')
const expiry = ref(''), status = ref('Pending'), confirmed = ref(false), changed = ref(false), replacing = ref(''), markers = ref<any[]>([])
let alive = true, generation = 0, requestId = crypto.randomUUID()
const items = computed<any[]>(() => (state.value?.items || []).filter((row: any) => ['Permit', 'Isolation', 'Document', 'Photo'].includes(row.kind)))
const outstanding = computed(() => items.value.filter(row => !row.historical && row.status !== 'Withdrawn' && row.kind !== 'Photo' && row.effective_status !== 'Confirmed').length)
const observations = computed<any[]>(() => (state.value?.items || []).filter((row: any) => row.kind === 'Observation'))
async function load() {
  const version = ++generation, name = props.jha.name
  state.value = null
  if (!online.value) return
  try {
    const result = await apiRequest<any>(`/api/method/verto.api.mobile.voice_jha_workpack.get_jha_resources?jha_name=${encodeURIComponent(name)}`, { cache: 'no-store' })
    if (alive && version === generation && props.jha.name === name) state.value = result.message
  } catch (err) { if (alive && version === generation) error.value = err instanceof Error ? err.message : 'Could not load supporting records.' }
}
function start(row?: any) {
  step.value = row?.step_row || props.jha.work_steps?.[0]?.name || ''; kind.value = row?.kind || 'Permit'
  reference.value = row?.reference || ''; details.value = ''; evidence.value = ''; permit.value = row?.ehs_permit || ''
  expiry.value = ''; status.value = row?.kind === 'Photo' ? 'Confirmed' : 'Pending'; confirmed.value = false
  changed.value = false; replacing.value = row?.name || ''; markers.value = []; requestId = crypto.randomUUID(); editing.value = true; error.value = ''
}
async function upload(event: Event) {
  const input = event.target as HTMLInputElement, file = input.files?.[0]
  if (!file) return
  if (file.size > 10 * 1024 * 1024) { error.value = 'Use a file up to 10 MB.'; input.value = ''; return }
  const name = props.jha.name, version = generation
  saving.value = true; error.value = ''
  try {
    const body = new FormData()
    body.append('file', file, file.name); body.append('file_name', file.name); body.append('is_private', '1')
    body.append('doctype', 'Digital Job Hazard Analysis'); body.append('docname', name)
    const result = await apiRequest<any>('/api/method/upload_file', { method: 'POST', body })
    if (alive && version === generation && props.jha.name === name) { evidence.value = result.message.file_url; markers.value = [] }
  } catch (err) { if (alive) error.value = err instanceof Error ? err.message : 'Upload failed.' }
  finally { saving.value = false; input.value = '' }
}
async function save() {
  if (!confirmed.value || saving.value || !online.value) return
  saving.value = true; error.value = ''
  const name = props.jha.name
  try {
    const body = new FormData()
    Object.entries({ jha_name: name, step_row: step.value, kind: kind.value, request_id: requestId,
      reference: reference.value, details: details.value, evidence: evidence.value, annotations: JSON.stringify(markers.value),
      expires_at: expiry.value.replace('T', ' '), status: kind.value === 'Photo' ? 'Confirmed' : status.value,
      ehs_permit: kind.value === 'Permit' ? permit.value : '', replaces: replacing.value,
      confirmation: '1', work_changed: changed.value ? '1' : '0' }).forEach(([key, value]) => body.append(key, value))
    const result = await apiRequest<any>('/api/method/verto.api.mobile.voice_jha_workpack.record_jha_resource', { method: 'POST', body })
    if (!alive || name !== props.jha.name) return
    editing.value = false; emit('updated', { name, status: result.message.jha_status }); await load()
  } catch (err) { if (alive) error.value = err instanceof Error ? err.message : 'Could not save supporting record.' }
  finally { saving.value = false }
}
function connectionChanged() { online.value = navigator.onLine; void load() }
watch(() => [props.jha.name, props.jha.status], () => { editing.value = false; error.value = ''; void load() }, { immediate: true })
onMounted(() => { window.addEventListener('online', connectionChanged); window.addEventListener('offline', connectionChanged) })
onBeforeUnmount(() => { alive = false; generation++; window.removeEventListener('online', connectionChanged); window.removeEventListener('offline', connectionChanged) })
</script>
<template>
  <details class="rounded-7 border border-outline-gray-1 bg-surface-base" data-testid="jha-step-resources">
    <summary class="cursor-pointer p-3 text-sm-medium">Permits, isolations and step photos<span v-if="state"> · {{ outstanding }} confirmations outstanding</span></summary>
    <div class="space-y-3 px-3 pb-3">
      <p class="text-xs text-ink-gray-6">Supporting records apply to revision {{ jha.revision || 1 }}. Confirming a reference records your check; site permits and work authorisation remain separate.</p>
      <p v-if="!online" class="text-sm text-amber-800">Connect to check live supporting records, or open your downloaded copy below.</p>
      <p v-if="error" role="alert" class="text-sm text-red-700">{{ error }}</p>
      <div class="flex flex-wrap gap-2"><Button v-if="state?.can_record" size="sm" :disabled="busy || saving" @click="start()">Add Supporting Record</Button><Button v-if="online" size="sm" :disabled="saving" @click="load">Refresh Records</Button></div>
      <form v-if="editing && state?.can_record" class="space-y-3 rounded-7 border p-3" @submit.prevent="save">
        <p v-if="replacing" class="text-sm text-amber-900">This retains the original record. Changing a permit or isolation reference, file or expiry, or withdrawing it, triggers JHA change review.</p>
        <label class="block text-sm">Work step<select v-model="step" required :disabled="Boolean(replacing)" class="mt-1 block w-full rounded-7 border p-2"><option v-for="item in jha.work_steps" :key="item.name" :value="item.name">{{ item.sequence }}. {{ item.activity }}</option></select></label>
        <label class="block text-sm">Record type<select v-model="kind" :disabled="Boolean(replacing)" class="mt-1 block w-full rounded-7 border p-2" @change="evidence = ''; markers = []; status = kind === 'Photo' ? 'Confirmed' : 'Pending'"><option>Permit</option><option>Isolation</option><option>Document</option><option>Photo</option></select></label>
        <label v-if="kind !== 'Photo'" class="block text-sm">{{ kind === 'Isolation' ? 'Isolation record number' : kind === 'Permit' ? 'Permit number' : 'Document reference' }}<input v-model="reference" :required="['Permit', 'Isolation'].includes(kind) && !permit" maxlength="140" class="mt-1 block w-full rounded-7 border p-2" /></label>
        <label v-if="kind === 'Permit'" class="block text-sm">Existing EHS Permit (optional)<input v-model="permit" maxlength="140" placeholder="PRM-00001" class="mt-1 block w-full rounded-7 border p-2" /></label>
        <label class="block text-sm">{{ kind === 'Photo' ? 'Photo description / what this shows' : 'Scope, confirmation needed or change reason' }}<textarea v-model="details" required maxlength="4000" rows="3" class="mt-1 block w-full rounded-7 border p-2" /></label>
        <template v-if="kind !== 'Photo'"><label class="block text-sm">Expiry (site date and time)<input v-model="expiry" type="datetime-local" class="mt-1 block w-full rounded-7 border p-2" /></label><label class="block text-sm">Confirmation state<select v-model="status" class="mt-1 block w-full rounded-7 border p-2"><option>Pending</option><option>Confirmed</option><option v-if="replacing">Withdrawn</option></select></label></template>
        <label class="block text-sm">{{ kind === 'Photo' ? 'Capture or select a photo' : 'Supporting document (optional for permits and isolations)' }}<input type="file" :accept="kind === 'Photo' ? 'image/jpeg,image/png,image/webp' : undefined" :disabled="saving" class="mt-1 block w-full text-sm" @change="upload" /></label>
        <JhaPhotoMarkers v-if="kind === 'Photo' && evidence" :src="evidence" v-model:markers="markers" editable />
        <a v-else-if="evidence" :href="evidence" target="_blank" rel="noopener" class="block text-sm text-blue-700 underline">View uploaded file</a>
        <label class="flex items-start gap-2 text-sm"><input v-model="changed" type="checkbox" class="mt-1" />This identifies changed work or a missing / ineffective control.</label>
        <label class="flex items-start gap-2 text-sm"><input v-model="confirmed" type="checkbox" class="mt-1" required />I checked this supporting record and confirm the description is accurate.</label>
        <div class="flex gap-2"><Button type="submit" variant="solid" :loading="saving" :disabled="!confirmed || saving || busy">Save Record</Button><Button :disabled="saving" @click="editing = false">Cancel</Button></div>
      </form>
      <p v-if="state && !items.length" class="text-sm text-ink-gray-6">No supporting records yet.</p>
      <article v-for="item in items.filter(row => !row.historical)" :key="item.name" class="rounded-7 border p-3 text-sm">
        <p class="font-semibold">Step {{ item.work_step }} · {{ item.kind }} · {{ item.reference || item.ehs_permit }}</p><p class="mt-1">{{ item.details }}</p>
        <p class="mt-1" :class="['Expired', 'Recheck Required', 'Not Yet Valid', 'Withdrawn'].includes(item.effective_status) ? 'font-medium text-red-700' : 'text-ink-gray-6'">{{ item.effective_status }}<span v-if="item.expires_at"> · Expires {{ item.expires_at }}</span></p><p class="text-xs text-ink-gray-6">{{ item.recorder_name }} · {{ item.recorded_at }}</p>
        <JhaPhotoMarkers v-if="item.kind === 'Photo' && item.evidence" class="mt-2" :src="item.evidence" :markers="item.annotations || []" />
        <a v-else-if="item.evidence" :href="item.evidence" target="_blank" rel="noopener" class="mt-2 block text-blue-700 underline">Open supporting file</a><p v-if="item.evidence_unavailable" class="mt-2 text-amber-800">Supporting file is no longer available to this account.</p>
        <Button v-if="state?.can_record && item.status !== 'Withdrawn'" size="sm" class="mt-2" :disabled="busy || saving" @click="start(item)">Update Supporting Record</Button>
      </article>
      <details v-if="items.some(row => row.historical)" class="text-sm"><summary class="cursor-pointer">Retained earlier records</summary><p v-for="item in items.filter(row => row.historical)" :key="item.name" class="mt-2">Step {{ item.work_step }} · {{ item.kind }} · {{ item.reference }} · {{ item.details }} · {{ item.recorder_name }} · {{ item.recorded_at }}</p></details>
      <details v-if="state?.earlier_photos?.length" class="rounded-7 border p-3 text-sm"><summary class="cursor-pointer font-medium">Photos from earlier revisions · {{ state.earlier_photos.length }}</summary><p class="mt-2 text-xs text-amber-800">Historical context for this change review. Step numbers refer to the source revision; these photos do not confirm today's conditions.</p><article v-for="photo in state.earlier_photos" :key="photo.name" class="mt-3"><p class="font-medium">{{ photo.source_jha }} · Revision {{ photo.source_revision }} · Step {{ photo.work_step }}</p><p class="my-2">{{ photo.details }}</p><JhaPhotoMarkers v-if="photo.evidence" :src="photo.evidence" :markers="photo.annotations || []" /></article></details>
      <details v-if="observations.length || state?.earlier_observations?.length" class="rounded-7 border p-3 text-sm"><summary class="cursor-pointer font-medium">Field observations</summary><p v-for="item in observations" :key="item.name" class="mt-2">Step {{ item.work_step || 'All' }} · {{ item.details }} · {{ item.recorder_name }} · {{ item.recorded_at }}</p><article v-for="item in state.earlier_observations" :key="item.name" class="mt-2 rounded-7 bg-amber-50 p-2"><p>Earlier revision {{ item.revision }} · {{ item.jha }} · Step {{ item.work_step || 'All' }}</p><p>{{ item.details }}</p><p>{{ item.recorded_by }} · {{ item.recorded_at }}</p></article></details>
      <Button v-if="jha.status === 'Review Required - Work Changed' && !jha.replacement_jha" variant="solid" :disabled="busy || saving" @click="emit('requestChange')">Review Reported Changes with PERI</Button>
    </div>
  </details>
</template>

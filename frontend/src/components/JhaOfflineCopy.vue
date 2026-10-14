<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { Button } from 'frappe-ui'
import { downloadOfflineJha, pendingJhaObservations, readOfflineJha, saveJhaObservation, type OfflineJhaCopy } from '../pwa/offlineJha'
import JhaPhotoMarkers from './JhaPhotoMarkers.vue'

const props = defineProps<{ jhaName: string; canDownload?: boolean }>()
const emit = defineEmits<{ changed: [] }>()
const copy = ref<OfflineJhaCopy | null>(null), online = ref(navigator.onLine), busy = ref(false), error = ref(''), message = ref('')
const notes = ref(''), step = ref(''), changed = ref(false), pending = ref<any[]>([]), open = ref(!navigator.onLine)
const photos = ref<Record<string, string>>({})
let alive = true, generation = 0, requestId = crypto.randomUUID()
const resources = computed(() => (copy.value?.resources || []).filter(row => !row.historical && row.status !== 'Withdrawn'))
function releasePhotos() { Object.values(photos.value).forEach(URL.revokeObjectURL); photos.value = {} }
async function load() {
  const version = ++generation, name = props.jhaName
  copy.value = null; pending.value = []; releasePhotos()
  try {
    const saved = await readOfflineJha(name), queue = await pendingJhaObservations(name)
    if (!alive || generation !== version) return
    copy.value = saved; pending.value = queue
    if (saved) photos.value = Object.fromEntries(Object.entries(saved.photos || {}).map(([url, blob]) => [url, URL.createObjectURL(blob)]))
  } catch { if (alive && generation === version) error.value = 'Offline storage is unavailable on this device.' }
}
async function download() {
  busy.value = true; error.value = ''; message.value = ''
  try {
    const name = props.jhaName
    await downloadOfflineJha(name)
    if (!alive || props.jhaName !== name) return
    await load(); open.value = true; message.value = 'Signed copy saved on this device.'
  } catch (err) { if (alive) error.value = err instanceof Error ? err.message : 'Could not download JHA.' }
  finally { busy.value = false }
}
async function observe() {
  if (!copy.value || !notes.value.trim() || busy.value) return
  busy.value = true; error.value = ''; message.value = ''
  const name = props.jhaName
  try {
    const result = await saveJhaObservation(copy.value, notes.value.trim(), step.value, changed.value, requestId)
    if (!alive || props.jhaName !== name) return
    message.value = result.queued ? 'Observation saved on this device. It is pending server sync.' : result.result?.message || 'Observation synced.'
    notes.value = ''; changed.value = false; requestId = crypto.randomUUID()
    pending.value = await pendingJhaObservations(name)
    emit('changed')
  } catch (err) { if (alive) error.value = err instanceof Error ? err.message : 'Could not save observation.' }
  finally { busy.value = false }
}
function connectionChanged() { online.value = navigator.onLine; if (!online.value) open.value = true }
function queueChanged() { void pendingJhaObservations(props.jhaName).then(rows => { if (alive) pending.value = rows }) }
watch(() => props.jhaName, () => { error.value = ''; message.value = ''; notes.value = ''; step.value = ''; changed.value = false; requestId = crypto.randomUUID(); void load() }, { immediate: true })
onMounted(() => { window.addEventListener('online', connectionChanged); window.addEventListener('offline', connectionChanged); window.addEventListener('verto:offline-queue-updated', queueChanged) })
onBeforeUnmount(() => { alive = false; generation++; releasePhotos(); window.removeEventListener('online', connectionChanged); window.removeEventListener('offline', connectionChanged); window.removeEventListener('verto:offline-queue-updated', queueChanged) })
</script>

<template>
  <details :open="open" class="rounded-7 border border-outline-gray-1 bg-surface-base" @toggle="open = ($event.target as HTMLDetailsElement).open">
    <summary class="cursor-pointer p-3 text-sm-medium">Offline JHA copy<span v-if="copy"> · Revision {{ copy.jha.revision }} · saved {{ copy.saved_at }}</span><span v-if="pending.length"> · {{ pending.length }} observations pending</span></summary>
    <div class="space-y-3 px-3 pb-3">
      <p class="text-sm text-amber-900">Downloaded copies are for reference. Current revision, permit validity and field conditions need a live check.</p>
      <Button v-if="online && canDownload !== false" :loading="busy" :disabled="busy" @click="download">Save Signed Copy for Offline</Button>
      <p v-if="error" role="alert" class="text-sm text-red-700">{{ error }}</p>
      <p v-if="message" role="status" class="text-sm text-blue-800">{{ message }}</p>
      <p v-if="!copy" class="text-sm text-ink-gray-6">No signed copy has been downloaded for this JHA on this device and account.</p>
      <template v-if="copy">
        <div class="rounded-7 border border-amber-200 bg-amber-50 p-3 text-sm"><strong>Downloaded signed revision {{ copy.jha.revision }} · {{ copy.jha.name }}</strong><p class="mt-1">{{ copy.jha.work_summary_title }} · {{ copy.jha.project }}</p><p class="mt-1">Saved {{ copy.saved_at }}. {{ copy.notice }}</p></div>
        <p v-if="copy.media_missing" class="text-sm text-amber-800">{{ copy.media_missing }} photo(s) could not be saved. Their descriptions remain below.</p>
        <article v-for="item in copy.jha.work_steps" :key="item.name" class="rounded-7 border p-3 text-sm">
          <p class="font-semibold">{{ item.sequence }}. {{ item.activity }}</p><p v-if="item.hold_or_pause_point" class="text-amber-800">Hold / pause point</p>
          <div v-for="hazard in copy.jha.hazards_and_controls.filter((h: any) => h.work_step_sequence === item.sequence)" :key="hazard.name" class="mt-2 space-y-1 border-t pt-2">
            <p><strong>Hazard:</strong> {{ hazard.hazard_or_energy_source }}</p><p v-if="hazard.people_exposed">People exposed: {{ hazard.people_exposed }}</p><p v-if="hazard.credible_consequence">Consequence: {{ hazard.credible_consequence }}</p>
            <p><strong>Controls:</strong> {{ hazard.existing_controls }}</p><p v-if="hazard.additional_controls">Additional: {{ hazard.additional_controls }}</p><p v-if="hazard.critical_control">Critical control: {{ hazard.critical_control }}</p><p>Owner: {{ hazard.control_owner || 'Not recorded' }} · Verification: {{ hazard.verification_method || 'Not recorded' }}</p><p v-if="hazard.residual_risk">Residual risk: {{ hazard.residual_risk }}</p><p v-if="hazard.permit_or_ccv_required">Permit / CCV: {{ hazard.permit_or_ccv_required }}</p>
          </div>
        </article>
        <details class="rounded-7 border p-3 text-sm"><summary class="cursor-pointer font-medium">Recorded review and sign-on</summary><p class="mt-2">Reviewer: {{ copy.review.reviewer_name }} · {{ copy.review.reviewed_at }}</p><img v-if="copy.review.review_signature" :src="copy.review.review_signature" alt="Recorded reviewer signature" class="max-h-20" /><p>{{ copy.review.review_notes }}</p><div v-for="person in copy.review.participants" :key="person.name" class="mt-2"><p>{{ person.participant_name }} · {{ person.role }} · {{ person.acknowledged ? 'Signed' : 'Not signed' }} · {{ person.acknowledged_at }}</p><img v-if="person.acknowledgement_signature" :src="person.acknowledgement_signature" :alt="`Recorded signature for ${person.participant_name}`" class="max-h-16" /></div></details>
        <details v-if="resources.length" class="rounded-7 border p-3 text-sm"><summary class="cursor-pointer font-medium">Supporting records at download</summary><article v-for="resource in resources" :key="resource.name" class="mt-3"><p class="font-medium">Step {{ resource.work_step }} · {{ resource.kind }} · {{ resource.reference }}</p><p>{{ resource.details }}</p><p>Recorded state at download: {{ resource.effective_status }}<span v-if="resource.expires_at"> · Expires {{ resource.expires_at }}</span></p><JhaPhotoMarkers v-if="photos[resource.evidence]" :src="photos[resource.evidence]" :markers="resource.annotations || []" /><p v-else-if="resource.kind === 'Photo'" class="text-ink-gray-6">Photo unavailable offline.</p></article></details>
        <form class="space-y-3 rounded-7 border p-3" @submit.prevent="observe">
          <p class="text-sm-medium">Record an observation against revision {{ copy.jha.revision }}</p>
          <label class="block text-sm">Step<select v-model="step" class="mt-1 block w-full rounded-7 border p-2"><option value="">Whole job</option><option v-for="item in copy.jha.work_steps" :key="item.name" :value="item.name">{{ item.sequence }}. {{ item.activity }}</option></select></label>
          <label class="block text-sm">Observation<textarea v-model="notes" required maxlength="4000" rows="3" class="mt-1 block w-full rounded-7 border p-2" /></label>
          <label class="flex items-start gap-2 text-sm"><input v-model="changed" type="checkbox" class="mt-1" />This identifies changed work or a missing / ineffective control.</label>
          <p v-if="changed" role="alert" class="text-sm text-amber-900">Hold the affected work and follow the site change process. An offline observation does not notify the server until synced.</p>
          <Button type="submit" variant="solid" :loading="busy" :disabled="busy">Save Observation</Button>
        </form>
        <article v-for="item in pending" :key="item.id" class="rounded-7 bg-amber-50 p-3 text-sm"><p class="font-medium">Pending sync · {{ item.status }}</p><p>{{ item.values.notes }}</p><p v-if="item.last_error" class="mt-1 text-red-700">{{ item.last_error }}</p></article>
      </template>
    </div>
  </details>
</template>

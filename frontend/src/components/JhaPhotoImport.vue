<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { Button } from 'frappe-ui'
import { apiRequest } from '../lib/api'

type Hazard = { hazard: string; controls: string; critical_control: string; control_owner: string }
type Step = { page: number; activity: string; hold_point: string; hazards: Hazard[] }
type Person = { participant_name: string; role: string }
type Content = { job_description: string; uncertainties: string[]; steps: Step[]; participants?: Person[] }
type Page = { url: string; size?: number }
type Reading = { name: string; status: string; pages: Page[]; content: Content; confirmed_by?: string }
const props = defineProps<{ jha: Record<string, any>; online: boolean; busy?: boolean }>()
const emit = defineEmits<{ updated: [value: Record<string, any>]; busy: [value: boolean] }>()
const loading = ref(false), saving = ref(''), error = ref(''), confirmed = ref(false)
const reading = ref<Reading | null>(null), content = ref<Content | null>(null), pages = ref<Page[]>([])
const serverAllows = ref(false)
const canPrepare = ref(false), mode = ref('Guided'), teamLeader = ref(''), crew = ref<Person[]>([])
const teamLeaders = ref<{ value: string; label: string }[]>([]), paperReview = ref<Record<string, any> | null>(null)
let pollTimer: ReturnType<typeof setTimeout> | undefined
let alive = true, generation = 0, readRequest = ''
const eligible = computed(() => props.jha.status === 'Draft' && !props.jha.photo_import && !props.jha.previous_jha
  && !props.jha.voice_started_at && !props.jha.job_steps_confirmed && !props.jha.hazards_and_controls?.length && !props.jha.participants?.length)
const visible = computed(() => eligible.value || Boolean(props.jha.photo_import))
const locked = computed(() => Boolean(props.busy || saving.value || loading.value || !props.online))
const editable = computed(() => eligible.value && serverAllows.value && reading.value?.status !== 'Imported')
const chooseMode = computed(() => (editable.value && Boolean(reading.value)) || canPrepare.value)
const autoReady = computed(() => Boolean(teamLeader.value && crew.value.length && crew.value.every(person => person.participant_name.trim())
  && new Set(crew.value.map(person => person.participant_name.trim().toLowerCase())).size === crew.value.length))
const endpoint = '/api/method/verto.api.mobile.voice_jha_photos.'
function clone(value: Content): Content { return JSON.parse(JSON.stringify(value)) }
function adopt(value: Reading) {
  reading.value = value; content.value = clone(value.content); pages.value = value.pages.map(page => ({ ...page })); confirmed.value = false
  const people = props.jha.participants?.length ? props.jha.participants : value.content.participants || []
  crew.value = people.map((person: Person) => ({ participant_name: person.participant_name, role: person.role || '' }))
  if (!crew.value.length) crew.value.push({ participant_name: '', role: '' })
}
function start(action: string) { saving.value = action; error.value = ''; emit('busy', true) }
function finish() { saving.value = ''; emit('busy', false) }
function current(version: number, name: string) { return alive && version === generation && name === props.jha.name }
async function load(poll = false) {
  clearTimeout(pollTimer)
  const version = ++generation, name = props.jha.name
  if (!poll) {
    reading.value = null; content.value = null; pages.value = []; error.value = ''; confirmed.value = false; readRequest = ''; serverAllows.value = false; loading.value = false
    canPrepare.value = false; paperReview.value = null; teamLeaders.value = []; teamLeader.value = ''; mode.value = 'Guided'; crew.value = []
  }
  if (!visible.value || !props.online) return
  loading.value = !poll
  try {
    const result = await apiRequest<any>(`${endpoint}get_jha_photo_import?jha_name=${encodeURIComponent(name)}`, { cache: 'no-store' })
    if (!current(version, name)) return
    serverAllows.value = result.message.can_import
    canPrepare.value = Boolean(result.message.can_prepare)
    teamLeaders.value = result.message.team_leaders || []
    paperReview.value = result.message.paper_review || null
    if (!poll && result.message.reading) adopt(result.message.reading)
    if (result.message.incident_learning) emit('updated', { name, incident_learning: result.message.incident_learning })
    if (paperReview.value && ['Pending', 'Queued', 'Sending'].includes(paperReview.value.status)) pollTimer = setTimeout(() => { void load(true) }, 5000)
  } catch (err) { if (current(version, name)) error.value = err instanceof Error ? err.message : 'Could not load the paper JHA reading.' }
  finally { if (current(version, name)) loading.value = false }
}
async function addPages(event: Event) {
  const input = event.target as HTMLInputElement, files = Array.from(input.files || [])
  input.value = ''
  if (!files.length || locked.value || !editable.value) return
  error.value = ''
  if (files.some(file => !['image/jpeg', 'image/png', 'image/webp'].includes(file.type) || file.size > 10 * 1024 * 1024)
    || pages.value.length + files.length > 10 || files.reduce((sum, file) => sum + file.size, pages.value.reduce((sum, page) => sum + (page.size || 0), 0)) > 30 * 1024 * 1024) {
    error.value = 'Use up to 10 JPG, PNG or WebP pages, up to 10 MB each and 30 MB in total.'; return
  }
  const version = generation, name = props.jha.name
  start('upload'); readRequest = ''
  try {
    for (const file of files) {
      const body = new FormData()
      body.append('file', file); body.append('is_private', '1'); body.append('doctype', 'Digital Job Hazard Analysis'); body.append('docname', name)
      const result = await apiRequest<any>('/api/method/upload_file', { method: 'POST', body })
      if (!current(version, name)) return
      const url = result.message?.file_url
      if (typeof url !== 'string' || !url.startsWith('/private/files/')) throw new Error('The page must be uploaded as a private JHA attachment.')
      if (pages.value.some(page => page.url === url)) throw new Error('That page photo has already been added.')
      pages.value.push({ url, size: file.size })
    }
  } catch (err) { if (current(version, name)) error.value = err instanceof Error ? err.message : 'Could not upload the page. Previously uploaded pages are retained.' }
  finally { finish() }
}
function movePage(index: number, offset: number) {
  if (locked.value || !editable.value) return
  const next = index + offset
  if (next < 0 || next >= pages.value.length) return
  ;[pages.value[index], pages.value[next]] = [pages.value[next], pages.value[index]]
  readRequest = ''
}
function removePage(index: number) { if (!locked.value && editable.value) { pages.value.splice(index, 1); readRequest = '' } }
function retake() { reading.value = null; content.value = null; confirmed.value = false; readRequest = ''; error.value = '' }
async function readPages() {
  if (locked.value || !editable.value || !pages.value.length) return
  const version = generation, name = props.jha.name
  readRequest ||= crypto.randomUUID(); start('read')
  try {
    const body = new FormData()
    body.append('jha_name', name); body.append('page_urls', JSON.stringify(pages.value.map(page => page.url))); body.append('request_id', readRequest)
    const result = await apiRequest<any>(`${endpoint}read_jha_photos`, { method: 'POST', body })
    if (current(version, name)) adopt(result.message)
  } catch (err) { if (current(version, name)) error.value = err instanceof Error ? err.message : 'PERI could not read the pages. Check the photos and try again.' }
  finally { finish() }
}
async function importReading() {
  if (locked.value || !editable.value || !confirmed.value || !content.value?.steps.length || !reading.value || (mode.value === 'Automatic' && !autoReady.value)) return
  const version = generation, name = props.jha.name
  start('import')
  try {
    const body = new FormData()
    body.append('jha_name', name); body.append('import_name', reading.value.name)
    body.append('reviewed_content', JSON.stringify(mode.value === 'Automatic' ? { ...content.value, participants: crew.value } : content.value)); body.append('confirmation', '1')
    body.append('auto_prepare', mode.value === 'Automatic' ? '1' : '0'); body.append('team_leader', teamLeader.value); body.append('participants', JSON.stringify(crew.value))
    const result = await apiRequest<any>(`${endpoint}confirm_jha_photo_import`, { method: 'POST', body })
    if (!current(version, name)) return
    adopt(result.message.reading); serverAllows.value = false; emit('updated', result.message.jha)
  } catch (err) { if (current(version, name)) error.value = err instanceof Error ? err.message : 'Could not import the checked reading. Your corrections are retained.' }
  finally { finish() }
}
async function prepareImported() {
  if (locked.value || !canPrepare.value || !confirmed.value || !autoReady.value) return
  const version = generation, name = props.jha.name
  start('prepare')
  try {
    const body = new FormData()
    body.append('jha_name', name); body.append('team_leader', teamLeader.value); body.append('participants', JSON.stringify(crew.value)); body.append('confirmation', '1')
    const result = await apiRequest<any>('/api/method/verto.api.mobile.voice_jha_paper_review.prepare_paper_jha_for_review', { method: 'POST', body })
    if (current(version, name)) { paperReview.value = result.message.paper_review; emit('updated', result.message.jha) }
  } catch (err) { if (current(version, name)) error.value = err instanceof Error ? err.message : 'Could not prepare this paper JHA for review.' }
  finally { finish() }
}
async function retryEmail() {
  if (locked.value || !paperReview.value?.can_retry) return
  const version = generation, name = props.jha.name
  start('retry')
  try {
    const body = new FormData(); body.append('jha_name', name); body.append('confirmation', '1')
    const result = await apiRequest<any>('/api/method/verto.api.mobile.voice_jha_paper_review.retry_paper_review_email', { method: 'POST', body })
    if (current(version, name)) { paperReview.value = result.message; pollTimer = setTimeout(() => { void load(true) }, 5000) }
  } catch (err) { if (current(version, name)) error.value = err instanceof Error ? err.message : 'Could not retry the review email.' }
  finally { finish() }
}
function addStep() { content.value?.steps.push({ page: 1, activity: '', hold_point: '', hazards: [] }) }
function addHazard(step: Step) { step.hazards.push({ hazard: '', controls: '', critical_control: '', control_owner: '' }) }
watch(content, () => { confirmed.value = false }, { deep: true })
watch([mode, teamLeader, crew], () => { confirmed.value = false }, { deep: true })
watch(() => [props.jha.name, props.jha.status, props.jha.photo_import, props.online], () => { void load() }, { immediate: true })
onBeforeUnmount(() => { alive = false; generation++; clearTimeout(pollTimer); emit('busy', false) })
</script>

<template>
  <section v-if="paperReview" class="space-y-3 rounded-7 border border-blue-200 bg-blue-50 p-4" data-testid="paper-review-status">
    <h3 class="font-semibold text-blue-900">Prepared from paper JHA</h3>
    <p class="text-sm text-blue-900">The guided voice discussion was skipped. Team leader review (Supervisor or above) and personal crew sign-on are still required.</p>
    <p class="text-sm">Team leader: {{ paperReview.team_leader }} · {{ paperReview.recipient }}</p>
    <p class="text-sm" role="status">Review email: {{ paperReview.status }}<span v-if="paperReview.status === 'Pending'"> · PERI is finding relevant incidents.</span><span v-if="paperReview.status === 'Sent'"> · Sent with the review link and incident briefing.</span></p>
    <details v-if="paperReview.notes?.length" class="rounded-7 border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900"><summary class="cursor-pointer font-medium">Items for the team leader to check · {{ paperReview.notes.length }}</summary><ul class="mt-2 list-disc space-y-1 pl-5"><li v-for="(note, index) in paperReview.notes" :key="index">{{ note }}</li></ul></details>
    <p v-if="paperReview.error" role="alert" class="text-sm text-red-700">{{ paperReview.error }}</p>
    <Button v-if="paperReview.can_retry" :loading="saving === 'retry'" :disabled="locked" @click="retryEmail">Retry review email</Button>
  </section>
  <details v-if="visible" class="rounded-7 border border-blue-200 bg-surface-base" data-testid="jha-photo-import">
    <summary class="cursor-pointer p-4 text-base-semibold text-ink-gray-9">{{ jha.photo_import ? 'Paper JHA source pages' : 'Use a paper JHA' }}</summary>
    <div class="space-y-4 px-4 pb-4">
      <p class="text-sm text-ink-gray-7">Photograph each page and check PERI’s reading. Choose a guided discussion, or let PERI prepare the paper JHA and incident briefing directly for team leader review.</p>
      <p v-if="!online" role="status" class="text-sm text-amber-800">Connect to the internet to upload and read JHA pages.</p>
      <p v-if="loading" role="status" class="text-sm">Loading paper JHA…</p>
      <p v-if="busy && (eligible || canPrepare)" class="text-sm text-amber-800">Disconnect voice or finish the current action before preparing the paper JHA.</p>
      <fieldset :disabled="locked" class="min-w-0 space-y-4">
        <template v-if="editable && !reading">
          <p class="text-xs text-ink-gray-6">Include the whole page in good light, with the writing in focus. Add pages in reading order. Up to 10 JPG, PNG or WebP photos; 10 MB per photo, 30 MB total.</p>
          <div class="grid gap-3 sm:grid-cols-2">
            <label class="block text-sm font-medium">Take a page photo<input aria-label="Take a JHA page photo" type="file" accept="image/jpeg,image/png,image/webp" capture="environment" class="mt-2 block w-full text-sm" @change="addPages" /></label>
            <label class="block text-sm font-medium">Choose page photos<input aria-label="Choose JHA page photos" type="file" accept="image/jpeg,image/png,image/webp" multiple class="mt-2 block w-full text-sm" @change="addPages" /></label>
          </div>
        </template>
        <ol v-if="pages.length" class="grid gap-3 sm:grid-cols-2">
          <li v-for="(page, index) in pages" :key="page.url" class="min-w-0 rounded-7 border p-3">
            <a :href="page.url" target="_blank" rel="noopener" class="block text-sm text-blue-700 underline"><img :src="page.url" :alt="`JHA page ${index + 1}`" loading="lazy" class="mb-2 h-36 w-full rounded-4 bg-surface-gray-1 object-contain" />View page {{ index + 1 }}</a>
            <div v-if="editable && !reading" class="mt-2 flex flex-wrap gap-2">
              <Button size="sm" :disabled="index === 0 || locked" :aria-label="`Move page ${index + 1} earlier`" @click="movePage(index, -1)">Earlier</Button>
              <Button size="sm" :disabled="index === pages.length - 1 || locked" :aria-label="`Move page ${index + 1} later`" @click="movePage(index, 1)">Later</Button>
              <Button size="sm" :disabled="locked" :aria-label="`Remove page ${index + 1}`" @click="removePage(index)">Remove</Button>
            </div>
          </li>
        </ol>
        <Button v-if="editable && !reading" variant="solid" :loading="saving === 'read'" :disabled="locked || !pages.length" @click="readPages">Read pages with PERI</Button>
        <p v-if="saving" role="status" class="text-sm text-ink-gray-6">{{ saving === 'read' ? 'PERI is reading all pages. This may take a minute.' : saving === 'upload' ? 'Uploading page photos…' : 'Saving the checked JHA…' }}</p>
        <template v-if="reading && content">
          <p v-if="reading.status === 'Imported'" role="status" class="rounded-7 bg-blue-50 p-3 text-sm text-blue-900">{{ paperReview ? 'Paper JHA prepared for team leader review.' : 'Paper JHA imported. Connect PERI for the guided review, or choose automatic preparation below.' }} Team leader review (Supervisor or above) and sign-on are still required.</p>
          <template v-else>
            <h3 class="font-semibold">Check PERI’s reading against every page</h3>
            <p class="text-sm text-ink-gray-7">Correct unclear writing and check that each control belongs to the right hazard and step. Missing details can be discussed with PERI. This will replace the draft’s planned step list.</p>
          </template>
          <div v-if="content.uncertainties.length" role="status" class="rounded-7 border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
            <p class="font-medium">Items to clarify with the team</p><ul class="mt-2 list-disc space-y-1 pl-5"><li v-for="(item, index) in content.uncertainties" :key="index">{{ item }}</li></ul>
          </div>
          <p v-if="!content.steps.length" class="text-sm text-amber-900">No readable job steps were found. Retake clearer photos or enter the missing steps below.</p>
          <fieldset :disabled="!editable" class="min-w-0 space-y-4">
            <label class="block text-sm">Job description on the paper<textarea v-model="content.job_description" rows="2" maxlength="1000" class="mt-1 w-full rounded-7 border p-2" /></label>
            <article v-for="(step, index) in content.steps" :key="index" class="min-w-0 space-y-3 rounded-7 border bg-surface-gray-1 p-3" :data-testid="`paper-step-${index + 1}`">
              <div class="flex items-center justify-between gap-2"><h4 class="font-semibold">Step {{ index + 1 }}</h4><Button v-if="editable" size="sm" :disabled="locked" :aria-label="`Remove step ${index + 1}`" @click="content.steps.splice(index, 1)">Remove step</Button></div>
              <label class="block text-sm">Source page<select v-model.number="step.page" class="mt-1 w-full rounded-7 border p-2"><option v-for="(_, page) in pages" :key="page" :value="page + 1">Page {{ page + 1 }}</option></select></label>
              <label class="block text-sm">Activity<textarea v-model="step.activity" :aria-label="`Step ${index + 1} activity`" maxlength="2000" rows="2" class="mt-1 w-full rounded-7 border p-2" /></label>
              <label class="block text-sm">Written hold point (if any)<textarea v-model="step.hold_point" maxlength="2000" rows="2" class="mt-1 w-full rounded-7 border p-2" /></label>
              <div v-for="(hazard, hazardIndex) in step.hazards" :key="hazardIndex" class="space-y-2 rounded-7 border bg-surface-base p-3">
                <label class="block text-sm">Hazard {{ hazardIndex + 1 }}<textarea v-model="hazard.hazard" :aria-label="`Step ${index + 1} hazard ${hazardIndex + 1}`" maxlength="2000" rows="2" class="mt-1 w-full rounded-7 border p-2" /></label>
                <label class="block text-sm">Written controls<textarea v-model="hazard.controls" :aria-label="`Step ${index + 1} controls ${hazardIndex + 1}`" maxlength="2000" rows="3" class="mt-1 w-full rounded-7 border p-2" /></label>
                <label class="block text-sm">Written critical control (if identified)<textarea v-model="hazard.critical_control" maxlength="2000" rows="2" class="mt-1 w-full rounded-7 border p-2" /></label>
                <label class="block text-sm">Written control owner / role<input v-model="hazard.control_owner" maxlength="140" class="mt-1 w-full rounded-7 border p-2" /></label>
                <Button v-if="editable" size="sm" :disabled="locked" :aria-label="`Remove step ${index + 1} hazard ${hazardIndex + 1}`" @click="step.hazards.splice(hazardIndex, 1)">Remove hazard</Button>
              </div>
              <Button v-if="editable" size="sm" :disabled="locked || step.hazards.length >= 30" @click="addHazard(step)">Add missing hazard</Button>
            </article>
            <Button v-if="editable" :disabled="locked || content.steps.length >= 60" @click="addStep">Add missing step</Button>
          </fieldset>
          <fieldset v-if="chooseMode" class="space-y-3 rounded-7 border p-3">
            <legend class="px-1 text-sm font-semibold">How should PERI prepare this JHA?</legend>
            <label class="flex items-start gap-2 text-sm"><input v-model="mode" type="radio" name="paper-preparation" value="Guided" class="mt-1" />Discuss each step with PERI</label>
            <label class="flex items-start gap-2 text-sm"><input v-model="mode" type="radio" name="paper-preparation" value="Automatic" class="mt-1" />Automatically prepare for team leader review</label>
            <template v-if="mode === 'Automatic'">
              <p class="text-xs text-ink-gray-6">Skip the voice interview. PERI sends the selected team leader a review link, relevant incidents and unclear or missing details. It does not sign or approve the JHA.</p>
              <label class="block text-sm">Team leader (Supervisor or above)<select v-model="teamLeader" aria-label="Paper JHA team leader" class="mt-1 w-full rounded-7 border p-2"><option value="">Select team leader</option><option v-for="person in teamLeaders" :key="person.value" :value="person.value">{{ person.label }}</option></select></label>
              <p v-if="!teamLeaders.length" class="text-xs text-amber-800">Assign the team leader to this Work Summary so they can open and review the JHA.</p>
              <p class="text-sm font-medium">Confirm the people who participated in the paper JHA</p>
              <div v-for="(person, index) in crew" :key="index" class="flex flex-wrap items-center gap-2">
                <input v-model="person.participant_name" :aria-label="`Paper participant ${index + 1} name`" maxlength="140" placeholder="Name" class="min-w-0 flex-1 rounded-7 border p-2 text-sm" />
                <input v-model="person.role" :aria-label="`Paper participant ${index + 1} role`" maxlength="140" placeholder="Role (optional)" class="min-w-0 flex-1 rounded-7 border p-2 text-sm" />
                <Button size="sm" :disabled="locked" :aria-label="`Remove paper participant ${index + 1}`" @click="crew.splice(index, 1)">Remove</Button>
              </div>
              <Button size="sm" :disabled="locked || crew.length >= 100" @click="crew.push({ participant_name: '', role: '' })">Add participant</Button>
            </template>
          </fieldset>
          <template v-if="editable || (canPrepare && mode === 'Automatic')">
            <label class="flex items-start gap-2 text-sm"><input v-model="confirmed" type="checkbox" class="mt-1" /><span>{{ mode === 'Automatic' ? 'I checked the paper reading and confirmed the people who participated. Send this draft to the selected team leader for review.' : 'I checked every page and corrected the reading. Use these steps and controls as the draft for discussion with PERI.' }}</span></label>
            <div class="flex flex-wrap gap-2"><Button v-if="editable" variant="solid" :loading="saving === 'import'" :disabled="locked || !confirmed || !content.steps.length || (mode === 'Automatic' && !autoReady)" @click="importReading">{{ mode === 'Automatic' ? 'Prepare and send for review' : 'Use checked JHA' }}</Button><Button v-else variant="solid" :loading="saving === 'prepare'" :disabled="locked || !confirmed || !autoReady" @click="prepareImported">Prepare and send for review</Button><Button v-if="editable" :disabled="locked" @click="retake">Retake or change pages</Button></div>
          </template>
        </template>
      </fieldset>
      <p v-if="error" role="alert" class="text-sm text-red-700">{{ error }}</p>
    </div>
  </details>
</template>

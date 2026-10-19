<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { Button } from 'frappe-ui'
import { apiRequest } from '../lib/api'

const props = defineProps<{ jha: Record<string, any> }>()
const state = ref<Record<string, any> | null>(null)
const loading = ref(false), sending = ref(false), confirming = ref(false), confirmation = ref(false)
const error = ref('')
let generation = 0, timer: ReturnType<typeof setTimeout> | undefined, polls = 0, requestId = ''
const pending = computed(() => ['Pending', 'Queued', 'Sending'].includes(state.value?.status))
const labels: Record<string, string> = { Pending: 'Sending print copy…', Queued: 'Print email queued', Sending: 'Sending print copy…',
  Sent: 'Print copy sent', Failed: 'Print email needs attention', Cancelled: 'Print email cancelled',
  'Not Configured': 'Printing email not configured', 'Not Requested': 'Print copy not emailed' }
const label = computed(() => labels[String(state.value?.status)] || 'Checking printing email…')

function stopPolling() { clearTimeout(timer); timer = undefined }
async function refresh() {
  if (!navigator.onLine || !props.jha.name || props.jha.status !== 'Signed') return
  stopPolling()
  const token = generation
  loading.value = true; error.value = ''
  try {
    const data = await apiRequest<any>(`/api/method/verto.api.mobile.voice_jha_email.get_jha_print_delivery?jha_name=${encodeURIComponent(props.jha.name)}`, { cache: 'no-store' })
    if (token !== generation) return
    state.value = data.message
    // Keep the normal finish screen up to date without polling for a whole shift.
    if (pending.value && polls++ < 12) timer = setTimeout(() => void refresh(), 5000)
  } catch (err) { if (token === generation) error.value = err instanceof Error ? err.message : 'Could not check print email delivery.' }
  finally { if (token === generation) loading.value = false }
}

async function sendCopy() {
  if (!confirmation.value || !state.value?.can_resend || loading.value || sending.value || !navigator.onLine) return
  const token = generation
  sending.value = true; error.value = ''
  requestId ||= crypto.randomUUID()
  try {
    const body = new FormData()
    body.append('jha_name', props.jha.name); body.append('confirmation', '1'); body.append('request_id', requestId)
    const data = await apiRequest<any>('/api/method/verto.api.mobile.voice_jha_email.resend_jha_print_email', { method: 'POST', body })
    if (token !== generation) return
    state.value = data.message; requestId = ''; confirming.value = false; confirmation.value = false; polls = 0
    if (pending.value) timer = setTimeout(() => void refresh(), 5000)
  } catch (err) { if (token === generation) error.value = err instanceof Error ? err.message : 'Could not request the print copy.' }
  finally { if (token === generation) sending.value = false }
}

watch([() => props.jha.name, () => props.jha.status, () => props.jha.revision], () => {
  generation += 1; stopPolling(); state.value = null; polls = 0; requestId = ''
  confirming.value = false; confirmation.value = false; sending.value = false
  if (props.jha.status === 'Signed') void refresh()
}, { immediate: true })
onBeforeUnmount(() => { generation += 1; stopPolling() })
</script>

<template>
  <section v-if="jha.status === 'Signed'" class="mt-3 rounded-7 border border-outline-gray-2 bg-surface-base p-3" data-testid="jha-print-email">
    <p class="text-sm-medium text-ink-gray-9" role="status" aria-live="polite">{{ label }}</p>
    <p v-if="state?.recipient" class="mt-1 break-words text-sm text-ink-gray-6">{{ state.recipient }} · Revision {{ state.revision }}</p>
    <p v-if="state?.status === 'Sent'" class="mt-1 text-xs text-ink-gray-5">The signed PDF has been sent to the printing inbox.</p>
    <p v-else-if="pending" class="mt-1 text-xs text-ink-gray-5">Your signed JHA is saved. The print copy will be emailed automatically.</p>
    <p v-else-if="state?.status === 'Not Configured'" class="mt-1 text-xs text-ink-gray-5">A supervisor can set the JHA Printing Email on the Project or the default in Verto Mobile Settings.</p>
    <p v-else-if="state?.status === 'Failed'" class="mt-1 text-xs text-amber-800">{{ state.message || 'Ask the supervisor to check the email settings and retry.' }}</p>
    <p v-if="error" role="alert" class="mt-2 text-sm text-red-700">{{ error }}</p>
    <div class="mt-2 flex flex-wrap gap-2">
      <Button variant="subtle" size="sm" :loading="loading" :disabled="loading || sending" @click="polls = 0; refresh()">Check email status</Button>
      <Button v-if="state?.can_resend && !confirming" variant="subtle" size="sm" :disabled="loading || sending" @click="confirming = true">{{ state.status === 'Sent' ? 'Resend print copy' : 'Send print copy' }}</Button>
    </div>
    <form v-if="confirming && state?.can_resend" class="mt-3 space-y-3" @submit.prevent="sendCopy">
      <label class="flex items-start gap-2 text-sm text-ink-gray-7"><input v-model="confirmation" type="checkbox" :disabled="sending" class="mt-1" />Send a signed copy to {{ state.configured_recipient }}.</label>
      <div class="flex gap-2"><Button type="submit" variant="solid" size="sm" :loading="sending" :disabled="!confirmation || sending">Email signed PDF</Button>
        <Button type="button" variant="subtle" size="sm" :disabled="sending" @click="confirming = false; confirmation = false">Cancel</Button></div>
    </form>
  </section>
</template>

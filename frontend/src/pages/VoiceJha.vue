<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()
const loading = ref(true)
const creating = ref(false)
const error = ref('')
const context = ref<any>(null)

const workSummary = computed(() => String(route.params.workSummary || ''))

async function frappeCall(method: string, args: Record<string, unknown> = {}, httpMethod = 'GET') {
  const url = new URL(`/api/method/${method}`, window.location.origin)
  const options: RequestInit = { method: httpMethod, credentials: 'include' }

  if (httpMethod === 'GET') {
    Object.entries(args).forEach(([key, value]) => url.searchParams.set(key, String(value)))
  } else {
    options.headers = { 'Content-Type': 'application/json' }
    options.body = JSON.stringify(args)
  }

  const response = await fetch(url, options)
  const payload = await response.json()
  if (!response.ok || payload.exc) throw new Error(payload.message || 'Request failed')
  return payload.message
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    context.value = await frappeCall('verto.api.mobile.voice_jha.get_voice_jha_bootstrap', {
      work_summary: workSummary.value,
    })
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Could not load the Work Summary.'
  } finally {
    loading.value = false
  }
}

async function createDraft() {
  creating.value = true
  error.value = ''
  try {
    const result = await frappeCall(
      'verto.api.mobile.voice_jha.create_voice_jha_draft',
      { work_summary: workSummary.value },
      'POST',
    )
    if (result?.name) window.location.href = `/app/digital-job-hazard-analysis/${encodeURIComponent(result.name)}`
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Could not create the Digital JHA draft.'
  } finally {
    creating.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="mx-auto w-full max-w-3xl p-4 sm:p-6">
    <button class="mb-4 text-sm text-gray-600 hover:text-gray-900" @click="router.back()">← Back</button>

    <div v-if="loading" class="rounded-xl border bg-white p-6">Loading Work Summary…</div>
    <div v-else-if="error && !context" class="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">{{ error }}</div>

    <template v-else-if="context">
      <div class="rounded-2xl border bg-white p-5 shadow-sm">
        <div class="text-xs font-semibold uppercase tracking-wide text-gray-500">PERI Voice JHA Prototype</div>
        <h1 class="mt-2 text-2xl font-semibold text-gray-900">{{ context.title }}</h1>
        <div class="mt-2 text-sm text-gray-600">{{ context.project }}<span v-if="context.work_area"> · {{ context.work_area }}</span></div>

        <div class="mt-5 rounded-xl bg-amber-50 p-4 text-sm text-amber-900">
          This prototype does not authorise work. PERI will assist with developing a draft JHA; the crew and supervisor remain responsible for reviewing and signing it.
        </div>

        <div class="mt-6 rounded-2xl border border-dashed p-8 text-center">
          <div class="text-lg font-medium text-gray-900">Voice connection coming next</div>
          <p class="mx-auto mt-2 max-w-lg text-sm text-gray-600">
            The Work Summary context and Digital JHA storage are now isolated behind this prototype. The next milestone will connect PERI Realtime voice, live transcription and restricted draft-only tools here.
          </p>
          <div class="mt-5 inline-flex rounded-full bg-gray-100 px-3 py-1 text-xs font-medium text-gray-700">
            {{ context.peri_bot ? `Facilitator: ${context.peri_bot}` : 'PERI bot configuration required' }}
          </div>
        </div>

        <div v-if="error" class="mt-4 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">{{ error }}</div>

        <button
          class="mt-6 w-full rounded-xl bg-gray-900 px-4 py-3 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-50"
          :disabled="creating"
          @click="createDraft"
        >
          {{ creating ? 'Creating draft…' : 'Create Digital JHA Draft' }}
        </button>
      </div>
    </template>
  </div>
</template>

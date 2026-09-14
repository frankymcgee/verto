<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Badge, Button } from 'frappe-ui'

import { apiRequest } from '../lib/api'

type FrappeResponse<T> = {
  message: T
}

type JhaSnapshot = {
  name: string
  status: string
  revision?: number
  project?: string
  work_summary?: string
  work_summary_title?: string
  work_order_number?: string
  work_area?: string
  ai_bot?: string
  modified?: string
  created?: boolean
  work_steps?: any[]
  hazards_and_controls?: any[]
  participants?: any[]
}

type VoiceJhaBootstrap = {
  work_summary: string
  title: string
  project?: string
  work_area?: string
  work_order_number?: string
  description?: string
  peri_bot?: string
  realtime_enabled: boolean
  prototype_stage?: string
  notice?: string
  existing_jha?: JhaSnapshot | null
}

const route = useRoute()
const router = useRouter()

const loading = ref(true)
const creating = ref(false)
const refreshing = ref(false)
const error = ref('')
const context = ref<VoiceJhaBootstrap | null>(null)
const jha = ref<JhaSnapshot | null>(null)

const workSummary = computed(() => String(route.params.workSummary || ''))
const workStepCount = computed(() => jha.value?.work_steps?.length || 0)
const hazardCount = computed(() => jha.value?.hazards_and_controls?.length || 0)
const participantCount = computed(() => jha.value?.participants?.length || 0)

async function load() {
  loading.value = true
  error.value = ''

  try {
    const data = await apiRequest<FrappeResponse<VoiceJhaBootstrap>>(
      `/api/method/verto.api.mobile.voice_jha.get_voice_jha_bootstrap?work_summary=${encodeURIComponent(workSummary.value)}`
    )

    context.value = data.message
    jha.value = data.message?.existing_jha || null
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Could not load the Work Summary.'
  } finally {
    loading.value = false
  }
}

async function createOrResumeDraft() {
  creating.value = true
  error.value = ''

  try {
    const payload = new FormData()
    payload.append('work_summary', workSummary.value)

    const data = await apiRequest<FrappeResponse<JhaSnapshot>>(
      '/api/method/verto.api.mobile.voice_jha.create_voice_jha_draft',
      {
        method: 'POST',
        body: payload,
      }
    )

    jha.value = data.message
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Could not create or resume the Digital JHA draft.'
  } finally {
    creating.value = false
  }
}

async function refreshJha() {
  if (!jha.value?.name) {
    await load()
    return
  }

  refreshing.value = true
  error.value = ''

  try {
    const data = await apiRequest<FrappeResponse<JhaSnapshot>>(
      `/api/method/verto.api.mobile.voice_jha.get_voice_jha_snapshot?jha_name=${encodeURIComponent(jha.value.name)}`
    )
    jha.value = data.message
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Could not refresh the Digital JHA.'
  } finally {
    refreshing.value = false
  }
}

onMounted(load)
</script>

<template>
  <section class="min-h-full bg-surface-gray-1 px-[var(--verto-page-x,0.75rem)] py-[var(--verto-page-y,0.75rem)]">
    <div class="mx-auto w-full max-w-3xl space-y-3">
      <div class="flex items-center justify-between gap-3">
        <Button variant="subtle" theme="gray" size="sm" @click="router.back()">
          Back
        </Button>

        <Button
          v-if="jha"
          variant="subtle"
          theme="gray"
          size="sm"
          :loading="refreshing"
          :disabled="refreshing"
          @click="refreshJha"
        >
          Refresh
        </Button>
      </div>

      <section v-if="loading" class="rounded-7 border border-outline-gray-1 bg-surface-base p-4 shadow-sm">
        <div class="space-y-3">
          <div class="h-5 w-40 rounded-4 bg-surface-gray-3" />
          <div class="h-8 w-3/4 rounded-4 bg-surface-gray-2" />
          <div class="h-24 rounded-7 bg-surface-gray-2" />
        </div>
      </section>

      <section
        v-else-if="error && !context"
        class="rounded-7 border border-red-200 bg-red-50 p-4 shadow-sm"
      >
        <p class="text-sm-medium text-red-800">Could not open this Work Summary.</p>
        <p class="mt-1 text-sm text-red-700">{{ error }}</p>
      </section>

      <template v-else-if="context">
        <section class="rounded-7 border border-outline-gray-1 bg-surface-base p-4 shadow-sm">
          <div class="flex flex-wrap items-center gap-2">
            <Badge variant="subtle">Develop JHA with PERI</Badge>
            <Badge v-if="jha?.status" variant="subtle">{{ jha.status }}</Badge>
            <Badge v-if="context.work_order_number" variant="subtle">WO: {{ context.work_order_number }}</Badge>
          </div>

          <h1 class="mt-3 text-xl-semibold text-ink-gray-9">
            {{ context.title }}
          </h1>

          <p class="mt-1 text-sm text-ink-gray-5">
            {{ context.project }}<span v-if="context.work_area"> · {{ context.work_area }}</span>
          </p>

          <div class="mt-4 rounded-7 border border-amber-200 bg-amber-50 p-3">
            <p class="text-sm-medium text-amber-900">Human review remains mandatory.</p>
            <p class="mt-1 text-sm leading-5 text-amber-800">
              PERI can help the crew develop and document a draft JHA. It does not authorise work, approve the JHA, or sign on behalf of any participant.
            </p>
          </div>
        </section>

        <section v-if="!jha" class="rounded-7 border border-outline-gray-1 bg-surface-base p-4 shadow-sm">
          <p class="text-base-semibold text-ink-gray-9">Start the JHA</p>
          <p class="mt-1 text-sm leading-5 text-ink-gray-6">
            PERI will use this assigned Work Summary as the controlled starting context. A Digital JHA draft will be created and linked to this work before the voice discussion begins.
          </p>

          <div class="mt-4 rounded-7 bg-surface-gray-1 p-3">
            <p class="text-xs-semibold uppercase tracking-wide text-ink-gray-5">AI facilitator</p>
            <p class="mt-1 text-sm-medium text-ink-gray-8">
              {{ context.peri_bot || 'PERI bot configuration required' }}
            </p>
          </div>

          <Button
            variant="solid"
            theme="gray"
            size="lg"
            class="mt-4 w-full justify-center"
            :loading="creating"
            :disabled="creating || !context.peri_bot"
            @click="createOrResumeDraft"
          >
            Start JHA with PERI
          </Button>
        </section>

        <template v-else>
          <section class="rounded-7 border border-outline-gray-1 bg-surface-base p-4 shadow-sm">
            <div class="flex items-start justify-between gap-3">
              <div class="min-w-0">
                <p class="text-xs-semibold uppercase tracking-wide text-ink-gray-5">Digital JHA</p>
                <p class="mt-1 truncate text-base-semibold text-ink-gray-9">{{ jha.name }}</p>
              </div>

              <Badge variant="subtle">Rev {{ jha.revision || 1 }}</Badge>
            </div>

            <div class="mt-4 grid grid-cols-3 gap-2">
              <div class="rounded-7 bg-surface-gray-1 p-3 text-center">
                <p class="text-lg-semibold text-ink-gray-9">{{ workStepCount }}</p>
                <p class="mt-0.5 text-xs text-ink-gray-5">Steps</p>
              </div>
              <div class="rounded-7 bg-surface-gray-1 p-3 text-center">
                <p class="text-lg-semibold text-ink-gray-9">{{ hazardCount }}</p>
                <p class="mt-0.5 text-xs text-ink-gray-5">Hazards</p>
              </div>
              <div class="rounded-7 bg-surface-gray-1 p-3 text-center">
                <p class="text-lg-semibold text-ink-gray-9">{{ participantCount }}</p>
                <p class="mt-0.5 text-xs text-ink-gray-5">People</p>
              </div>
            </div>

            <p class="mt-4 text-sm text-ink-gray-6">
              {{ jha.created === false ? 'Existing draft resumed.' : 'Draft ready.' }} Changes made during the PERI discussion will be stored against this record.
            </p>
          </section>

          <section class="rounded-7 border border-outline-gray-1 bg-surface-base p-4 shadow-sm">
            <div class="flex items-center justify-between gap-3">
              <div>
                <p class="text-base-semibold text-ink-gray-9">Voice discussion</p>
                <p class="mt-1 text-sm text-ink-gray-5">Next workflow stage</p>
              </div>
              <Badge variant="subtle">Not connected</Badge>
            </div>

            <div class="mt-4 space-y-2 text-sm text-ink-gray-6">
              <p>1. Confirm everyone present and obtain transcription consent.</p>
              <p>2. Discuss the job steps, hazards, credible consequences and controls with PERI.</p>
              <p>3. PERI records structured draft entries against this JHA.</p>
              <p>4. Crew reviews the completed JHA before individual acknowledgement and sign-on.</p>
            </div>

            <Button
              variant="solid"
              theme="gray"
              size="lg"
              class="mt-4 w-full justify-center"
              disabled
            >
              Connect Voice with PERI — next milestone
            </Button>
          </section>
        </template>

        <section
          v-if="error"
          class="rounded-7 border border-red-200 bg-red-50 p-3 shadow-sm"
        >
          <p class="text-sm text-red-700">{{ error }}</p>
        </section>
      </template>
    </div>
  </section>
</template>

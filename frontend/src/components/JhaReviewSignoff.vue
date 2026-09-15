<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { Badge, Button, Checkbox } from 'frappe-ui'

import { apiRequest } from '../lib/api'
import SignatureField from './mobile-fields/SignatureField.vue'

type FrappeResponse<T> = { message: T }

type ReviewParticipant = {
  name: string
  participant_name: string
  employee?: string
  role?: string
  present_for_discussion?: number | boolean
  transcription_consent?: number | boolean
  acknowledged?: number | boolean
  acknowledged_at?: string
  acknowledged_by_user?: string
  acknowledgement_signature?: string
}

type ReviewState = {
  name: string
  status: string
  revision?: number
  review_completed?: number | boolean
  reviewed_by?: string
  reviewer_name?: string
  reviewed_at?: string
  review_signature?: string
  review_notes?: string
  signed_at?: string
  signed_by_user?: string
  participants?: ReviewParticipant[]
}

const props = defineProps<{
  jha: Record<string, any>
}>()

const emit = defineEmits<{
  updated: [value: ReviewState]
}>()

const loading = ref(false)
const submittingReview = ref(false)
const submittingParticipant = ref('')
const reopening = ref(false)
const error = ref('')
const state = ref<ReviewState | null>(null)
const reviewSignature = ref('')
const reviewConfirmation = ref(false)
const reviewNotes = ref('')
const participantSignatures = ref<Record<string, string>>({})
const participantConfirmations = ref<Record<string, boolean>>({})

const reviewStatuses = new Set([
  'Ready for Team Review',
  'Signed',
  'Review Required - Work Changed',
])

const visible = computed(() => reviewStatuses.has(String(props.jha?.status || '')))
const reviewComplete = computed(() => Boolean(state.value?.review_completed))
const presentParticipants = computed(() =>
  (state.value?.participants || []).filter((row) => Boolean(row.present_for_discussion))
)
const acknowledgedCount = computed(() =>
  presentParticipants.value.filter((row) => Boolean(row.acknowledged)).length
)
const remainingCount = computed(() => Math.max(0, presentParticipants.value.length - acknowledgedCount.value))

function formatDateTime(value?: string) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString()
}

function mergeAndEmit(next: ReviewState) {
  state.value = next
  reviewNotes.value = next.review_notes || reviewNotes.value
  emit('updated', next)
}

async function loadReviewState() {
  if (!props.jha?.name || !visible.value) return

  loading.value = true
  error.value = ''
  try {
    const data = await apiRequest<FrappeResponse<ReviewState>>(
      `/api/method/verto.api.mobile.voice_jha_review.get_jha_review_state?jha_name=${encodeURIComponent(props.jha.name)}`
    )
    state.value = data.message
    reviewNotes.value = data.message?.review_notes || ''

    if (
      data.message?.status !== props.jha?.status ||
      data.message?.revision !== props.jha?.revision
    ) {
      emit('updated', data.message)
    }
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Could not load JHA review status.'
  } finally {
    loading.value = false
  }
}

async function completeReview() {
  if (!props.jha?.name || !reviewSignature.value || !reviewConfirmation.value) return

  submittingReview.value = true
  error.value = ''
  try {
    const payload = new FormData()
    payload.append('jha_name', props.jha.name)
    payload.append('signature', reviewSignature.value)
    payload.append('confirmation', '1')
    payload.append('review_notes', reviewNotes.value || '')

    const data = await apiRequest<FrappeResponse<ReviewState>>(
      '/api/method/verto.api.mobile.voice_jha_review.complete_human_review',
      { method: 'POST', body: payload }
    )
    mergeAndEmit(data.message)
    reviewSignature.value = ''
    reviewConfirmation.value = false
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Could not complete the human review.'
  } finally {
    submittingReview.value = false
  }
}

async function acknowledgeParticipant(participant: ReviewParticipant) {
  const rowName = participant.name
  const signature = participantSignatures.value[rowName] || ''
  const confirmed = Boolean(participantConfirmations.value[rowName])
  if (!props.jha?.name || !rowName || !signature || !confirmed) return

  submittingParticipant.value = rowName
  error.value = ''
  try {
    const payload = new FormData()
    payload.append('jha_name', props.jha.name)
    payload.append('participant_row', rowName)
    payload.append('signature', signature)
    payload.append('confirmation', '1')

    const data = await apiRequest<FrappeResponse<ReviewState>>(
      '/api/method/verto.api.mobile.voice_jha_review.acknowledge_jha_participant',
      { method: 'POST', body: payload }
    )
    mergeAndEmit(data.message)
    participantSignatures.value[rowName] = ''
    participantConfirmations.value[rowName] = false
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Could not record participant sign-on.'
  } finally {
    submittingParticipant.value = ''
  }
}

async function reopenForChange() {
  if (!props.jha?.name) return

  reopening.value = true
  error.value = ''
  try {
    const payload = new FormData()
    payload.append('jha_name', props.jha.name)
    payload.append('confirmation', '1')

    const data = await apiRequest<FrappeResponse<ReviewState>>(
      '/api/method/verto.api.mobile.voice_jha_review.reopen_changed_jha',
      { method: 'POST', body: payload }
    )
    mergeAndEmit(data.message)
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Could not reopen the JHA for changed work.'
  } finally {
    reopening.value = false
  }
}

watch(
  [() => props.jha?.name, () => props.jha?.status],
  () => {
    if (visible.value) void loadReviewState()
  }
)

onMounted(() => {
  if (visible.value) void loadReviewState()
})
</script>

<template>
  <section
    v-if="visible"
    class="rounded-7 border border-outline-gray-1 bg-surface-base p-4 shadow-sm"
  >
    <div class="flex items-start justify-between gap-3">
      <div>
        <p class="text-base-semibold text-ink-gray-9">Human review & sign-on</p>
        <p class="mt-1 text-sm text-ink-gray-5">
          Human verification and individual crew acknowledgement
        </p>
      </div>
      <Badge variant="subtle">{{ state?.status || jha.status }}</Badge>
    </div>

    <div v-if="loading" class="mt-4 rounded-7 bg-surface-gray-1 p-4 text-sm text-ink-gray-5">
      Loading review status…
    </div>

    <template v-else-if="state">
      <div
        v-if="state.status === 'Review Required - Work Changed'"
        class="mt-4 rounded-7 border border-red-200 bg-red-50 p-3"
      >
        <p class="text-sm-medium text-red-900">The planned work has changed.</p>
        <p class="mt-1 text-sm leading-5 text-red-800">
          This JHA can no longer rely on its previous review or signatures. Reopen it as a new revision, reassess the changed work with the crew, then complete review and sign-on again.
        </p>
        <Button
          variant="solid"
          theme="gray"
          class="mt-3 w-full justify-center"
          :loading="reopening"
          :disabled="reopening"
          @click="reopenForChange"
        >
          Reopen as Revision {{ (state.revision || 1) + 1 }}
        </Button>
      </div>

      <div
        v-else-if="state.status === 'Signed'"
        class="mt-4 rounded-7 border border-green-200 bg-green-50 p-3"
      >
        <p class="text-sm-medium text-green-900">Human review and participant sign-on complete.</p>
        <p class="mt-1 text-sm text-green-800">
          Fully signed {{ formatDateTime(state.signed_at) }}. This status records acknowledgement of the JHA; it does not replace site permits, isolations or other work-authorisation requirements.
        </p>
      </div>

      <template v-else-if="state.status === 'Ready for Team Review'">
        <div v-if="!reviewComplete" class="mt-4 space-y-4">
          <div class="rounded-7 border border-blue-200 bg-blue-50 p-3">
            <p class="text-sm-medium text-blue-900">Reviewer verification required.</p>
            <p class="mt-1 text-sm leading-5 text-blue-800">
              Review the work steps, hazards and controls above. Correct the JHA before signing if anything is inaccurate, incomplete or no longer reflects the planned work.
            </p>
          </div>

          <div>
            <label class="block text-sm-medium text-ink-gray-8">Review notes</label>
            <textarea
              v-model="reviewNotes"
              rows="4"
              class="mt-2 w-full rounded-7 border border-outline-gray-2 bg-surface-base px-3 py-2 text-sm text-ink-gray-8 outline-none focus:border-outline-gray-4"
              placeholder="Optional notes, corrections or review comments"
            />
          </div>

          <SignatureField
            v-model="reviewSignature"
            label="Reviewer signature"
            description="The reviewer must personally sign after checking the complete JHA."
            required
          />

          <label class="flex cursor-pointer items-start gap-3 rounded-7 bg-surface-gray-1 p-3">
            <Checkbox
              class="mt-0.5 shrink-0"
              size="md"
              :model-value="reviewConfirmation"
              @update:model-value="(checked) => reviewConfirmation = Boolean(checked)"
            />
            <span class="text-sm leading-5 text-ink-gray-7">
              I have reviewed this JHA against the planned work and the crew discussion. I understand that signing the review does not itself authorise work to proceed.
            </span>
          </label>

          <Button
            variant="solid"
            theme="gray"
            size="lg"
            class="w-full justify-center"
            :loading="submittingReview"
            :disabled="submittingReview || !reviewSignature || !reviewConfirmation"
            @click="completeReview"
          >
            Complete Human Review
          </Button>
        </div>

        <div v-else class="mt-4 space-y-4">
          <div class="rounded-7 border border-green-200 bg-green-50 p-3">
            <p class="text-sm-medium text-green-900">Human review completed.</p>
            <p class="mt-1 text-sm text-green-800">
              {{ state.reviewer_name || state.reviewed_by }} · {{ formatDateTime(state.reviewed_at) }}
            </p>
          </div>

          <div class="flex items-center justify-between gap-3">
            <div>
              <p class="text-sm-semibold text-ink-gray-9">Participant acknowledgement</p>
              <p class="mt-1 text-xs text-ink-gray-5">
                {{ acknowledgedCount }}/{{ presentParticipants.length }} present participants signed · {{ remainingCount }} remaining
              </p>
            </div>
          </div>

          <div class="space-y-3">
            <div
              v-for="participant in presentParticipants"
              :key="participant.name"
              class="rounded-7 border border-outline-gray-1 bg-surface-gray-1 p-3"
            >
              <div class="flex items-start justify-between gap-3">
                <div class="min-w-0">
                  <p class="text-sm-medium text-ink-gray-9">{{ participant.participant_name }}</p>
                  <p v-if="participant.role" class="mt-0.5 text-xs text-ink-gray-5">{{ participant.role }}</p>
                </div>
                <Badge variant="subtle">{{ participant.acknowledged ? 'Signed' : 'Awaiting sign-on' }}</Badge>
              </div>

              <div v-if="participant.acknowledged" class="mt-3 text-xs text-ink-gray-5">
                Acknowledged {{ formatDateTime(participant.acknowledged_at) }}
              </div>

              <div v-else class="mt-3 space-y-3">
                <SignatureField
                  :model-value="participantSignatures[participant.name] || ''"
                  label="Participant signature"
                  :description="`${participant.participant_name} must sign personally on this device.`"
                  required
                  @update:model-value="(value) => participantSignatures[participant.name] = value"
                />

                <label class="flex cursor-pointer items-start gap-3 rounded-7 bg-surface-base p-3">
                  <Checkbox
                    class="mt-0.5 shrink-0"
                    size="md"
                    :model-value="Boolean(participantConfirmations[participant.name])"
                    @update:model-value="(checked) => participantConfirmations[participant.name] = Boolean(checked)"
                  />
                  <span class="text-sm leading-5 text-ink-gray-7">
                    I confirm that I am {{ participant.participant_name }}, I have reviewed this JHA, understand the hazards and controls discussed, and will raise any change or uncertainty before proceeding.
                  </span>
                </label>

                <Button
                  variant="solid"
                  theme="gray"
                  class="w-full justify-center"
                  :loading="submittingParticipant === participant.name"
                  :disabled="submittingParticipant === participant.name || !participantSignatures[participant.name] || !participantConfirmations[participant.name]"
                  @click="acknowledgeParticipant(participant)"
                >
                  Sign & Acknowledge
                </Button>
              </div>
            </div>
          </div>
        </div>
      </template>
    </template>

    <div v-if="error" class="mt-4 rounded-7 border border-red-200 bg-red-50 p-3">
      <p class="text-sm text-red-700">{{ error }}</p>
    </div>
  </section>
</template>

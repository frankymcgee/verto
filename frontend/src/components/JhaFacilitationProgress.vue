<script setup lang="ts">
import { computed } from 'vue'
import { Badge } from 'frappe-ui'

type StepProgress = {
  name?: string
  sequence: number
  activity: string
  hazard_count: number
  hazards_complete: boolean
  controls_complete: boolean
  critical_control_required: boolean
  critical_controls_reviewed: boolean
  critical_owner_complete: boolean
  hold_point_complete: boolean
  hold_point?: boolean | null
  discussion_complete: boolean
  is_current: boolean
}

type FacilitationProgress = {
  stage: string
  job_steps_confirmed: boolean
  current_step_sequence?: number
  current_step_activity?: string
  completed_step_count?: number
  total_step_count?: number
  steps?: StepProgress[]
}

const props = defineProps<{
  progress?: FacilitationProgress | null
}>()

const steps = computed(() => props.progress?.steps || [])
const stageHelp = computed(() => {
  const stage = props.progress?.stage || ''
  if (stage === 'Job Steps') return 'Confirm the complete ordered job-step list before hazard analysis begins.'
  if (stage === 'Step Analysis') return `PERI is working through Step ${props.progress?.current_step_sequence || ''} only.`
  if (stage === 'Development Team') return 'All job steps are complete. Record the people who participated in the JHA discussion.'
  if (stage === 'Completeness Check') return 'The field discussion is complete. PERI is checking for any remaining JHA gaps.'
  if (stage === 'Ready for Team Review') return 'PERI facilitation is complete. Human review and sign-on are now required.'
  if (stage === 'Signed') return 'The JHA has completed human review and sign-on.'
  if (stage === 'Review Required - Work Changed') return 'The planned work changed after review. The JHA must be reassessed.'
  return ''
})

function itemClass(done: boolean) {
  return done ? 'text-green-700' : 'text-ink-gray-5'
}

function criticalLabel(step: StepProgress) {
  if (step.critical_control_required) {
    return step.critical_owner_complete ? 'Critical owner' : 'Critical owner'
  }
  if (step.discussion_complete && step.critical_controls_reviewed) return 'Critical control N/A'
  return 'Critical control review'
}
</script>

<template>
  <section
    v-if="progress"
    class="rounded-7 border border-outline-gray-1 bg-surface-base p-4 shadow-sm"
  >
    <div class="flex items-start justify-between gap-3">
      <div>
        <p class="text-base-semibold text-ink-gray-9">JHA facilitation progress</p>
        <p class="mt-1 text-sm text-ink-gray-5">Persisted across refreshes and voice reconnects</p>
      </div>
      <Badge variant="subtle">{{ progress.stage }}</Badge>
    </div>

    <p v-if="stageHelp" class="mt-3 text-sm leading-5 text-ink-gray-6">
      {{ stageHelp }}
    </p>

    <div class="mt-4 flex items-center justify-between rounded-7 bg-surface-gray-1 px-3 py-2">
      <div>
        <p class="text-xs-semibold uppercase tracking-wide text-ink-gray-5">Job-step list</p>
        <p class="mt-0.5 text-sm-medium text-ink-gray-8">
          {{ progress.job_steps_confirmed ? 'Confirmed by crew' : 'Awaiting crew confirmation' }}
        </p>
      </div>
      <span
        class="text-lg-semibold"
        :class="progress.job_steps_confirmed ? 'text-green-700' : 'text-ink-gray-4'"
      >
        {{ progress.job_steps_confirmed ? '✓' : '○' }}
      </span>
    </div>

    <div v-if="steps.length" class="mt-3 space-y-2">
      <div
        v-for="step in steps"
        :key="step.name || step.sequence"
        class="rounded-7 border p-3"
        :class="step.is_current ? 'border-blue-300 bg-blue-50' : step.discussion_complete ? 'border-green-200 bg-green-50' : 'border-outline-gray-1 bg-surface-gray-1'"
      >
        <div class="flex items-start justify-between gap-3">
          <div class="min-w-0">
            <p class="text-sm-medium text-ink-gray-9">
              Step {{ step.sequence }} · {{ step.activity }}
            </p>
            <p v-if="step.is_current" class="mt-1 text-xs-medium text-blue-700">Current step</p>
            <p v-else-if="step.discussion_complete" class="mt-1 text-xs-medium text-green-700">Step complete</p>
            <p v-else class="mt-1 text-xs text-ink-gray-5">Not started / incomplete</p>
          </div>
          <span
            class="text-lg-semibold"
            :class="step.discussion_complete ? 'text-green-700' : step.is_current ? 'text-blue-700' : 'text-ink-gray-4'"
          >
            {{ step.discussion_complete ? '✓' : step.is_current ? '●' : '○' }}
          </span>
        </div>

        <div class="mt-3 grid grid-cols-2 gap-x-3 gap-y-1 text-xs sm:grid-cols-4">
          <span :class="itemClass(step.hazards_complete)">{{ step.hazards_complete ? '✓' : '○' }} Hazards</span>
          <span :class="itemClass(step.controls_complete)">{{ step.controls_complete ? '✓' : '○' }} Controls</span>
          <span :class="itemClass(step.critical_owner_complete)">{{ step.critical_owner_complete ? '✓' : '○' }} {{ criticalLabel(step) }}</span>
          <span :class="itemClass(step.hold_point_complete)">
            {{ step.hold_point_complete ? '✓' : '○' }} Hold point<span v-if="step.hold_point_complete">: {{ step.hold_point ? 'Yes' : 'No' }}</span>
          </span>
        </div>
      </div>
    </div>
  </section>
</template>

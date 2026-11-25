<script setup lang="ts">
import { nextTick, ref, useId } from 'vue'
import { Button } from 'frappe-ui'
import type { SubmissionIssue } from '../lib/submissionChecklist'

defineProps<{ issues: SubmissionIssue[]; disabled?: boolean }>()
const emit = defineEmits<{ navigate: [issue: SubmissionIssue] }>()
const expanded = ref(false)
const root = ref<HTMLElement | null>(null)
const listId = useId()
async function reveal() {
  expanded.value = true
  await nextTick()
  root.value?.scrollIntoView({ block: 'start', behavior: 'instant' })
  root.value?.focus({ preventScroll: true })
}
defineExpose({ reveal })
</script>

<template>
  <section ref="root" tabindex="-1" aria-label="Submission checklist" class="submission-checklist scroll-mt-3 rounded-7 border border-outline-gray-2 bg-surface-base p-3 focus:outline focus:outline-2 focus:outline-offset-2 focus:outline-outline-gray-3">
    <div class="flex items-center justify-between gap-3">
      <div class="min-w-0">
        <h2 class="text-sm-semibold text-ink-gray-9">Submission checklist</h2>
        <p role="status" class="mt-1 text-sm text-ink-gray-6">
          <template v-if="issues.length">{{ issues.length }} {{ issues.length === 1 ? 'item needs' : 'items need' }} attention</template>
          <template v-else><span class="lucide-circle-check mr-1 inline-block size-4 align-text-bottom text-ink-green-7" aria-hidden="true" />No missing required items</template>
        </p>
      </div>
      <Button v-if="issues.length" type="button" variant="subtle" class="shrink-0" :disabled="disabled" :aria-expanded="expanded" :aria-controls="listId" @click="expanded = !expanded">
        {{ expanded ? 'Hide' : 'Review' }}
      </Button>
    </div>
    <div v-if="expanded && issues.length" :id="listId" class="mt-3 space-y-2">
      <p class="text-xs text-ink-gray-5">Tap an item to go to its field or row. Your entries stay in this form.</p>
      <ul class="space-y-2">
        <li v-for="issue in issues" :key="issue.id">
          <button type="button" class="flex w-full items-center justify-between gap-3 rounded-5 border border-outline-gray-1 px-3 py-2 text-left hover:bg-surface-gray-1 focus-visible:outline focus-visible:outline-2 focus-visible:outline-outline-gray-3" :disabled="disabled" @click="emit('navigate', issue)">
            <span class="min-w-0 break-words [overflow-wrap:anywhere]">
              <span class="block text-sm-medium text-ink-gray-9">{{ issue.label }}</span>
              <span class="mt-0.5 block text-xs text-ink-gray-5">{{ issue.location }}</span>
              <span class="mt-1 block text-sm text-ink-red-7">{{ issue.message }}</span>
            </span>
            <span class="lucide-chevron-right size-4 shrink-0 text-ink-gray-5" aria-hidden="true" />
          </button>
        </li>
      </ul>
    </div>
  </section>
</template>

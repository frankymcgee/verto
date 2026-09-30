<script setup lang="ts">
import { Badge } from 'frappe-ui'

defineProps<{ searches?: Record<string, any>[] }>()
</script>

<template>
  <section v-if="searches?.length" class="rounded-7 border border-outline-gray-1 bg-surface-base p-4 shadow-sm">
    <p class="text-base-semibold text-ink-gray-9">Previous incidents & lessons</p>
    <p class="mt-1 text-sm leading-5 text-ink-gray-5">Discuss the investigation lessons and confirm suitable controls for this job.</p>

    <div v-for="(search, index) in searches" :key="`${search.hazard_identifier || 'preview'}-${index}`" class="mt-4 rounded-7 border border-outline-gray-1 p-3">
      <div class="flex flex-wrap items-center gap-2">
        <p class="text-sm-medium text-ink-gray-9">Step {{ search.work_step_sequence }}</p>
        <Badge v-if="search.preview" variant="subtle">Potential exposure</Badge>
        <Badge v-for="mechanism in search.signals?.mechanisms || []" :key="mechanism" variant="subtle">{{ mechanism }}</Badge>
      </div>
      <p v-if="search.signals?.critical_risks?.length" class="mt-2 text-xs leading-5 text-ink-gray-6">Risk categories considered: {{ search.signals.critical_risks.join(' · ') }}</p>

      <p v-if="search.status === 'unavailable'" class="mt-3 text-sm text-amber-800">Incident evidence is unavailable. Continue assessing the exposure with the crew.</p>
      <p v-else-if="!search.incidents?.length" class="mt-3 text-sm text-ink-gray-6">No relevant incident was found in the accessible dataset. Continue assessing the exposure with the crew.</p>
      <p v-if="search.search_limited" class="mt-2 text-xs text-amber-800">This search considered a limited set of matching records.</p>

      <article v-for="incident in search.incidents || []" :key="incident.name" class="mt-3 rounded-7 bg-surface-gray-1 p-3">
        <a :href="incident.record_url" target="_blank" rel="noopener" class="break-words text-sm-medium text-blue-700 underline">{{ incident.source_system }} · {{ incident.source_reference }}</a>
        <p class="mt-1 text-xs text-ink-gray-5">{{ [incident.incident_date, incident.site_name].filter(Boolean).join(' · ') }}</p>
        <p class="mt-2 text-sm-medium text-ink-gray-9">{{ incident.title }}</p>
        <p class="mt-1 whitespace-pre-wrap text-sm leading-5 text-ink-gray-7">{{ incident.incident_summary }}</p>
        <p v-if="incident.matched_on?.mechanisms?.length" class="mt-2 text-xs text-ink-gray-6">Matching mechanism: {{ incident.matched_on.mechanisms.join(' · ') }}</p>
        <p v-if="incident.source_changed" class="mt-2 text-xs text-amber-800">The incident record has changed since this lookup. Discuss the updated lesson.</p>
        <p v-if="incident.evidence_excerpt" class="mt-2 text-xs text-ink-gray-5">Evidence excerpts are shown. Open the incident record for the full investigation details.</p>

        <div v-if="incident.investigation_findings" class="mt-3">
          <p class="text-xs-semibold text-ink-gray-8">Investigation findings</p>
          <p class="mt-1 whitespace-pre-wrap text-sm leading-5 text-ink-gray-7">{{ incident.investigation_findings }}</p>
        </div>
        <div class="mt-3">
          <p class="text-xs-semibold text-ink-gray-8">Recorded investigation actions</p>
          <p v-if="incident.investigation_actions" class="mt-1 whitespace-pre-wrap text-sm leading-5 text-ink-gray-7">{{ incident.investigation_actions }}</p>
          <ul v-if="incident.actions?.length" class="mt-2 list-disc space-y-2 pl-4 text-sm leading-5 text-ink-gray-7">
            <li v-for="(action, actionIndex) in incident.actions" :key="action.source_action_reference || actionIndex">
              <span v-if="action.source_action_reference">{{ action.source_action_reference }} · </span>{{ action.action_description }}
              <p class="mt-0.5 text-xs text-ink-gray-5">{{ action.action_status || 'Status not recorded' }}</p>
              <p v-if="action.effectiveness_notes" class="mt-0.5 text-xs text-ink-gray-6">Effectiveness evidence: {{ action.effectiveness_notes }}</p>
            </li>
          </ul>
          <p v-if="!incident.actions_available" class="mt-1 text-sm text-ink-gray-5">Investigation actions were not recorded in this dataset.</p>
        </div>
        <div v-if="incident.recommended_controls" class="mt-3">
          <p class="text-xs-semibold text-ink-gray-8">Controls recorded in the investigation</p>
          <p class="mt-1 whitespace-pre-wrap text-sm leading-5 text-ink-gray-7">{{ incident.recommended_controls }}</p>
        </div>
      </article>
    </div>
  </section>
</template>

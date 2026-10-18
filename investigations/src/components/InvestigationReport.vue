<template>
  <article class="investigation-report">
    <header>
      <p>VERTO · INVESTIGATION REPORT · CONFIDENTIAL</p>
      <h1>{{ doc.title }}</h1>
      <p>{{ doc.name }} · {{ doc.method }} · {{ doc.status }}</p>
    </header>
    <dl class="report-facts">
      <template v-for="(value, label) in facts" :key="label"
        ><dt>{{ label }}</dt>
        <dd>{{ value || 'Not recorded' }}</dd></template
      >
    </dl>
    <h2>Incident and immediate response</h2>
    <h3>What happened</h3>
    <p>{{ doc.description }}</p>
    <h3>Immediate response</h3>
    <p>{{ doc.immediate_response }}</p>
    <h3>Reportability assessment: {{ doc.regulatory_review }}</h3>
    <p>{{ doc.reportability_notes }}</p>
    <p>{{ doc.regulator }} {{ doc.regulator_reference }}</p>
    <h2>Investigation team</h2>
    <p>Lead: {{ doc.lead_investigator }} · Reviewer: {{ doc.reviewer }}</p>
    <p v-for="member in doc.team" :key="member.user">{{ member.user }} — {{ member.team_role }}</p>
    <h2>Evidence register</h2>
    <section v-for="row in doc.evidence" :key="row.entry_id" class="report-item">
      <h3>{{ row.entry_id }} · {{ row.title }} · {{ row.verification_status }}</h3>
      <p>{{ row.evidence_type }} · {{ row.observed_at }}</p>
      <p>{{ row.notes }}</p>
      <p v-if="row.file">Attachment: {{ row.file }}</p>
      <p>
        Verification: {{ row.verification_notes }} · {{ row.verified_by }} {{ row.verified_on }}
      </p>
    </section>
    <h2>Timeline</h2>
    <p v-for="row in doc.timeline" :key="row.entry_id">
      {{ row.event_datetime }} — {{ row.description }} · Evidence: {{ row.evidence_refs }}
    </p>
    <template v-if="doc.method !== 'ICAM'"
      ><h2>5 Whys analysis</h2>
      <section v-for="row in doc.five_whys" :key="row.entry_id" class="report-item">
        <h3>
          {{ row.entry_id }} · {{ row.finding_status
          }}<span v-if="row.is_root_cause"> · Root cause</span>
        </h3>
        <p v-if="row.parent_id">Preceding why: {{ row.parent_id }}</p>
        <p>{{ row.description }}</p>
        <p>Evidence: {{ row.evidence_refs }}</p>
        <p v-if="row.is_root_cause">Stopping rationale: {{ row.root_cause_reason }}</p>
      </section></template
    >
    <template v-if="doc.method !== '5 Whys'"
      ><h2>ICAM analysis</h2>
      <section v-for="category in categories" :key="category">
        <h3>{{ category }}</h3>
        <div
          v-for="row in doc.icam_factors.filter((row) => row.category === category)"
          :key="row.entry_id"
          class="report-item"
        >
          <p>
            <strong>{{ row.entry_id }} · {{ row.finding_status }}</strong> {{ row.description }}
          </p>
          <p>Evidence: {{ row.evidence_refs }} · Contributes to: {{ row.contributes_to }}</p>
        </div>
        <p
          v-if="
            !doc.icam_factors.some(
              (row) => row.category === category && row.finding_status === 'Supported',
            )
          "
        >
          {{ doc.category_reviews.find((row) => row.category === category)?.no_finding_reason }}
        </p>
      </section></template
    >
    <h2>Findings and lessons</h2>
    <p>{{ doc.findings_summary }}</p>
    <h3>Lessons learned</h3>
    <p>{{ doc.lessons_learned }}</p>
    <h2>Corrective actions and effectiveness</h2>
    <section v-for="row in doc.actions" :key="row.entry_id" class="report-item">
      <h3>{{ row.entry_id }} · {{ row.title }} · {{ row.action_status }}</h3>
      <p>{{ row.details }}</p>
      <p>Findings: {{ row.finding_refs }} · Control: {{ row.control_type }}</p>
      <p>
        Owner: {{ row.assigned_to_user }} · Due: {{ row.due_date }} · Verifier: {{ row.verifier }} ·
        Verification due: {{ row.verification_due_date }}
      </p>
      <p>Effectiveness criteria: {{ row.success_criteria }}</p>
      <p>Completion: {{ row.completion_notes }} · {{ row.completed_by }} {{ row.completed_on }}</p>
      <p v-if="row.completion_file">Completion attachment: {{ row.completion_file }}</p>
      <p>
        Effectiveness: {{ row.verification_notes }} · {{ row.verified_by }} {{ row.verified_on }}
      </p>
      <p v-if="row.cancellation_reason">Cancellation: {{ row.cancellation_reason }}</p>
    </section>
    <h2>Review and close-out</h2>
    <p>{{ doc.review_notes }}</p>
    <p>Approved by {{ doc.approved_by || 'Not approved' }} {{ doc.approved_on }}</p>
    <p>{{ doc.closure_summary }}</p>
    <p>Closed by {{ doc.closed_by || 'Not closed' }} {{ doc.closed_on }}</p>
    <h2>Workflow history</h2>
    <p v-for="(event, index) in doc.history" :key="index">
      {{ event.recorded_at }} · {{ event.actor }} · {{ event.event }} — {{ event.notes }}
    </p>
  </article>
</template>
<script setup>
import { computed } from 'vue'
import { categories } from '../model'
const props = defineProps({ doc: { type: Object, required: true } })
const facts = computed(() => ({
  'Incident date/time': props.doc.incident_datetime,
  'Time precision': props.doc.incident_time_precision || 'Exact',
  Project: props.doc.project,
  'Site / area': props.doc.site_location,
  'Actual consequence': props.doc.actual_severity,
  'Potential consequence': props.doc.potential_severity,
  'Source incident': [props.doc.source_doctype, props.doc.source_name].filter(Boolean).join(' / '),
  'External reference': props.doc.external_reference,
  'Investigation due': props.doc.due_date,
}))
</script>

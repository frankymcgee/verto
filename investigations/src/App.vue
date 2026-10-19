<template>
  <FrappeUIProvider>
    <div class="investigations-app">
      <InvestigationShell
        :meta="meta"
        :record="doc"
        :tabs="tabs"
        :active-tab="tab"
        @navigate="navigate"
        @select-tab="selectTab"
        @open-app="openApp"
      >
        <Alert
          v-if="error && !operation"
          theme="red"
          title="The operation could not be completed"
          :description="error"
          dismissible
          role="alert"
          class="workspace-alert screen-only"
          @dismiss="error = ''"
        />
        <div v-if="!ready" class="loading-state screen-only">
          <Spinner v-if="!error" class="mx-auto mb-3 size-5" />
          {{
            error
              ? 'The investigations workspace could not be opened.'
              : 'Opening your investigations workspace…'
          }}
        </div>

        <main v-else-if="!doc" class="dashboard screen-only">
          <div class="page-heading">
            <div>
              <p class="eyebrow">SAFETY · ASSURANCE · LEARNING</p>
              <h1>Investigations</h1>
              <p>Establish the facts. Understand the causes. Verify the improvements.</p>
            </div>
            <Button variant="solid" :disabled="busy" @click="navigate('new')"
              >New investigation</Button
            >
          </div>
          <div class="metrics">
            <div>
              <span>Open investigations</span><strong>{{ totalOpen }}</strong>
            </div>
            <div>
              <span>Awaiting review</span><strong>{{ list.counts?.['In Review'] || 0 }}</strong>
            </div>
            <div>
              <span>Action follow-up</span
              ><strong>{{ list.counts?.['Actions in Progress'] || 0 }}</strong>
            </div>
            <div>
              <span>Closed</span><strong>{{ list.counts?.Closed || 0 }}</strong>
            </div>
          </div>
          <div class="list-toolbar">
            <FormControl
              size="md"
              class="search-field"
              v-model="filters.search"
              placeholder="Search title, reference or investigation number…"
              label="Search investigations"
              :disabled="busy"
              type="search"
            /><FormControl
              size="md"
              v-model="filters.status"
              type="select"
              label="Status"
              :options="[{ label: 'All statuses', value: '' }, ...(meta.statuses || [])]"
            /><FormControl
              size="md"
              v-model="filters.method"
              type="select"
              label="Analysis method"
              :options="[{ label: 'All methods', value: '' }, ...methods]"
            />
          </div>
          <p v-if="listLoading" class="help" role="status">Loading investigations…</p>
          <div v-if="!list.items?.length && !listLoading" class="empty-state">
            <div class="empty-symbol">⌕</div>
            <h2>
              {{
                filters.search || filters.status || filters.method
                  ? 'No matching investigations'
                  : 'Start with the facts'
              }}
            </h2>
            <p>
              {{
                filters.search || filters.status || filters.method
                  ? 'Change the search or filters to see other records you can access.'
                  : 'Create an investigation or link an existing EHS or shutdown incident.'
              }}
            </p>
            <Button
              v-if="!filters.search && !filters.status && !filters.method"
              variant="solid"
              @click="navigate('new')"
              :disabled="busy"
              >Create investigation</Button
            >
          </div>
          <div class="investigation-list">
            <ItemListRow
              as="button"
              v-for="item in list.items"
              :key="item.name"
              type="button"
              class="investigation-card"
              :disabled="busy"
              :aria-disabled="busy"
              @click="navigate(item.name)"
            >
              <div class="card-row">
                <div class="card-leading">
                  <span :class="['state-dot', statusClass(item.status)]"></span>
                  <div>
                    <div class="card-reference">
                      {{ item.name }} <span>{{ item.method }}</span>
                    </div>
                    <h2>{{ item.title }}</h2>
                    <p>
                      {{
                        [item.site_location, item.project].filter(Boolean).join(' · ') ||
                        'Location not recorded'
                      }}
                    </p>
                  </div>
                </div>
                <div class="card-meta">
                  <Badge :label="item.status" :theme="statusTheme(item.status)" /><span
                    v-if="item.due_date"
                    :class="{ overdue: item.due_date < list.today && item.status !== 'Closed' }"
                    >Due {{ dateLabel(item.due_date) }}</span
                  ><span>{{ item.open_actions || 0 }} open actions</span
                  ><span class="card-arrow" aria-hidden="true">→</span>
                </div>
              </div>
            </ItemListRow>
          </div>
          <div v-if="list.items?.length" class="pagination">
            <Button :disabled="pageStart === 0 || listLoading" @click="changePage(-25)"
              >Previous</Button
            ><span>{{ pageStart + 1 }}–{{ pageStart + list.items.length }}</span
            ><Button :disabled="!list.has_more || listLoading" @click="changePage(25)">Next</Button>
          </div>
        </main>

        <template v-else>
          <div class="record-heading screen-only">
            <div>
              <Button
                variant="ghost"
                icon-left="lucide-arrow-left"
                class="back-link"
                @click="navigate('')"
                :disabled="busy"
                >Investigations</Button
              >
              <div class="record-title">
                <h1>{{ doc.title || 'New investigation' }}</h1>
                <Badge :label="doc.status" :theme="statusTheme(doc.status)" />
              </div>
              <p>
                {{ doc.name || 'Unsaved draft' }} · {{ doc.method
                }}<span v-if="dirty" class="unsaved-dot"> · Unsaved changes</span>
              </p>
            </div>
            <div class="record-buttons">
              <Button v-if="doc.name" :disabled="busy" @click="printReport">Print / PDF</Button
              ><Button
                v-if="editable"
                variant="solid"
                :loading="busy"
                :disabled="busy"
                @click="save"
                >Save investigation</Button
              >
            </div>
          </div>
          <div class="record-layout screen-only">
            <div class="record-content">
              <div v-if="!editable" class="locked-note">
                {{
                  doc.status === 'In Review'
                    ? 'Submitted for independent review. The reviewer can approve it or return it for further work.'
                    : doc.status === 'Closed'
                      ? 'Investigation closed. Its findings, approvals and action history are retained.'
                      : 'Findings approved. Record action completion and verify effectiveness below.'
                }}
              </div>

              <section v-if="tab === 'overview'" class="workspace-panel">
                <div class="section-heading">
                  <div>
                    <p class="eyebrow">01 · ESTABLISH THE EVENT</p>
                    <h2>Incident overview</h2>
                  </div>
                </div>
                <fieldset :disabled="!editable || busy" class="form-grid">
                  <FormControl
                    size="md"
                    class="field span-2"
                    v-model="doc.title"
                    maxlength="140"
                    placeholder="A specific, factual description of the event"
                    label="Investigation title"
                    required
                    :disabled="!editable || busy"
                  /><FormControl
                    size="md"
                    class="field"
                    v-model="doc.method"
                    label="Analysis method"
                    :disabled="!editable || busy"
                    type="select"
                    :options="[...methods]"
                  /><FormControl
                    size="md"
                    class="field"
                    label="Incident date and time"
                    required
                    :disabled="!editable || busy"
                    v-model="doc.incident_datetime"
                    type="datetime"
                    format="YYYY-MM-DD HH:mm"
                  /><FormControl
                    size="md"
                    class="field"
                    v-model="doc.incident_time_precision"
                    label="Time precision"
                    :disabled="!editable || busy"
                    type="select"
                    :options="['Exact', 'Approximate', 'Date only']"
                  /><FormControl
                    size="md"
                    class="field"
                    v-model="doc.due_date"
                    label="Investigation due"
                    :disabled="!editable || busy"
                    type="date"
                  /><LookupField
                    v-model="doc.project"
                    label="Project"
                    kind="projects"
                    :disabled="!editable || busy"
                  /><FormControl
                    size="md"
                    class="field"
                    v-model="doc.site_location"
                    label="Site / work area"
                    :disabled="!editable || busy"
                  /><FormControl
                    size="md"
                    class="field"
                    v-model="doc.incident_type"
                    label="Incident type"
                    :disabled="!editable || busy"
                    type="select"
                    :options="[
                      ...[
                        'Injury or illness',
                        'Near miss',
                        'Equipment damage',
                        'Environmental',
                        'Process safety',
                        'Other',
                      ],
                    ]"
                  /><FormControl
                    size="md"
                    class="field"
                    v-model="doc.classification"
                    placeholder="For example, the client’s injury classification"
                    label="Client classification"
                    :disabled="!editable || busy"
                  /><FormControl
                    size="md"
                    v-for="field in ['actual_severity', 'potential_severity']"
                    :key="field"
                    class="field"
                    v-model="doc[field]"
                    :label="
                      field === 'actual_severity' ? 'Actual consequence' : 'Potential consequence'
                    "
                    :disabled="!editable || busy"
                    type="select"
                    :options="[{ label: 'Not assessed', value: '' }, ...severities]"
                  /><FormControl
                    size="md"
                    class="field span-2"
                    v-model="doc.description"
                    :rows="5"
                    placeholder="Describe the event, work and circumstances. Separate facts from assumptions."
                    label="What happened"
                    :disabled="!editable || busy"
                    type="textarea"
                  /><FormControl
                    size="md"
                    class="field span-2"
                    v-model="doc.immediate_response"
                    :rows="3"
                    placeholder="Record the response and immediate risk controls."
                    label="Immediate response"
                    :disabled="!editable || busy"
                    type="textarea"
                  />
                </fieldset>
                <details class="subsection" :open="Boolean(doc.source_name)">
                  <summary>Link an existing incident</summary>
                  <div class="form-grid">
                    <FormControl
                      size="md"
                      class="field"
                      v-model="doc.source_doctype"
                      :disabled="!editable || busy"
                      @update:modelValue="doc.source_name = ''"
                      label="Source type"
                      type="select"
                      :options="[
                        { label: 'Standalone investigation', value: '' },
                        'EHS Incident',
                        'Shutdown Incident Tracker',
                      ]"
                    /><LookupField
                      v-if="doc.source_doctype"
                      v-model="doc.source_name"
                      label="Source incident"
                      kind="sources"
                      :source-doctype="doc.source_doctype"
                      :disabled="!editable || busy"
                    /><FormControl
                      size="md"
                      class="field"
                      v-model="doc.external_reference"
                      :disabled="!editable || busy"
                      label="External incident reference"
                    />
                  </div>
                  <Button v-if="editable && doc.source_name" :disabled="busy" @click="useSource"
                    >Use incident details in empty fields</Button
                  >
                </details>
                <details class="subsection" open>
                  <summary>Reportability assessment</summary>
                  <fieldset :disabled="!editable || busy" class="form-grid">
                    <FormControl
                      size="md"
                      class="field"
                      v-model="doc.regulatory_review"
                      label="Assessment status"
                      :disabled="!editable || busy"
                      type="select"
                      :options="[
                        ...['Not assessed', 'Review required', 'Not reportable', 'Reportable'].map(
                          (status) => ({ label: `${status}`, value: `${status}` }),
                        ),
                      ]"
                    /><FormControl
                      size="md"
                      class="field"
                      v-model="doc.regulator"
                      label="Regulator"
                      :disabled="!editable || busy"
                    /><FormControl
                      size="md"
                      class="field"
                      v-model="doc.regulator_reference"
                      label="Notification / regulator reference"
                      :disabled="!editable || busy"
                    /><FormControl
                      size="md"
                      class="field span-2"
                      v-model="doc.reportability_notes"
                      :rows="3"
                      placeholder="Record the authorised assessment, reasons and any notification details."
                      label="Assessment basis and notification record"
                      :disabled="!editable || busy"
                      type="textarea"
                    />
                  </fieldset>
                </details>
                <div v-if="editable && doc.name" class="section-footer">
                  <Button
                    v-if="['Draft', 'Reopened'].includes(doc.status)"
                    @click="workflow('gather_evidence')"
                    :disabled="busy"
                    >Begin evidence gathering</Button
                  ><Button
                    v-if="['Draft', 'Evidence Gathering', 'Reopened'].includes(doc.status)"
                    @click="workflow('analyse')"
                    :disabled="busy"
                    >Begin analysis</Button
                  >
                </div>
              </section>

              <section v-if="tab === 'team'" class="workspace-panel">
                <div class="section-heading">
                  <div>
                    <p class="eyebrow">RESPONSIBILITY & ACCESS</p>
                    <h2>Investigation team</h2>
                    <p>Assigned investigators can contribute. Observers can read the record.</p>
                  </div>
                  <Button
                    v-if="editable"
                    @click="doc.team.push({ user: '', team_role: 'Investigator' })"
                    :disabled="busy"
                    >Add member</Button
                  >
                </div>
                <div class="form-grid">
                  <LookupField
                    v-model="doc.lead_investigator"
                    label="Lead investigator"
                    kind="users"
                    :disabled="!editable || busy"
                  /><LookupField
                    v-model="doc.reviewer"
                    label="Independent reviewer"
                    kind="reviewers"
                    :disabled="!editable || busy"
                  />
                </div>
                <div v-for="(member, index) in doc.team" :key="index" class="team-row">
                  <LookupField
                    v-model="member.user"
                    label="Team member"
                    kind="users"
                    :disabled="!editable || busy"
                  /><FormControl
                    size="md"
                    class="field"
                    v-model="member.team_role"
                    :disabled="!editable || busy"
                    label="Investigation role"
                    type="select"
                    :options="['Investigator', 'Subject matter expert', 'Observer']"
                  /><Button
                    v-if="editable"
                    theme="red"
                    @click="doc.team.splice(index, 1)"
                    :disabled="busy"
                    >Remove</Button
                  >
                </div>
                <p class="help">
                  The reviewer needs Verto Investigation Manager access and must be different from
                  the lead investigator. Action owners and verifiers must belong to this team.
                </p>
              </section>

              <section v-if="tab === 'evidence'" class="workspace-panel">
                <div class="section-heading">
                  <div>
                    <p class="eyebrow">
                      PEOPLE · ENVIRONMENT · EQUIPMENT · PROCEDURES · ORGANISATION
                    </p>
                    <h2>Evidence register</h2>
                    <p>Record the source, observations and verification basis.</p>
                  </div>
                  <Button v-if="editable" @click="addEvidence" :disabled="busy"
                    >Add evidence</Button
                  >
                </div>
                <div v-if="!doc.evidence.length" class="inline-empty">
                  Add statements, photographs, documents, equipment records and other evidence.
                </div>
                <article
                  v-for="(row, index) in doc.evidence"
                  :key="row.entry_id"
                  class="entry-card"
                >
                  <div class="entry-heading">
                    <code>{{ row.entry_id }}</code
                    ><Button
                      v-if="editable"
                      theme="red"
                      @click="removeEntry('evidence', index)"
                      :disabled="busy"
                      >Remove</Button
                    >
                  </div>
                  <fieldset :disabled="!editable || busy" class="form-grid">
                    <FormControl
                      size="md"
                      class="field span-2"
                      v-model="row.title"
                      label="Evidence title"
                      :disabled="!editable || busy"
                    /><FormControl
                      size="md"
                      class="field"
                      v-model="row.evidence_type"
                      label="PEEPO category"
                      :disabled="!editable || busy"
                      type="select"
                      :options="[
                        ...[
                          'People',
                          'Environment',
                          'Equipment',
                          'Procedures',
                          'Organisation',
                          'Other',
                        ],
                      ]"
                    /><FormControl
                      size="md"
                      class="field"
                      label="Observed / recorded time"
                      :disabled="!editable || busy"
                      v-model="row.observed_at"
                      type="datetime"
                      format="YYYY-MM-DD HH:mm"
                    /><FormControl
                      size="md"
                      class="field span-2"
                      v-model="row.notes"
                      :rows="3"
                      label="Facts and observations"
                      :disabled="!editable || busy"
                      type="textarea"
                    /><FormControl
                      size="md"
                      class="field"
                      v-model="row.verification_status"
                      label="Evidence status"
                      :disabled="!editable || busy"
                      type="select"
                      :options="['Unverified', 'Verified', 'Disputed']"
                    /><FormControl
                      size="md"
                      class="field"
                      v-model="row.verification_notes"
                      :rows="2"
                      placeholder="How was this evidence checked?"
                      label="Verification basis"
                      :disabled="!editable || busy"
                      type="textarea"
                    />
                  </fieldset>
                  <div class="file-row">
                    <a v-if="row.file" :href="row.file" target="_blank" rel="noopener"
                      >Open private evidence attachment ↗</a
                    ><PrivateFileInput
                      v-if="editable && doc.name"
                      :label="row.file ? 'Replace attachment' : 'Attach file'"
                      :disabled="busy"
                      @change="attach(row, 'file', $event)"
                    />
                    <span v-else-if="editable" class="help"
                      >Save the draft before attaching files.</span
                    >
                  </div>
                  <p v-if="row.verified_by" class="help">
                    Verified by {{ row.verified_by }} · {{ dateLabel(row.verified_on, true) }}
                  </p>
                </article>
              </section>

              <section v-if="tab === 'timeline'" class="workspace-panel">
                <div class="section-heading">
                  <div>
                    <p class="eyebrow">SEQUENCE & CONTEXT</p>
                    <h2>Event timeline</h2>
                    <p>Build the sequence from evidence, including conditions before the event.</p>
                  </div>
                  <Button
                    v-if="editable"
                    @click="
                      doc.timeline.push({
                        entry_id: id('T'),
                        event_datetime: '',
                        description: '',
                        evidence_refs: '',
                      })
                    "
                    :disabled="busy"
                    >Add event</Button
                  >
                </div>
                <div v-if="!doc.timeline.length" class="inline-empty">
                  Record what happened before, during and after the incident.
                </div>
                <article
                  v-for="(row, index) in doc.timeline"
                  :key="row.entry_id"
                  class="entry-card"
                >
                  <div class="entry-heading">
                    <code>{{ row.entry_id }}</code
                    ><Button
                      v-if="editable"
                      theme="red"
                      @click="doc.timeline.splice(index, 1)"
                      :disabled="busy"
                      >Remove</Button
                    >
                  </div>
                  <fieldset :disabled="!editable || busy" class="form-grid">
                    <FormControl
                      size="md"
                      class="field"
                      label="Event time"
                      :disabled="!editable || busy"
                      v-model="row.event_datetime"
                      type="datetime"
                      format="YYYY-MM-DD HH:mm"
                    /><FormControl
                      size="md"
                      class="field span-2"
                      v-model="row.description"
                      :rows="2"
                      label="Event or condition"
                      :disabled="!editable || busy"
                      type="textarea"
                    />
                  </fieldset>
                  <ReferencePicker
                    v-model="row.evidence_refs"
                    :items="doc.evidence"
                    :disabled="!editable || busy"
                  />
                </article>
              </section>

              <section v-if="tab === 'whys'" class="workspace-panel">
                <div class="section-heading">
                  <div>
                    <p class="eyebrow">FOLLOW THE CAUSAL PATH</p>
                    <h2>5 Whys</h2>
                    <p>
                      Branch when several causes contributed. Continue until the stopping point is
                      supported by evidence.
                    </p>
                  </div>
                  <Button v-if="editable" @click="addWhy('')" :disabled="busy"
                    >Add causal branch</Button
                  >
                </div>
                <div class="problem-statement">
                  <span>Starting event</span>
                  <p>
                    {{ doc.description || 'Record what happened in the incident overview first.' }}
                  </p>
                </div>
                <div v-if="!doc.five_whys.length" class="inline-empty">
                  Start with why the event occurred. Each answer becomes the starting point for the
                  next why.
                </div>
                <article
                  v-for="({ row, depth }, index) in whyTree(doc.five_whys)"
                  :key="row.entry_id"
                  class="entry-card why-card"
                  :style="{ '--depth': Math.min(depth, 5) }"
                >
                  <div class="entry-heading">
                    <span class="why-number">Why {{ depth + 1 }}</span
                    ><code>{{ row.entry_id }}</code
                    ><Button
                      v-if="editable"
                      theme="red"
                      @click="removeEntry('five_whys', doc.five_whys.indexOf(row))"
                      :disabled="busy"
                      >Remove</Button
                    >
                  </div>
                  <p v-if="row.parent_id" class="preceding-cause">
                    Because:
                    {{
                      doc.five_whys.find((item) => item.entry_id === row.parent_id)?.description ||
                      row.parent_id
                    }}
                  </p>
                  <fieldset :disabled="!editable || busy" class="form-grid">
                    <FormControl
                      size="md"
                      class="field span-2"
                      v-model="row.description"
                      :rows="3"
                      placeholder="Describe a specific cause and how it contributed."
                      label="Why did this happen?"
                      :disabled="!editable || busy"
                      type="textarea"
                    /><FormControl
                      size="md"
                      class="field"
                      v-model="row.finding_status"
                      label="Finding status"
                      :disabled="!editable || busy"
                      type="select"
                      :options="['Hypothesis', 'Supported', 'Not supported']"
                    /><Checkbox
                      class="check-line root-cause-toggle"
                      v-model="row.is_root_cause"
                      :true-value="1"
                      :false-value="0"
                      label="Identified root cause"
                      :disabled="!editable || busy"
                      type="checkbox"
                    /><FormControl
                      size="md"
                      v-if="row.is_root_cause"
                      class="field span-2"
                      v-model="row.root_cause_reason"
                      :rows="2"
                      placeholder="Explain the evidence and systemic issue addressed at this point."
                      label="Why can the analysis stop here?"
                      :disabled="!editable || busy"
                      type="textarea"
                    />
                  </fieldset>
                  <ReferencePicker
                    v-model="row.evidence_refs"
                    :items="doc.evidence"
                    :disabled="!editable || busy"
                  /><Button v-if="editable" @click="addWhy(row.entry_id)" :disabled="busy"
                    >Add next why</Button
                  >
                </article>
              </section>

              <section v-if="tab === 'icam'" class="workspace-panel">
                <div class="section-heading">
                  <div>
                    <p class="eyebrow">CONTROLS · ACTIONS · CONDITIONS · SYSTEMS</p>
                    <h2>ICAM analysis</h2>
                    <p>
                      Start with the defences, then examine actions, conditions and organisational
                      influences.
                    </p>
                  </div>
                </div>
                <IcamMap :factors="doc.icam_factors" />
                <section
                  v-for="(category, categoryIndex) in categories"
                  :key="category"
                  class="icam-category"
                >
                  <div class="section-heading">
                    <h3>
                      <span class="category-index">{{ categoryIndex + 1 }}</span
                      >{{ category }}
                    </h3>
                    <Button v-if="editable" @click="addFactor(category)" :disabled="busy"
                      >Add factor</Button
                    >
                  </div>
                  <p class="help">{{ categoryPrompts[categoryIndex] }}</p>
                  <article
                    v-for="row in doc.icam_factors.filter((row) => row.category === category)"
                    :key="row.entry_id"
                    class="entry-card"
                  >
                    <div class="entry-heading">
                      <code>{{ row.entry_id }}</code
                      ><Button
                        v-if="editable"
                        theme="red"
                        @click="removeEntry('icam_factors', doc.icam_factors.indexOf(row))"
                        :disabled="busy"
                        >Remove</Button
                      >
                    </div>
                    <fieldset :disabled="!editable || busy" class="form-grid">
                      <FormControl
                        size="md"
                        class="field span-2"
                        v-model="row.description"
                        :rows="3"
                        label="Contributing factor and relationship to the event"
                        :disabled="!editable || busy"
                        type="textarea"
                      /><FormControl
                        size="md"
                        class="field"
                        v-model="row.finding_status"
                        label="Finding status"
                        :disabled="!editable || busy"
                        type="select"
                        :options="['Hypothesis', 'Supported', 'Not supported']"
                      />
                    </fieldset>
                    <ReferencePicker
                      v-model="row.evidence_refs"
                      :items="doc.evidence"
                      :disabled="!editable || busy"
                    /><ReferencePicker
                      v-model="row.contributes_to"
                      label="This factor contributes to"
                      :items="
                        doc.icam_factors
                          .filter((item) => item.entry_id !== row.entry_id)
                          .map((item) => ({ ...item, title: item.description }))
                      "
                      :disabled="!editable || busy"
                      empty-text="Add another factor to connect the causal pathway."
                    />
                  </article>
                  <FormControl
                    size="md"
                    v-if="
                      !doc.icam_factors.some(
                        (row) => row.category === category && row.finding_status === 'Supported',
                      )
                    "
                    class="field"
                    :disabled="!editable || busy"
                    :rows="2"
                    label="Reason no supported factor has been identified"
                    type="textarea"
                    v-model="categoryReview(category).no_finding_reason"
                  />
                </section>
              </section>

              <section v-if="tab === 'actions'" class="workspace-panel">
                <div class="section-heading">
                  <div>
                    <p class="eyebrow">IMPLEMENT & VERIFY</p>
                    <h2>Corrective actions</h2>
                    <p>
                      Connect each action to its finding and define how effectiveness will be
                      checked.
                    </p>
                  </div>
                  <Button v-if="editable" @click="addAction" :disabled="busy">Add action</Button>
                </div>
                <div v-if="!doc.actions.length" class="inline-empty">
                  Create actions for the supported causes and factors identified in your analysis.
                </div>
                <article
                  v-for="(row, index) in doc.actions"
                  :key="row.entry_id"
                  class="entry-card action-card"
                >
                  <div class="entry-heading">
                    <code>{{ row.entry_id }}</code
                    ><Badge
                      :label="row.action_status"
                      :theme="statusTheme(row.action_status)"
                    /><Button
                      v-if="editable && row.action_status === 'Open'"
                      theme="red"
                      @click="doc.actions.splice(index, 1)"
                      :disabled="busy"
                      >Remove</Button
                    >
                  </div>
                  <fieldset
                    :disabled="!editable || busy || row.action_status !== 'Open'"
                    class="form-grid"
                  >
                    <FormControl
                      size="md"
                      class="field span-2"
                      v-model="row.title"
                      label="Action"
                      :disabled="!editable || busy || row.action_status !== 'Open'"
                    /><FormControl
                      size="md"
                      class="field span-2"
                      v-model="row.details"
                      :rows="3"
                      label="Implementation details"
                      :disabled="!editable || busy || row.action_status !== 'Open'"
                      type="textarea"
                    /><FormControl
                      size="md"
                      class="field"
                      v-model="row.assigned_to_user"
                      label="Action owner"
                      :disabled="!editable || busy || row.action_status !== 'Open'"
                      type="select"
                      :options="[{ label: 'Select a team member', value: '' }, ...contributors]"
                    /><FormControl
                      size="md"
                      class="field"
                      v-model="row.due_date"
                      label="Action due date"
                      :disabled="!editable || busy || row.action_status !== 'Open'"
                      type="date"
                    /><FormControl
                      size="md"
                      class="field"
                      v-model="row.control_type"
                      label="Hierarchy of control"
                      :disabled="!editable || busy || row.action_status !== 'Open'"
                      type="select"
                      :options="[{ label: 'Select control type', value: '' }, ...controls]"
                    /><FormControl
                      size="md"
                      class="field"
                      v-model="row.priority"
                      label="Priority"
                      :disabled="!editable || busy || row.action_status !== 'Open'"
                      type="select"
                      :options="['Low', 'Medium', 'High', 'Critical']"
                    /><FormControl
                      size="md"
                      class="field span-2"
                      v-model="row.success_criteria"
                      :rows="2"
                      placeholder="What observation, measurement or test will show this control is effective?"
                      label="Effectiveness criteria"
                      :disabled="!editable || busy || row.action_status !== 'Open'"
                      type="textarea"
                    /><FormControl
                      size="md"
                      class="field"
                      v-model="row.verifier"
                      label="Independent verifier"
                      :disabled="!editable || busy || row.action_status !== 'Open'"
                      type="select"
                      :options="[
                        { label: 'Select a different team member', value: '' },
                        ...contributors.filter((user) => user !== row.assigned_to_user),
                      ]"
                    /><FormControl
                      size="md"
                      class="field"
                      v-model="row.verification_due_date"
                      label="Effectiveness review due"
                      :disabled="!editable || busy || row.action_status !== 'Open'"
                      type="date"
                    />
                  </fieldset>
                  <ReferencePicker
                    v-model="row.finding_refs"
                    label="Findings addressed"
                    :items="supportedFindings(doc)"
                    :disabled="!editable || busy || row.action_status !== 'Open'"
                    empty-text="Mark supported root causes or ICAM factors before linking actions."
                  />
                  <div v-if="row.completion_notes" class="action-outcome">
                    <strong>Completion evidence</strong>
                    <p>{{ row.completion_notes }}</p>
                    <a
                      v-if="row.completion_file"
                      :href="row.completion_file"
                      target="_blank"
                      rel="noopener"
                      >Open private attachment ↗</a
                    ><small>{{ row.completed_by }} · {{ dateLabel(row.completed_on, true) }}</small>
                  </div>
                  <div v-if="row.verification_notes" class="action-outcome">
                    <strong>Effectiveness review</strong>
                    <p>{{ row.verification_notes }}</p>
                    <small v-if="row.verified_by"
                      >{{ row.verified_by }} · {{ dateLabel(row.verified_on, true) }}</small
                    >
                  </div>
                  <p v-if="row.cancellation_reason" class="help">
                    Cancellation reason: {{ row.cancellation_reason }}
                  </p>
                  <div class="action-buttons">
                    <Button
                      v-if="row.can_complete"
                      :disabled="busy"
                      @click="actionOperation(row, 'complete')"
                      >Record completion</Button
                    ><Button
                      v-if="row.can_verify"
                      variant="solid"
                      :disabled="busy"
                      @click="actionOperation(row, 'verify')"
                      >Verify effective</Button
                    ><Button
                      v-if="row.can_verify"
                      :disabled="busy"
                      @click="actionOperation(row, 'ineffective')"
                      >Further work required</Button
                    ><Button
                      v-if="row.can_cancel"
                      theme="red"
                      :disabled="busy"
                      @click="actionOperation(row, 'cancel')"
                      >Cancel action</Button
                    >
                    <Button
                      v-if="row.can_reassign"
                      :disabled="busy"
                      @click="actionOperation(row, 'reassign')"
                      >Reassign responsibilities</Button
                    >
                  </div>
                </article>
              </section>

              <section v-if="tab === 'review'" class="workspace-panel">
                <div class="section-heading">
                  <div>
                    <p class="eyebrow">FINDINGS · APPROVAL · CLOSE-OUT</p>
                    <h2>Review and learning</h2>
                  </div>
                </div>
                <fieldset :disabled="!editable || busy" class="form-grid">
                  <FormControl
                    size="md"
                    class="field span-2"
                    v-model="doc.findings_summary"
                    :rows="5"
                    label="Findings summary"
                    :disabled="!editable || busy"
                    type="textarea"
                  /><FormControl
                    size="md"
                    class="field span-2"
                    v-model="doc.lessons_learned"
                    :rows="4"
                    label="Lessons learned"
                    :disabled="!editable || busy"
                    type="textarea"
                  />
                </fieldset>
                <div class="readiness-box">
                  <div class="section-heading">
                    <h3>
                      {{
                        doc.status === 'Actions in Progress'
                          ? 'Close-out checks'
                          : 'Review readiness'
                      }}
                    </h3>
                    <Button v-if="editable" :disabled="busy" @click="save">Save and check</Button>
                  </div>
                  <p v-if="dirty || !doc.name" class="help">
                    Save the draft to refresh these checks.
                  </p>
                  <ul v-else-if="checks.length">
                    <li v-for="check in checks" :key="check">{{ check }}</li>
                  </ul>
                  <p v-else class="ready-message">{{ readinessMessage }}</p>
                </div>
                <div class="action-buttons">
                  <Button
                    v-if="editable"
                    variant="solid"
                    :disabled="busy || !doc.name"
                    @click="workflow('submit_review')"
                    >Submit for review</Button
                  ><Button
                    v-if="doc.capabilities.can_review"
                    variant="solid"
                    :disabled="busy"
                    @click="decision('approve')"
                    >Approve findings and actions</Button
                  ><Button
                    v-if="doc.capabilities.can_review"
                    :disabled="busy"
                    @click="decision('return')"
                    >Return for further work</Button
                  ><Button
                    v-if="doc.capabilities.can_withdraw"
                    :disabled="busy"
                    @click="decision('withdraw_review')"
                    >Withdraw for revision</Button
                  ><Button
                    v-if="doc.capabilities.can_close"
                    variant="solid"
                    :disabled="busy || doc.closure_readiness.length > 0"
                    @click="decision('close')"
                    >Close investigation</Button
                  ><Button
                    v-if="doc.capabilities.can_reopen"
                    :disabled="busy"
                    @click="decision('reopen')"
                    >Reopen investigation</Button
                  >
                </div>
                <div v-if="doc.review_notes" class="action-outcome">
                  <strong>Review decision</strong>
                  <p>{{ doc.review_notes }}</p>
                  <small v-if="doc.approved_by"
                    >Approved by {{ doc.approved_by }} ·
                    {{ dateLabel(doc.approved_on, true) }}</small
                  >
                </div>
                <div v-if="doc.closure_summary" class="action-outcome">
                  <strong>Close-out summary</strong>
                  <p>{{ doc.closure_summary }}</p>
                  <small>{{ doc.closed_by }} · {{ dateLabel(doc.closed_on, true) }}</small>
                </div>
                <h3 class="history-title">Workflow history</h3>
                <div v-if="!doc.history.length" class="help">
                  Workflow decisions will appear here.
                </div>
                <div
                  v-for="(event, index) in [...doc.history].reverse()"
                  :key="index"
                  class="history-entry"
                >
                  <span class="state-dot"></span>
                  <div>
                    <strong>{{ event.event }}</strong>
                    <p>{{ event.notes }}</p>
                    <small>{{ event.actor }} · {{ dateLabel(event.recorded_at, true) }}</small>
                  </div>
                </div>
              </section>
            </div>
          </div>
        </template>
      </InvestigationShell>
      <InvestigationReport v-if="doc" :doc="doc" />
      <Dialog
        :open="!!operation"
        :title="operationTitle"
        :dismissible="!busy"
        :show-close-button="!busy"
        @update:open="closeOperation"
      >
        <div v-if="operation" class="decision-panel">
          <Dialog.Description class="text-p-sm text-ink-gray-6">
            Record your decision and the evidence or reasons supporting it.
          </Dialog.Description>
          <Alert
            v-if="error"
            theme="red"
            title="Could not record decision"
            :description="error"
            role="alert"
          />
          <p v-if="operation.type === 'action'">Action {{ operation.entry_id }}</p>
          <div v-if="operation.action === 'reassign'" class="form-grid">
            <FormControl
              size="md"
              class="field"
              v-model="operationOwner"
              :disabled="operation.completed || busy"
              label="Action owner"
              type="select"
              :options="[...contributors]"
            />
            <FormControl
              size="md"
              class="field"
              v-model="operationVerifier"
              :disabled="busy"
              label="Independent verifier"
              type="select"
              :options="[
                { label: 'Select a team member', value: '' },
                ...contributors.filter(
                  (user) => user !== operationOwner && user !== operation.completed_by,
                ),
              ]"
            />
          </div>
          <FormControl
            size="md"
            class="field"
            v-model="operationNotes"
            :rows="4"
            :label="
              operation.action === 'complete'
                ? 'What was done and what evidence demonstrates completion?'
                : operation.action === 'verify'
                  ? 'What evidence shows the action met its effectiveness criteria?'
                  : 'Decision, reasons and supporting evidence'
            "
            :disabled="busy"
            type="textarea"
          /><PrivateFileInput
            v-if="operation.action === 'complete'"
            label="Optional private completion attachment"
            :disabled="busy"
            @change="attachOperation"
          />
          <p v-if="operationFile" class="help">Attachment uploaded</p>
          <div class="action-buttons">
            <Button
              variant="solid"
              :disabled="busy || !operationNotes.trim()"
              :loading="busy"
              @click="confirmOperation"
              >Record decision</Button
            ><Button :disabled="busy" @click="operation = null">Cancel</Button>
          </div>
        </div>
      </Dialog>
      <Dialog
        :open="!!pendingNavigation"
        title="Discard unsaved changes?"
        message="Your investigation has unsaved changes. Discard them and leave this page?"
        @update:open="
          (open) => {
            if (!open) pendingNavigation = null
          }
        "
      >
        <template #actions>
          <div class="flex justify-end gap-2">
            <Button @click="pendingNavigation = null" :disabled="busy">Keep editing</Button>
            <Button theme="red" variant="solid" @click="discardAndNavigate" :disabled="busy"
              >Discard changes</Button
            >
          </div>
        </template>
      </Dialog>
    </div>
  </FrappeUIProvider>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import {
  Alert,
  Badge,
  Button,
  Checkbox,
  Dialog,
  FormControl,
  FrappeUIProvider,
  ItemListRow,
  Spinner,
  toast,
} from 'frappe-ui'
import { call, uploadFile } from './api'
import InvestigationShell from './components/InvestigationShell.vue'
import PrivateFileInput from './components/PrivateFileInput.vue'
import {
  categories,
  clearReferences,
  controls,
  draft,
  id,
  methods,
  removeWhy,
  supportedFindings,
  whyTree,
} from './model'
import LookupField from './components/LookupField.vue'
import ReferencePicker from './components/ReferencePicker.vue'
import IcamMap from './components/IcamMap.vue'
import InvestigationReport from './components/InvestigationReport.vue'

const meta = ref({ apps: [] }),
  ready = ref(false),
  busy = ref(false),
  error = ref('')
const doc = ref(null),
  savedSnapshot = ref(''),
  tab = ref('overview'),
  list = ref({ items: [], counts: {} })
const filters = ref({ search: '', status: '', method: '' }),
  pageStart = ref(0),
  listLoading = ref(false)
const operation = ref(null),
  operationNotes = ref(''),
  operationFile = ref(''),
  operationOwner = ref(''),
  operationVerifier = ref('')
const pendingNavigation = ref(null)
const severities = ['Minor', 'Moderate', 'Serious', 'Major', 'Severe', 'Catastrophic']
const categoryPrompts = [
  'Identify the barriers or safeguards that were absent or did not prevent the outcome.',
  'Describe the actions in their work context and explain how they contributed.',
  'Examine the task, equipment, environment and local conditions influencing the work.',
  'Identify the systems, decisions or arrangements that created or sustained the contributing conditions.',
]
const editable = computed(() => !!doc.value?.capabilities?.can_edit)
const dirty = computed(() => doc.value && JSON.stringify(doc.value) !== savedSnapshot.value)
const contributors = computed(() => [
  ...new Set(
    [
      doc.value?.lead_investigator,
      doc.value?.reviewer,
      ...(doc.value?.team || [])
        .filter((row) => row.team_role !== 'Observer')
        .map((row) => row.user),
    ].filter(Boolean),
  ),
])
const checks = computed(() =>
  doc.value?.status === 'Actions in Progress'
    ? doc.value.closure_readiness
    : doc.value?.readiness || [],
)
const readinessMessage = computed(() =>
  doc.value?.status === 'Closed'
    ? 'This investigation is closed. The review and action evidence are retained below.'
    : doc.value?.status === 'In Review'
      ? 'Awaiting the appointed reviewer’s decision.'
      : doc.value?.status === 'Actions in Progress'
        ? 'All actions have been verified or cancelled with a reason.'
        : 'The recorded investigation is ready for independent review.',
)
const totalOpen = computed(() =>
  Object.entries(list.value.counts || {})
    .filter(([status]) => status !== 'Closed')
    .reduce((sum, [, total]) => sum + Number(total), 0),
)
const tabs = computed(() => [
  { key: 'overview', label: 'Incident overview' },
  { key: 'team', label: 'Investigation team' },
  { key: 'evidence', label: 'Evidence register' },
  { key: 'timeline', label: 'Event timeline' },
  ...(doc.value?.method !== 'ICAM' ? [{ key: 'whys', label: '5 Whys' }] : []),
  ...(doc.value?.method !== '5 Whys' ? [{ key: 'icam', label: 'ICAM analysis' }] : []),
  { key: 'actions', label: 'Corrective actions' },
  { key: 'review', label: 'Review & close-out' },
])
const operationTitle = computed(
  () =>
    ({
      approve: 'Approve investigation findings',
      return: 'Return for further investigation',
      close: 'Close investigation',
      reopen: 'Reopen investigation',
      complete: 'Record action completion',
      verify: 'Verify action effectiveness',
      ineffective: 'Record further work required',
      cancel: 'Cancel corrective action',
      reassign: 'Reassign action responsibilities',
      withdraw_review: 'Withdraw investigation for revision',
    })[operation.value?.action] || 'Record decision',
)
let filterTimer,
  routeGeneration = 0,
  listGeneration = 0,
  lastRoute = location.hash || '#/'
function selectTab(key) {
  if (busy.value) return
  tab.value = key
  operation.value = null
}
function statusClass(value) {
  return String(value || '')
    .toLowerCase()
    .replaceAll(' ', '-')
}
function statusTheme(value) {
  return (
    {
      'In Review': 'amber',
      'Actions in Progress': 'blue',
      Closed: 'green',
      Verified: 'green',
      Completed: 'blue',
      Cancelled: 'gray',
      Reopened: 'red',
    }[value] || 'gray'
  )
}
function dateLabel(value, time = false) {
  if (!value) return 'Not recorded'
  const raw = String(value)
  // A date-only deadline is a calendar day, not UTC midnight.
  const date = new Date(/^\d{4}-\d{2}-\d{2}$/.test(raw) ? `${raw}T12:00:00` : raw.replace(' ', 'T'))
  return Number.isNaN(date.getTime())
    ? value
    : new Intl.DateTimeFormat(undefined, {
        dateStyle: 'medium',
        ...(time ? { timeStyle: 'short' } : {}),
      }).format(date)
}
function setDoc(value) {
  doc.value = value
  savedSnapshot.value = JSON.stringify(value)
}
function flash(message) {
  toast.success(message)
}
async function run(job) {
  if (busy.value) return false
  busy.value = true
  error.value = ''
  try {
    await job()
    return true
  } catch (failure) {
    error.value = failure.message || 'The operation could not be completed.'
    return false
  } finally {
    busy.value = false
  }
}
async function fetchList() {
  const current = ++listGeneration
  listLoading.value = true
  try {
    const result = await call('list_investigations', { ...filters.value, start: pageStart.value })
    if (current === listGeneration) list.value = result
  } catch (failure) {
    if (current === listGeneration) error.value = failure.message
  } finally {
    if (current === listGeneration) listLoading.value = false
  }
}
function changePage(amount) {
  pageStart.value = Math.max(0, pageStart.value + amount)
  fetchList()
}
watch(
  filters,
  () => {
    clearTimeout(filterTimer)
    pageStart.value = 0
    filterTimer = setTimeout(fetchList, 250)
  },
  { deep: true },
)
async function loadRoute() {
  const current = ++routeGeneration
  const name = decodeURIComponent((location.hash || '#/').replace(/^#\/?/, ''))
  operation.value = null
  tab.value = 'overview'
  if (!name) {
    setDoc(null)
    await fetchList()
  } else if (name === 'new') setDoc(draft(meta.value.user))
  else {
    const result = await call('get_investigation', { name })
    if (current === routeGeneration) setDoc(result)
  }
  lastRoute = location.hash || '#/'
}
async function followNavigation(target) {
  if (target.external) {
    window.location.assign(target.href)
    return
  }
  history[target.replace ? 'replaceState' : 'pushState'](null, '', target.hash)
  await run(loadRoute)
}
async function requestNavigation(target) {
  if (busy.value) return
  if (dirty.value) {
    pendingNavigation.value = target
    return
  }
  await followNavigation(target)
}
async function navigate(name) {
  await requestNavigation({ hash: '#/' + encodeURIComponent(name) })
}
async function openApp(href) {
  await requestNavigation({ external: true, href })
}
async function discardAndNavigate() {
  const target = pendingNavigation.value
  pendingNavigation.value = null
  if (target) await followNavigation(target)
}
async function routeChanged() {
  const hash = location.hash || '#/'
  if (dirty.value) history.replaceState(null, '', lastRoute)
  await requestNavigation({ hash, replace: true })
}
function beforeUnload(event) {
  if (dirty.value) {
    event.preventDefault()
    event.returnValue = ''
  }
}
async function persist() {
  if (!doc.value?.title?.trim() || !doc.value.incident_datetime)
    throw new Error('Enter an investigation title and incident date/time.')
  const result = await call('save_investigation', {
    data: doc.value,
    expected_modified: doc.value.modified,
  })
  setDoc(result)
  lastRoute = '#/' + encodeURIComponent(result.name)
  history.replaceState(null, '', lastRoute)
}
async function save() {
  await run(async () => {
    await persist()
    flash('Investigation saved')
  })
}
async function workflow(action) {
  await run(async () => {
    if (dirty.value) await persist()
    setDoc(
      await call('transition', {
        name: doc.value.name,
        action,
        expected_modified: doc.value.modified,
      }),
    )
    if (action === 'submit_review') tab.value = 'review'
    if (action === 'analyse') tab.value = doc.value.method === 'ICAM' ? 'icam' : 'whys'
    flash('Investigation updated')
  })
}
function categoryReview(category) {
  return (
    doc.value.category_reviews.find((row) => row.category === category) || {
      category,
      no_finding_reason: '',
    }
  )
}
function addEvidence() {
  doc.value.evidence.push({
    entry_id: id('E'),
    title: '',
    evidence_type: 'Other',
    verification_status: 'Unverified',
    notes: '',
    verification_notes: '',
  })
}
function addWhy(parent_id) {
  const parent = doc.value.five_whys.find((row) => row.entry_id === parent_id)
  if (parent) parent.is_root_cause = 0
  doc.value.five_whys.push({
    entry_id: id('W'),
    parent_id,
    description: '',
    finding_status: 'Hypothesis',
    evidence_refs: '',
    is_root_cause: 0,
    root_cause_reason: '',
  })
}
function addFactor(category) {
  doc.value.icam_factors.push({
    entry_id: id('F'),
    category,
    description: '',
    finding_status: 'Hypothesis',
    evidence_refs: '',
    contributes_to: '',
  })
}
function addAction() {
  doc.value.actions.push({
    entry_id: id('A'),
    title: '',
    details: '',
    action_status: 'Open',
    priority: 'Medium',
    finding_refs: '',
    assigned_to_user: '',
    verifier: '',
    control_type: '',
  })
}
function removeEntry(table, index) {
  const row = doc.value[table][index]
  if (table === 'five_whys') doc.value.five_whys = removeWhy(doc.value.five_whys, row.entry_id)
  else doc.value[table].splice(index, 1)
  clearReferences(doc.value, row.entry_id)
}
async function attach(row, field, event) {
  const file = event.target.files?.[0]
  if (!file || !doc.value.name) return
  await run(async () => {
    row[field] = await uploadFile(file, doc.value.name)
    flash('Private attachment uploaded. Save the investigation to retain its evidence reference.')
  })
  event.target.value = ''
}
async function useSource() {
  await run(async () => {
    const details = await call('get_source_details', {
      source_doctype: doc.value.source_doctype,
      source_name: doc.value.source_name,
    })
    const copyingTime = !doc.value.incident_datetime && details.incident_datetime
    for (const [field, value] of Object.entries(details))
      if (!doc.value[field] && value) doc.value[field] = value
    if (copyingTime && details.incident_time_precision)
      doc.value.incident_time_precision = details.incident_time_precision
    flash('Source details added to empty fields. Check the incident date and time.')
  })
}
async function decision(action) {
  error.value = ''
  operation.value = { type: 'transition', action }
  operationNotes.value = ''
  operationFile.value = ''
}
async function actionOperation(row, action) {
  error.value = ''
  operation.value = {
    type: 'action',
    action,
    entry_id: row.entry_id,
    completed: row.action_status === 'Completed',
    completed_by: row.completed_by,
  }
  operationNotes.value = ''
  operationFile.value = ''
  operationOwner.value = row.assigned_to_user
  operationVerifier.value = row.verifier
}
async function attachOperation(event) {
  const file = event.target.files?.[0]
  if (file)
    await run(async () => {
      operationFile.value = await uploadFile(file, doc.value.name)
    })
}
function closeOperation(open) {
  if (!open && !busy.value) operation.value = null
}
async function confirmOperation() {
  await run(async () => {
    if (dirty.value) await persist()
    const op = operation.value
    const result = await call(op.type === 'action' ? 'update_action' : 'transition', {
      name: doc.value.name,
      action: op.action,
      expected_modified: doc.value.modified,
      notes: operationNotes.value,
      ...(op.type === 'action'
        ? {
            entry_id: op.entry_id,
            file_url: operationFile.value || null,
            ...(op.action === 'reassign'
              ? { assigned_to_user: operationOwner.value, verifier: operationVerifier.value }
              : {}),
          }
        : {}),
    })
    setDoc(result)
    operation.value = null
    flash('Decision recorded')
  })
}
async function printReport() {
  await run(async () => {
    if (dirty.value) await persist()
    await nextTick()
    window.print()
  })
}
onMounted(async () => {
  await run(async () => {
    meta.value = await call('get_bootstrap')
    ready.value = true
    await loadRoute()
  })
  window.addEventListener('hashchange', routeChanged)
  window.addEventListener('beforeunload', beforeUnload)
})
onBeforeUnmount(() => {
  routeGeneration++
  listGeneration++
  clearTimeout(filterTimer)
  window.removeEventListener('hashchange', routeChanged)
  window.removeEventListener('beforeunload', beforeUnload)
})
</script>

<!-- VERTO_HOME_APP_BROWSER_DRAWER_2026_06_11 -->
<!-- VERTO_HOME_HANDOVER_TYPE_FROM_BASE_FIX_2026_06_11 -->
<template>
  <section class="h-full min-h-0 bg-surface-gray-1">
    <main class="space-y-3 px-[var(--verto-page-x,0.75rem)] py-[var(--verto-page-y,0.75rem)]">
      <!-- Loading State -->
      <Card
        v-if="loading"
        class="p-3"
      >
        <div class="space-y-3">
          <div class="h-4 w-36 rounded bg-surface-gray-3" />
          <div class="h-24 rounded-xl bg-surface-gray-2" />
          <div class="h-24 rounded-xl bg-surface-gray-2" />
          <div class="h-24 rounded-xl bg-surface-gray-2" />
        </div>
      </Card>

      <!-- Error State -->
      <Card
        v-else-if="error"
        class="border border-red-200 bg-red-50 p-3"
      >
        <div class="space-y-2">
          <p class="text-sm font-medium text-red-800">
            Could not load assigned work
          </p>

          <p class="text-sm text-red-700">
            {{ error }}
          </p>
        </div>
      </Card>

      <template v-else>
        <!-- Refresh Row -->
        <div class="flex items-center justify-end">
          <Button
            variant="subtle"
            theme="gray"
            size="sm"
            :loading="loading"
            :disabled="loading"
            @click="loadHome"
          >
            Refresh
          </Button>
        </div>

        <!-- Empty State -->
        <Card
          v-if="groupedTasks.length === 0"
          class="p-3"
        >
          <div class="rounded-xl border border-dashed border-outline-gray-2 bg-surface-gray-1 px-3 py-6 text-center">
            <p class="text-sm font-medium text-ink-gray-7">
              No tasks allocated.
            </p>

            <p class="mt-1 text-sm text-ink-gray-5">
              Assigned work will appear here when it is allocated to you.
            </p>
          </div>
        </Card>

        <!-- Scope Groups -->
        <Card
          v-for="scope in groupedTasks"
          :key="scope.scope_name"
          class="overflow-hidden border border-outline-gray-1 bg-surface-white !py-1 !px-1 !mt-1"
        >
          <!-- Scope Header -->
          <button
            type="button"
            class="flex w-full items-center justify-between gap-3 border-b border-outline-gray-1 px-3 py-3 text-left active:scale-[0.99]"
            @click="toggleScope(scope.scope_name)"
          >
            <div class="min-w-0">
              <p class="truncate text-base font-semibold text-ink-gray-9">
                {{ scope.scope_name }}
              </p>

              <p class="mt-1 truncate text-xs text-ink-gray-5">
                {{ getProjectCustomer(scope) }}
              </p>
            </div>

            <div class="flex shrink-0 items-center gap-2">
              <div
                class="flex h-10 w-10 items-center justify-center overflow-hidden rounded-full border border-outline-gray-1 bg-surface-gray-2"
              >
                <img
                  v-if="getCustomerImage(scope)"
                  :src="getCustomerImage(scope)"
                  :alt="getProjectCustomer(scope) || 'Customer'"
                  class="h-full w-full object-cover"
                  @error="hideBrokenImage"
                >

                <span
                  v-else
                  class="text-sm font-semibold text-ink-gray-6"
                >
                  {{ getCustomerInitials(scope) }}
                </span>
              </div>

              <span class="text-xl font-medium text-ink-gray-5">
                {{ openScopes[scope.scope_name] ? '−' : '+' }}
              </span>
            </div>
          </button>

          <!-- Scope Body -->
          <div
            v-if="openScopes[scope.scope_name]"
            class="space-y-3 p-2"
          >
            <!-- Parent Groups -->
            <Card
              v-for="parent in scope.parent_groups"
              :key="parent.parent_task_name"
              class="overflow-hidden border border-outline-gray-1 bg-surface-gray-1 !py-1 !px-1 !mt-1"
            >
              <button
                type="button"
                class="w-full px-3 py-3 text-left active:scale-[0.99]"
                @click="toggleParent(getParentKey(scope, parent))"
              >
                <div class="flex items-start justify-between gap-3">
                  <div class="min-w-0">
                    <p class="truncate text-sm font-semibold text-ink-gray-9">
                      {{ parent.parent_task_name }}
                    </p>
                    <p class="mt-1 text-xs text-ink-gray-5">
                      Area Location
                    </p>
                  </div>

                  <span class="shrink-0 text-lg font-medium text-ink-gray-5">
                    {{ openParents[getParentKey(scope, parent)] ? '−' : '+' }}
                  </span>
                </div>

                <div class="mt-3 h-2 overflow-hidden rounded-full bg-surface-gray-3">
                  <div
                    class="h-full rounded-full bg-blue-600 transition-all"
                    :style="{ width: `${clampPercent(parent.progress || 0)}%` }"
                  />
                </div>
              </button>

              <div
                v-if="openParents[getParentKey(scope, parent)]"
                class="space-y-3 border-t border-outline-gray-1 bg-surface-white p-2"
              >
                <Button
                  variant="subtle"
                  theme="gray"
                  class="w-full justify-center"
                  @click.stop="openInternalUrl(getAreaGanttUrl(parent), 'Area Gantt')"
                >
                  Area Gantt
                </Button>

                <!-- Tasks -->
                <Card
                  v-for="task in parent.tasks"
                  :key="task.name"
                  class="overflow-hidden border border-outline-gray-1 bg-surface-white !py-1 !px-1 !mt-1"
                >
                  <div class="space-y-3 p-3">
                    <div class="flex items-start justify-between gap-3">
                      <div class="min-w-0 flex-1">
                        <h3 class="text-base font-semibold text-ink-gray-9">
                          {{ task.subject || task.name }}
                        </h3>

                        <p class="mt-1 text-xs text-ink-gray-5">
                          {{ formatDate(task.exp_start_date) }}
                          {{ formatTime(task.exp_start_time) }}
                          -
                          {{ formatDate(task.exp_end_date) }}
                          {{ formatTime(task.exp_end_time) }}
                        </p>
                      </div>

                      <Badge
                        v-if="task.status"
                        variant="subtle"
                      >
                        {{ task.status }}
                      </Badge>
                    </div>

                    <div>
                      <div
                        class="h-2 overflow-hidden rounded-full"
                        :style="{ backgroundColor: getPriorityColor(task.priority) }"
                      >
                        <div
                          class="h-full rounded-full bg-black/20 transition-all"
                          :style="{ width: `${clampPercent(task.progress || 0)}%` }"
                        />
                      </div>

                      <div class="mt-1 flex items-center justify-between text-xs text-ink-gray-5">
                        <span>{{ task.priority || 'No priority' }}</span>
                        <span>{{ clampPercent(task.progress || 0) }}%</span>
                      </div>
                    </div>

                    <div class="flex flex-wrap gap-2">
                      <Badge
                        v-if="task.responsible_contractor"
                        variant="subtle"
                      >
                        Vendor: {{ task.responsible_contractor }}
                      </Badge>

                      <Badge
                        v-if="task.work_order_number"
                        variant="subtle"
                      >
                        WO: {{ task.work_order_number }}
                      </Badge>
                    </div>

                    <div
                      v-if="task.checklist?.length"
                      class="overflow-hidden rounded-xl border border-outline-gray-1 bg-surface-gray-1"
                    >
                      <div class="flex items-center justify-between gap-3 border-b border-outline-gray-1 px-3 py-2">
                        <p class="text-xs font-semibold uppercase tracking-wide text-ink-gray-6">
                          Checklist
                        </p>

                        <p class="text-xs font-medium text-ink-gray-5">
                          {{ getCompletedChecklistCount(task) }}/{{ getChecklistItemCount(task) }} complete
                        </p>
                      </div>

                      <div class="divide-y divide-outline-gray-1">
                        <div
                          v-for="item in (task.checklist || [])"
                          :key="item.name"
                        >
                          <label
                            class="flex min-h-11 cursor-pointer items-start gap-3 px-3 py-2.5 active:bg-surface-gray-2"
                            :class="{
                              'cursor-wait opacity-60': isChecklistItemPending(task, item),
                              'cursor-default': isChecklistItemAwaitingEvidence(task, item),
                            }"
                          >
                            <Checkbox
                              class="mt-0.5 shrink-0"
                              size="md"
                              :model-value="isChecklistItemComplete(item)"
                              :disabled="isChecklistItemBusy(task, item)"
                              @update:model-value="(checked) => toggleChecklistItem(parent, task, item, Boolean(checked))"
                            />

                            <span
                              class="min-w-0 flex-1 text-sm leading-5"
                              :class="isChecklistItemComplete(item)
                                ? 'text-ink-gray-5 line-through'
                                : 'text-ink-gray-8'"
                            >
                              {{ item.description }}
                            </span>

                            <span
                              v-if="isChecklistItemPending(task, item)"
                              class="shrink-0 text-xs text-ink-gray-5"
                            >
                              Saving…
                            </span>
                          </label>

                          <p
                            v-if="getChecklistItemError(task, item)"
                            class="px-3 pb-2 text-xs text-red-700"
                          >
                            {{ getChecklistItemError(task, item) }}
                          </p>
                        </div>
                      </div>
                    </div>

                    <div class="grid grid-cols-2 gap-2 pt-1">
                      <Button
                        variant="solid"
                        theme="gray"
                        class="w-full justify-center"
                        @click="openPicker('form', task)"
                      >
                        + Form
                      </Button>

                      <Button
                        variant="subtle"
                        theme="gray"
                        class="w-full justify-center"
                        @click="openPicker('ccv', task)"
                      >
                        + CCV
                      </Button>
                    </div>
                  </div>
                </Card>
              </div>
            </Card>

            <div
              class="grid gap-2"
              :class="projectToolDefinitions.length ? 'grid-cols-2' : 'grid-cols-1'"
            >
              <Button
                v-if="projectToolDefinitions.length"
                variant="subtle"
                theme="gray"
                class="w-full justify-center"
                @click="openProjectTools(scope)"
              >
                Project Tools
              </Button>

              <Button
                variant="solid"
                theme="gray"
                class="w-full justify-center"
                @click="analyseProjectWithPeri(scope)"
              >
                Analyse with PERI
              </Button>
            </div>
          </div>
        </Card>

        <!-- Generic Form Button -->
        <Button
          variant="solid"
          theme="gray"
          size="lg"
          class="w-full justify-center"
          @click="openPicker('generic')"
        >
          + Form
        </Button>
      </template>
    </main>

    <!-- Project Tools Sheet -->
    <Teleport to="body">
      <Transition name="drawer-fade-slide">
        <div
          v-if="projectToolsOpen && projectToolsScope"
          class="bottom-sheet-overlay fixed inset-0 z-[60] flex items-end bg-black/40"
          @click.self="closeProjectTools"
        >
          <Card class="bottom-sheet-panel drawer-panel flex w-full min-w-0 flex-col overflow-hidden rounded-b-none rounded-t-3xl border border-outline-gray-1 bg-surface-white shadow-2xl">
          <div class="z-10 flex shrink-0 items-center justify-between border-b border-outline-gray-1 bg-surface-white px-4 py-3">
            <div class="min-w-0">
              <h2 class="truncate text-lg font-semibold text-ink-gray-9">
                Project Tools
              </h2>

              <p class="mt-1 truncate text-sm text-ink-gray-5">
                {{ projectToolsProjectName }}
              </p>
            </div>

            <Button
              variant="subtle"
              theme="gray"
              @click="closeProjectTools"
            >
              Close
            </Button>
          </div>

          <div class="bottom-sheet-body grid grid-cols-2 content-start gap-3 p-4 pb-[calc(env(safe-area-inset-bottom)+2rem)] sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 2xl:grid-cols-6">
            <button
              v-for="tool in projectToolDefinitions"
              :key="tool.key"
              type="button"
              class="min-h-24 rounded-xl border border-outline-gray-1 bg-surface-white p-3 text-left shadow-sm transition hover:border-outline-gray-2 hover:bg-surface-gray-1 active:scale-[0.99]"
              @click="openProjectTool(tool.key)"
            >
              <p class="text-sm font-semibold text-ink-gray-9">
                {{ tool.label }}
              </p>

              <p class="mt-1 text-xs leading-4 text-ink-gray-5">
                {{ tool.description }}
              </p>
            </button>
          </div>
          </Card>
        </div>
      </Transition>
    </Teleport>

    <!-- Picker Sheet -->
    <Teleport to="body">
      <Transition name="drawer-fade-slide">
        <div
          v-if="pickerOpen"
          class="bottom-sheet-overlay fixed inset-0 z-[60] flex items-end bg-black/40"
          @click.self="closePicker"
        >
          <Card class="bottom-sheet-panel drawer-panel flex w-full min-w-0 flex-col overflow-hidden rounded-b-none rounded-t-3xl border border-outline-gray-1 bg-surface-white shadow-2xl">
        <div class="z-10 flex shrink-0 items-center justify-between border-b border-outline-gray-1 bg-surface-white px-4 py-3">
          <div class="min-w-0">
            <h2 class="truncate text-lg font-semibold text-ink-gray-9">
              {{ pickerTitle }}
            </h2>

            <p
              v-if="pickerTask?.subject"
              class="mt-1 truncate text-sm text-ink-gray-5"
            >
              {{ pickerTask.subject }}
            </p>
          </div>

          <Button
            variant="subtle"
            theme="gray"
            @click="closePicker"
          >
            Close
          </Button>
        </div>

        <div class="bottom-sheet-body grid grid-cols-1 content-start gap-2 p-4 pb-[calc(env(safe-area-inset-bottom)+2rem)] sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          <button
            v-for="button in pickerButtons"
            :key="button.mobile_doctype"
            type="button"
            class="w-full rounded-xl border border-outline-gray-1 bg-surface-white p-3 text-left shadow-sm transition hover:border-outline-gray-2 hover:bg-surface-gray-1 active:scale-[0.99]"
            @click="createFromPicker(button)"
          >
            <p class="font-semibold text-ink-gray-9">
              {{ button.label }}
            </p>

            <p class="mt-1 text-xs text-ink-gray-5">
              {{ button.doctype }}
            </p>
          </button>

          <div
            v-if="pickerButtons.length === 0"
            class="rounded-xl border border-dashed border-outline-gray-2 bg-surface-gray-1 px-4 py-6 text-center sm:col-span-2 lg:col-span-3 xl:col-span-4"
          >
            <p class="text-sm font-medium text-ink-gray-7">
              No forms available.
            </p>

            <p class="mt-1 text-sm text-ink-gray-5">
              Check the mobile form configuration for this action.
            </p>
          </div>
        </div>
          </Card>
        </div>
      </Transition>
    </Teleport>

    <!-- Personnel Sheet -->
    <Teleport to="body">
      <Transition name="drawer-fade-slide">
        <div
          v-if="personnelOpen"
          class="bottom-sheet-overlay fixed inset-0 z-[60] flex items-end bg-black/40"
          @click.self="closePersonnelDrawer"
        >
          <Card class="bottom-sheet-panel drawer-panel flex w-full min-w-0 flex-col overflow-hidden rounded-b-none rounded-t-3xl border border-outline-gray-1 bg-surface-white shadow-2xl">
          <div class="z-10 flex shrink-0 items-center justify-between border-b border-outline-gray-1 bg-surface-white px-4 py-3">
            <div class="min-w-0">
              <h2 class="truncate text-lg font-semibold text-ink-gray-9">
                Project Personnel
              </h2>

              <p
                v-if="personnelProjectTitle"
                class="mt-1 truncate text-sm text-ink-gray-5"
              >
                {{ personnelProjectTitle }}
              </p>
            </div>

            <Button
              variant="subtle"
              theme="gray"
              @click="closePersonnelDrawer"
            >
              Close
            </Button>
          </div>

          <div class="bottom-sheet-body space-y-3 p-4 pb-[calc(env(safe-area-inset-bottom)+2rem)]">
            <div
              v-if="personnelLoading"
              class="space-y-2"
            >
              <div class="h-20 rounded-xl bg-surface-gray-2" />
              <div class="h-20 rounded-xl bg-surface-gray-2" />
              <div class="h-20 rounded-xl bg-surface-gray-2" />
            </div>

            <div
              v-else-if="personnelError"
              class="rounded-xl border border-red-200 bg-red-50 px-4 py-3"
            >
              <p class="text-sm font-medium text-red-800">
                Could not load project personnel.
              </p>

              <p class="mt-1 text-sm text-red-700">
                {{ personnelError }}
              </p>
            </div>

            <div
              v-else-if="personnelRows.length === 0"
              class="rounded-xl border border-dashed border-outline-gray-2 bg-surface-gray-1 px-4 py-6 text-center"
            >
              <p class="text-sm font-medium text-ink-gray-7">
                No personnel found.
              </p>

              <p class="mt-1 text-sm text-ink-gray-5">
                No submitted shift allocations were found for this project.
              </p>
            </div>

            <div
              v-else
              class="space-y-2"
            >
              <div
                v-for="person in personnelRows"
                :key="person.employee || person.employee_name || person.user_id"
                class="rounded-xl border border-outline-gray-1 bg-surface-white p-3 shadow-sm"
              >
                <div class="flex items-start gap-3">
                  <div class="flex h-11 w-11 shrink-0 items-center justify-center overflow-hidden rounded-full bg-surface-gray-2">
                    <img
                      v-if="person.image"
                      :src="person.image"
                      :alt="person.employee_name || 'Personnel'"
                      class="h-full w-full object-cover"
                      @error="hideBrokenImage"
                    >

                    <span
                      v-else
                      class="text-sm font-semibold text-ink-gray-7"
                    >
                      {{ getPersonnelInitials(person) }}
                    </span>
                  </div>

                  <div class="min-w-0 flex-1">
                    <div class="flex items-start justify-between gap-2">
                      <div class="min-w-0">
                        <p class="truncate text-sm font-semibold text-ink-gray-9">
                          {{ person.employee_name || person.employee || 'Unknown personnel' }}
                        </p>

                        <p
                          v-if="getPersonnelSubtitle(person)"
                          class="mt-0.5 truncate text-xs text-ink-gray-5"
                        >
                          {{ getPersonnelSubtitle(person) }}
                        </p>
                      </div>

                      <span
                        v-if="getPersonnelShiftLabel(person)"
                        :class="getPersonnelShiftBadgeClass(person)"
                      >
                        {{ getPersonnelShiftLabel(person) }}
                      </span>
                    </div>

                    <p
                      v-if="formatPersonnelDateRange(person)"
                      class="mt-2 text-xs text-ink-gray-5"
                    >
                      {{ formatPersonnelDateRange(person) }}
                    </p>

                    <div
                      v-if="person.contact_number || person.email"
                      class="mt-3 grid grid-cols-1 gap-2"
                    >
                      <a
                        v-if="person.contact_number"
                        :href="`tel:${normaliseTel(person.contact_number)}`"
                        class="block rounded-lg border border-outline-gray-1 bg-surface-gray-1 px-3 py-2 text-sm font-medium text-ink-gray-8"
                      >
                        Call {{ person.contact_number }}
                      </a>

                      <a
                        v-if="person.email"
                        :href="`mailto:${person.email}`"
                        class="block rounded-lg border border-outline-gray-1 bg-surface-gray-1 px-3 py-2 text-sm font-medium text-ink-gray-8"
                      >
                        {{ person.email }}
                      </a>
                    </div>

                    <p
                      v-else
                      class="mt-3 text-xs text-ink-gray-5"
                    >
                      No contact details available.
                    </p>
                  </div>
                </div>
              </div>
            </div>

          </div>
          </Card>
        </div>
      </Transition>
    </Teleport>

    <input
      ref="checklistEvidenceInput"
      type="file"
      class="hidden"
      accept="image/*,.pdf,.doc,.docx,.xls,.xlsx,.csv,.txt,.odt,.ods"
      @change="handleChecklistEvidenceSelected"
      @cancel="cancelChecklistEvidenceSelection"
    >

    <Teleport to="body">
      <Transition name="checklist-toast">
        <div
          v-if="checklistToast"
          class="bottom-toast fixed inset-x-0 bottom-0 z-[80] w-full rounded-b-none rounded-t-2xl border border-b-0 bg-surface-white px-4 pt-3 pb-[calc(env(safe-area-inset-bottom)+0.75rem)] shadow-2xl"
          :class="getChecklistToastClass(checklistToast.tone)"
          :role="checklistToast.tone === 'error' ? 'alert' : 'status'"
          aria-live="polite"
        >
          <div class="flex items-start gap-3">
            <div class="min-w-0 flex-1">
              <p class="text-sm font-semibold text-ink-gray-9">
                {{ checklistToast.title }}
              </p>

              <p class="mt-1 text-sm leading-5 text-ink-gray-6">
                {{ checklistToast.message }}
              </p>
            </div>

            <button
              type="button"
              class="shrink-0 rounded-md px-1.5 py-1 text-xs font-medium text-ink-gray-5 hover:bg-surface-gray-2 hover:text-ink-gray-8"
              @click="dismissChecklistToast"
            >
              {{ checklistEvidenceRequest ? 'Not now' : 'Close' }}
            </button>
          </div>

          <Button
            v-if="checklistToast.actionLabel"
            variant="solid"
            theme="gray"
            size="sm"
            class="mt-3 w-full justify-center"
            @click="chooseChecklistEvidence"
          >
            {{ checklistToast.actionLabel }}
          </Button>
        </div>
      </Transition>
    </Teleport>
  </section>
</template>

<script setup lang="ts">
// VERTO_HOME_ACTION_BUTTONS_V1
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  Badge,
  Button,
  Card,
  Checkbox,
} from 'frappe-ui'
import { apiRequest } from '../lib/api'
import { openAppBrowser } from '../lib/appBrowser'

type HomeButton = {
  label: string
  doctype: string
  mobile_doctype: string
}

type ChecklistItem = {
  name: string
  description: string
  completed: number | boolean | string
  completed_by?: string | null
  completed_on?: string | null
}

type ChecklistEvidenceRequest = {
  parent: ParentGroup
  task: TaskItem
  item: ChecklistItem
}

type ChecklistToastTone = 'info' | 'success' | 'error'

type ChecklistToastState = {
  title: string
  message: string
  tone: ChecklistToastTone
  actionLabel?: string
  persistent?: boolean
}

type TaskItem = {
  name: string
  progress?: number | string
  checklist?: ChecklistItem[]
  [key: string]: any
}

type ProjectDetails = {
  name?: string
  project_name?: string
  title?: string
  status?: string
  gameplan_team_name?: string
  gameplan_project?: string
  raven_channel?: string
  raven_channel_id?: string
  channel_id?: string
  raven_workspace?: string
  roster_or_shutdown?: string
  customer?: string
  customer_name?: string
  client?: string
  client_name?: string
  customer_image?: string
  image?: string
  [key: string]: any
}

type ParentGroup = {
  parent_task_name: string
  parent_task: string
  progress: number
  project: string
  project_details: ProjectDetails
  tasks: TaskItem[]
}

type ScopeGroup = {
  scope_name: string
  project: string
  project_details: ProjectDetails
  parent_groups: ParentGroup[]
  customer?: string
}

type ProjectToolKey =
  | 'gantt'
  | 'map'
  | 'folder'
  | 'handover'
  | 'personnel'
  | 'gameplan'
  | 'chat'

type ProjectToolDefinition = {
  key: ProjectToolKey
  label: string
  description: string
}

type HomePayload = {
  user: string
  full_name?: string
  user_full_name?: string
  user_fullname?: string
  user_name?: string
  employee_name?: string
  handover_base: string
  raven_base: string
  grouped_tasks: ScopeGroup[]
  generic_forms: HomeButton[]
  task_forms: HomeButton[]
  ccv_forms: HomeButton[]
  project_tools?: ProjectToolDefinition[]
}

type FrappeResponse<T> = {
  message: T
}

type PeriChannelResponse = {
  channel?: string | Record<string, any>
  name?: string
  channel_id?: string
  channel_name?: string
  message?: string | Record<string, any>
}

type ProjectHandoverResponse = {
  doctype: string
  mobile_doctype: string
  name: string
  route?: string
  created?: boolean
  requested_doctype?: string
  handover_base?: string
}

type ProjectPersonnelItem = {
  employee?: string
  employee_name?: string
  user_id?: string
  email?: string
  contact_number?: string
  image?: string
  designation?: string
  department?: string
  shift_type?: string
  shift_label?: string
  shift_kind?: 'day' | 'night' | 'mixed' | ''
  start_date?: string
  end_date?: string
}

type ProjectPersonnelResponse = {
  personnel: ProjectPersonnelItem[]
  project?: string
  project_name?: string
  matched_shift_count?: number
}

type ChecklistUpdateResponse = {
  task: string
  item: ChecklistItem
  checklist: ChecklistItem[]
  completed_count: number
  total_count: number
  progress: number | string
  parent_task?: string | null
  parent_progress?: number | string | null
  evidence?: {
    name: string
    file_name: string
    file_url: string
    is_private: number | boolean
  } | null
}

const router = useRouter()

const loading = ref(true)
const error = ref('')
const home = ref<HomePayload | null>(null)
const checklistPending = ref<Record<string, boolean>>({})
const checklistErrors = ref<Record<string, string>>({})
const checklistEvidenceInput = ref<HTMLInputElement | null>(null)
const checklistEvidenceRequest = ref<ChecklistEvidenceRequest | null>(null)
const checklistToast = ref<ChecklistToastState | null>(null)

let checklistToastTimer: number | undefined

const openScopes = ref<Record<string, boolean>>({})
const openParents = ref<Record<string, boolean>>({})

const projectToolsOpen = ref(false)
const projectToolsScope = ref<ScopeGroup | null>(null)

const defaultProjectToolDefinitions: ProjectToolDefinition[] = [
  { key: 'gantt', label: 'Gantt', description: 'View the project schedule.' },
  { key: 'map', label: 'Map', description: 'View Work Summary locations.' },
  { key: 'folder', label: 'Folder', description: 'Open shared project files.' },
  { key: 'handover', label: 'Handover', description: 'Open the project handover.' },
  { key: 'personnel', label: 'Personnel', description: 'View allocated personnel.' },
  { key: 'gameplan', label: 'Gameplan', description: 'Open project collaboration.' },
  { key: 'chat', label: 'Chat', description: 'Open the project channel.' },
]

const pickerOpen = ref(false)
const pickerType = ref<'generic' | 'form' | 'ccv'>('generic')
const pickerTask = ref<TaskItem | null>(null)

const personnelOpen = ref(false)
const personnelLoading = ref(false)
const personnelError = ref('')
const personnelProjectTitle = ref('')
const personnelRows = ref<ProjectPersonnelItem[]>([])

const groupedTasks = computed(() => {
  return home.value?.grouped_tasks || []
})

const projectToolDefinitions = computed<ProjectToolDefinition[]>(() => {
  if (!home.value || home.value.project_tools === undefined) {
    return defaultProjectToolDefinitions
  }

  return home.value.project_tools
})

const projectToolsProjectName = computed(() => {
  if (!projectToolsScope.value) {
    return ''
  }

  return getProjectDisplayName(projectToolsScope.value)
})

const pickerTitle = computed(() => {
  if (pickerType.value === 'ccv') {
    return 'Select CCV to Create'
  }

  return 'Select Form to Create'
})

const pickerButtons = computed(() => {
  if (!home.value) {
    return []
  }

  if (pickerType.value === 'ccv') {
    return home.value.ccv_forms || []
  }

  if (pickerType.value === 'form') {
    return home.value.task_forms || []
  }

  return home.value.generic_forms || []
})

function toggleScope(name: string) {
  openScopes.value[name] = !openScopes.value[name]
}

function toggleParent(key: string) {
  openParents.value[key] = !openParents.value[key]
}

function openProjectTools(scope: ScopeGroup) {
  projectToolsScope.value = scope
  projectToolsOpen.value = true
}

function closeProjectTools() {
  projectToolsOpen.value = false
  projectToolsScope.value = null
}

async function openProjectTool(tool: ProjectToolKey) {
  const scope = projectToolsScope.value

  if (!scope) {
    return
  }

  closeProjectTools()

  if (tool === 'gantt') {
    openInternalUrl(getProjectGanttUrl(scope), 'Gantt')
    return
  }

  if (tool === 'map') {
    openInternalUrl(getProjectMapUrl(scope), 'Map')
    return
  }

  if (tool === 'folder') {
    openExternalUrl(getShareFolder(scope), 'Folder')
    return
  }

  if (tool === 'handover') {
    await openProjectHandover(scope)
    return
  }

  if (tool === 'personnel') {
    await openPersonnelDrawer(scope)
    return
  }

  if (tool === 'gameplan') {
    openExternalUrl(getGameplanUrl(scope), 'Gameplan')
    return
  }

  if (tool === 'chat') {
    await openProjectChat(scope)
  }
}

function getChecklistItemKey(task: TaskItem, item: ChecklistItem) {
  return `${task.name}::${item.name}`
}

function isChecklistItemComplete(item: ChecklistItem) {
  if (item.completed === true) {
    return true
  }

  const normalised = String(item.completed ?? '').trim().toLowerCase()
  return normalised === '1' || normalised === 'true' || normalised === 'yes'
}

function isChecklistItemPending(task: TaskItem, item: ChecklistItem) {
  return Boolean(checklistPending.value[getChecklistItemKey(task, item)])
}

function isChecklistItemAwaitingEvidence(task: TaskItem, item: ChecklistItem) {
  const request = checklistEvidenceRequest.value

  return Boolean(
    request &&
    getChecklistItemKey(request.task, request.item) === getChecklistItemKey(task, item)
  )
}

function isChecklistItemBusy(task: TaskItem, item: ChecklistItem) {
  return (
    isChecklistItemPending(task, item) ||
    isChecklistItemAwaitingEvidence(task, item)
  )
}

function getChecklistItemError(task: TaskItem, item: ChecklistItem) {
  return checklistErrors.value[getChecklistItemKey(task, item)] || ''
}

function getCompletedChecklistCount(task: TaskItem) {
  return (task.checklist || []).filter(isChecklistItemComplete).length
}

function getChecklistItemCount(task: TaskItem) {
  return (task.checklist || []).length
}

function getChecklistToastClass(tone: ChecklistToastTone) {
  if (tone === 'success') {
    return 'border-green-200'
  }

  if (tone === 'error') {
    return 'border-red-200'
  }

  return 'border-blue-200'
}

function clearChecklistToastTimer() {
  window.clearTimeout(checklistToastTimer)
  checklistToastTimer = undefined
}

function showChecklistToast(toast: ChecklistToastState) {
  clearChecklistToastTimer()
  checklistToast.value = toast

  if (!toast.persistent) {
    checklistToastTimer = window.setTimeout(() => {
      checklistToast.value = null
      checklistToastTimer = undefined
    }, 5000)
  }
}

function dismissChecklistToast() {
  const cancelsEvidenceRequest = Boolean(checklistEvidenceRequest.value)

  clearChecklistToastTimer()
  checklistToast.value = null

  if (cancelsEvidenceRequest) {
    checklistEvidenceRequest.value = null

    if (checklistEvidenceInput.value) {
      checklistEvidenceInput.value.value = ''
    }
  }
}

function requestChecklistEvidence(
  parent: ParentGroup,
  task: TaskItem,
  item: ChecklistItem
) {
  const key = getChecklistItemKey(task, item)

  if (!task.name || !item.name || checklistPending.value[key]) {
    return
  }

  checklistErrors.value[key] = ''
  checklistEvidenceRequest.value = {
    parent,
    task,
    item,
  }

  showChecklistToast({
    title: 'Evidence required',
    message: `Upload evidence to complete “${item.description}”.`,
    tone: 'info',
    actionLabel: 'Upload evidence',
    persistent: true,
  })
}

function chooseChecklistEvidence() {
  if (!checklistEvidenceRequest.value || !checklistEvidenceInput.value) {
    return
  }

  checklistEvidenceInput.value.value = ''

  showChecklistToast({
    title: 'Select evidence',
    message: 'Choose a photo or supporting document from your device.',
    tone: 'info',
    persistent: true,
  })

  checklistEvidenceInput.value.click()
}

function cancelChecklistEvidenceSelection() {
  checklistEvidenceRequest.value = null

  if (checklistEvidenceInput.value) {
    checklistEvidenceInput.value.value = ''
  }

  showChecklistToast({
    title: 'Checklist unchanged',
    message: 'No evidence was selected, so the checklist item remains incomplete.',
    tone: 'info',
  })
}

function applyChecklistUpdate(
  parent: ParentGroup,
  task: TaskItem,
  update: ChecklistUpdateResponse
) {
  task.checklist = update.checklist || task.checklist
  task.progress = Number(update.progress || 0)

  if (update.parent_progress !== null && update.parent_progress !== undefined) {
    parent.progress = Number(update.parent_progress || 0)
  }
}

async function saveChecklistItemCompletion(
  parent: ParentGroup,
  task: TaskItem,
  item: ChecklistItem,
  completed: boolean,
  evidenceFile?: File
) {
  const key = getChecklistItemKey(task, item)

  if (!task.name || !item.name || checklistPending.value[key]) {
    return false
  }

  checklistPending.value[key] = true
  checklistErrors.value[key] = ''

  try {
    const payload = new FormData()
    payload.append('task_name', task.name)
    payload.append('item_name', item.name)
    payload.append('completed', completed ? '1' : '0')

    if (evidenceFile) {
      payload.append('evidence_file', evidenceFile, evidenceFile.name)
    }

    const data = await apiRequest<FrappeResponse<ChecklistUpdateResponse>>(
      '/api/method/verto.api.mobile.task_checklist.set_checklist_item_completed',
      {
        method: 'POST',
        body: payload,
      }
    )

    applyChecklistUpdate(parent, task, data.message)
    return true
  } catch (err) {
    const message = err instanceof Error
      ? err.message
      : 'Could not update this checklist item.'

    checklistErrors.value[key] = message

    showChecklistToast({
      title: 'Could not update checklist',
      message,
      tone: 'error',
    })

    return false
  } finally {
    delete checklistPending.value[key]
  }
}

async function handleChecklistEvidenceSelected(event: Event) {
  const input = event.target as HTMLInputElement
  const request = checklistEvidenceRequest.value
  const evidenceFile = input.files?.[0]

  if (!request || !evidenceFile) {
    cancelChecklistEvidenceSelection()
    return
  }

  checklistEvidenceRequest.value = null

  showChecklistToast({
    title: 'Uploading evidence',
    message: `Attaching ${evidenceFile.name} to the Task…`,
    tone: 'info',
    persistent: true,
  })

  const completed = await saveChecklistItemCompletion(
    request.parent,
    request.task,
    request.item,
    true,
    evidenceFile
  )

  input.value = ''

  if (completed) {
    showChecklistToast({
      title: 'Checklist completed',
      message: 'Evidence was attached to the Task and checklist progress was updated.',
      tone: 'success',
    })
  }
}

async function toggleChecklistItem(
  parent: ParentGroup,
  task: TaskItem,
  item: ChecklistItem,
  nextCompleted: boolean
) {
  if (nextCompleted === isChecklistItemComplete(item)) {
    return
  }

  if (nextCompleted) {
    requestChecklistEvidence(parent, task, item)
    return
  }

  const unchecked = await saveChecklistItemCompletion(
    parent,
    task,
    item,
    false
  )

  if (unchecked) {
    showChecklistToast({
      title: 'Checklist reopened',
      message: 'Existing evidence remains attached to the Task for audit purposes.',
      tone: 'info',
    })
  }
}

function openPicker(type: 'generic' | 'form' | 'ccv', task?: TaskItem) {
  pickerType.value = type
  pickerTask.value = task || null
  pickerOpen.value = true
}

function closePicker() {
  pickerOpen.value = false
  pickerTask.value = null
}

function createFromPicker(button: HomeButton) {
  const query = new URLSearchParams()

  if (pickerTask.value?.name) {
    query.set('link_task', pickerTask.value.name)
  }

  if (pickerTask.value?.project) {
    query.set('project', pickerTask.value.project)
  }

  if (pickerTask.value?.project_scope_name) {
    query.set('project_scope_name', pickerTask.value.project_scope_name)
  }

  if (pickerTask.value?.parent_task_name) {
    query.set('parent_task_name', pickerTask.value.parent_task_name)
  }

  if (pickerTask.value?.work_order_number) {
    query.set('work_order_number', pickerTask.value.work_order_number)
  }

  const queryString = query.toString()

  window.location.href = `/verto-mobile/new/${button.mobile_doctype}${queryString ? `?${queryString}` : ''}`
}

function getParentKey(scope: ScopeGroup, parent: ParentGroup) {
  return `${scope.scope_name}::${parent.parent_task_name}`
}

function getScopeAverageProgress(scope: ScopeGroup) {
  const parents = scope.parent_groups || []

  if (!parents.length) {
    return 0
  }

  const totalProgress = parents.reduce((total, parent) => {
    return total + Number(parent.progress || 0)
  }, 0)

  return Math.round(totalProgress / parents.length)
}

function clampPercent(value: number | string | null | undefined) {
  if (!Number.isFinite(Number(value))) {
    return 0
  }

  return Math.max(0, Math.min(100, Math.round(Number(value))))
}

function formatDate(value?: string) {
  if (!value) {
    return ''
  }

  const date = new Date(`${value}T00:00:00`)

  if (Number.isNaN(date.getTime())) {
    return value
  }

  return date.toLocaleDateString('en-AU', {
    day: 'numeric',
    month: 'short',
  })
}

function formatTime(value?: string) {
  if (!value) {
    return ''
  }

  const [rawHours, rawMinutes = '00'] = value.split(':')
  let hours = Number(rawHours)

  if (!Number.isFinite(hours)) {
    return value
  }

  const ampm = hours >= 12 ? 'pm' : 'am'
  hours = hours % 12 || 12

  return `${hours}:${rawMinutes}${ampm}`
}

function getPriorityColor(priority?: string) {
  const map: Record<string, string> = {
    Low: '#dcfce7',
    Medium: '#fef9c3',
    High: '#ffedd5',
    Urgent: '#fee2e2',
  }

  return map[priority || ''] || '#f3f4f6'
}

function slugifyRavenChannelName(value?: string) {
  return String(value || '')
    .trim()
    .toLowerCase()
    .replace(/&/g, ' and ')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
}

function getProjectDisplayName(scope: ScopeGroup) {
  const project = scope.project_details || {}

  return (
    project.project_name ||
    project.title ||
    project.name ||
    scope.project ||
    scope.scope_name ||
    ''
  )
}

function getProjectCustomer(scope: ScopeGroup) {
  const project = scope.project_details || {}

  return (
    project.customer ||
    project.customer_name ||
    project.client ||
    project.client_name ||
    scope.customer ||
    ''
  )
}

function getCustomerImage(scope: ScopeGroup) {
  const project = scope.project_details || {}

  return (
    project.customer_image ||
    project.image ||
    ''
  )
}

function getCustomerInitials(scope: ScopeGroup) {
  const customer = getProjectCustomer(scope) || getProjectDisplayName(scope)

  const words = String(customer)
    .trim()
    .split(/\s+/)
    .filter(Boolean)

  if (!words.length) {
    return '?'
  }

  if (words.length === 1) {
    return words[0].slice(0, 2).toUpperCase()
  }

  return `${words[0][0]}${words[1][0]}`.toUpperCase()
}

function hideBrokenImage(event: Event) {
  const image = event.target as HTMLImageElement
  image.style.display = 'none'
}


function isUsableUrl(url?: string) {
  const value = String(url || '').trim()

  return Boolean(value) && value !== '#'
}

function openInternalUrl(url?: string, label = 'link') {
  const value = String(url || '').trim()

  if (!isUsableUrl(value)) {
    error.value = `Could not open ${label}. The URL is not configured for this project.`
    return
  }

  openAppBrowser({
    url: value,
    title: label,
  })
}

function openExternalUrl(url?: string, label = 'link') {
  const value = String(url || '').trim()

  if (!isUsableUrl(value)) {
    error.value = `Could not open ${label}. The URL is not configured for this project.`
    return
  }

  openAppBrowser({
    url: value,
    title: label,
  })
}

function getProjectChatChannel(scope: ScopeGroup) {
  const project = scope.project_details || {}

  return (
    project.raven_channel ||
    project.raven_channel_id ||
    project.channel_id ||
    slugifyRavenChannelName(getProjectDisplayName(scope))
  )
}

async function openProjectChat(scope: ScopeGroup) {
  const channel = getProjectChatChannel(scope)

  if (!channel) {
    error.value = 'Could not determine the Raven channel for this project.'
    return
  }

  await router.push({
    path: '/chat',
    query: {
      channel,
    },
  })
}

function getPeriChannelIdFromResponse(value: any) {
  const channel = value?.channel || value?.message || value

  if (typeof channel === 'string') {
    return channel
  }

  return (
    channel?.name ||
    channel?.channel_id ||
    value?.name ||
    value?.channel_id ||
    ''
  )
}

async function getOrCreatePeriChannelId() {
  const data = await apiRequest<FrappeResponse<PeriChannelResponse>>(
    '/api/method/verto.api.mobile.raven.get_or_create_peri_channel'
  )

  const channelId = getPeriChannelIdFromResponse(data.message)

  if (!channelId) {
    throw new Error('Could not determine the Ask PERI channel.')
  }

  return channelId
}

// Analyse with PERI: resolve the dedicated user <-> PERI DM channel before routing.
async function analyseProjectWithPeri(scope: ScopeGroup) {
  const projectName =
    scope.scope_name ||
    scope.project_details?.project_name ||
    scope.project_details?.title ||
    scope.project_details?.project_title ||
    scope.project_details?.subject ||
    scope.project ||
    ''

  if (!projectName) {
    error.value = 'Could not determine the project name for PERI analysis.'
    return
  }

  try {
    const channel = await getOrCreatePeriChannelId()

    sessionStorage.setItem(
      'verto_peri_autosend_message',
      `Analyse the dashboard for ${projectName}`
    )

    sessionStorage.setItem('verto_peri_source_project', projectName)

    await router.push({
      path: '/chat/peri',
      query: {
        channel,
        mode: 'ai',
        auto: 'analyse',
      },
    })
  } catch (err) {
    error.value = err instanceof Error
      ? err.message
      : 'Could not open Ask PERI.'
  }
}

function getProjectGanttUrl(scope: ScopeGroup) {
  return `/app/task/view/gantt?status=%5B%22not%20in%22%2C%5B%22Completed%22%2C%22Cancelled%22%5D%5D&type=%5B%22not%20in%22%2C%5B%22Task%20Step%22%2C%22Outline%22%5D%5D&project=${encodeURIComponent(scope.project || '')}`
}

function getProjectMapUrl(scope: ScopeGroup) {
  return `/app/task/view/map?status=%5B%22not%20in%22%2C%5B%22Completed%22%2C%22Cancelled%22%5D%5D&type=Work%20Summary&project=${encodeURIComponent(scope.project || '')}`
}

function getAreaGanttUrl(parent: ParentGroup) {
  return `/app/task/view/gantt?status=%5B%22not%20in%22%2C%5B%22Completed%22%2C%22Cancelled%22%5D%5D&type=%5B%22not%20in%22%2C%5B%22Task%20Step%22%2C%22Outline%22%5D%5D&name=%5B%22descendants%20of%20%28inclusive%29%22%2C%22${encodeURIComponent(parent.parent_task || '')}%22%5D&project=${encodeURIComponent(parent.project || '')}`
}

function getShareFolder(scope: ScopeGroup) {
  const firstTask = scope.parent_groups?.[0]?.tasks?.[0]

  return firstTask?.share_folder || '#'
}

function getConfiguredHandoverBase() {
  return String(home.value?.handover_base || '').trim()
}

function inferHandoverDoctypeFromBase(base?: string) {
  const value = String(base || '').trim().toLowerCase()

  if (!value) {
    return ''
  }

  if (value.includes('lead-safety-handover') || value.includes('lead_safety_handover')) {
    return 'Lead Safety Handover'
  }

  if (value.includes('safety-handover') || value.includes('safety_handover')) {
    return 'Safety Handover'
  }

  if (value.includes('project-handover') || value.includes('project_handover')) {
    return 'Project Handover'
  }

  if (value.includes('handover')) {
    return 'Handover'
  }

  return ''
}

function getProjectIdForHandover(scope: ScopeGroup) {
  const project = scope.project_details || {}

  return (
    scope.project ||
    project.name ||
    project.project ||
    project.project_name ||
    scope.scope_name ||
    ''
  )
}

async function openProjectHandover(scope: ScopeGroup) {
  const project = getProjectIdForHandover(scope)
  const projectName = getProjectDisplayName(scope) || scope.scope_name || project
  const handoverBase = getConfiguredHandoverBase()
  const handoverDoctype = inferHandoverDoctypeFromBase(handoverBase)

  if (!project && !projectName) {
    error.value = 'Could not determine the project for this handover.'
    return
  }

  try {
    const payload = new FormData()

    if (project) {
      payload.append('project', project)
    }

    if (projectName) {
      payload.append('project_name', projectName)
    }

    if (scope.scope_name) {
      payload.append('scope_name', scope.scope_name)
    }

    if (handoverBase) {
      payload.append('handover_base', handoverBase)
    }

    if (handoverDoctype) {
      payload.append('handover_doctype', handoverDoctype)
    }

    const data = await apiRequest<FrappeResponse<ProjectHandoverResponse>>(
      '/api/method/verto.api.mobile.handover.get_or_create_project_handover',
      {
        method: 'POST',
        body: payload,
      }
    )

    const handover = data.message

    if (!handover?.mobile_doctype || !handover?.name) {
      throw new Error('Could not resolve the project handover record.')
    }

    if (handover.route) {
      await router.push(handover.route)
      return
    }

    await router.push({
      path: `/edit/${encodeURIComponent(handover.mobile_doctype)}/${encodeURIComponent(handover.name)}`,
    })
  } catch (err) {
    if (err instanceof Error && err.message === 'Login required') {
      return
    }

    error.value = err instanceof Error
      ? err.message
      : 'Could not open the project handover.'
  }
}

function getProjectIdForPersonnel(scope: ScopeGroup) {
  const project = scope.project_details || {}

  return (
    scope.project ||
    project.name ||
    project.project ||
    project.project_name ||
    scope.scope_name ||
    ''
  )
}

function closePersonnelDrawer() {
  personnelOpen.value = false
  personnelRows.value = []
  personnelError.value = ''
  personnelProjectTitle.value = ''
}

async function openPersonnelDrawer(scope: ScopeGroup) {
  const project = getProjectIdForPersonnel(scope)
  const projectName = getProjectDisplayName(scope) || scope.scope_name || project

  if (!project && !projectName) {
    error.value = 'Could not determine the project for personnel.'
    return
  }

  personnelOpen.value = true
  personnelLoading.value = true
  personnelError.value = ''
  personnelRows.value = []
  personnelProjectTitle.value = projectName || 'Project'

  try {
    const payload = new FormData()

    if (project) {
      payload.append('project', project)
    }

    if (projectName) {
      payload.append('project_name', projectName)
    }

    if (scope.scope_name) {
      payload.append('scope_name', scope.scope_name)
    }

    const data = await apiRequest<FrappeResponse<ProjectPersonnelResponse>>(
      '/api/method/verto.api.mobile.project_personnel.get_project_personnel',
      {
        method: 'POST',
        body: payload,
      }
    )

    personnelRows.value = data.message?.personnel || []
  } catch (err) {
    if (err instanceof Error && err.message === 'Login required') {
      return
    }

    personnelError.value = err instanceof Error
      ? err.message
      : 'Could not load project personnel.'
  } finally {
    personnelLoading.value = false
  }
}

function getPersonnelInitials(person: ProjectPersonnelItem) {
  const value = person.employee_name || person.employee || person.email || '?'

  const words = String(value)
    .trim()
    .split(/\s+/)
    .filter(Boolean)

  if (!words.length) {
    return '?'
  }

  if (words.length === 1) {
    return words[0].slice(0, 2).toUpperCase()
  }

  return `${words[0][0]}${words[1][0]}`.toUpperCase()
}

function getPersonnelShiftLabel(person: ProjectPersonnelItem) {
  return person.shift_label || normalisePersonnelShiftLabel(person.shift_type)
}

function normalisePersonnelShiftLabel(value?: string) {
  const cleaned = String(value || '').trim()

  if (!cleaned) {
    return ''
  }

  const normalised = cleaned
    .toUpperCase()
    .replace(/^(FG|RH)[\s_-]*/i, '')
    .replace(/[^A-Z0-9]+/g, ' ')
    .trim()

  const tokens = normalised.split(/\s+/).filter(Boolean)

  if (
    tokens.includes('DS') ||
    tokens.includes('D') ||
    normalised.includes('DAY')
  ) {
    return 'Day Shift'
  }

  if (
    tokens.includes('NS') ||
    tokens.includes('N') ||
    normalised.includes('NIGHT')
  ) {
    return 'Night Shift'
  }

  return cleaned
}

function getPersonnelShiftKind(person: ProjectPersonnelItem) {
  if (person.shift_kind) {
    return person.shift_kind
  }

  const label = getPersonnelShiftLabel(person).toLowerCase()

  if (label.includes('day')) {
    return 'day'
  }

  if (label.includes('night')) {
    return 'night'
  }

  return ''
}

function getPersonnelShiftBadgeClass(person: ProjectPersonnelItem) {
  const shiftKind = getPersonnelShiftKind(person)

  const baseClass = 'shrink-0 rounded-full px-2.5 py-1 text-xs font-semibold'

  if (shiftKind === 'day') {
    return `${baseClass} bg-green-100 text-green-800`
  }

  if (shiftKind === 'night') {
    return `${baseClass} bg-blue-100 text-blue-800`
  }

  if (shiftKind === 'mixed') {
    return `${baseClass} bg-purple-100 text-purple-800`
  }

  return `${baseClass} bg-surface-gray-2 text-ink-gray-7`
}

function getPersonnelSubtitle(person: ProjectPersonnelItem) {
  return [
    person.designation,
    person.department,
  ]
    .filter(Boolean)
    .join(' · ')
}

function formatPersonnelDateRange(person: ProjectPersonnelItem) {
  const startDate = formatDate(person.start_date)
  const endDate = formatDate(person.end_date)

  if (startDate && endDate) {
    return `${startDate} - ${endDate}`
  }

  return startDate || endDate || ''
}

function normaliseTel(value?: string) {
  return String(value || '').replace(/[^+0-9]/g, '')
}

function getGameplanUrl(scope: ScopeGroup) {
  const project = scope.project_details || {}
  const team = project.gameplan_team_name || ''
  const gameplanProject = project.gameplan_project || ''

  return `/g/${team}/projects/${gameplanProject}`
}

async function loadHome() {
  loading.value = true
  error.value = ''

  try {
    const data = await apiRequest<FrappeResponse<HomePayload>>(
      '/api/method/verto.api.mobile.home.get_home_summary'
    )

    home.value = data.message

    for (const scope of data.message.grouped_tasks || []) {
      if (openScopes.value[scope.scope_name] === undefined) {
        openScopes.value[scope.scope_name] = false
      }

      for (const parent of scope.parent_groups || []) {
        const key = getParentKey(scope, parent)

        if (openParents.value[key] === undefined) {
          openParents.value[key] = false
        }
      }
    }
  } catch (err) {
    if (err instanceof Error && err.message === 'Login required') {
      return
    }

    error.value = err instanceof Error ? err.message : 'Could not load assigned tasks.'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadHome()
})

onBeforeUnmount(() => {
  clearChecklistToastTimer()
})
</script>

<style scoped>
.bottom-sheet-overlay {
  padding-top: max(env(safe-area-inset-top, 0px), 0.75rem);
}

.bottom-sheet-panel {
  max-height: min(
    82dvh,
    calc(100dvh - max(env(safe-area-inset-top, 0px), 0.75rem))
  );
  min-height: 0;
}

.bottom-sheet-body {
  min-height: 0;
  flex: 1 1 auto;
  overflow-x: hidden;
  overflow-y: auto;
  overscroll-behavior: contain;
  touch-action: pan-y;
  -webkit-overflow-scrolling: touch;
}

.bottom-toast {
  max-height: calc(
    100dvh - max(env(safe-area-inset-top, 0px), 0.75rem)
  );
  overflow-x: hidden;
  overflow-y: auto;
  overscroll-behavior: contain;
  touch-action: pan-y;
  -webkit-overflow-scrolling: touch;
}

.checklist-toast-enter-active,
.checklist-toast-leave-active {
  transition: opacity 0.18s ease, transform 0.18s ease;
}

.checklist-toast-enter-from,
.checklist-toast-leave-to {
  opacity: 0;
  transform: translateY(100%);
}

.drawer-fade-slide-enter-active,
.drawer-fade-slide-leave-active {
  transition: opacity 0.18s ease;
}

.drawer-fade-slide-enter-active :deep(.drawer-panel),
.drawer-fade-slide-leave-active :deep(.drawer-panel) {
  transition: transform 0.24s ease, opacity 0.24s ease;
}

.drawer-fade-slide-enter-from,
.drawer-fade-slide-leave-to {
  opacity: 0;
}

.drawer-fade-slide-enter-from :deep(.drawer-panel),
.drawer-fade-slide-leave-to :deep(.drawer-panel) {
  opacity: 0;
  transform: translateY(100%);
}

.drawer-fade-slide-enter-to :deep(.drawer-panel),
.drawer-fade-slide-leave-from :deep(.drawer-panel) {
  opacity: 1;
  transform: translateY(0);
}

@media (prefers-reduced-motion: reduce) {
  .checklist-toast-enter-active,
  .checklist-toast-leave-active,
  .drawer-fade-slide-enter-active,
  .drawer-fade-slide-leave-active,
  .drawer-fade-slide-enter-active :deep(.drawer-panel),
  .drawer-fade-slide-leave-active :deep(.drawer-panel) {
    transition: none;
  }
}
</style>

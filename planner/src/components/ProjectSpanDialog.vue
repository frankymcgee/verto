<template>
  <Dialog
    :open="isOpen && !suspended"
    :title="dialogTitle"
    size="4xl"
    @update:open="
      (open) => {
        if (!open) {
          closeDialog();
        }
      }
    "
  >
    <div class="max-h-[calc(100vh-13rem)] overflow-y-auto px-6 py-5">
      <div class="space-y-6">
        <div
          v-if="projectDetails.loading"
          class="rounded-6 border border-gray-200 bg-gray-50 px-4 py-6 text-sm text-gray-600"
        >
          Loading project details...
        </div>

        <template v-else>
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <FormControl
              type="text"
              label="Project"
              v-model="form.project_name"
              :disabled="true"
            />
            <FormControl
              type="text"
              label="Project ID"
              v-model="form.project"
              :disabled="true"
            />

            <FormControl
              type="text"
              label="Customer"
              v-model="form.customer"
              :disabled="true"
            />
            <FormControl
              type="text"
              label="Location"
              v-model="form.custom_project_location"
              :disabled="true"
            />

            <FormControl
              v-if="isPoCheckField"
              type="checkbox"
              label="PO Entered"
              v-model="form.po_entered"
              :disabled="!form.can_update_po"
            />
            <FormControl
              v-else
              type="text"
              label="PO Number"
              placeholder="Enter PO number"
              v-model="form.po_number"
              :disabled="!form.can_update_po"
            />

            <FormControl
              type="checkbox"
              label="Active"
              v-model="form.is_active"
              :disabled="!form.can_update_is_active"
            />

            <FormControl
              type="number"
              label="DS Personnel Required"
              v-model="form.ds_requested"
              :disabled="!form.can_update_ds"
            />
            <FormControl
              type="number"
              label="NS Personnel Required"
              v-model="form.ns_requested"
              :disabled="!form.can_update_ns"
            />

            <template v-if="showProjectDateFields">
              <div
                class="col-span-2 rounded-6 border px-3 py-2 text-xs"
                :class="projectDateHelpClass"
              >
                {{ projectDateHelpMessage }}
              </div>

              <FormControl
                type="date"
                format="YYYY-MM-DD"
                label="Project Start Date"
                v-model="form.project_start_date"
                :disabled="!form.can_update_project_dates"
              />
              <FormControl
                type="date"
                format="YYYY-MM-DD"
                label="Project End Date"
                v-model="form.project_end_date"
                :disabled="!form.can_update_project_dates"
              />
            </template>

            <div class="col-span-2">
              <label class="mb-1.5 block text-sm text-gray-700">
                Project Notes
              </label>
              <Textarea
                v-model="form.project_notes"
                :rows="5"
                placeholder="Add project notes..."
                :disabled="!form.can_update_notes"
              />
              <p
                v-if="!form.can_update_notes"
                class="mt-1 text-xs text-gray-500"
              >
                Project notes cannot be edited because the matching Project
                notes field was not found.
              </p>
            </div>
          </div>

          <div
            v-if="missingEditableFieldMessage"
            class="rounded-6 border border-yellow-200 bg-yellow-50 px-3 py-2 text-xs text-yellow-800"
          >
            {{ missingEditableFieldMessage }}
          </div>

          <div class="rounded-6 border border-gray-200 bg-white">
            <div class="border-b border-gray-100 px-4 py-3">
              <div class="flex items-start justify-between gap-3">
                <div>
                  <div class="text-sm-semibold text-gray-800">
                    Generic Task Structure
                  </div>
                  <div class="mt-0.5 text-xs text-gray-500">
                    {{ genericTaskStatusMessage }}
                  </div>
                </div>
                <div
                  class="shrink-0 rounded-full px-2 py-0.5 text-xs-semibold"
                  :class="
                    form.has_tasks
                      ? 'bg-green-50 text-green-700'
                      : 'bg-yellow-50 text-yellow-700'
                  "
                >
                  {{
                    form.has_tasks
                      ? `${form.task_count} task(s)`
                      : "Gantt missing"
                  }}
                </div>
              </div>
            </div>

            <div
              v-if="form.has_tasks"
              class="space-y-3 border-b border-gray-100 p-4"
            >
              <div v-if="form.execution_tasks.length" class="space-y-2">
                <div
                  v-for="task in form.execution_tasks"
                  :key="task.name"
                  class="flex items-center gap-3 rounded-5 border border-gray-200 px-3 py-3"
                >
                  <div class="min-w-0 flex-1">
                    <div
                      class="flex flex-wrap items-baseline gap-x-2 gap-y-0.5"
                    >
                      <div class="text-sm-semibold text-gray-800">
                        {{ task.subject || "Execution" }}
                      </div>
                      <div class="text-xs text-gray-500">
                        {{ task.location_subject || task.parent_task }}
                      </div>
                    </div>
                    <div class="mt-2 flex flex-wrap gap-1.5">
                      <div
                        v-for="assignee in task.assignees"
                        :key="`${task.name}-${assignee.user}`"
                        class="inline-flex items-center gap-1.5 rounded-full bg-blue-50 px-2 py-1 text-xs-medium text-blue-800"
                      >
                        <img
                          v-if="assignee.user_image"
                          :src="assignee.user_image"
                          :alt="assignee.full_name || assignee.user"
                          class="h-4 w-4 rounded-full object-cover"
                        />
                        <span
                          v-else
                          class="flex h-4 w-4 items-center justify-center rounded-full bg-blue-200 text-[9px] font-bold text-blue-800"
                        >
                          {{ userInitials(assignee) }}
                        </span>
                        {{ assignee.full_name || assignee.user }}
                      </div>
                      <div
                        v-if="!task.assignees.length"
                        class="text-xs text-gray-500"
                      >
                        Unassigned
                      </div>
                    </div>
                  </div>
                  <Button
                    variant="ghost"
                    type="button"
                    class="flex h-8 shrink-0 items-center justify-center rounded-5 border border-gray-300 bg-white px-3 text-sm-medium text-gray-700 transition hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-40"
                    :disabled="!task.can_assign"
                    :title="
                      task.can_assign
                        ? `Manage personnel for ${task.subject}`
                        : 'You do not have permission to assign this task'
                    "
                    :aria-label="`Manage personnel for ${task.subject}`"
                    @click="openTaskAssignmentModal(task)"
                  >
                    {{ task.assignees.length ? "Manage" : "+ Assign" }}
                  </Button>
                </div>
              </div>
              <div
                v-else
                class="rounded-5 bg-gray-50 px-3 py-4 text-center text-sm text-gray-500"
              >
                No Work Summary/Execution tasks were found for this project.
              </div>
            </div>

            <div class="space-y-4 p-4">
              <div
                class="rounded-5 border border-blue-100 bg-blue-50 px-3 py-2 text-xs text-blue-800"
              >
                <div class="font-semibold">
                  {{ form.project_name || form.project }}
                </div>
                <div
                  v-for="(location, index) in form.generic_locations"
                  :key="`generic-preview-${location.key}`"
                  :class="index === 0 ? 'mt-1' : 'mt-1.5'"
                >
                  <div class="pl-3">
                    └─
                    {{
                      location.task
                        ? form.location_tasks.find(
                            (task) => task.name === location.task,
                          )?.subject
                        : location.subject || `Location ${index + 1}`
                    }}
                  </div>
                  <div
                    v-for="(summary, summaryIndex) in location.work_summaries"
                    :key="summaryIndex"
                    class="pl-6"
                  >
                    └─ {{ summary || "Work Summary" }}
                  </div>
                </div>
              </div>

              <div class="rounded-5 border border-gray-200">
                <div
                  class="flex items-center justify-between gap-3 border-b border-gray-100 px-3 py-2"
                >
                  <div>
                    <div
                      class="text-xs-semibold uppercase tracking-wide text-gray-600"
                    >
                      Locations
                    </div>
                    <div class="text-xs text-gray-500">
                      Choose a new or existing location, then add its Work
                      Summaries.
                    </div>
                  </div>
                  <Button
                    variant="ghost"
                    type="button"
                    class="rounded-5 border border-gray-300 bg-white px-2.5 py-1.5 text-xs-semibold text-gray-700 transition hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
                    :disabled="!canAddGenericLocation"
                    @click="addGenericLocation"
                  >
                    + Add Location
                  </Button>
                </div>

                <div class="space-y-3 p-3">
                  <div
                    v-for="(location, index) in form.generic_locations"
                    :key="location.key"
                    class="flex items-end gap-2"
                  >
                    <div class="min-w-0 flex-1 space-y-3">
                      <label class="block text-xs-medium text-gray-600">
                        Location {{ index + 1 }} target
                        <Combobox
                          v-model="location.task"
                          :aria-label="`Location ${index + 1} target`"
                          :disabled="
                            !form.can_create_generic_tasks ||
                            createGenericTasks.loading
                          "
                          :options="[
                            { label: `New Location`, value: '' },
                            ...form.location_tasks.map((task) => ({
                              label: `${task.subject} (${task.name})`,
                              value: task.name,
                            })),
                          ]"
                        />
                      </label>
                      <FormControl
                        v-if="!location.task"
                        type="text"
                        :label="`Location ${index + 1}`"
                        :placeholder="
                          index === 0
                            ? 'General'
                            : `Enter location ${index + 1}`
                        "
                        v-model="location.subject"
                        :disabled="
                          !form.can_create_generic_tasks ||
                          createGenericTasks.loading
                        "
                      />
                      <div
                        v-for="(
                          summary, summaryIndex
                        ) in location.work_summaries"
                        :key="summaryIndex"
                        class="flex items-end gap-2"
                      >
                        <FormControl
                          class="flex-1"
                          type="text"
                          :label="`Location ${index + 1} Work Summary ${summaryIndex + 1}`"
                          v-model="location.work_summaries[summaryIndex]"
                          :disabled="
                            !form.can_create_generic_tasks ||
                            createGenericTasks.loading
                          "
                        />
                        <Button
                          variant="ghost"
                          type="button"
                          class="p-2 text-xs text-red-600"
                          :aria-label="`Remove Work Summary ${summaryIndex + 1} from Location ${index + 1}`"
                          :disabled="
                            location.work_summaries.length <= 1 ||
                            createGenericTasks.loading
                          "
                          @click="
                            location.work_summaries.splice(summaryIndex, 1)
                          "
                          >Remove</Button
                        >
                      </div>
                      <Button
                        size="sm"
                        :aria-label="`Add Work Summary to Location ${index + 1}`"
                        :disabled="
                          !form.can_create_generic_tasks ||
                          createGenericTasks.loading ||
                          location.work_summaries.length >= 100
                        "
                        @click="location.work_summaries.push('')"
                        >+ Add Work Summary</Button
                      >
                    </div>
                    <Button
                      variant="ghost"
                      type="button"
                      class="mb-0.5 rounded-5 border border-red-200 bg-white px-2.5 py-2 text-xs-semibold text-red-600 transition hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-40"
                      :disabled="
                        form.generic_locations.length <= 1 ||
                        createGenericTasks.loading
                      "
                      :aria-label="`Remove location ${index + 1}`"
                      @click="removeGenericLocation(index)"
                    >
                      Remove
                    </Button>
                  </div>

                  <p
                    v-if="!genericLocationNamesAreUnique"
                    class="text-xs-medium text-red-600"
                  >
                    Each location task must have a unique name.
                  </p>
                </div>
              </div>

              <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <FormControl
                  type="time"
                  label="Expected Start Time"
                  v-model="form.generic_start_time"
                  :disabled="
                    !form.can_create_generic_tasks || createGenericTasks.loading
                  "
                />
                <FormControl
                  type="time"
                  label="Expected End Time"
                  v-model="form.generic_end_time"
                  :disabled="
                    !form.can_create_generic_tasks || createGenericTasks.loading
                  "
                />
              </div>

              <div class="flex items-center justify-between gap-3">
                <p class="text-xs text-gray-500">
                  New locations are created under a new Outline. Existing
                  locations receive only the additional Work Summaries.
                </p>
                <Button
                  size="sm"
                  variant="solid"
                  class="shrink-0"
                  :disabled="!canSubmitGenericTasks || updateProject.loading"
                  :loading="createGenericTasks.loading"
                  @click="confirmCreateGenericTasks"
                >
                  {{ form.has_tasks ? "Add" : "Create" }}
                  {{ genericTaskTotalCount }} Generic Tasks
                </Button>
              </div>
            </div>
          </div>

          <div class="rounded-6 border border-gray-200 bg-white">
            <div class="border-b border-gray-100 px-4 py-3">
              <div class="text-sm-semibold text-gray-800">
                Personnel Assigned
              </div>
              <div class="mt-0.5 text-xs text-gray-500">
                Current annual view assignments split by DS and NS shift types.
              </div>
            </div>

            <div
              class="grid grid-cols-1 divide-y divide-gray-100 sm:grid-cols-1 sm:grid-cols-2 sm:divide-x sm:divide-y-0"
            >
              <div class="p-4">
                <div class="mb-2 flex items-center justify-between gap-2">
                  <div
                    class="text-xs-semibold uppercase tracking-wide text-gray-500"
                  >
                    DS
                  </div>
                  <div
                    class="rounded-full bg-gray-100 px-2 py-0.5 text-xs-semibold text-gray-600"
                  >
                    {{ dsPersonnel.length }}
                  </div>
                </div>

                <Button
                  size="sm"
                  class="mb-3 w-full"
                  aria-label="Assign day shifts"
                  :disabled="!canAssignShifts"
                  @click="assignProjectShifts('DS')"
                  >+ Assign shifts</Button
                >

                <div v-if="dsPersonnel.length" class="space-y-1.5">
                  <div
                    v-for="person in dsPersonnel"
                    :key="`ds-${person}`"
                    class="rounded-5 bg-gray-50 px-2.5 py-1.5 text-sm text-gray-700"
                  >
                    {{ person }}
                  </div>
                </div>
                <div
                  v-else
                  class="rounded-5 bg-gray-50 px-2.5 py-4 text-center text-sm text-gray-500"
                >
                  No DS personnel assigned
                </div>
              </div>

              <div class="p-4">
                <div class="mb-2 flex items-center justify-between gap-2">
                  <div
                    class="text-xs-semibold uppercase tracking-wide text-gray-500"
                  >
                    NS
                  </div>
                  <div
                    class="rounded-full bg-gray-100 px-2 py-0.5 text-xs-semibold text-gray-600"
                  >
                    {{ nsPersonnel.length }}
                  </div>
                </div>

                <Button
                  size="sm"
                  class="mb-3 w-full"
                  aria-label="Assign night shifts"
                  :disabled="!canAssignShifts"
                  @click="assignProjectShifts('NS')"
                  >+ Assign shifts</Button
                >

                <div v-if="nsPersonnel.length" class="space-y-1.5">
                  <div
                    v-for="person in nsPersonnel"
                    :key="`ns-${person}`"
                    class="rounded-5 bg-gray-50 px-2.5 py-1.5 text-sm text-gray-700"
                  >
                    {{ person }}
                  </div>
                </div>
                <div
                  v-else
                  class="rounded-5 bg-gray-50 px-2.5 py-4 text-center text-sm text-gray-500"
                >
                  No NS personnel assigned
                </div>
              </div>
            </div>
          </div>
        </template>
      </div>
    </div>
    <template #actions
      ><div class="border-t border-gray-200 bg-gray-50 px-6 py-4">
        <div class="flex justify-end gap-3">
          <Button size="md" label="Cancel" class="w-28" @click="closeDialog" />
          <Button
            size="md"
            variant="solid"
            class="w-28"
            :disabled="
              projectDetails.loading ||
              updateProject.loading ||
              createGenericTasks.loading ||
              !form.project
            "
            :loading="updateProject.loading"
            @click="updateProject.submit()"
          >
            Update
          </Button>
        </div>
      </div></template
    >
  </Dialog>

  <Dialog
    :open="showTaskAssignmentModal"
    :title="'Manage personnel'"
    size="lg"
    :dismissible="!updateExecutionTaskAssignments.loading"
    :show-close-button="!updateExecutionTaskAssignments.loading"
    @update:open="
      (open) => {
        if (!open) {
          closeTaskAssignmentModal();
        }
      }
    "
  >
    <div class="min-h-0 space-y-3 overflow-y-auto px-5 py-4">
      <p class="text-sm text-gray-600">
        Tick people to assign them, or untick to remove them. Changes apply when
        you save.
      </p>
      <TextInput
        v-model="assignmentSearch"
        type="search"
        placeholder="Search personnel by name or email..."
        aria-label="Search personnel"
      />

      <div
        v-if="assignmentUsers.loading"
        class="rounded-5 bg-gray-50 px-3 py-8 text-center text-sm text-gray-500"
      >
        Loading personnel...
      </div>
      <div
        v-else-if="assignmentUsersReady"
        class="max-h-80 overflow-y-auto rounded-5 border border-gray-200"
      >
        <label
          v-for="user in filteredAssignmentUsers"
          :key="user.user"
          class="flex items-center gap-3 border-b border-gray-100 px-3 py-2.5 last:border-b-0"
          :class="
            updateExecutionTaskAssignments.loading
              ? 'cursor-wait opacity-70'
              : 'cursor-pointer hover:bg-gray-50'
          "
        >
          <Checkbox
            :model-value="selectedAssignmentUsers.includes(user.user)"
            :value="user.user"
            :disabled="updateExecutionTaskAssignments.loading"
            @update:model-value="
              (checked) => {
                selectedAssignmentUsers = checked
                  ? [...new Set([...selectedAssignmentUsers, user.user])]
                  : selectedAssignmentUsers.filter(
                      (value) => value !== user.user,
                    );
              }
            "
          />
          <Avatar
            :image="user.user_image || undefined"
            :label="user.full_name || user.user"
            size="lg"
          />
          <span class="min-w-0 flex-1">
            <span class="block truncate text-sm-medium text-gray-800">{{
              user.full_name || user.user
            }}</span>
            <span class="block truncate text-xs text-gray-500">{{
              user.user
            }}</span>
          </span>
          <span
            v-if="
              isExistingAssignee(user.user) &&
              !selectedAssignmentUsers.includes(user.user)
            "
            class="text-xs-medium text-red-700"
            >To remove</span
          >
          <span
            v-else-if="isExistingAssignee(user.user)"
            class="text-xs-medium text-green-700"
            >Assigned</span
          >
          <span
            v-else-if="selectedAssignmentUsers.includes(user.user)"
            class="text-xs-medium text-blue-700"
            >To add</span
          >
        </label>
        <div
          v-if="!filteredAssignmentUsers.length"
          class="px-3 py-8 text-center text-sm text-gray-500"
        >
          No matching personnel found.
        </div>
      </div>
      <div class="flex items-center justify-between gap-3">
        <p class="text-xs text-gray-500" aria-live="polite">
          {{ assignmentChangeSummary }}
        </p>
        <Button
          variant="ghost"
          type="button"
          class="shrink-0 text-xs-medium text-red-700 disabled:opacity-40"
          :disabled="
            !assignmentUsersReady ||
            assignmentUsers.loading ||
            updateExecutionTaskAssignments.loading ||
            !selectedAssignmentUsers.length
          "
          @click="selectedAssignmentUsers = []"
          >Clear selection</Button
        >
      </div>
    </div>
    <template #actions
      ><div
        class="flex shrink-0 justify-end gap-3 border-t border-gray-200 bg-gray-50 px-5 py-4"
      >
        <Button
          size="md"
          label="Cancel"
          class="w-24"
          :disabled="updateExecutionTaskAssignments.loading"
          @click="closeTaskAssignmentModal"
        />
        <Button
          size="md"
          variant="solid"
          :disabled="!canSaveAssignments"
          :loading="updateExecutionTaskAssignments.loading"
          @click="saveTaskAssignments"
        >
          Save changes
        </Button>
      </div></template
    >
  </Dialog>
</template>

<script setup lang="ts">
import { Textarea, TextInput, Checkbox, Avatar } from "frappe-ui";
import Dialog from "./PlannerDialog.vue";
import { dialog } from "frappe-ui";
import { Combobox } from "frappe-ui";
import { computed, reactive, ref, watch } from "vue";
import { Button, FormControl, createResource } from "frappe-ui";
import { raiseToast } from "../utils";
import type { ProjectShiftAssignmentDefaults } from "../types/shiftAssignment";

type ProjectDialogRow = {
  project: string;
  project_name?: string;
  customer?: string | null;
  customer_name?: string | null;
  custom_project_location?: string | null;
  status?: string | null;
  ds_personnel?: string[];
  ns_personnel?: string[];
};

type ProjectDetails = {
  project: string;
  project_name?: string;
  customer?: string | null;
  custom_project_location?: string | null;
  status?: string | null;
  po_field?: string | null;
  po_fieldtype?: string | null;
  po_number?: string | null;
  po_entered?: boolean | number | string | null;
  ds_requested?: number | string | null;
  ns_requested?: number | string | null;
  is_active?: boolean | number | string | null;
  project_start_date?: string | null;
  project_end_date?: string | null;
  notes_field?: string | null;
  notes?: string | null;
  task_count?: number | string | null;
  has_tasks?: boolean | number | string | null;
  location_tasks?: Array<{ name: string; subject: string }>;
  execution_tasks?: ExecutionTask[];
  can_create_generic_tasks?: boolean;
  generic_tasks_unavailable_reason?: string | null;
  can_update_po?: boolean;
  can_update_ds?: boolean;
  can_update_ns?: boolean;
  can_update_is_active?: boolean;
  can_update_project_dates?: boolean;
  can_update_notes?: boolean;
};

type TaskAssignee = {
  user: string;
  full_name?: string | null;
  user_image?: string | null;
};

type ExecutionTask = {
  name: string;
  subject: string;
  parent_task?: string | null;
  location_subject?: string | null;
  assignees: TaskAssignee[];
  can_assign: boolean;
};

type AssignmentUser = TaskAssignee;

type AssignmentUsersResponse = {
  task: string;
  users?: AssignmentUser[];
  assigned_users: string[];
};

type AssignmentResponse = {
  task?: string;
  assigned_users?: string[];
  removed_users?: string[];
  project_details?: ProjectDetails;
};

type GenericTaskResponse = {
  project?: string;
  created_tasks?: Array<{
    name: string;
    subject?: string;
    type?: string | null;
    parent_task?: string | null;
  }>;
  project_details?: ProjectDetails;
};

const props = defineProps<{
  modelValue?: boolean;
  isDialogOpen: boolean;
  suspended?: boolean;
  project?: ProjectDialogRow | null;
}>();

const emit = defineEmits<{
  (e: "update:modelValue", value: boolean): void;
  (e: "fetchEvents"): void;
  (e: "assignShifts", defaults: ProjectShiftAssignmentDefaults): void;
}>();

const isOpen = computed({
  get: () => props.modelValue ?? props.isDialogOpen,
  set: (value: boolean) => emit("update:modelValue", value),
});

type GenericLocationRow = {
  key: number;
  subject: string;
  task: string;
  work_summaries: string[];
};

const GENERIC_LOCATION_LIMIT = 100;
let nextGenericLocationKey = 1;

function newGenericLocation(subject = ""): GenericLocationRow {
  return {
    key: nextGenericLocationKey++,
    subject,
    task: "",
    work_summaries: ["Execution Works"],
  };
}

const form = reactive({
  project: "",
  project_name: "",
  customer: "",
  custom_project_location: "",
  status: "",
  po_fieldtype: "",
  po_number: "",
  po_entered: false,
  ds_requested: 0,
  ns_requested: 0,
  is_active: true,
  project_start_date: "",
  project_end_date: "",
  project_notes: "",
  task_count: 0,
  has_tasks: false,
  execution_tasks: [] as ExecutionTask[],
  location_tasks: [] as Array<{ name: string; subject: string }>,
  can_create_generic_tasks: false,
  generic_tasks_unavailable_reason: "",
  generic_locations: [newGenericLocation("General")],
  generic_start_time: "08:00",
  generic_end_time: "20:00",
  can_update_po: false,
  can_update_ds: false,
  can_update_ns: false,
  can_update_is_active: false,
  can_update_project_dates: false,
  can_update_notes: false,
});

const dialogTitle = computed(() => {
  const name =
    form.project_name ||
    props.project?.project_name ||
    props.project?.project ||
    "Project";
  return `Project Details - ${name}`;
});

const isPoCheckField = computed(() => form.po_fieldtype === "Check");
const showProjectDateFields = computed(
  () =>
    form.can_update_project_dates ||
    form.has_tasks ||
    Boolean(form.project_start_date || form.project_end_date),
);
const projectDateHelpClass = computed(() =>
  form.can_update_project_dates
    ? "border-blue-200 bg-blue-50 text-blue-800"
    : "border-gray-200 bg-gray-50 text-gray-600",
);
const projectDateHelpMessage = computed(() => {
  if (form.can_update_project_dates) {
    return "Project dates can be adjusted, but must include all linked tasks: start on or before the earliest task start and end on or after the latest task end.";
  }

  return "Project dates are not editable because the matching Project date fields were not found.";
});

const genericTaskStatusMessage = computed(() => {
  if (form.generic_tasks_unavailable_reason)
    return form.generic_tasks_unavailable_reason;

  if (form.has_tasks) {
    return `This project has ${form.task_count} task(s). Add another generic task structure below, or manage personnel on the existing Execution tasks.`;
  }

  return "Create new locations or select existing ones, then enter the Work Summaries to add under each.";
});

const genericLocationNames = computed(() =>
  form.generic_locations
    .filter((location) => !location.task)
    .map((location) => String(location.subject || "").trim()),
);
const genericLocationNamesAreUnique = computed(() => {
  const names = genericLocationNames.value
    .filter(Boolean)
    .map((name) => name.toLowerCase());
  return new Set(names).size === names.length;
});
const genericTaskTotalCount = computed(
  () =>
    (form.generic_locations.some((location) => !location.task) ? 1 : 0) +
    form.generic_locations.reduce(
      (count, location) =>
        count + (location.task ? 0 : 1) + location.work_summaries.length,
      0,
    ),
);
const canAddGenericLocation = computed(
  () =>
    form.can_create_generic_tasks &&
    !createGenericTasks.loading &&
    form.generic_locations.length < GENERIC_LOCATION_LIMIT,
);

const canSubmitGenericTasks = computed(
  () =>
    form.can_create_generic_tasks &&
    Boolean(form.project) &&
    form.generic_locations.length > 0 &&
    genericLocationNames.value.every(Boolean) &&
    genericLocationNamesAreUnique.value &&
    form.generic_locations.every(
      (location) =>
        (!location.task ||
          form.location_tasks.some((task) => task.name === location.task)) &&
        location.work_summaries.length > 0 &&
        location.work_summaries.every((subject) => subject.trim()),
    ) &&
    form.generic_locations.reduce(
      (count, location) => count + location.work_summaries.length,
      0,
    ) <= 500 &&
    Boolean(form.generic_start_time) &&
    Boolean(form.generic_end_time),
);

const dsPersonnel = computed(() =>
  normalisePersonnel(props.project?.ds_personnel),
);
const nsPersonnel = computed(() =>
  normalisePersonnel(props.project?.ns_personnel),
);
const canAssignShifts = computed(
  () =>
    Boolean(form.project) &&
    !projectDetails.loading &&
    !updateProject.loading &&
    !createGenericTasks.loading,
);

function assignProjectShifts(shiftType: "DS" | "NS") {
  if (!canAssignShifts.value) return;
  emit("assignShifts", {
    custom_project: form.project,
    project_name: form.project_name,
    shift_location: form.custom_project_location,
    shift_type: shiftType,
    start_date: form.project_start_date,
    end_date: form.project_end_date,
  });
}

const showTaskAssignmentModal = ref(false);
const selectedExecutionTask = ref<ExecutionTask | null>(null);
const assignmentSearch = ref("");
const selectedAssignmentUsers = ref<string[]>([]);
const initialAssignmentUsers = ref<string[]>([]);
const assignmentUsersReady = computed(
  () =>
    showTaskAssignmentModal.value &&
    assignmentUsers.data?.task === selectedExecutionTask.value?.name,
);
const assignmentUserRows = computed<AssignmentUser[]>(() => {
  const data = assignmentUsers.data as AssignmentUsersResponse | undefined;
  return assignmentUsersReady.value && Array.isArray(data?.users)
    ? data.users
    : [];
});
const existingAssigneeIds = computed(
  () => new Set(initialAssignmentUsers.value),
);
const assignmentAdditions = computed(() =>
  selectedAssignmentUsers.value.filter(
    (user) => !existingAssigneeIds.value.has(user),
  ),
);
const assignmentRemovals = computed(() =>
  initialAssignmentUsers.value.filter(
    (user) => !selectedAssignmentUsers.value.includes(user),
  ),
);
const canSaveAssignments = computed(
  () =>
    assignmentUsersReady.value &&
    !assignmentUsers.loading &&
    !updateExecutionTaskAssignments.loading &&
    Boolean(
      assignmentAdditions.value.length || assignmentRemovals.value.length,
    ),
);
const assignmentChangeSummary = computed(() => {
  const additions = assignmentAdditions.value.length;
  const removals = assignmentRemovals.value.length;
  return additions || removals
    ? `${additions} to add · ${removals} to remove`
    : "No changes";
});
const filteredAssignmentUsers = computed(() => {
  const search = assignmentSearch.value.trim().toLowerCase();
  if (!search) return assignmentUserRows.value;
  return assignmentUserRows.value.filter(
    (user) =>
      String(user.full_name || "")
        .toLowerCase()
        .includes(search) || user.user.toLowerCase().includes(search),
  );
});

const missingEditableFieldMessage = computed(() => {
  const missing: string[] = [];
  if (!form.can_update_po) missing.push("PO Number");
  if (!form.can_update_ds) missing.push("DS Personnel Required");
  if (!form.can_update_ns) missing.push("NS Personnel Required");
  if (!form.can_update_is_active) missing.push("Active");
  if (!form.can_update_notes) missing.push("Project Notes");

  if (!missing.length) return "";
  return `Some fields cannot be edited because the matching Project fields were not found: ${missing.join(", ")}.`;
});

function normalisePersonnel(value?: string[] | null) {
  return Array.isArray(value) ? value.filter(Boolean).sort() : [];
}

function addGenericLocation() {
  if (!canAddGenericLocation.value) return;
  form.generic_locations.push(newGenericLocation());
}

function removeGenericLocation(index: number) {
  if (form.generic_locations.length <= 1 || createGenericTasks.loading) return;
  form.generic_locations.splice(index, 1);
}

function userInitials(user: TaskAssignee) {
  const name = String(user.full_name || user.user || "").trim();
  if (!name) return "?";
  return name
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part.charAt(0))
    .join("")
    .toUpperCase();
}

function isExistingAssignee(user: string) {
  return existingAssigneeIds.value.has(user);
}

async function openTaskAssignmentModal(task: ExecutionTask) {
  if (!task.can_assign) return;
  selectedExecutionTask.value = task;
  assignmentSearch.value = "";
  initialAssignmentUsers.value = task.assignees.map(
    (assignee) => assignee.user,
  );
  selectedAssignmentUsers.value = [...initialAssignmentUsers.value];
  showTaskAssignmentModal.value = true;
  try {
    await assignmentUsers.fetch();
  } catch {
    // The resource's onError reports the error and closes the picker.
  }
}

function closeTaskAssignmentModal() {
  if (updateExecutionTaskAssignments.loading) return;
  resetTaskAssignmentModal();
}

function resetTaskAssignmentModal() {
  showTaskAssignmentModal.value = false;
  selectedExecutionTask.value = null;
  assignmentSearch.value = "";
  selectedAssignmentUsers.value = [];
  initialAssignmentUsers.value = [];
}

async function saveTaskAssignments() {
  if (!canSaveAssignments.value) return;
  try {
    await updateExecutionTaskAssignments.submit();
  } catch {
    // The resource's onError reports the error and preserves edits for retry.
  }
}

function boolValue(value: unknown, fallback = false) {
  if (value === undefined || value === null || value === "") return fallback;
  if (typeof value === "boolean") return value;
  if (typeof value === "number") return value !== 0;
  const normalised = String(value).trim().toLowerCase();
  return !["0", "no", "false", "missing", "not entered", "none"].includes(
    normalised,
  );
}

function intValue(value: unknown) {
  const parsed = Number.parseInt(String(value ?? 0), 10);
  return Number.isFinite(parsed) ? parsed : 0;
}

function resetForm() {
  closeTaskAssignmentModal();
  form.project = "";
  form.project_name = "";
  form.customer = "";
  form.custom_project_location = "";
  form.status = "";
  form.po_fieldtype = "";
  form.po_number = "";
  form.po_entered = false;
  form.ds_requested = 0;
  form.ns_requested = 0;
  form.is_active = true;
  form.project_start_date = "";
  form.project_end_date = "";
  form.project_notes = "";
  form.task_count = 0;
  form.has_tasks = false;
  form.location_tasks.splice(0);
  form.execution_tasks.splice(0);
  form.can_create_generic_tasks = false;
  form.generic_tasks_unavailable_reason = "";
  form.generic_locations.splice(
    0,
    form.generic_locations.length,
    newGenericLocation("General"),
  );
  form.generic_start_time = "08:00";
  form.generic_end_time = "20:00";
  form.can_update_po = false;
  form.can_update_ds = false;
  form.can_update_ns = false;
  form.can_update_is_active = false;
  form.can_update_project_dates = false;
  form.can_update_notes = false;
}

function applyDetails(data: ProjectDetails | undefined) {
  if (!data) return;

  form.project = data.project || "";
  form.project_name = data.project_name || data.project || "";
  form.customer =
    data.customer ||
    props.project?.customer_name ||
    props.project?.customer ||
    "";
  form.custom_project_location = data.custom_project_location || "";
  form.status = data.status || "";
  form.po_fieldtype = data.po_fieldtype || "";
  form.po_number = data.po_number || "";
  form.po_entered = boolValue(data.po_entered);
  form.ds_requested = intValue(data.ds_requested);
  form.ns_requested = intValue(data.ns_requested);
  form.is_active = boolValue(data.is_active, true);
  form.project_start_date = data.project_start_date || "";
  form.project_end_date = data.project_end_date || "";
  form.project_notes = data.notes || "";
  form.task_count = intValue(data.task_count);
  form.has_tasks = boolValue(data.has_tasks);
  form.execution_tasks.splice(
    0,
    form.execution_tasks.length,
    ...(data.execution_tasks || []),
  );
  form.location_tasks.splice(
    0,
    form.location_tasks.length,
    ...(data.location_tasks || []),
  );
  form.can_create_generic_tasks = Boolean(data.can_create_generic_tasks);
  form.generic_tasks_unavailable_reason =
    data.generic_tasks_unavailable_reason || "";
  form.can_update_po = Boolean(data.can_update_po);
  form.can_update_ds = Boolean(data.can_update_ds);
  form.can_update_ns = Boolean(data.can_update_ns);
  form.can_update_is_active = Boolean(data.can_update_is_active);
  form.can_update_project_dates = Boolean(data.can_update_project_dates);
  form.can_update_notes = Boolean(data.can_update_notes);
}

function closeDialog() {
  if (updateExecutionTaskAssignments.loading) return;
  closeTaskAssignmentModal();
  isOpen.value = false;
}

const projectDetails = createResource({
  url: "verto.api.planner.get_project_planner_details",
  auto: false,
  makeParams() {
    return {
      project: props.project?.project,
    };
  },
  onSuccess(data: ProjectDetails | undefined) {
    applyDetails(data);
  },
  onError(error: { messages?: string[]; message?: string }) {
    raiseToast(
      "error",
      error?.messages?.[0] ||
        error?.message ||
        "Failed to load project details",
    );
  },
});

function confirmCreateGenericTasks() {
  if (!canSubmitGenericTasks.value || createGenericTasks.loading) return;

  const locationCount = form.generic_locations.length;
  const locationLabel = locationCount === 1 ? "location" : "locations";
  dialog.confirm({
    title: `Add tasks to ${form.project_name || form.project}?`,
    message: `This will add ${genericTaskTotalCount.value} tasks across ${locationCount} ${locationLabel}. Existing tasks will be preserved.`,
    onConfirm: () => createGenericTasks.submit(),
  });
}

const createGenericTasks = createResource({
  url: "verto.api.planner.create_generic_project_tasks",
  auto: false,
  makeParams() {
    return {
      project: form.project,
      locations: form.generic_locations.map((location) => ({
        subject: location.subject.trim(),
        task: location.task || undefined,
        work_summaries: location.work_summaries.map((subject) =>
          subject.trim(),
        ),
      })),
      expected_start_time: form.generic_start_time,
      expected_end_time: form.generic_end_time,
    };
  },
  onSuccess(data: GenericTaskResponse | undefined) {
    applyDetails(data?.project_details);
    const createdCount =
      data?.created_tasks?.length || genericTaskTotalCount.value;
    raiseToast(
      "success",
      `Created ${createdCount} linked generic tasks for ${form.project_name || form.project}.`,
    );
    emit("fetchEvents");
  },
  onError(error: { messages?: string[]; message?: string }) {
    raiseToast(
      "error",
      error?.messages?.[0] ||
        error?.message ||
        "Failed to create generic tasks",
    );
    projectDetails.fetch();
  },
});

const assignmentUsers = createResource({
  url: "verto.api.planner.get_task_assignment_users",
  auto: false,
  makeParams() {
    return {
      project: form.project,
      task: selectedExecutionTask.value?.name,
    };
  },
  onSuccess(data: AssignmentUsersResponse) {
    if (data.task !== selectedExecutionTask.value?.name) return;
    initialAssignmentUsers.value = [...data.assigned_users];
    selectedAssignmentUsers.value = [...data.assigned_users];
  },
  onError(error: { messages?: string[]; message?: string }) {
    raiseToast(
      "error",
      error?.messages?.[0] || error?.message || "Failed to load personnel",
    );
    closeTaskAssignmentModal();
  },
});

const updateExecutionTaskAssignments = createResource({
  url: "verto.api.planner.update_project_execution_task_assignments",
  auto: false,
  makeParams() {
    return {
      project: form.project,
      task: selectedExecutionTask.value?.name,
      add_users: assignmentAdditions.value,
      remove_users: assignmentRemovals.value,
    };
  },
  onSuccess(data: AssignmentResponse | undefined) {
    applyDetails(data?.project_details);
    resetTaskAssignmentModal();
    const added = data?.assigned_users?.length || 0;
    const removed = data?.removed_users?.length || 0;
    raiseToast(
      "success",
      `Task personnel updated: ${added} added, ${removed} removed.`,
    );
    emit("fetchEvents");
  },
  onError(error: { messages?: string[]; message?: string }) {
    raiseToast(
      "error",
      error?.messages?.[0] ||
        error?.message ||
        "Failed to update task personnel",
    );
  },
});

const updateProject = createResource({
  url: "verto.api.planner.update_project_planner_details",
  auto: false,
  makeParams() {
    return {
      project: form.project,
      po_number: form.po_number,
      po_entered: form.po_entered ? 1 : 0,
      ds_requested: form.ds_requested,
      ns_requested: form.ns_requested,
      is_active: form.is_active ? 1 : 0,
      project_start_date: form.project_start_date,
      project_end_date: form.project_end_date,
      project_notes: form.project_notes,
    };
  },
  onSuccess(data: ProjectDetails | undefined) {
    applyDetails(data);
    raiseToast("success", "Project updated successfully!");
    emit("fetchEvents");
  },
  onError(error: { messages?: string[]; message?: string }) {
    raiseToast(
      "error",
      error?.messages?.[0] || error?.message || "Failed to update project",
    );
  },
});

watch(
  [() => props.isDialogOpen, () => props.project?.project],
  ([open]) => {
    if (!open) return;
    resetForm();
    if (props.project?.project) projectDetails.fetch();
  },
  { immediate: true },
);
</script>

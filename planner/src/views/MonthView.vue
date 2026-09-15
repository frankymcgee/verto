<template>
  <div
    ref="shellRef"
    class="overflow-hidden flex flex-col"
    :style="{ height: shellHeight + 'px' }"
  >
    <!-- Toolbar / Title row -->
    <div ref="toolbarRef" class="px-6 py-4 pb-4">
      <div v-if="plannerViewReady" class="flex items-center">
        <Icon name="lucide-calendar" class="h-7 w-7 text-gray-500 mr-2.5" />
        <span class="text-3xl-semibold text-gray-500 mr-2">Roster:</span>
        <span class="text-3xl-semibold">{{ activeViewLabel }}</span>

        <button
          type="button"
          class="ml-3 flex items-center gap-1.5 rounded-full border border-gray-200 px-2.5 py-1 text-xs text-gray-600"
          :title="lastUpdated ? `Last updated ${lastUpdated.toLocaleTimeString()}. Click to refresh.` : 'Click to refresh planner data'"
          @click="refreshLive"
        >
          <span class="h-2 w-2 rounded-full" :class="liveStatus === 'Live' ? 'bg-green-500' : 'bg-amber-500'" />
          {{ liveRefreshing ? 'Updating…' : liveStatus }}
        </button>

        <TabButtons
          class="ml-6"
          :model-value="viewMode"
          :options="[
            { label: 'Month', value: 'month' },
            { label: 'Annual', value: 'year' },
          ]"
          @update:model-value="(value) => setViewMode(value as ViewMode)"
        />

        <button
          v-if="viewMode === 'year'"
          type="button"
          class="ml-2 rounded-5 border border-gray-200 bg-white px-3 py-1.5 text-sm-medium text-gray-700 shadow-sm transition hover:bg-gray-50 hover:text-gray-900"
          @click="goToToday"
        >
          Today
        </button>

        <div class="ml-auto space-x-2.5">
          <Dropdown
            :options="VIEW_OPTIONS"
            :button="{
              label: 'View',
              iconRight: 'lucide-chevron-down',
              size: 'md',
            }"
          />
          <Dropdown
            :options="[
              {
                label: 'Project',
                onClick: () => {
                  showProjectDialog = true;
                },
              },
              {
                label: 'Leave Application',
                onClick: () => {
                  showLeaveApplicationDialog = true;
                },
              },
              {
                label: 'Shift Assignment',
                onClick: () => {
                  showShiftAssignmentDialog = true;
                },
              },
              {
                label: 'Event',
                onClick: () => {
                  showEventDialog = true;
                },
              },
            ]"
            :button="{
              label: 'Create',
              variant: 'solid',
              iconRight: 'lucide-chevron-down',
              size: 'md',
            }"
          />
        </div>
      </div>
    </div>

    <!-- Filters header -->
    <div ref="filtersRef" class="px-6 pb-4">
      <MonthViewHeader
        v-if="plannerViewReady"
        :firstOfMonth="firstOfMonth"
        :viewMode="viewMode"
        @updateFilters="updateFilters"
        @addToMonth="addToMonth"
        @updateDateRange="onUpdateDateRange"
        @updateProjectShiftsFilled="onUpdateProjectShiftsFilled"
      />
    </div>

    <!-- Projects timeline (collapsible) - month view only -->
    <div
      v-if="plannerViewReady && isCompanySelected && viewMode === 'month'"
      ref="timelineRef"
      class="px-6 pb-4"
    >
      <ProjectTimelineRow
        ref="projectTimeline"
        v-model:collapsed="projectsCollapsed"
        :firstOfMonth="firstOfMonth"
        :projectFilters="projectFilters"
        :dayColWidthPx="144"
        :leftColWidthPx="256"
        :scrollLeft="hScroll"
        @height="timelineHeight = $event"
      />
    </div>

    <!-- Table area fills remaining height -->
    <div ref="tableAreaRef" class="px-6 pb-8 flex-1 min-h-0 mt-px">
      <template v-if="plannerViewReady">
        <MonthViewTable
          v-if="isCompanySelected && viewMode === 'month'"
          ref="monthViewTable"
          :firstOfMonth="firstOfMonth"
          :employees="availableEmployees"
          :employeeFilters="employeeFilters"
          :shiftFilters="shiftFilters"
          :maxHeightPx="tableHeight"
          @hscroll="hScroll = $event"
        />

        <YearViewTable
          v-else-if="isCompanySelected && viewMode === 'year'"
          ref="yearViewTable"
          :firstOfMonth="firstOfMonth"
          :employees="availableEmployees"
          :employeeFilters="employeeFilters"
          :shiftFilters="shiftFilters"
          :maxHeightPx="tableHeight"
          @hscroll="hScroll = $event"
        />

        <div v-else class="py-40 text-center">Please select a company.</div>
      </template>
      <div v-else class="py-40 text-center text-gray-500">
        Loading planner...
      </div>
    </div>
  </div>

  <ProjectDialog
    v-model="showProjectDialog"
    :isDialogOpen="showProjectDialog"
    :company="employeeFilters.company"
    @fetchEvents="
      fetchActiveEvents();
      showProjectDialog = false;
    "
  />

  <LeaveApplicationDialog
    v-model="showLeaveApplicationDialog"
    :isDialogOpen="showLeaveApplicationDialog"
    :company="employeeFilters.company"
    @fetchEvents="
      fetchActiveEvents();
      showLeaveApplicationDialog = false;
    "
  />

  <ShiftAssignmentDialog
    v-model="showShiftAssignmentDialog"
    :isDialogOpen="showShiftAssignmentDialog"
    :employees="employees.data"
    @fetchEvents="
      fetchActiveEvents();
      showShiftAssignmentDialog = false;
    "
  />

  <EventDialog
    v-model="showEventDialog"
    :isDialogOpen="showEventDialog"
    @fetchEvents="
      fetchActiveEvents();
      showEventDialog = false;
    "
  />
</template>

<script setup lang="ts">
import { usePlannerSettings } from "../utils/settings";
import { usePlannerBootstrap } from "../utils/bootstrap";
import { usePlannerRealtime } from "../composables/usePlannerRealtime";
import { coalesceResource } from "../utils/coalesceResource";
import {
  ref,
  reactive,
  computed,
  nextTick,
  onMounted,
  onBeforeUnmount,
  toRaw,
  watch,
} from "vue";
import {
  TabButtons,
  Dropdown,
  Icon,
  createListResource,
  createResource,
} from "frappe-ui";
import { dayjs, goTo, raiseToast } from "../utils";
import MonthViewTable from "../components/MonthViewTable.vue";
import YearViewTable from "../components/YearViewTable.vue";
import ProjectTimelineRow from "../components/ProjectTimelineRow.vue";
import MonthViewHeader from "../components/MonthViewHeader.vue";
import ShiftAssignmentDialog from "../components/ShiftAssignmentDialog.vue";
import EventDialog from "../components/EventDialog.vue";
import ProjectDialog from "../components/ProjectDialog.vue";
import LeaveApplicationDialog from "../components/LeaveApplicationDialog.vue";

export type EmployeeFilters = {
  [
    K in "status" | "company" | "department" | "branch" | "designation"
  ]?: string;
};
export type ShiftFilters = {
  [K in "shift_type" | "shift_location"]?: string;
};

type AvailabilityResponse = { employees: { name: string }[] };
type ViewMode = "month" | "year";

const shellRef = ref<HTMLElement | null>(null);
const tableAreaRef = ref<HTMLElement | null>(null);
const monthViewTable = ref<InstanceType<typeof MonthViewTable>>();
const yearViewTable = ref<InstanceType<typeof YearViewTable>>();
const projectTimeline = ref<InstanceType<typeof ProjectTimelineRow>>();
const isCompanySelected = ref(false);
const showProjectDialog = ref(false);
const showLeaveApplicationDialog = ref(false);
const showShiftAssignmentDialog = ref(false);
const showEventDialog = ref(false);
const firstOfMonth = ref(dayjs().date(1).startOf("D"));
const viewMode = ref<ViewMode>("month");
const plannerDefaultViewApplied = ref(false);
const plannerViewReady = ref(false);
const employeeFilters = reactive<EmployeeFilters>({ status: "Active" });
const shiftFilters = reactive<ShiftFilters>({});
const dateRange = reactive<{ from: string | null; to: string | null }>({
  from: null,
  to: null,
});
const hScroll = ref(0);
const projectsCollapsed = ref(false);
const toolbarRef = ref<HTMLElement | null>(null);
const filtersRef = ref<HTMLElement | null>(null);
const timelineRef = ref<HTMLElement | null>(null);
const toolbarHeight = ref(0);
const filtersHeight = ref(0);
const timelineHeight = ref(0);
const shellHeight = ref(window.innerHeight);
const viewportHeight = ref(window.innerHeight);
const tableAreaTop = ref(0);
const projectFilters = reactive<{ company?: string; shifts_filled?: 0 | 1 }>(
  {},
);
let roToolbar: ResizeObserver | null = null;
let roFilters: ResizeObserver | null = null;
let roTimeline: ResizeObserver | null = null;
let todayScrollTimers: number[] = [];

const activeViewLabel = computed(() => {
  if (!plannerViewReady.value) return "Loading...";
  return viewMode.value === "month" ? "Month View" : "Annual View";
});

const VIEW_OPTIONS = [
  "Shift Type",
  "Shift Location",
  "Shift Assignment",
  "Shift Schedule",
  "Shift Schedule Assignment",
].map((label) => ({
  label,
  onClick: () => goTo(`/app/${label.toLowerCase().split(" ").join("-")}`),
}));

function setViewMode(mode: ViewMode) {
  if (mode === "year") {
    goToToday();
    return;
  }

  clearTodayScrollTimers();
  viewMode.value = mode;
  hScroll.value = 0;
}

function clearTodayScrollTimers() {
  todayScrollTimers.forEach((timer) => window.clearTimeout(timer));
  todayScrollTimers = [];
}

async function scrollYearViewToToday() {
  await nextTick();
  clearTodayScrollTimers();

  const runScroll = () => {
    if (viewMode.value !== "year") return;
    yearViewTable.value?.scrollToToday?.();
  };

  window.requestAnimationFrame(() => {
    runScroll();
    updateLayoutMeasurements();
  });

  [80, 180, 350, 700, 1200, 2000].forEach((delay) => {
    const timer = window.setTimeout(() => {
      runScroll();
      updateLayoutMeasurements();
    }, delay);
    todayScrollTimers.push(timer);
  });
}

async function goToToday() {
  viewMode.value = "year";
  firstOfMonth.value = dayjs().date(1).startOf("D");
  hScroll.value = 0;

  await scrollYearViewToToday();
}

function normalisePlannerDefaultView(value: unknown): ViewMode {
  const selected = String(value || "")
    .trim()
    .toLowerCase();
  return selected === "annual" || selected === "year" ? "year" : "month";
}

async function applyPlannerDefaultView(value: unknown) {
  if (plannerDefaultViewApplied.value) return;

  const defaultView = normalisePlannerDefaultView(value);

  if (defaultView === "year") {
    viewMode.value = "year";
    firstOfMonth.value = dayjs().date(1).startOf("D");
  } else {
    viewMode.value = "month";
  }

  hScroll.value = 0;
  plannerDefaultViewApplied.value = true;
  plannerViewReady.value = true;

  await nextTick();
  updateLayoutMeasurements();
  window.requestAnimationFrame(updateLayoutMeasurements);

  if (defaultView === "year") {
    await scrollYearViewToToday();
  }
}

function fetchActiveEvents() {
  if (!plannerViewReady.value) return;
  if (viewMode.value === "month") void monthViewTable.value?.events.fetch().catch(() => {});
  else void yearViewTable.value?.events.fetch().catch(() => {});
}

function addToMonth(change: number) {
  firstOfMonth.value = firstOfMonth.value.add(change, "M");
  // If you want the dateRange to snap with month/year navigation, uncomment:
  // dateRange.from = firstOfMonth.value.startOf(viewMode.value === 'year' ? 'year' : 'month').format('YYYY-MM-DD')
  // dateRange.to = firstOfMonth.value.endOf(viewMode.value === 'year' ? 'year' : 'month').format('YYYY-MM-DD')
  // fetchAvailability()
}

function updateFilters(newFilters: EmployeeFilters & ShiftFilters) {
  isCompanySelected.value = !!newFilters.company;

  let employeeUpdated = false;
  (
    Object.entries(newFilters) as [
      keyof EmployeeFilters | keyof ShiftFilters,
      string,
    ][]
  ).forEach(([key, value]) => {
    if (["shift_type", "shift_location"].includes(key as string)) {
      if (value) shiftFilters[key as keyof ShiftFilters] = value;
      else delete shiftFilters[key as keyof ShiftFilters];
      return;
    }
    if ((employeeFilters[key as keyof EmployeeFilters] || "") !== (value || "")) {
      if (value) employeeFilters[key as keyof EmployeeFilters] = value;
      else delete employeeFilters[key as keyof EmployeeFilters];
      employeeUpdated = true;
    }
  });

  if (employeeUpdated && isCompanySelected.value) {
    void employees.fetch().catch(() => {});
    void fetchAvailability()?.catch(() => {});
  }
}

// Calculate the height available to the employee table area from its actual
// viewport position. This accounts for the Frappe navbar/top chrome, toolbar,
// filters, the month-project timeline, and the bottom page padding.
const tableHeight = computed(() => {
  const bottomPadding = 32;
  const top = tableAreaTop.value;

  if (top > 0) {
    return Math.max(200, viewportHeight.value - top - bottomPadding);
  }

  // Fallback for the first render before refs are measured.
  const used =
    toolbarHeight.value +
    filtersHeight.value +
    (viewMode.value === "month" ? timelineHeight.value : 0);
  return Math.max(200, shellHeight.value - used - bottomPadding);
});

function observeHeights() {
  if (toolbarRef.value) {
    roToolbar = new ResizeObserver(() => {
      toolbarHeight.value = toolbarRef.value!.getBoundingClientRect().height;
      window.requestAnimationFrame(updateTableAreaTop);
    });
    roToolbar.observe(toolbarRef.value);
  }
  if (filtersRef.value) {
    roFilters = new ResizeObserver(() => {
      filtersHeight.value = filtersRef.value!.getBoundingClientRect().height;
      window.requestAnimationFrame(updateTableAreaTop);
    });
    roFilters.observe(filtersRef.value);
  }
}

// The month timeline now mounts only when visible, including after an annual
// view switch. Attach its size observer when that element becomes available.
watch(timelineRef, (element) => {
  roTimeline?.disconnect();
  if (!element) return;
  roTimeline = new ResizeObserver(() => {
    timelineHeight.value = element.getBoundingClientRect().height;
    window.requestAnimationFrame(updateTableAreaTop);
  });
  roTimeline.observe(element);
}, { flush: 'post' });

function unobserveHeights() {
  roToolbar?.disconnect();
  roFilters?.disconnect();
  roTimeline?.disconnect();
}

function updateShellHeight() {
  viewportHeight.value = window.innerHeight;
  const top = shellRef.value?.getBoundingClientRect().top ?? 0;
  shellHeight.value = Math.max(320, viewportHeight.value - top);
}

function updateTableAreaTop() {
  tableAreaTop.value = tableAreaRef.value?.getBoundingClientRect().top ?? 0;
}

function updateLayoutMeasurements() {
  updateShellHeight();
  updateTableAreaTop();
}

function onWindowResize() {
  updateLayoutMeasurements();
}

onMounted(() => {
  observeHeights();
  window.addEventListener("resize", onWindowResize);

  // The roster is rendered below the Frappe navbar. Using plain h-screen makes
  // the page taller than the visible area, so measure where this component
  // starts and subtract that offset from the viewport height.
  updateLayoutMeasurements();
  window.requestAnimationFrame(updateLayoutMeasurements);

  // initialize once
  toolbarHeight.value = toolbarRef.value?.getBoundingClientRect().height ?? 0;
  filtersHeight.value = filtersRef.value?.getBoundingClientRect().height ?? 0;
  timelineHeight.value = timelineRef.value?.getBoundingClientRect().height ?? 0;
  updateTableAreaTop();
});

onBeforeUnmount(() => {
  clearTodayScrollTimers();
  unobserveHeights();
  window.removeEventListener("resize", onWindowResize);
});

watch(
  () => [
    plannerViewReady.value,
    viewMode.value,
    firstOfMonth.value?.valueOf?.(),
    projectsCollapsed.value,
    isCompanySelected.value,
  ],
  async () => {
    if (!plannerViewReady.value) return;

    await nextTick();
    updateLayoutMeasurements();
    window.requestAnimationFrame(updateLayoutMeasurements);

    if (viewMode.value === "year" && isCompanySelected.value) {
      scrollYearViewToToday();
    }
  },
);

const plannerSettings = usePlannerSettings();
const bootstrap = usePlannerBootstrap();
watch(
  () => [plannerSettings.fetched, plannerSettings.error],
  () => {
    if (plannerSettings.fetched || plannerSettings.error) {
      applyPlannerDefaultView(plannerSettings.data?.planner_view_default || "Month");
    }
  },
  { immediate: true },
);

const employees = coalesceResource(createListResource({
  doctype: "Employee",
  fields: [
    "name",
    "employee_name",
    "first_name",
    "last_name",
    "department",
    "designation",
    "image",
  ],
  filters: employeeFilters,
  pageLength: 99999,
  onError(error: { messages: string[] }) {
    raiseToast("error", error.messages[0]);
  },
}));

const availableNameSet = ref<Set<string>>(new Set());
const availableEmployees = computed(() => {
  const base = employees.data || [];
  if (!availableNameSet.value.size) return base;
  return base.filter((e: any) => availableNameSet.value.has(e.name));
});

function cleaned<T extends Record<string, any>>(obj: T): Partial<T> {
  const raw = { ...toRaw(obj) };
  Object.keys(raw).forEach((k) => {
    if (raw[k] === "" || raw[k] == null) delete raw[k];
  });
  return raw;
}

const availability = coalesceResource(createResource({
  url: "verto.api.planner.get_available_employees",
  auto: false,
  makeParams() {
    return {
      from_date: dateRange.from,
      to_date: dateRange.to,
      ...cleaned(employeeFilters), // company/department/branch/designation
    };
  },
  onSuccess: (data: AvailabilityResponse | undefined) => {
    const names = (data?.employees || []).map((e: { name: string }) => e.name);
    availableNameSet.value = new Set(names);
  },
  onError(error: { messages?: string[]; message?: string }) {
    raiseToast(
      "error",
      error?.messages?.[0] || error?.message || "Failed to fetch availability",
    );
    availableNameSet.value = new Set();
  },
}));

onBeforeUnmount(() => { employees.disposeRefresh(); availability.disposeRefresh(); });

function fetchAvailability() {
  if (!isCompanySelected.value || !dateRange.from || !dateRange.to) {
    availableNameSet.value = new Set(); // show base list
    return;
  }
  return availability.fetch();
}

function onUpdateDateRange(
  payload: { from: string | null; to: string | null } | string,
) {
  if (typeof payload === "string") {
    const [from, to] = payload.split(",").map((s) => s?.trim() || "");
    dateRange.from = from || null;
    dateRange.to = to || null;
  } else {
    dateRange.from = payload.from;
    dateRange.to = payload.to;
  }
  void fetchAvailability()?.catch(() => {});
}

watch(
  () => employeeFilters.company,
  (company) => {
    if (company) projectFilters.company = company;
    else delete projectFilters.company;
  },
  { immediate: true },
);

function onUpdateProjectShiftsFilled(value: 0 | 1) {
  projectFilters.shifts_filled = value; // 0 = unfilled (default), 1 = filled
}

const activeTable = computed(() => viewMode.value === 'month' ? monthViewTable.value : yearViewTable.value);
const { status: liveStatus, refreshing: liveRefreshing, lastUpdated, refresh: refreshLive } = usePlannerRealtime({
  ready: () => Boolean(plannerViewReady.value && !employees.list.loading && !availability.loading
    && !plannerSettings.loading && !activeTable.value?.events.loading && !activeTable.value?.liveBusy),
  async refresh(scopes) {
    const check = (resource: any) => { const error = (resource?.list ?? resource)?.error; if (error) throw error; };
    const refreshes: Promise<any>[] = [];
    const load = (resource: any) => resource.fetch().then(() => check(resource));
    const sections = (['settings', 'references', 'projects'] as const).filter(scope => scopes.has(scope));
    if (sections.length) refreshes.push(bootstrap.fetch({ sections }).then(() => check(bootstrap)));
    if (scopes.has('employees') && isCompanySelected.value) refreshes.push(load(employees));
    if (isCompanySelected.value && dateRange.from && dateRange.to &&
      (scopes.has('roster') || scopes.has('employees') || scopes.has('settings'))) {
      refreshes.push(load(availability));
    }
    if (scopes.has('projects') && projectTimeline.value) refreshes.push(projectTimeline.value.refreshLive());
    // The annual response includes projects, hours and roster data together.
    const table = activeTable.value;
    if (table && isCompanySelected.value) {
      refreshes.push(load(table.events));
    }
    // Start independent reads together so the transport sends a single batch.
    // Wait for every read even when one fails, preserving live queue ordering.
    const results = await Promise.allSettled(refreshes);
    const failed = results.find(result => result.status === 'rejected');
    if (failed?.status === 'rejected') throw failed.reason;
    if (table && isCompanySelected.value && viewMode.value === 'year') await yearViewTable.value?.refreshLiveProjectDetails();
  },
});
</script>

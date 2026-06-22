<template>
  <div
    ref="shellRef"
    class="overflow-hidden flex flex-col"
    :style="{ height: shellHeight + 'px' }"
  >
    <!-- Toolbar / Title row -->
    <div ref="toolbarRef" class="px-6 py-4 pb-4">
      <div class="flex items-center">
        <FeatherIcon name="calendar" class="h-7 w-7 text-gray-500 mr-2.5" />
        <span class="font-semibold text-2xl text-gray-500 mr-2">Roster:</span>
        <span class="font-semibold text-2xl">{{ activeViewLabel }}</span>

        <div class="ml-6 inline-flex rounded-md border border-gray-200 bg-gray-50 p-0.5">
          <button
            type="button"
            class="px-3 py-1.5 text-sm font-medium rounded transition"
            :class="viewMode === 'month' ? 'bg-white shadow-sm text-gray-900' : 'text-gray-600 hover:text-gray-900'"
            @click="setViewMode('month')"
          >
            Month
          </button>
          <button
            type="button"
            class="px-3 py-1.5 text-sm font-medium rounded transition"
            :class="viewMode === 'year' ? 'bg-white shadow-sm text-gray-900' : 'text-gray-600 hover:text-gray-900'"
            @click="setViewMode('year')"
          >
            Annual
          </button>
        </div>

        <button
          v-if="viewMode === 'year'"
          type="button"
          class="ml-2 rounded-md border border-gray-200 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 shadow-sm transition hover:bg-gray-50 hover:text-gray-900"
          @click="goToToday"
        >
          Today
        </button>

        <div class="ml-auto space-x-2.5">
          <Dropdown
            :options="VIEW_OPTIONS"
            :button="{ label: 'View', iconRight: 'chevron-down', size: 'md' }"
          />
          <Dropdown
            :options="[
              {
                label: 'Shift Assignment',
                onClick: () => { showShiftAssignmentDialog = true },
              },
            ]"
            :button="{ label: 'Create', variant: 'solid', iconRight: 'chevron-down', size: 'md' }"
          />
        </div>
      </div>
    </div>

    <!-- Filters header -->
    <div ref="filtersRef" class="px-6 pb-4">
      <MonthViewHeader
        :firstOfMonth="firstOfMonth"
        :viewMode="viewMode"
        @updateFilters="updateFilters"
        @addToMonth="addToMonth"
        @updateDateRange="onUpdateDateRange"
        @updateProjectShiftsFilled="onUpdateProjectShiftsFilled"
      />
    </div>

    <!-- Projects timeline (collapsible) - month view only -->
    <div v-show="viewMode === 'month'" ref="timelineRef" class="px-6 pb-4">
      <ProjectTimelineRow
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
        :projectFilters="projectFilters"
        :maxHeightPx="tableHeight"
        @hscroll="hScroll = $event"
      />

      <div v-else class="py-40 text-center">Please select a company.</div>
    </div>
  </div>

  <ShiftAssignmentDialog
    v-model="showShiftAssignmentDialog"
    :isDialogOpen="showShiftAssignmentDialog"
    :employees="employees.data"
    @fetchEvents="
      fetchActiveEvents();
      showShiftAssignmentDialog = false;
    "
  />
</template>

<script setup lang="ts">
import { ref, reactive, computed, nextTick, onMounted, onBeforeUnmount, toRaw, watch } from 'vue'
import { Dropdown, FeatherIcon, createListResource, createResource } from 'frappe-ui'
import { dayjs, goTo, raiseToast } from '../utils'
import MonthViewTable from '../components/MonthViewTable.vue'
import YearViewTable from '../components/YearViewTable.vue'
import ProjectTimelineRow from '../components/ProjectTimelineRow.vue'
import MonthViewHeader from '../components/MonthViewHeader.vue'
import ShiftAssignmentDialog from '../components/ShiftAssignmentDialog.vue'

export type EmployeeFilters = {
  [K in 'status' | 'company' | 'department' | 'branch' | 'designation']?: string;
};
export type ShiftFilters = {
  [K in 'shift_type' | 'shift_location']?: string;
};

type AvailabilityResponse = { employees: { name: string }[] }
type ViewMode = 'month' | 'year'

const shellRef = ref<HTMLElement | null>(null)
const tableAreaRef = ref<HTMLElement | null>(null)
const monthViewTable = ref<InstanceType<typeof MonthViewTable>>()
const yearViewTable = ref<InstanceType<typeof YearViewTable>>()
const isCompanySelected = ref(false)
const showShiftAssignmentDialog = ref(false)
const firstOfMonth = ref(dayjs().date(1).startOf('D'))
const viewMode = ref<ViewMode>('month')
const employeeFilters = reactive<EmployeeFilters>({ status: 'Active' })
const shiftFilters = reactive<ShiftFilters>({})
const dateRange = reactive<{ from: string | null; to: string | null }>({ from: null, to: null })
const hScroll = ref(0)
const projectsCollapsed = ref(false)
const toolbarRef = ref<HTMLElement | null>(null)
const filtersRef = ref<HTMLElement | null>(null)
const timelineRef = ref<HTMLElement | null>(null)
const toolbarHeight = ref(0)
const filtersHeight = ref(0)
const timelineHeight = ref(0)
const shellHeight = ref(window.innerHeight)
const viewportHeight = ref(window.innerHeight)
const tableAreaTop = ref(0)
const projectFilters = reactive<{ company?: string; shifts_filled?: 0 | 1 }>({})
let roToolbar: ResizeObserver | null = null
let roFilters: ResizeObserver | null = null
let roTimeline: ResizeObserver | null = null

const activeViewLabel = computed(() => viewMode.value === 'month' ? 'Month View' : 'Annual View')

const VIEW_OPTIONS = [
  'Shift Type',
  'Shift Location',
  'Shift Assignment',
  'Shift Schedule',
  'Shift Schedule Assignment',
].map((label) => ({
  label,
  onClick: () => goTo(`/app/${label.toLowerCase().split(' ').join('-')}`),
}))

function setViewMode(mode: ViewMode) {
  if (mode === 'year') {
    goToToday()
    return
  }

  viewMode.value = mode
  hScroll.value = 0
}

async function goToToday() {
  viewMode.value = 'year'
  firstOfMonth.value = dayjs().date(1).startOf('D')
  hScroll.value = 0

  await nextTick()

  const runScroll = () => yearViewTable.value?.scrollToToday?.()

  window.requestAnimationFrame(() => {
    runScroll()
    window.setTimeout(runScroll, 80)
    window.setTimeout(runScroll, 250)
  })
}

function fetchActiveEvents() {
  if (viewMode.value === 'month') monthViewTable.value?.events.fetch()
  else yearViewTable.value?.events.fetch()
}

function addToMonth(change: number) {
  firstOfMonth.value = firstOfMonth.value.add(change, 'M')
  // If you want the dateRange to snap with month/year navigation, uncomment:
  // dateRange.from = firstOfMonth.value.startOf(viewMode.value === 'year' ? 'year' : 'month').format('YYYY-MM-DD')
  // dateRange.to = firstOfMonth.value.endOf(viewMode.value === 'year' ? 'year' : 'month').format('YYYY-MM-DD')
  // fetchAvailability()
}

function updateFilters(newFilters: EmployeeFilters & ShiftFilters) {
  isCompanySelected.value = !!newFilters.company
  if (!isCompanySelected.value) return

  let employeeUpdated = false
  ;(Object.entries(newFilters) as [keyof EmployeeFilters | keyof ShiftFilters, string][])
    .forEach(([key, value]) => {
      if (['shift_type', 'shift_location'].includes(key as string)) {
        if (value) shiftFilters[key as keyof ShiftFilters] = value
        else delete shiftFilters[key as keyof ShiftFilters]
        return
      }
      if (value) employeeFilters[key as keyof EmployeeFilters] = value
      else delete employeeFilters[key as keyof EmployeeFilters]
      employeeUpdated = true
    })

  if (employeeUpdated) employees.fetch()
  fetchAvailability()
}

// Calculate the height available to the employee table area from its actual
// viewport position. This accounts for the Frappe navbar/top chrome, toolbar,
// filters, the month-project timeline, and the bottom page padding.
const tableHeight = computed(() => {
  const bottomPadding = 32
  const top = tableAreaTop.value

  if (top > 0) {
    return Math.max(200, viewportHeight.value - top - bottomPadding)
  }

  // Fallback for the first render before refs are measured.
  const used = toolbarHeight.value + filtersHeight.value + (viewMode.value === 'month' ? timelineHeight.value : 0)
  return Math.max(200, shellHeight.value - used - bottomPadding)
})

function observeHeights() {
  if (toolbarRef.value) {
    roToolbar = new ResizeObserver(() => {
      toolbarHeight.value = toolbarRef.value!.getBoundingClientRect().height
      window.requestAnimationFrame(updateTableAreaTop)
    })
    roToolbar.observe(toolbarRef.value)
  }
  if (filtersRef.value) {
    roFilters = new ResizeObserver(() => {
      filtersHeight.value = filtersRef.value!.getBoundingClientRect().height
      window.requestAnimationFrame(updateTableAreaTop)
    })
    roFilters.observe(filtersRef.value)
  }
  if (timelineRef.value) {
    roTimeline = new ResizeObserver(() => {
      timelineHeight.value = timelineRef.value!.getBoundingClientRect().height
      window.requestAnimationFrame(updateTableAreaTop)
    })
    roTimeline.observe(timelineRef.value)
  }
}

function unobserveHeights() {
  roToolbar?.disconnect()
  roFilters?.disconnect()
  roTimeline?.disconnect()
}

function updateShellHeight() {
  viewportHeight.value = window.innerHeight
  const top = shellRef.value?.getBoundingClientRect().top ?? 0
  shellHeight.value = Math.max(320, viewportHeight.value - top)
}

function updateTableAreaTop() {
  tableAreaTop.value = tableAreaRef.value?.getBoundingClientRect().top ?? 0
}

function updateLayoutMeasurements() {
  updateShellHeight()
  updateTableAreaTop()
}

function onWindowResize() {
  updateLayoutMeasurements()
}

onMounted(() => {
  observeHeights()
  window.addEventListener('resize', onWindowResize)

  // The roster is rendered below the Frappe navbar. Using plain h-screen makes
  // the page taller than the visible area, so measure where this component
  // starts and subtract that offset from the viewport height.
  updateLayoutMeasurements()
  window.requestAnimationFrame(updateLayoutMeasurements)

  // initialize once
  toolbarHeight.value = toolbarRef.value?.getBoundingClientRect().height ?? 0
  filtersHeight.value = filtersRef.value?.getBoundingClientRect().height ?? 0
  timelineHeight.value = timelineRef.value?.getBoundingClientRect().height ?? 0
  updateTableAreaTop()
})

onBeforeUnmount(() => {
  unobserveHeights()
  window.removeEventListener('resize', onWindowResize)
})

watch(
  () => [viewMode.value, firstOfMonth.value?.valueOf?.(), projectsCollapsed.value, isCompanySelected.value],
  async () => {
    await nextTick()
    updateLayoutMeasurements()
    window.requestAnimationFrame(updateLayoutMeasurements)
  },
)

const employees = createListResource({
  doctype: 'Employee',
  fields: ['name', 'employee_name', 'first_name', 'last_name', 'department', 'designation', 'image'],
  filters: employeeFilters,
  pageLength: 99999,
  onSuccess() {
    fetchAvailability()
  },
  onError(error: { messages: string[] }) {
    raiseToast('error', error.messages[0])
  },
})

const availableNameSet = ref<Set<string>>(new Set())
const availableEmployees = computed(() => {
  const base = employees.data || []
  if (!availableNameSet.value.size) return base
  return base.filter((e: any) => availableNameSet.value.has(e.name))
})

function cleaned<T extends Record<string, any>>(obj: T): Partial<T> {
  const raw = { ...toRaw(obj) }
  Object.keys(raw).forEach((k) => {
    if (raw[k] === '' || raw[k] == null) delete raw[k]
  })
  return raw
}

const availability = createResource({
  url: 'verto.api.planner.get_available_employees',
  auto: false,
  makeParams() {
    return {
      from_date: dateRange.from,
      to_date: dateRange.to,
      ...cleaned(employeeFilters), // company/department/branch/designation
    }
  },
  onSuccess: (data: AvailabilityResponse | undefined) => {
    const names = (data?.employees || []).map((e: { name: string }) => e.name)
    availableNameSet.value = new Set(names)
  },
  onError(error: { messages?: string[]; message?: string }) {
    raiseToast('error', error?.messages?.[0] || error?.message || 'Failed to fetch availability')
    availableNameSet.value = new Set()
  },
})

function fetchAvailability() {
  if (!isCompanySelected.value || !dateRange.from || !dateRange.to) {
    availableNameSet.value = new Set() // show base list
    return
  }
  availability.fetch()
}

function onUpdateDateRange(payload: { from: string | null; to: string | null } | string) {
  if (typeof payload === 'string') {
    const [from, to] = payload.split(',').map(s => s?.trim() || '')
    dateRange.from = from || null
    dateRange.to = to || null
  } else {
    dateRange.from = payload.from
    dateRange.to = payload.to
  }
  fetchAvailability()
}

watch(
  () => employeeFilters.company,
  (company) => {
    if (company) projectFilters.company = company
    else delete projectFilters.company
  },
  { immediate: true }
)

function onUpdateProjectShiftsFilled(value: 0 | 1) {
  projectFilters.shifts_filled = value   // 0 = unfilled (default), 1 = filled
}
</script>

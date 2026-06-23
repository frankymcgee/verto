<template>
  <div
    class="year-roster-shell flex flex-col gap-0"
    :class="[
      loading && 'animate-pulse pointer-events-none',
      showShiftAssignmentDialog && 'year-dialog-open',
      showProjectSpanDialog && 'year-dialog-open',
    ]"
    :style="maxHeightPx ? { height: maxHeightPx + 'px' } : {}"
  >
    <!-- Annual project / planning view. This is intentionally separate from employees. -->
    <section v-if="showProjectsPanel" class="year-roster-panel rounded-lg border bg-white">
      <div
        ref="projectScroller"
        class="year-roster-scroller overflow-auto"
        :style="{ maxHeight: projectTableMaxHeight + 'px' }"
        @scroll="onProjectScroll"
      >
        <div class="year-table-stage">
          <div
            v-if="showTodayOverlay"
            class="year-today-overlay"
            :style="todayOverlayStyle"
            aria-hidden="true"
          />

          <table class="year-roster-table border-separate border-spacing-0">
            <colgroup>
              <col class="year-left-colgroup" />
              <col v-for="day in daysOfYear" :key="`project-col-${day.date}`" class="year-day-colgroup" />
            </colgroup>
          <thead>
            <tr>
              <th rowspan="2" class="year-left-header year-left-col year-project-legend-header border-b border-r bg-white text-left">
                <div class="year-project-header-content px-2 py-1.5">
                  <div class="flex items-center justify-between gap-2 text-xs font-semibold text-gray-800">
                    <div class="flex min-w-0 items-center gap-1.5">
                      <FeatherIcon name="briefcase" class="year-project-header-icon" />
                      <span>Projects</span>
                    </div>

                    <button
                      v-if="allProjectRows.length"
                      type="button"
                      class="year-section-toggle year-section-inline-toggle"
                      :class="projectCollapsed && 'year-section-toggle-inactive'"
                      @click.stop="toggleProjectCollapsed"
                    >
                      <span class="year-section-toggle-icon">{{ projectCollapsed ? '▸' : '▾' }}</span>
                      <span>{{ projectCollapsed ? 'Show' : 'Hide' }}</span>
                    </button>
                  </div>

                  <div class="year-project-filter-row mt-1">
                    <span>Type</span>
                    <div class="year-project-filter-toggle" role="group" aria-label="Filter annual projects by roster or shutdown">
                      <button
                        type="button"
                        class="year-project-filter-option"
                        :class="projectTypeFilter === 'all' && 'year-project-filter-option-active'"
                        @click.stop="projectTypeFilter = 'all'"
                      >
                        Show All
                      </button>
                      <button
                        type="button"
                        class="year-project-filter-option"
                        :class="projectTypeFilter === 'roster' && 'year-project-filter-option-active'"
                        @click.stop="projectTypeFilter = 'roster'"
                      >
                        Roster
                      </button>
                      <button
                        type="button"
                        class="year-project-filter-option"
                        :class="projectTypeFilter === 'shutdown' && 'year-project-filter-option-active'"
                        @click.stop="projectTypeFilter = 'shutdown'"
                      >
                        Shutdown
                      </button>
                    </div>
                  </div>

                  <div class="mt-1 text-[10px] font-semibold leading-none text-gray-600">Legend</div>

                  <div class="year-project-legend mt-1">
                    <div class="year-project-legend-item">
                      <FeatherIcon name="check-circle" class="year-legend-icon year-legend-po-entered" />
                      <span>PO Entered</span>
                    </div>
                    <div class="year-project-legend-item">
                      <FeatherIcon name="x-circle" class="year-legend-icon year-legend-po-missing" />
                      <span>PO Missing</span>
                    </div>
                    <div class="year-project-legend-item">
                      <FeatherIcon name="bar-chart-2" class="year-legend-icon year-legend-gantt-available" />
                      <span>Gantt Available</span>
                    </div>
                    <div class="year-project-legend-item">
                      <FeatherIcon name="alert-triangle" class="year-legend-icon year-legend-gantt-missing" />
                      <span>Gantt Missing</span>
                    </div>
                    <div class="year-project-legend-item">
                      <FeatherIcon name="sun" class="year-legend-icon year-legend-ds-requested" />
                      <span># DS Requested</span>
                    </div>
                    <div class="year-project-legend-item">
                      <FeatherIcon name="moon" class="year-legend-icon year-legend-ns-requested" />
                      <span># NS Requested</span>
                    </div>
                  </div>
                </div>
              </th>

              <th
                v-for="month in monthGroups"
                :key="`project-month-${month.key}`"
                class="year-month-header border-b border-r bg-gray-50 text-center font-semibold text-gray-700"
                :colspan="month.days"
              >
                {{ month.label }}
              </th>
            </tr>
            <tr>
              <th
                v-for="day in daysOfYear"
                :key="`project-day-${day.date}`"
                class="year-day-header border-b border-r bg-white text-center font-medium"
                :class="{
                  'year-month-start': day.isMonthStart,
                  'year-weekend': day.isWeekend,
                  ...dayHeaderMarkerClass(day.date),
                }"
                :title="dayHeaderTitle(day.date)"
                @mouseenter="showDayMarkerHover(day.date, $event)"
                @mousemove="moveHoverCard"
                @mouseleave="() => scheduleClearHoverCard()"
              >
                <div class="text-[10px] leading-none text-gray-500">{{ day.weekday }}</div>
                <div class="mt-0.5 text-[11px] leading-none">{{ day.day }}</div>
              </th>
            </tr>
          </thead>

          <tbody v-show="showProjectBody">
            <tr v-if="!projectLanes.length" class="year-project-row">
              <td class="year-left-col border-b border-r bg-white">
                <div class="px-2 leading-tight">
                  <div class="truncate text-xs font-semibold text-gray-800">
                    No projects to show
                  </div>
                  <div class="truncate text-[10px] text-gray-500">
                    {{ projectEmptyStateMessage }}
                  </div>
                </div>
              </td>
              <td
                class="year-cell year-project-empty-cell border-b border-r text-left"
                :colspan="daysOfYear.length"
              >
                <div class="px-3 text-[10px] font-medium text-gray-500">
                  {{ projectEmptyStateMessage }}
                </div>
              </td>
            </tr>

            <tr v-for="lane in projectLanes" :key="lane.key" class="year-project-row">
              <td class="year-left-col border-b border-r bg-white">
                <div class="px-2 leading-tight">
                  <div class="truncate text-xs font-semibold text-gray-800" :title="lane.groupLabel">
                    {{ lane.groupLabel }}
                  </div>
                  <div class="truncate text-[10px] text-gray-500" :title="projectLaneSubline(lane)">
                    {{ projectLaneSubline(lane) }}
                  </div>
                </div>
              </td>

              <td
                v-for="segment in projectLaneSegments(lane)"
                :key="segment.key"
                class="year-cell year-project-cell border-b border-r text-center"
                :class="projectSegmentClass(segment)"
                :style="[projectSegmentStyle(segment), projectSegmentDragStyle(segment)]"
                :aria-label="segment.title"
                :colspan="segment.days"
                @mouseenter="segment.project ? showProjectHover(segment.project, segment, $event) : scheduleClearHoverCard()"
                @mousemove="moveHoverCard"
                @mouseleave="() => scheduleClearHoverCard()"
                @pointerdown="onProjectSegmentPointerDown(segment, $event)"
                @click="onProjectSegmentClick(segment, $event)"
              >
                <div
                  v-if="segment.active"
                  class="year-project-span-content"
                  :style="projectSegmentContentDragStyle(segment)"
                >
                  <button
                    type="button"
                    class="year-project-span-drag-handle year-project-span-drag-start"
                    title="Adjust project start date"
                    aria-label="Adjust project start date"
                    @pointerdown.stop.prevent="startProjectSpanDrag(segment, 'resize-start', $event)"
                  />
                  <button
                    type="button"
                    class="year-project-span-drag-handle year-project-span-drag-end"
                    title="Adjust project end date"
                    aria-label="Adjust project end date"
                    @pointerdown.stop.prevent="startProjectSpanDrag(segment, 'resize-end', $event)"
                  />

                  <div class="year-project-span-title-row">
                    <span class="year-project-span-name truncate">
                      {{ segment.label }}
                    </span>
                  </div>

                  <div class="year-project-span-meta-row">
                    <span
                      class="year-project-gantt-status-icon"
                      :class="projectHasGantt(segment.project) ? 'year-project-gantt-available' : 'year-project-gantt-missing'"
                      :title="projectGanttStatusLabel(segment.project)"
                    >
                      <FeatherIcon :name="projectHasGantt(segment.project) ? 'bar-chart-2' : 'alert-triangle'" class="year-project-inline-icon" />
                    </span>

                    <span
                      class="year-project-status-icon"
                      :class="segment.poEntered ? 'year-project-po-entered' : 'year-project-po-missing'"
                      :title="segment.poEntered ? 'PO Entered' : 'PO Missing'"
                    >
                      <FeatherIcon :name="segment.poEntered ? 'check-circle' : 'x-circle'" class="year-project-inline-icon" />
                    </span>

                    <span class="year-project-request-group" title="# DS Requested">
                      <span class="year-project-request year-project-request-ds">
                        <FeatherIcon name="sun" class="year-project-request-icon" />
                      </span>
                      <span class="year-project-request-count">{{ segment.dsRequested || 0 }}</span>
                    </span>

                    <span class="year-project-request-group" title="# NS Requested">
                      <span class="year-project-request year-project-request-ns">
                        <FeatherIcon name="moon" class="year-project-request-icon" />
                      </span>
                      <span class="year-project-request-count">{{ segment.nsRequested || 0 }}</span>
                    </span>
                  </div>
                </div>
              </td>
            </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div
        v-if="showTableResizer"
        class="year-table-resizer"
        :class="isResizingTables && 'year-table-resizer-active'"
        title="Drag to resize project and employee tables. Double-click to reset."
        @pointerdown="startTableResize"
        @dblclick="resetTableResize"
      >
        <span class="year-table-resizer-line"></span>
        <span class="year-table-resizer-handle" aria-hidden="true">
          <FeatherIcon name="menu" class="year-table-resizer-icon" />
        </span>
        <span class="year-table-resizer-line"></span>
      </div>
    </section>

    <!-- Annual employee roster view. This scrolls separately from the project table. -->
    <section v-if="showEmployeesPanel" class="year-roster-panel year-employee-panel flex min-h-0 flex-1 flex-col rounded-lg border bg-white">
      <div
        ref="employeeScroller"
        class="year-roster-scroller min-h-0 flex-1 overflow-auto"
        :style="{ maxHeight: employeeTableMaxHeight + 'px' }"
        @scroll="onEmployeeScroll"
      >
        <div class="year-table-stage">
          <div
            v-if="showTodayOverlay"
            class="year-today-overlay"
            :style="todayOverlayStyle"
            aria-hidden="true"
          />

          <table class="year-roster-table border-separate border-spacing-0">
            <colgroup>
              <col class="year-left-colgroup" />
              <col v-for="day in daysOfYear" :key="`employee-col-${day.date}`" class="year-day-colgroup" />
            </colgroup>
          <thead>
            <tr>
              <th rowspan="2" class="year-left-header year-left-col year-employee-search-header border-b border-r bg-white text-left">
                <div class="year-employee-header-content px-2 py-1.5">
                  <div class="flex items-center justify-between gap-2">
                    <div class="text-xs font-semibold text-gray-700">Employee</div>

                    <button
                      type="button"
                      class="year-section-toggle year-section-inline-toggle"
                      :class="employeeCollapsed && 'year-section-toggle-inactive'"
                      @click.stop="toggleEmployeeCollapsed"
                    >
                      <span class="year-section-toggle-icon">{{ employeeCollapsed ? '▸' : '▾' }}</span>
                      <span>{{ employeeCollapsed ? 'Show' : 'Hide' }}</span>
                    </button>
                  </div>

                  <div class="year-employee-search">
                    <Autocomplete
                      :options="employeeSearchOptions"
                      v-model="employeeSearch"
                      placeholder="Search Employee"
                      :multiple="true"
                    />
                  </div>

                  <div class="year-employee-legend-title">Legend</div>

                  <div class="year-employee-legend">
                    <div class="year-employee-legend-item">
                      <span class="year-employee-legend-dot year-employee-legend-fifo"></span>
                      <span>Fly-in/Fly-out</span>
                    </div>
                    <div class="year-employee-legend-item">
                      <span class="year-employee-legend-dot year-employee-legend-ds"></span>
                      <span>DS</span>
                    </div>
                    <div class="year-employee-legend-item">
                      <span class="year-employee-legend-dot year-employee-legend-ns"></span>
                      <span>NS</span>
                    </div>
                    <div class="year-employee-legend-item">
                      <span class="year-employee-legend-dot year-employee-legend-pth"></span>
                      <span>PTH</span>
                    </div>
                  </div>
                </div>
              </th>

              <th
                v-for="month in monthGroups"
                :key="`employee-month-${month.key}`"
                class="year-month-header border-b border-r bg-gray-50 text-center font-semibold text-gray-700"
                :colspan="month.days"
              >
                {{ month.label }}
              </th>
            </tr>
            <tr>
              <th
                v-for="day in daysOfYear"
                :key="`employee-day-${day.date}`"
                class="year-day-header border-b border-r bg-white text-center font-medium"
                :class="{
                  'year-month-start': day.isMonthStart,
                  'year-weekend': day.isWeekend,
                  ...dayHeaderMarkerClass(day.date),
                }"
                :title="dayHeaderTitle(day.date)"
                @mouseenter="showDayMarkerHover(day.date, $event)"
                @mousemove="moveHoverCard"
                @mouseleave="() => scheduleClearHoverCard()"
              >
                <div class="text-[10px] leading-none text-gray-500">{{ day.weekday }}</div>
                <div class="mt-0.5 text-[11px] leading-none">{{ day.day }}</div>
              </th>
            </tr>
          </thead>

          <tbody v-show="showEmployeeBody">
            <tr v-for="employee in visibleEmployees" :key="employee.name" class="year-employee-row">
              <td class="year-left-col border-b border-r bg-white">
                <div class="px-2 leading-tight">
                  <div class="truncate text-xs font-semibold text-gray-800" :title="employeeTitle(employee)">
                    {{ employeeDisplayName(employee) }}
                  </div>
                  <div class="truncate text-[10px] text-gray-500" :title="employeeSubline(employee)">
                    {{ employeeSubline(employee) }}
                  </div>
                </div>
              </td>

              <td
                v-for="day in daysOfYear"
                :key="`${employee.name}-${day.date}`"
                class="year-cell cursor-pointer border-b border-r text-center"
                :class="{
                  'year-month-start': day.isMonthStart,
                  'year-weekend': day.isWeekend,
                  ...employeeCellClass(employee.name, day.date),
                  ...employeeDragCellClass(employee.name, day.date),
                }"
                :style="employeeCellStyle(employee.name, day.date)"
                :aria-label="employeeCellTitle(employee.name, day.date)"
                :draggable="isEmployeeShiftCell(employee.name, day.date)"
                @mouseenter="showEmployeeHover(employee, day.date, $event)"
                @mousemove="moveHoverCard"
                @mouseleave="() => scheduleClearHoverCard()"
                @dragstart="onEmployeeCellDragStart(employee.name, day.date, $event)"
                @dragend="onEmployeeCellDragEnd"
                @dragenter="onEmployeeCellDragEnter(employee.name, day.date)"
                @dragleave="onEmployeeCellDragLeave(employee.name, day.date, $event)"
                @dragover="onEmployeeCellDragOver(employee.name, day.date, $event)"
                @drop="onEmployeeCellDrop(employee.name, day.date, $event)"
                @click="openEmployeeCell(employee.name, day.date, $event)"
              >
                {{ employeeCellLabel(employee.name, day.date) }}
              </td>
            </tr>
            </tbody>
          </table>
        </div>
      </div>
    </section>
  </div>


  <Teleport to="body">
    <div
      v-if="hoverCard"
      ref="hoverCardElement"
      class="year-hover-card"
      :class="`year-hover-card-${hoverCard.type}`"
      :style="hoverCardStyle"
      role="tooltip"
    >
      <div class="year-hover-card-header">
        <div class="min-w-0">
          <div class="year-hover-card-kicker">{{ hoverCard.kicker }}</div>
          <div class="year-hover-card-title truncate">{{ hoverCard.title }}</div>
          <div v-if="hoverCard.subtitle" class="year-hover-card-subtitle truncate">
            {{ hoverCard.subtitle }}
          </div>
        </div>

        <div
          v-if="hoverCard.badge || hoverCard.secondaryBadge"
          class="year-hover-card-badge-stack"
        >
          <span
            v-if="hoverCard.badge"
            class="year-hover-card-badge"
            :class="`year-hover-card-badge-${hoverCard.badgeTone || 'gray'}`"
          >
            {{ hoverCard.badge }}
          </span>
          <span
            v-if="hoverCard.secondaryBadge"
            class="year-hover-card-badge"
            :class="`year-hover-card-badge-${hoverCard.secondaryBadgeTone || 'gray'}`"
          >
            {{ hoverCard.secondaryBadge }}
          </span>
        </div>
      </div>

      <div class="year-hover-card-grid">
        <template v-for="row in hoverCard.rows" :key="row.label">
          <div v-if="row.value !== undefined && row.value !== null && row.value !== ''" class="year-hover-card-label">
            {{ row.label }}
          </div>
          <div v-if="row.value !== undefined && row.value !== null && row.value !== ''" class="year-hover-card-value truncate">
            {{ row.value }}
          </div>
        </template>
      </div>

      <div v-if="hoverCard.note" class="year-hover-card-note">
        {{ hoverCard.note }}
      </div>
    </div>
  </Teleport>

  <ShiftAssignmentDialog
    v-model="showShiftAssignmentDialog"
    :isDialogOpen="showShiftAssignmentDialog"
    :shiftAssignmentName="shiftAssignment"
    :selectedCell="selectedCell"
    :employees="employees"
    @fetchEvents="
      events.fetch();
      showShiftAssignmentDialog = false;
    "
  />

  <ProjectSpanDialog
    v-model="showProjectSpanDialog"
    :isDialogOpen="showProjectSpanDialog"
    :project="selectedProjectSpan"
    @fetchEvents="
      events.fetch();
      showProjectSpanDialog = false;
    "
  />
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue'
import colors from 'tailwindcss/colors'
import { Autocomplete, createResource, FeatherIcon } from 'frappe-ui'
import type { Dayjs } from 'dayjs'

import { dayjs, raiseToast } from '../utils'
import type { EmployeeFilters, ShiftFilters } from '../views/MonthView.vue'
import ShiftAssignmentDialog from './ShiftAssignmentDialog.vue'
import ProjectSpanDialog from './ProjectSpanDialog.vue'

type Color =
  | 'blue'
  | 'cyan'
  | 'fuchsia'
  | 'green'
  | 'lime'
  | 'orange'
  | 'pink'
  | 'red'
  | 'violet'
  | 'yellow'
  | 'gray'

type Employee = {
  name: string
  employee_name: string
  first_name?: string
  last_name?: string
  designation?: string
  department?: string
  image?: string
}

interface HolidayWithDate {
  holiday: string
  holiday_date: string
  description: string
  weekly_off: 0 | 1
}

interface LeaveApplication {
  leave: string
  leave_type: string
  from_date: string
  to_date: string
  reason?: string | null
  description?: string | null
  status?: string | null
  total_leave_days?: number | string | null
  half_day?: 0 | 1 | boolean | null
  half_day_date?: string | null
}

type DayMarkerType = 'holiday' | 'event' | 'today'

interface DayMarker {
  type: DayMarkerType
  name?: string | null
  title: string
  description?: string | null
  date?: string | null
  start_date?: string | null
  end_date?: string | null
  event_type?: string | null
  color?: string | null
  all_day?: 0 | 1 | boolean | null
  weekly_off?: 0 | 1 | boolean | null
}

type DayMarkers = Record<string, DayMarker[]>

type ShiftAssignment = {
  name: string
  shift_type: string
  shift_location?: string
  status: string
  start_date: string
  end_date?: string | null
  start_time?: string
  end_time?: string
  color?: string
  custom_project?: string
  custom_project_name?: string
  customer_abbreviation?: string | null
  note?: string | null
}

type RawEvent = HolidayWithDate | LeaveApplication | ShiftAssignment
type Events = Record<string, RawEvent[]>

type YearCell =
  | { type: 'holiday'; label: string; title: string }
  | { type: 'leave'; label: string; title: string; leave: LeaveApplication }
  | { type: 'shift'; label: string; title: string; shift: ShiftAssignment; shifts: ShiftAssignment[] }

type MappedEvents = Record<string, Record<string, YearCell>>

type ProjectDayCell = {
  label: string
  count: number
  color?: string
  shift_types?: string[]
  employees?: string[]
  ds_personnel?: string[]
  ns_personnel?: string[]
}

type ProjectRow = {
  project: string
  project_name: string
  status?: string
  customer?: string | null
  customer_name?: string | null
  custom_project_location?: string | null
  notes?: string | null
  roster_or_shutdown?: string | null
  task_count?: number | string | null
  has_tasks?: boolean | number | string | null
  shifts_filled?: boolean | number | string | null
  is_active?: boolean | number | string | null
  ds_personnel?: string[]
  ns_personnel?: string[]
  po_entered?: boolean
  ds_requested?: number
  ns_requested?: number
  customer_color?: string | null
  assignments: Record<string, ProjectDayCell>
}

type YearEventsResponse = {
  events?: Events
  project_rows?: ProjectRow[]
  day_markers?: DayMarkers
}

const emit = defineEmits<{ (e: 'hscroll', left: number): void }>()
const employeeScroller = ref<HTMLDivElement | null>(null)
const projectScroller = ref<HTMLDivElement | null>(null)

const props = defineProps<{
  firstOfMonth: Dayjs
  employees: Employee[]
  employeeFilters: { [K in keyof EmployeeFilters]?: string }
  shiftFilters: { [K in keyof ShiftFilters]?: string }
  projectFilters?: { company?: string; shifts_filled?: 0 | 1; roster_or_shutdown?: string }
  maxHeightPx?: number
}>()

const loading = ref(true)
const employeeSearch = ref<{ value: string; label: string }[]>([])
const projectCollapsed = ref(false)
const employeeCollapsed = ref(false)
const projectTypeFilter = ref<'all' | 'roster' | 'shutdown'>('all')
const shiftAssignment = ref<string>('')
const showShiftAssignmentDialog = ref(false)
const showProjectSpanDialog = ref(false)
const selectedProjectSpan = ref<ProjectRow | null>(null)
const selectedCell = ref<{ employee: string; date: string }>({ employee: '', date: '' })

type DraggedShift = {
  employee: string
  date: string
  shift: ShiftAssignment
}

type SelectedShiftCell = DraggedShift

type DropCell = {
  employee: string
  date: string
  shift: string
}

type BulkMoveShiftItem = {
  shift: string
  employee: string
  date: string
}

type BulkMoveShiftParams = {
  shifts: BulkMoveShiftItem[]
  target_employee: string
  target_date: string
}

const draggedShift = ref<DraggedShift | null>(null)
const selectedShiftCells = ref<Record<string, SelectedShiftCell>>({})
const dropCell = ref<DropCell>({ employee: '', date: '', shift: '' })
const pendingBulkShiftParams = ref<BulkMoveShiftParams | null>(null)
const pendingBulkShiftWillSwap = ref(false)
const isDroppingShift = ref(false)
const suppressNextCellClick = ref(false)
let suppressClickTimer: number | null = null
let dragPreviewElement: HTMLDivElement | null = null

type HoverCardRow = {
  label: string
  value?: string | number | null
}

type HoverCard = {
  type: 'shift' | 'project' | 'leave' | 'day-marker'
  x?: number
  y?: number
  kicker: string
  title: string
  subtitle?: string
  badge?: string
  badgeTone?: 'green' | 'red' | 'gray' | 'blue' | 'yellow'
  secondaryBadge?: string
  secondaryBadgeTone?: 'green' | 'red' | 'gray' | 'blue' | 'yellow'
  accent?: string
  rows: HoverCardRow[]
  note?: string
}

const hoverCard = shallowRef<HoverCard | null>(null)
const hoverCardElement = ref<HTMLDivElement | null>(null)

type HoverPointer = {
  clientX: number
  clientY: number
}

let hoverPositionFrame = 0
let pendingHoverPointer: HoverPointer | null = null
let hoverHideTimer: number | null = null
let activeHoverKey = ''
const htmlPlainTextCache = new Map<string, string>()

const LEFT_COLUMN_WIDTH = 300
const DAY_COLUMN_WIDTH = 28
const RESIZER_HEIGHT = 18
const PROJECT_TABLE_MIN_HEIGHT = 132
const PROJECT_TABLE_HEADER_HEIGHT = 112
const PROJECT_TABLE_ROW_HEIGHT = 36
const EMPLOYEE_TABLE_MIN_HEIGHT = 220

const projectTableHeight = ref<number | null>(null)
const isResizingTables = ref(false)

type ProjectSpanDragMode = 'move' | 'resize-start' | 'resize-end'

type ProjectSpanDateUpdateParams = {
  project: string
  project_start_date: string
  project_end_date: string
}

type ProjectSpanDragState = {
  mode: ProjectSpanDragMode
  project: ProjectRow
  projectKey: string
  startX: number
  originalStartIndex: number
  originalEndIndex: number
  deltaDays: number
}

const projectSpanDrag = ref<ProjectSpanDragState | null>(null)
const projectSpanDragMoved = ref(false)
const suppressNextProjectSpanClick = ref(false)
const pendingProjectDateUpdate = ref<ProjectSpanDateUpdateParams | null>(null)

let tableResizeStartY = 0
let tableResizeStartProjectHeight = 0
let syncingHorizontalScroll = false

function syncHorizontalScroll(source: 'project' | 'employee') {
  const sourceScroller = source === 'project' ? projectScroller.value : employeeScroller.value
  const targetScroller = source === 'project' ? employeeScroller.value : projectScroller.value

  if (!sourceScroller) return

  const left = sourceScroller.scrollLeft

  if (syncingHorizontalScroll) {
    emit('hscroll', left)
    return
  }

  if (targetScroller && Math.abs(targetScroller.scrollLeft - left) > 1) {
    syncingHorizontalScroll = true
    targetScroller.scrollLeft = left

    window.requestAnimationFrame(() => {
      syncingHorizontalScroll = false
    })
  }

  emit('hscroll', left)
}

function clampProjectTableHeight(height: number) {
  const maxHeight = Math.max(
    PROJECT_TABLE_MIN_HEIGHT,
    annualContentHeight.value - EMPLOYEE_TABLE_MIN_HEIGHT - sectionGap - RESIZER_HEIGHT,
  )

  return Math.min(maxHeight, Math.max(PROJECT_TABLE_MIN_HEIGHT, Math.round(height)))
}

function startTableResize(event: PointerEvent) {
  if (!showTableResizer.value) return

  isResizingTables.value = true
  tableResizeStartY = event.clientY
  tableResizeStartProjectHeight = projectTableMaxHeight.value

  window.addEventListener('pointermove', onTableResizePointerMove)
  window.addEventListener('pointerup', stopTableResize)
  window.addEventListener('pointercancel', stopTableResize)
  document.body.classList.add('year-table-is-resizing')
  event.preventDefault()
}

function onTableResizePointerMove(event: PointerEvent) {
  if (!isResizingTables.value) return

  const delta = event.clientY - tableResizeStartY
  projectTableHeight.value = clampProjectTableHeight(tableResizeStartProjectHeight + delta)
}

function stopTableResize() {
  if (!isResizingTables.value) return

  isResizingTables.value = false
  window.removeEventListener('pointermove', onTableResizePointerMove)
  window.removeEventListener('pointerup', stopTableResize)
  window.removeEventListener('pointercancel', stopTableResize)
  document.body.classList.remove('year-table-is-resizing')
}

function resetTableResize() {
  projectTableHeight.value = null
}

function onWindowKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') {
    clearSelectedShiftCells()
    clearProjectSpanDragState()
  }
}

onMounted(() => {
  window.addEventListener('keydown', onWindowKeydown)
})

onBeforeUnmount(() => {
  stopTableResize()
  clearProjectSpanDragState()
  window.removeEventListener('keydown', onWindowKeydown)
  if (suppressClickTimer !== null) {
    window.clearTimeout(suppressClickTimer)
    suppressClickTimer = null
  }
  clearDragPreviewElement()
})

function onProjectScroll() {
  syncHorizontalScroll('project')
}

function onEmployeeScroll() {
  syncHorizontalScroll('employee')
}

const firstOfYear = computed(() => props.firstOfMonth.startOf('year'))

const daysOfYear = computed(() => {
  const days = []
  let date = firstOfYear.value.startOf('day')
  const end = firstOfYear.value.endOf('year')

  while (date.isSameOrBefore(end, 'day')) {
    days.push({
      date: date.format('YYYY-MM-DD'),
      day: date.format('D'),
      weekday: date.format('dd').charAt(0),
      month: date.format('MMM'),
      monthKey: date.format('YYYY-MM'),
      isMonthStart: date.date() === 1,
      isWeekend: [0, 6].includes(date.day()),
      isToday: date.isSame(dayjs(), 'day'),
    })
    date = date.add(1, 'day')
  }

  return days
})

const monthGroups = computed(() => {
  const groups: { key: string; label: string; days: number }[] = []
  for (const day of daysOfYear.value) {
    const last = groups[groups.length - 1]
    if (!last || last.key !== day.monthKey) {
      groups.push({ key: day.monthKey, label: day.month, days: 1 })
    } else {
      last.days += 1
    }
  }
  return groups
})

const dayMarkers = computed<DayMarkers>(() => events.data?.dayMarkers || {})

const todayIndex = computed(() => {
  const today = dayjs().format('YYYY-MM-DD')
  return daysOfYear.value.findIndex((day) => day.date === today)
})

const showTodayOverlay = computed(() => todayIndex.value >= 0)

const todayOverlayStyle = computed(() => ({
  left: `${LEFT_COLUMN_WIDTH + todayIndex.value * DAY_COLUMN_WIDTH}px`,
  width: `${DAY_COLUMN_WIDTH}px`,
}))

const hoverCardStyle = computed(() => ({
  '--year-hover-accent': hoverCard.value?.accent || 'rgb(59 130 246)',
}))

const employeeSearchOptions = computed(() => {
  return props.employees.map((employee) => ({
    value: employee.name,
    label: `${employee.name}: ${employee.employee_name}`,
  }))
})

function naturalCompare(a?: string, b?: string) {
  return String(a || '').localeCompare(String(b || ''), undefined, { numeric: true, sensitivity: 'base' })
}

function sortEmployeesByDepartmentAndId(employees: Employee[]) {
  return [...employees].sort((a, b) => {
    const departmentCompare = naturalCompare(a.department, b.department)
    if (departmentCompare !== 0) return departmentCompare

    return naturalCompare(a.name, b.name)
  })
}

const sortedEmployees = computed(() => sortEmployeesByDepartmentAndId(props.employees || []))

const visibleEmployees = computed(() => {
  if (!employeeSearch.value?.length) return sortedEmployees.value
  const selected = new Set(employeeSearch.value.map((item) => item.value))
  return sortedEmployees.value.filter((employee) => selected.has(employee.name))
})

const allProjectRows = computed(() => {
  return (events.data?.projectRows || []) as ProjectRow[]
})

const projectRows = computed(() => {
  if (projectTypeFilter.value === 'all') return allProjectRows.value

  return allProjectRows.value.filter((project) => {
    return normaliseProjectType(project.roster_or_shutdown) === projectTypeFilter.value
  })
})

const projectEmptyStateMessage = computed(() => {
  if (!allProjectRows.value.length) return 'No active projects found for this year'
  if (projectTypeFilter.value === 'roster') return 'No roster projects found for this year'
  if (projectTypeFilter.value === 'shutdown') return 'No shutdown projects found for this year'
  return 'No projects match the current annual filters'
})

function normaliseProjectType(value: string | null | undefined) {
  const normalised = String(value || '').trim().toLowerCase()
  if (normalised === 'roster') return 'roster'
  if (normalised === 'shutdown') return 'shutdown'
  return ''
}

function projectTypeLabel(project: ProjectRow) {
  const type = normaliseProjectType(project.roster_or_shutdown)
  if (type === 'roster') return 'Roster'
  if (type === 'shutdown') return 'Shutdown'
  return project.roster_or_shutdown || 'Not Set'
}

function projectRequestedCount(project: ProjectRow) {
  return Math.max(0, Number(project.ds_requested || 0) + Number(project.ns_requested || 0))
}

function projectShiftsFilledValue(value: ProjectRow['shifts_filled']) {
  if (value === undefined || value === null || value === '') return null
  if (typeof value === 'string') {
    return !['0', 'no', 'false', 'none'].includes(value.trim().toLowerCase())
  }
  return Boolean(value)
}

function projectActiveValue(project: ProjectRow) {
  const active = projectShiftsFilledValue(project.is_active as ProjectRow['shifts_filled'])
  return active === null ? true : active
}

function projectIsFilled(project: ProjectRow) {
  // Prefer the Project checkbox field from ERPNext. This matches the monthly
  // roster behaviour and avoids trying to infer filled status from allocations.
  const explicitFilled = projectShiftsFilledValue(project.shifts_filled)
  if (explicitFilled !== null) return explicitFilled

  // Fallback only for older data/API responses that do not yet return the field.
  const requested = projectRequestedCount(project)
  if (requested <= 0) return false

  const cells = Object.values(project.assignments || {})
  if (!cells.length) return false

  return cells.every((cell) => Number(cell?.count || 0) >= requested)
}

function projectTaskCount(project: ProjectRow) {
  const count = Number(project.task_count || 0)
  return Number.isFinite(count) && count > 0 ? Math.floor(count) : 0
}

function projectTaskSummary(project: ProjectRow) {
  const count = projectTaskCount(project)
  return count > 0 ? `Yes (${count})` : 'No'
}

function projectPersonnelSummary(personnel?: string[]) {
  const people = Array.from(new Set((personnel || []).filter(Boolean))).sort()
  return people.length ? people.join(', ') : 'None'
}

function projectHasGantt(project?: ProjectRow | null) {
  return project ? projectTaskCount(project) > 0 : false
}

function projectGanttStatus(project: ProjectRow) {
  return projectHasGantt(project) ? 'Gantt Available' : 'Gantt Missing'
}

function projectGanttStatusLabel(project?: ProjectRow | null) {
  return projectHasGantt(project) ? 'Gantt Available' : 'Gantt Missing'
}

function projectGanttStatusTone(project: ProjectRow): 'green' | 'red' {
  return projectHasGantt(project) ? 'green' : 'red'
}

type ProjectLane = {
  key: string
  groupKey: string
  customerKey: string
  customerLabel: string
  locationLabel: string
  groupLabel: string
  laneIndex: number
  projects: ProjectRow[]
}

type ProjectSpan = {
  start: string
  end: string
  startIndex: number
  days: number
  color?: string
  customerColor?: string | null
  employeeCount: number
  shiftTypes: string[]
  poEntered: boolean
  dsRequested: number
  nsRequested: number
  isActive: boolean
}

type ProjectSegment = {
  key: string
  days: number
  active: boolean
  project?: ProjectRow
  date?: string
  isMonthStart?: boolean
  isWeekend?: boolean
  isToday?: boolean
  label?: string
  subline?: string
  title?: string
  color?: string
  customerColor?: string | null
  poEntered?: boolean
  dsRequested?: number
  nsRequested?: number
  isActive?: boolean
}

function projectKey(project: ProjectRow) {
  return project.project || project.project_name
}

const projectSpans = computed<Record<string, ProjectSpan>>(() => {
  const spans: Record<string, ProjectSpan> = {}

  for (const project of projectRows.value) {
    const dates = Object.keys(project.assignments || {}).sort()
    if (!dates.length) continue

    const employeeSet = new Set<string>()
    const shiftTypeSet = new Set<string>()
    let largestDailyCount = 0

    for (const date of dates) {
      const assignment = project.assignments?.[date]
      largestDailyCount = Math.max(largestDailyCount, Number(assignment?.count || 0))

      for (const employee of assignment?.employees || []) {
        employeeSet.add(employee)
      }

      for (const shiftType of assignment?.shift_types || []) {
        shiftTypeSet.add(shiftType)
      }
    }

    const startIndex = daysOfYear.value.findIndex((day) => day.date === dates[0])
    const endIndex = daysOfYear.value.findIndex((day) => day.date === dates[dates.length - 1])

    spans[projectKey(project)] = {
      start: dates[0],
      end: dates[dates.length - 1],
      startIndex: Math.max(0, startIndex),
      days: Math.max(1, endIndex - startIndex + 1),
      color: project.po_entered === false ? 'red' : 'green',
      customerColor: project.customer_color || null,
      employeeCount: employeeSet.size || largestDailyCount,
      shiftTypes: Array.from(shiftTypeSet).sort(),
      poEntered: project.po_entered !== false,
      dsRequested: Number(project.ds_requested || 0),
      nsRequested: Number(project.ns_requested || 0),
      isActive: projectActiveValue(project),
    }
  }

  return spans
})

function projectSpan(project: ProjectRow) {
  return projectSpans.value[projectKey(project)]
}

function projectSpanSubline(_project: ProjectRow, span: ProjectSpan) {
  return `${dayjs(span.start).format('DD MMM')} – ${dayjs(span.end).format('DD MMM')}`
}

function projectSpanTitle(project: ProjectRow, span: ProjectSpan) {
  return [
    project.project_name,
    project.project,
    project.status,
    projectGroupLabel(project),
    `${dayjs(span.start).format('DD MMM YYYY')} - ${dayjs(span.end).format('DD MMM YYYY')}`,
    span.poEntered ? 'PO Entered' : 'PO Missing',
    `${span.dsRequested || 0} DS Requested`,
    `${span.nsRequested || 0} NS Requested`,
  ].filter(Boolean).join(' | ')
}

function projectCustomerKey(project: ProjectRow) {
  return project.customer || project.customer_name || 'Unassigned Customer'
}

function projectCustomerLabel(project: ProjectRow) {
  return project.customer_name || project.customer || 'Unassigned Customer'
}

function projectLocationLabel(project: ProjectRow) {
  return project.custom_project_location?.trim() || 'No Location'
}

function projectGroupKey(project: ProjectRow) {
  return `${projectCustomerKey(project)}::${projectLocationLabel(project)}`
}

function projectGroupLabel(project: ProjectRow) {
  return `${projectCustomerLabel(project)} - ${projectLocationLabel(project)}`
}

function projectSpanEndIndex(span: ProjectSpan) {
  return span.startIndex + span.days - 1
}

const projectLanes = computed<ProjectLane[]>(() => {
  const grouped = new Map<
    string,
    {
      customerKey: string
      customerLabel: string
      locationLabel: string
      groupLabel: string
      projects: ProjectRow[]
    }
  >()

  for (const project of projectRows.value) {
    const span = projectSpan(project)
    if (!span) continue

    const groupKey = projectGroupKey(project)
    const existing = grouped.get(groupKey)
    if (existing) {
      existing.projects.push(project)
    } else {
      grouped.set(groupKey, {
        customerKey: projectCustomerKey(project),
        customerLabel: projectCustomerLabel(project),
        locationLabel: projectLocationLabel(project),
        groupLabel: projectGroupLabel(project),
        projects: [project],
      })
    }
  }

  const lanes: ProjectLane[] = []
  const sortedGroups = Array.from(grouped.entries()).sort((a, b) => naturalCompare(a[1].groupLabel, b[1].groupLabel))

  for (const [groupKey, group] of sortedGroups) {
    const groupLanes: ProjectRow[][] = []
    const laneEndIndexes: number[] = []
    const sortedProjects = [...group.projects].sort((a, b) => {
      const aSpan = projectSpan(a)
      const bSpan = projectSpan(b)
      const startCompare = (aSpan?.startIndex ?? 0) - (bSpan?.startIndex ?? 0)
      if (startCompare !== 0) return startCompare
      return naturalCompare(a.project_name, b.project_name)
    })

    for (const project of sortedProjects) {
      const span = projectSpan(project)
      if (!span) continue

      let laneIndex = groupLanes.findIndex((_, index) => span.startIndex > laneEndIndexes[index])
      if (laneIndex < 0) {
        laneIndex = groupLanes.length
        groupLanes.push([])
        laneEndIndexes.push(-1)
      }

      groupLanes[laneIndex].push(project)
      laneEndIndexes[laneIndex] = Math.max(laneEndIndexes[laneIndex], projectSpanEndIndex(span))
    }

    groupLanes.forEach((laneProjects, laneIndex) => {
      lanes.push({
        key: `${groupKey}-${laneIndex}`,
        groupKey,
        customerKey: group.customerKey,
        customerLabel: group.customerLabel,
        locationLabel: group.locationLabel,
        groupLabel: group.groupLabel,
        laneIndex,
        projects: laneProjects,
      })
    })
  }

  return lanes
})

function projectLaneSubline(lane: ProjectLane) {
  const projectCount = lane.projects.length
  const laneCount = projectLanes.value.filter((item) => item.groupKey === lane.groupKey).length
  const pieces = [`${projectCount} project${projectCount === 1 ? '' : 's'}`]

  if (laneCount > 1) {
    pieces.push(`row ${lane.laneIndex + 1} of ${laneCount}`)
  }

  return pieces.join(' · ')
}

function projectLaneSegments(lane: ProjectLane): ProjectSegment[] {
  const byStartIndex = new Map<number, ProjectRow>()

  for (const project of lane.projects) {
    const span = projectSpan(project)
    if (!span) continue
    byStartIndex.set(span.startIndex, project)
  }

  const segments: ProjectSegment[] = []

  for (let index = 0; index < daysOfYear.value.length; index++) {
    const day = daysOfYear.value[index]
    const project = byStartIndex.get(index)
    const span = project ? projectSpan(project) : undefined

    if (project && span) {
      segments.push({
        key: `${lane.key}-${projectKey(project)}-${span.start}-${span.end}`,
        days: span.days,
        active: true,
        project,
        date: span.start,
        isMonthStart: day.isMonthStart,
        isToday: daysOfYear.value
          .slice(span.startIndex, span.startIndex + span.days)
          .some((spanDay) => spanDay.isToday),
        label: project.project_name,
        subline: projectSpanSubline(project, span),
        title: projectSpanTitle(project, span),
        color: span.color,
        customerColor: span.customerColor,
        poEntered: span.poEntered,
        dsRequested: span.dsRequested,
        nsRequested: span.nsRequested,
        isActive: span.isActive,
      })
      index += span.days - 1
      continue
    }

    segments.push({
      key: `${lane.key}-${day.date}`,
      days: 1,
      active: false,
      date: day.date,
      isMonthStart: day.isMonthStart,
      isWeekend: day.isWeekend,
      isToday: day.isToday,
      title: `${lane.groupLabel} | ${dayjs(day.date).format('DD MMM YYYY')}`,
    })
  }

  return segments
}

const showProjectsPanel = computed(() => allProjectRows.value.length > 0)
const showEmployeesPanel = computed(() => true)
const showProjectBody = computed(() => !projectCollapsed.value)
const showEmployeeBody = computed(() => !employeeCollapsed.value)

function toggleProjectCollapsed() {
  if (!projectCollapsed.value && employeeCollapsed.value) {
    raiseToast('error', 'At least one annual roster section must remain visible')
    return
  }

  projectCollapsed.value = !projectCollapsed.value
}

function toggleEmployeeCollapsed() {
  if (!employeeCollapsed.value && (projectCollapsed.value || !projectLanes.value.length)) {
    raiseToast('error', 'At least one annual roster section must remain visible')
    return
  }

  employeeCollapsed.value = !employeeCollapsed.value
}

const sectionGap = 16
const PROJECT_COLLAPSED_HEIGHT = 98
const EMPLOYEE_COLLAPSED_HEIGHT = 96

const annualContentHeight = computed(() => {
  const total = props.maxHeightPx || 650
  return Math.max(220, total)
})

const showTableResizer = computed(() => {
  return showProjectsPanel.value && showEmployeesPanel.value && !projectCollapsed.value && !employeeCollapsed.value
})

const projectTableContentHeight = computed(() => {
  const visibleProjectRowCount = Math.max(1, projectLanes.value.length)
  return Math.max(
    PROJECT_TABLE_MIN_HEIGHT,
    PROJECT_TABLE_HEADER_HEIGHT + visibleProjectRowCount * PROJECT_TABLE_ROW_HEIGHT,
  )
})

const naturalProjectTableHeight = computed(() => {
  return Math.min(240, projectTableContentHeight.value)
})

const projectTableMaxHeight = computed(() => {
  if (!showProjectsPanel.value) return 0
  if (projectCollapsed.value) return PROJECT_COLLAPSED_HEIGHT

  if (employeeCollapsed.value) {
    return Math.max(220, annualContentHeight.value - EMPLOYEE_COLLAPSED_HEIGHT - sectionGap)
  }

  if (showTableResizer.value && projectTableHeight.value !== null) {
    return clampProjectTableHeight(projectTableHeight.value)
  }

  return naturalProjectTableHeight.value
})

const projectTableRenderedHeight = computed(() => {
  if (!showProjectsPanel.value) return 0
  if (projectCollapsed.value) return PROJECT_COLLAPSED_HEIGHT
  if (employeeCollapsed.value) return projectTableMaxHeight.value

  return Math.min(projectTableMaxHeight.value, projectTableContentHeight.value)
})

const employeeTableMaxHeight = computed(() => {
  if (employeeCollapsed.value) return EMPLOYEE_COLLAPSED_HEIGHT

  if (!showProjectsPanel.value) return annualContentHeight.value

  const resizerUsed = showTableResizer.value ? RESIZER_HEIGHT : 0
  const projectPanelUsed = projectTableRenderedHeight.value + sectionGap + resizerUsed
  return Math.max(EMPLOYEE_TABLE_MIN_HEIGHT, annualContentHeight.value - projectPanelUsed)
})

function employeeDisplayName(employee: Employee) {
  return employee.employee_name || [employee.first_name, employee.last_name].filter(Boolean).join(' ') || employee.name
}

function employeeSubline(employee: Employee) {
  return [employee.name, employee.designation].filter(Boolean).join(' · ')
}

function employeeTitle(employee: Employee) {
  return [employee.employee_name, employee.name, employee.designation].filter(Boolean).join(' | ')
}

function isHoliday(event: RawEvent): event is HolidayWithDate {
  return 'holiday' in event
}

function isLeave(event: RawEvent): event is LeaveApplication {
  return 'leave' in event
}

function isShift(event: RawEvent): event is ShiftAssignment {
  return 'shift_type' in event
}

function overlaps(date: Dayjs, startDate?: string | null, endDate?: string | null) {
  if (!startDate) return false
  const start = dayjs(startDate)
  const end = endDate ? dayjs(endDate) : firstOfYear.value.endOf('year')
  return start.isSameOrBefore(date, 'day') && end.isSameOrAfter(date, 'day')
}

function safeColor(color?: string): Color {
  const key = (color || 'gray').toLowerCase() as Color
  const allowed: Color[] = ['blue', 'cyan', 'fuchsia', 'green', 'lime', 'orange', 'pink', 'red', 'violet', 'yellow', 'gray']
  return allowed.includes(key) ? key : 'gray'
}

function palette(color?: string) {
  const key = safeColor(color)
  return ((colors as any)[key] || (colors as any).gray) as Record<string, string>
}

function normaliseHexColor(value?: string | null) {
  if (!value) return ''

  const trimmed = value.trim()
  if (/^#[0-9a-fA-F]{3}$/.test(trimmed) || /^#[0-9a-fA-F]{6}$/.test(trimmed)) return trimmed
  if (/^[0-9a-fA-F]{3}$/.test(trimmed) || /^[0-9a-fA-F]{6}$/.test(trimmed)) return `#${trimmed}`

  return ''
}

function hexToRgb(hex: string) {
  const normalized = normaliseHexColor(hex)
  if (!normalized) return null

  const raw = normalized.slice(1)
  const expanded = raw.length === 3 ? raw.split('').map((char) => char + char).join('') : raw
  const numeric = Number.parseInt(expanded, 16)

  return {
    r: (numeric >> 16) & 255,
    g: (numeric >> 8) & 255,
    b: numeric & 255,
  }
}

function contrastTextColor(hex: string) {
  const rgb = hexToRgb(hex)
  if (!rgb) return (colors as any).gray[800]

  const brightness = (rgb.r * 299 + rgb.g * 587 + rgb.b * 114) / 1000
  return brightness >= 150 ? (colors as any).gray[900] : '#ffffff'
}

function mutedContrastTextColor(hex: string) {
  const textColor = contrastTextColor(hex)
  return textColor === '#ffffff' ? 'rgb(255 255 255 / 0.82)' : 'rgb(55 65 81 / 0.78)'
}

function darkenHexColor(hex: string, amount = 0.28) {
  const rgb = hexToRgb(hex)
  if (!rgb) return normaliseHexColor(hex)

  const clamp = (value: number) => Math.max(0, Math.min(255, Math.round(value)))
  const toHex = (value: number) => clamp(value).toString(16).padStart(2, '0')

  return `#${toHex(rgb.r * (1 - amount))}${toHex(rgb.g * (1 - amount))}${toHex(rgb.b * (1 - amount))}`
}

function lightenHexColor(hex: string, amount = 0.62) {
  const rgb = hexToRgb(hex)
  if (!rgb) return normaliseHexColor(hex)

  const clamp = (value: number) => Math.max(0, Math.min(255, Math.round(value)))
  const toHex = (value: number) => clamp(value).toString(16).padStart(2, '0')

  return `#${toHex(rgb.r + (255 - rgb.r) * amount)}${toHex(rgb.g + (255 - rgb.g) * amount)}${toHex(rgb.b + (255 - rgb.b) * amount)}`
}

function formatShift(shift: ShiftAssignment): ShiftAssignment {
  return {
    ...shift,
    color: safeColor(shift.color),
    start_time: shift.start_time ? dayjs(shift.start_time, 'hh:mm:ss').format('HH:mm') : '',
    end_time: shift.end_time ? dayjs(shift.end_time, 'hh:mm:ss').format('HH:mm') : '',
  }
}

function shiftCellLabel(shift: ShiftAssignment) {
  const customerAbbreviation = shift.customer_abbreviation?.trim()

  if (customerAbbreviation) return customerAbbreviation

  // Project-linked shifts should not fall back to the full project name in the
  // compact annual cells. If the Project is missing customer_abbreviation, leave
  // the annual cell blank so the missing abbreviation is obvious.
  if (shift.custom_project) return ''

  // Non-project shift assignments can still show their shift type.
  return shift.shift_type
}

function hasNote(note: string | null | undefined) {
  return typeof note === 'string' && note.trim().length > 0
}

function plainTextFromHtml(value: string | null | undefined) {
  const raw = typeof value === 'string' ? value.trim() : ''
  if (!raw) return ''

  const cached = htmlPlainTextCache.get(raw)
  if (cached !== undefined) return cached

  const withLineBreaks = raw
    .replace(/<br\s*\/?>/gi, '\n')
    .replace(/<\/p>/gi, '\n')
    .replace(/<\/div>/gi, '\n')
    .replace(/<\/li>/gi, '\n')

  let output = ''

  if (typeof DOMParser !== 'undefined') {
    const parsed = new DOMParser().parseFromString(withLineBreaks, 'text/html')
    output = (parsed.body.textContent || '')
      .replace(/\u00a0/g, ' ')
      .replace(/[ \t]+\n/g, '\n')
      .replace(/\n{3,}/g, '\n\n')
      .trim()
  } else {
    output = withLineBreaks
      .replace(/<[^>]*>/g, '')
      .replace(/&nbsp;/gi, ' ')
      .replace(/&amp;/gi, '&')
      .replace(/&lt;/gi, '<')
      .replace(/&gt;/gi, '>')
      .replace(/&quot;/gi, '"')
      .replace(/&#39;/gi, "'")
      .replace(/[ \t]+\n/g, '\n')
      .replace(/\n{3,}/g, '\n\n')
      .trim()
  }

  // Keep the cache bounded so long sessions do not keep growing indefinitely.
  if (htmlPlainTextCache.size > 300) htmlPlainTextCache.clear()
  htmlPlainTextCache.set(raw, output)
  return output
}

function mapEventsToYear(data: Events): MappedEvents {
  const mappedEvents: MappedEvents = {}

  for (const employee in data) {
    mappedEvents[employee] = {}

    for (const day of daysOfYear.value) {
      const date = dayjs(day.date)
      const shifts: ShiftAssignment[] = []
      let blockedCell: YearCell | null = null

      for (const event of data[employee] || []) {
        if (isHoliday(event) && date.isSame(event.holiday_date, 'day')) {
          // Annual holidays are displayed in the date header only. Do not block
          // or populate employee cells with holiday markers.
          continue
        }

        if (isLeave(event) && overlaps(date, event.from_date, event.to_date)) {
          blockedCell = {
            type: 'leave',
            label: 'L',
            title: event.leave_type,
            leave: event,
          }
          break
        }

        if (isShift(event) && overlaps(date, event.start_date, event.end_date)) {
          shifts.push(formatShift(event))
        }
      }

      if (blockedCell) {
        mappedEvents[employee][day.date] = blockedCell
        continue
      }

      if (shifts.length) {
        shifts.sort((a, b) => (a.start_time || '').localeCompare(b.start_time || ''))
        const firstShift = shifts[0]
        const firstShiftLabel = shiftCellLabel(firstShift)
        mappedEvents[employee][day.date] = {
          type: 'shift',
          label: shifts.length > 1 && firstShiftLabel ? `${firstShiftLabel}+` : firstShiftLabel,
          title: [
            firstShift.customer_abbreviation ? `Customer: ${firstShift.customer_abbreviation}` : '',
            firstShift.custom_project_name,
            firstShift.shift_type,
            firstShift.shift_location,
            firstShift.note ? `Note: ${firstShift.note}` : '',
          ].filter(Boolean).join(' | '),
          shift: firstShift,
          shifts,
        }
      }
    }
  }

  return mappedEvents
}

function getEmployeeCell(employee: string, date: string): YearCell | undefined {
  return events.data?.mappedEvents?.[employee]?.[date]
}

function employeeCellLabel(employee: string, date: string) {
  return getEmployeeCell(employee, date)?.label || ''
}

function employeeCellTitle(employee: string, date: string) {
  return getEmployeeCell(employee, date)?.title || dayjs(date).format('dddd, DD MMMM YYYY')
}

function isEmployeeShiftCell(employee: string, date: string) {
  return getEmployeeCell(employee, date)?.type === 'shift'
}

function adjacentDate(date: string, days: number) {
  return dayjs(date).add(days, 'day').format('YYYY-MM-DD')
}

function employeeShiftContinuesLeft(employee: string, date: string) {
  return isEmployeeShiftCell(employee, date) && isEmployeeShiftCell(employee, adjacentDate(date, -1))
}

function employeeShiftContinuesRight(employee: string, date: string) {
  return isEmployeeShiftCell(employee, date) && isEmployeeShiftCell(employee, adjacentDate(date, 1))
}

function employeeCellClass(employee: string, date: string) {
  const isShift = isEmployeeShiftCell(employee, date)

  return {
    'year-employee-shift-cell': isShift,
    'year-employee-shift-continues-left': isShift && employeeShiftContinuesLeft(employee, date),
    'year-employee-shift-continues-right': isShift && employeeShiftContinuesRight(employee, date),
  }
}

function shiftRunBoxShadow(employee: string, date: string, borderColor: string) {
  const continuesLeft = employeeShiftContinuesLeft(employee, date)
  const continuesRight = employeeShiftContinuesRight(employee, date)
  const shadows = [`inset 0 1px 0 ${borderColor}`, `inset 0 -1px 0 ${borderColor}`]

  if (!continuesLeft) shadows.push(`inset 1px 0 0 ${borderColor}`)
  if (!continuesRight) shadows.push(`inset -1px 0 0 ${borderColor}`)

  return shadows.join(', ')
}

function employeeCellStyle(employee: string, date: string) {
  const cell = getEmployeeCell(employee, date)
  if (!cell) return {}

  if (cell.type === 'holiday') {
    return { backgroundColor: (colors as any).blue[50], color: (colors as any).blue[700] }
  }

  if (cell.type === 'leave') {
    return { backgroundColor: (colors as any).pink[50], color: (colors as any).pink[700] }
  }

  const color = palette(cell.shift.color)
  const borderColor = hasNote(cell.shift.note) ? (colors as any).red[500] : color[300]
  const continuesRight = employeeShiftContinuesRight(employee, date)

  return {
    backgroundColor: color[100],
    borderColor,
    borderRightColor: continuesRight ? 'transparent' : borderColor,
    boxShadow: shiftRunBoxShadow(employee, date, borderColor),
    color: (colors as any).gray[900],
  }
}

function getPrimaryShift(employee: string, date: string) {
  const cell = getEmployeeCell(employee, date)
  return cell?.type === 'shift' ? cell.shift : null
}

function isLeaveCell(employee: string, date: string) {
  return getEmployeeCell(employee, date)?.type === 'leave'
}

function shiftCellKey(employee: string, date: string) {
  return `${employee}::${date}`
}

function selectedShiftList() {
  return Object.values(selectedShiftCells.value).sort(
    (a, b) => a.employee.localeCompare(b.employee) || a.date.localeCompare(b.date),
  )
}

function selectedShiftCount() {
  return selectedShiftList().length
}

function selectedShiftEmployee() {
  return selectedShiftList()[0]?.employee || ''
}

function isSelectedShiftCell(employee: string, date: string) {
  return Boolean(selectedShiftCells.value[shiftCellKey(employee, date)])
}

function clearSelectedShiftCells() {
  selectedShiftCells.value = {}
}

function toggleSelectedShiftCell(employee: string, date: string) {
  const shift = getPrimaryShift(employee, date)
  if (!shift) return

  const existingEmployee = selectedShiftEmployee()
  const key = shiftCellKey(employee, date)
  const next = existingEmployee && existingEmployee !== employee ? {} : { ...selectedShiftCells.value }

  if (next[key]) {
    delete next[key]
  } else {
    next[key] = { employee, date, shift }
  }

  selectedShiftCells.value = next
}

function activeDragShiftCells() {
  if (!draggedShift.value) return []

  const selected = selectedShiftList()
  if (selected.some((cell) => cell.employee === draggedShift.value?.employee && cell.date === draggedShift.value?.date)) {
    return selected
  }

  return [draggedShift.value]
}

function firstActiveDragDate() {
  return activeDragShiftCells()[0]?.date || draggedShift.value?.date || ''
}

function targetDateForDragCell(cell: SelectedShiftCell, targetStartDate: string) {
  const firstDate = firstActiveDragDate()
  if (!firstDate) return targetStartDate

  const offset = dayjs(cell.date).diff(dayjs(firstDate), 'day')
  return dayjs(targetStartDate).add(offset, 'day').format('YYYY-MM-DD')
}

function activeDragTargetDates(targetStartDate: string) {
  return activeDragShiftCells().map((cell) => targetDateForDragCell(cell, targetStartDate))
}

function isSameDragSourceCell(employee: string, date: string) {
  return activeDragShiftCells().some((cell) => cell.employee === employee && cell.date === date)
}

function sameShiftIdentity(a?: ShiftAssignment | null, b?: ShiftAssignment | null) {
  if (!a || !b) return false

  return (
    a.shift_type === b.shift_type &&
    (a.shift_location || '') === (b.shift_location || '') &&
    a.status === b.status
  )
}

function targetHasSameShiftAsDragged(employee: string, date: string) {
  const dragCells = activeDragShiftCells()
  if (!dragCells.length) return false

  for (const source of dragCells) {
    const targetDate = targetDateForDragCell(source, date)
    const target = getEmployeeCell(employee, targetDate)
    if (target?.type !== 'shift') continue

    if (target.shifts.some((shift) => shift.name !== source.shift.name && sameShiftIdentity(source.shift, shift))) {
      return true
    }
  }

  return false
}

function targetRangeHasLeave(employee: string, date: string) {
  return activeDragTargetDates(date).some((targetDate) => isLeaveCell(employee, targetDate))
}

function targetRangeIntersectsSource(employee: string, date: string) {
  const dragCells = activeDragShiftCells()
  if (!dragCells.length || dragCells[0].employee !== employee) return false

  const sourceDates = new Set(dragCells.map((cell) => cell.date))
  return activeDragTargetDates(date).some((targetDate) => sourceDates.has(targetDate))
}

function targetRangeHasShift(employee: string, date: string) {
  return activeDragTargetDates(date).some((targetDate) => Boolean(getPrimaryShift(employee, targetDate)))
}

function canDropOnEmployeeCell(employee: string, date: string) {
  if (!draggedShift.value || isDroppingShift.value) return false
  if (targetRangeIntersectsSource(employee, date)) return false
  if (targetRangeHasLeave(employee, date)) return false
  if (targetHasSameShiftAsDragged(employee, date)) return false

  return true
}

function isCurrentDropCell(employee: string, date: string) {
  return dropCell.value.employee === employee && dropCell.value.date === date
}

function employeeDragCellClass(employee: string, date: string) {
  // Keep this cheap. It runs for every visible employee/day cell whenever drag
  // or multi-select state changes. Selection is a direct key lookup; drop
  // validation only runs on the current drop target.
  const isSelected = isSelectedShiftCell(employee, date)
  const isSource = isSameDragSourceCell(employee, date)
  const isDropTarget = isCurrentDropCell(employee, date)

  if (!isSelected && !isSource && !isDropTarget) {
    return {}
  }

  if (!isDropTarget) {
    return {
      'year-employee-shift-selected': isSelected,
      'year-employee-drag-source': isSource,
    }
  }

  const canDrop = canDropOnEmployeeCell(employee, date)
  const hasTargetShift = targetRangeHasShift(employee, date)
  const hasActiveDrag = Boolean(draggedShift.value)

  return {
    'year-employee-shift-selected': isSelected,
    'year-employee-drag-source': isSource,
    'year-employee-drop-target': hasActiveDrag,
    'year-employee-drop-target-move': canDrop && !hasTargetShift,
    'year-employee-drop-target-swap': canDrop && hasTargetShift,
    'year-employee-drop-target-invalid': hasActiveDrag && !canDrop,
  }
}

function setDropCell(employee: string, date: string) {
  // Dragover fires continuously; do not trigger a Vue update when the target
  // cell has not actually changed. This keeps annual drag/drop responsive.
  if (dropCell.value.employee === employee && dropCell.value.date === date) {
    return
  }

  const targetShift = getPrimaryShift(employee, date)
  dropCell.value = { employee, date, shift: targetShift?.name || '' }
}

function clearDropCell() {
  dropCell.value = { employee: '', date: '', shift: '' }
}

function clearDragPreviewElement() {
  if (dragPreviewElement?.parentNode) {
    dragPreviewElement.parentNode.removeChild(dragPreviewElement)
  }

  dragPreviewElement = null
}

function createDragPreviewElement(shift: ShiftAssignment, count = 1) {
  clearDragPreviewElement()

  const preview = document.createElement('div')
  preview.className = 'year-drag-preview'
  preview.textContent = count > 1 ? `Moving ${count} shifts` : shiftCellLabel(shift) || shift.custom_project_name || shift.shift_type || 'Shift'
  document.body.appendChild(preview)
  dragPreviewElement = preview

  return preview
}

function clearDragState() {
  draggedShift.value = null
  clearDropCell()
  isDroppingShift.value = false
  clearDragPreviewElement()
}

function releaseSuppressedClickSoon() {
  if (suppressClickTimer !== null) {
    window.clearTimeout(suppressClickTimer)
  }

  suppressClickTimer = window.setTimeout(() => {
    suppressNextCellClick.value = false
    suppressClickTimer = null
  }, 0)
}

function onEmployeeCellDragStart(employee: string, date: string, event: DragEvent) {
  const shift = getPrimaryShift(employee, date)
  if (!shift) {
    event.preventDefault()
    return
  }

  clearHoverCard()
  suppressNextCellClick.value = true

  if (selectedShiftCount() && !isSelectedShiftCell(employee, date)) {
    clearSelectedShiftCells()
  }

  draggedShift.value = { employee, date, shift }
  clearDropCell()

  const dragCells = activeDragShiftCells()

  if (event.dataTransfer) {
    const preview = createDragPreviewElement(shift, dragCells.length)
    event.dataTransfer.effectAllowed = 'move'
    event.dataTransfer.setData('text/plain', dragCells.map((cell) => cell.shift.name).join(','))
    event.dataTransfer.setDragImage(preview, 18, 14)
  }
}

function onEmployeeCellDragEnd() {
  clearDragPreviewElement()

  if (!isDroppingShift.value) {
    clearDragState()
  }

  releaseSuppressedClickSoon()
}

function onEmployeeCellDragEnter(employee: string, date: string) {
  if (!draggedShift.value) return
  setDropCell(employee, date)
}

function onEmployeeCellDragLeave(employee: string, date: string, event: DragEvent) {
  const currentTarget = event.currentTarget as HTMLElement | null
  const relatedTarget = event.relatedTarget as Node | null

  if (currentTarget && relatedTarget && currentTarget.contains(relatedTarget)) return
  if (!isCurrentDropCell(employee, date)) return

  clearDropCell()
}

function onEmployeeCellDragOver(employee: string, date: string, event: DragEvent) {
  if (!draggedShift.value) return

  setDropCell(employee, date)

  if (!canDropOnEmployeeCell(employee, date)) {
    if (event.dataTransfer) event.dataTransfer.dropEffect = 'none'
    return
  }

  event.preventDefault()
  if (event.dataTransfer) event.dataTransfer.dropEffect = 'move'
}

function onEmployeeCellDrop(employee: string, date: string, event: DragEvent) {
  if (!draggedShift.value) return

  setDropCell(employee, date)

  if (!canDropOnEmployeeCell(employee, date)) {
    event.preventDefault()
    clearDropCell()
    return
  }

  event.preventDefault()
  clearHoverCard()

  const dragCells = activeDragShiftCells()
  pendingBulkShiftWillSwap.value = targetRangeHasShift(employee, date)
  pendingBulkShiftParams.value = {
    shifts: dragCells.map((cell) => ({
      shift: cell.shift.name,
      employee: cell.employee,
      date: cell.date,
    })),
    target_employee: employee,
    target_date: date,
  }

  isDroppingShift.value = true
  clearDragPreviewElement()
  loading.value = true
  bulkMoveOrSwapShifts.submit()
}

function openEmployeeCell(employee: string, date: string, event?: MouseEvent) {
  if (suppressNextCellClick.value || isDroppingShift.value) return

  clearHoverCard()
  const cell = getEmployeeCell(employee, date)
  if (cell?.type === 'holiday' || cell?.type === 'leave') return

  if (event?.shiftKey) {
    toggleSelectedShiftCell(employee, date)
    return
  }

  if (selectedShiftCount()) {
    clearSelectedShiftCells()
  }

  selectedCell.value = { employee, date }
  shiftAssignment.value = cell?.type === 'shift' ? cell.shift.name : ''
  showShiftAssignmentDialog.value = true
}

function projectSegmentClass(segment: ProjectSegment) {
  const isDragTarget = isProjectSpanDragTarget(segment)
  return {
    'year-project-span': segment.active,
    'cursor-pointer': segment.active,
    'year-project-span-inactive': segment.active && segment.isActive === false,
    'year-project-span-date-dragging': isDragTarget,
    'year-project-span-date-resizing': isDragTarget && projectSpanDrag.value?.mode !== 'move',
    'year-month-start': segment.isMonthStart,
    'year-weekend': segment.isWeekend && !segment.active,
  }
}

function projectSegmentStyle(segment: ProjectSegment) {
  if (!segment.active) return {}

  const isInactive = segment.isActive === false
  const customerColor = normaliseHexColor(segment.customerColor)
  if (customerColor) {
    const displayColor = isInactive ? lightenHexColor(customerColor, 0.64) : customerColor
    const borderColor = isInactive ? lightenHexColor(darkenHexColor(customerColor), 0.42) : darkenHexColor(customerColor)
    return {
      backgroundColor: displayColor,
      borderColor,
      boxShadow: `inset 0 0 0 1px ${borderColor}`,
      color: contrastTextColor(displayColor),
      '--year-project-span-text': contrastTextColor(displayColor),
      '--year-project-span-muted': mutedContrastTextColor(displayColor),
    }
  }

  const color = palette(segment.poEntered === false ? 'red' : 'green')
  return {
    backgroundColor: color[50],
    borderColor: isInactive ? color[200] : color[300],
    color: isInactive ? (colors as any).gray[600] : (colors as any).gray[800],
    '--year-project-span-text': isInactive ? (colors as any).gray[600] : (colors as any).gray[800],
    '--year-project-span-muted': isInactive ? (colors as any).gray[500] : (colors as any).gray[600],
  }
}

function isProjectSpanDragTarget(segment: ProjectSegment) {
  const drag = projectSpanDrag.value
  return Boolean(drag && segment.active && segment.project && projectKey(segment.project) === drag.projectKey)
}

function projectSpanDragPreview(drag: ProjectSpanDragState | null = projectSpanDrag.value) {
  if (!drag) return null

  const lastIndex = daysOfYear.value.length - 1
  let startIndex = drag.originalStartIndex
  let endIndex = drag.originalEndIndex

  if (drag.mode === 'move') {
    const spanLength = drag.originalEndIndex - drag.originalStartIndex + 1
    const minDelta = -drag.originalStartIndex
    const maxDelta = lastIndex - drag.originalEndIndex
    const delta = Math.min(maxDelta, Math.max(minDelta, drag.deltaDays))
    startIndex = drag.originalStartIndex + delta
    endIndex = startIndex + spanLength - 1
  } else if (drag.mode === 'resize-start') {
    startIndex = Math.min(drag.originalEndIndex, Math.max(0, drag.originalStartIndex + drag.deltaDays))
  } else if (drag.mode === 'resize-end') {
    endIndex = Math.max(drag.originalStartIndex, Math.min(lastIndex, drag.originalEndIndex + drag.deltaDays))
  }

  const start = daysOfYear.value[startIndex]?.date || daysOfYear.value[drag.originalStartIndex]?.date
  const end = daysOfYear.value[endIndex]?.date || daysOfYear.value[drag.originalEndIndex]?.date

  return {
    startIndex,
    endIndex,
    days: Math.max(1, endIndex - startIndex + 1),
    start,
    end,
    deltaStart: startIndex - drag.originalStartIndex,
    deltaEnd: endIndex - drag.originalEndIndex,
  }
}

function projectSegmentDragStyle(segment: ProjectSegment) {
  const drag = projectSpanDrag.value
  if (!drag || !segment.active || !segment.project || projectKey(segment.project) !== drag.projectKey) return {}

  const preview = projectSpanDragPreview(drag)
  if (!preview) return {}

  if (drag.mode === 'move') {
    return {
      transform: `translateX(${preview.deltaStart * DAY_COLUMN_WIDTH}px)`,
      zIndex: 7,
    }
  }

  return {
    zIndex: 7,
  }
}

function projectSegmentContentDragStyle(segment: ProjectSegment) {
  const drag = projectSpanDrag.value
  if (!drag || !segment.active || !segment.project || projectKey(segment.project) !== drag.projectKey) return {}

  const preview = projectSpanDragPreview(drag)
  if (!preview) return {}

  if (drag.mode === 'resize-start') {
    return {
      transform: `translateX(${preview.deltaStart * DAY_COLUMN_WIDTH}px)`,
      width: `${preview.days * DAY_COLUMN_WIDTH}px`,
      minWidth: `${preview.days * DAY_COLUMN_WIDTH}px`,
    }
  }

  if (drag.mode === 'resize-end') {
    return {
      width: `${preview.days * DAY_COLUMN_WIDTH}px`,
      minWidth: `${preview.days * DAY_COLUMN_WIDTH}px`,
    }
  }

  return {}
}

function projectSpanHasAssignedTasks(project?: ProjectRow | null) {
  return projectHasGantt(project)
}

function notifyProjectSpanDateLocked(project?: ProjectRow | null) {
  const taskCount = project ? projectTaskCount(project) : 0
  const suffix = taskCount ? ` (${taskCount} task${taskCount === 1 ? '' : 's'})` : ''
  raiseToast('error', `Project has tasks assigned${suffix}, so project dates cannot be changed.`)
}

function onProjectSegmentPointerDown(segment: ProjectSegment, event: PointerEvent) {
  if (!segment.active || !segment.project) return

  // Normal click should always open the project details dialog.
  // Moving the whole project span now requires Shift + drag so it does not block details access.
  if (!event.shiftKey) return

  startProjectSpanDrag(segment, 'move', event)
}

function onProjectSegmentClick(segment: ProjectSegment, event: MouseEvent) {
  if (!segment.active || !segment.project) return

  if (suppressNextProjectSpanClick.value) {
    suppressNextProjectSpanClick.value = false
    return
  }

  // Shift is reserved for drag-moving the whole span.
  if (event.shiftKey) return

  openProjectSpanDialog(segment.project)
}

function startProjectSpanDrag(segment: ProjectSegment, mode: ProjectSpanDragMode, event: PointerEvent) {
  if (event.button !== 0 || !segment.active || !segment.project) return

  if (projectSpanHasAssignedTasks(segment.project)) {
    notifyProjectSpanDateLocked(segment.project)
    event.preventDefault()
    return
  }

  const span = projectSpan(segment.project)
  if (!span) return

  scheduleClearHoverCard(0)
  projectSpanDrag.value = {
    mode,
    project: segment.project,
    projectKey: projectKey(segment.project),
    startX: event.clientX,
    originalStartIndex: span.startIndex,
    originalEndIndex: span.startIndex + span.days - 1,
    deltaDays: 0,
  }
  projectSpanDragMoved.value = false

  window.addEventListener('pointermove', onProjectSpanDragPointerMove)
  window.addEventListener('pointerup', stopProjectSpanDrag)
  window.addEventListener('pointercancel', cancelProjectSpanDrag)
  document.body.classList.add('year-project-span-is-dragging')

  event.preventDefault()
}

function onProjectSpanDragPointerMove(event: PointerEvent) {
  const drag = projectSpanDrag.value
  if (!drag) return

  const deltaPx = event.clientX - drag.startX
  if (Math.abs(deltaPx) > 4) projectSpanDragMoved.value = true

  drag.deltaDays = Math.round(deltaPx / DAY_COLUMN_WIDTH)
}

function clearProjectSpanDragState() {
  window.removeEventListener('pointermove', onProjectSpanDragPointerMove)
  window.removeEventListener('pointerup', stopProjectSpanDrag)
  window.removeEventListener('pointercancel', cancelProjectSpanDrag)
  document.body.classList.remove('year-project-span-is-dragging')
  projectSpanDrag.value = null
  projectSpanDragMoved.value = false
}

function cancelProjectSpanDrag() {
  clearProjectSpanDragState()
}

function stopProjectSpanDrag() {
  const drag = projectSpanDrag.value
  if (!drag) return

  const preview = projectSpanDragPreview(drag)
  const moved = projectSpanDragMoved.value
  const project = drag.project
  const originalStart = daysOfYear.value[drag.originalStartIndex]?.date
  const originalEnd = daysOfYear.value[drag.originalEndIndex]?.date

  clearProjectSpanDragState()

  if (!moved) {
    if (drag.mode === 'move') {
      suppressNextProjectSpanClick.value = true
      window.setTimeout(() => {
        suppressNextProjectSpanClick.value = false
      }, 0)
    }
    return
  }

  suppressNextProjectSpanClick.value = true
  window.setTimeout(() => {
    suppressNextProjectSpanClick.value = false
  }, 0)

  if (!preview || !preview.start || !preview.end || (preview.start === originalStart && preview.end === originalEnd)) {
    return
  }

  if (projectSpanHasAssignedTasks(project)) {
    notifyProjectSpanDateLocked(project)
    return
  }

  pendingProjectDateUpdate.value = {
    project: project.project,
    project_start_date: preview.start,
    project_end_date: preview.end,
  }
  loading.value = true
  updateProjectSpanDates.submit()
}


function getHoverPointer(event: MouseEvent): HoverPointer {
  return {
    clientX: event.clientX,
    clientY: event.clientY,
  }
}

function applyHoverCardPosition(pointer: HoverPointer) {
  if (!hoverCard.value || !hoverCardElement.value) return

  const padding = 12
  const cursorOffset = 14
  const fallbackCardWidth = 340
  const fallbackCardHeight = hoverCard.value.type === 'project' ? 168 : hoverCard.value.type === 'leave' ? 210 : 240
  const cardWidth = hoverCardElement.value.offsetWidth || fallbackCardWidth
  const cardHeight = hoverCardElement.value.offsetHeight || fallbackCardHeight
  const maxLeft = Math.max(padding, window.innerWidth - cardWidth - padding)
  const maxTop = Math.max(padding, window.innerHeight - cardHeight - padding)

  let x = pointer.clientX + cursorOffset
  if (x + cardWidth + padding > window.innerWidth) {
    x = pointer.clientX - cardWidth - cursorOffset
  }

  let y = pointer.clientY + cursorOffset
  if (y + cardHeight + padding > window.innerHeight) {
    y = pointer.clientY - cardHeight - cursorOffset
  }

  const clampedX = Math.min(Math.max(padding, x), maxLeft)
  const clampedY = Math.min(Math.max(padding, y), maxTop)

  hoverCardElement.value.style.transform = `translate3d(${clampedX}px, ${clampedY}px, 0)`
}

function scheduleHoverCardPosition(event: MouseEvent) {
  if (!hoverCard.value) return

  pendingHoverPointer = getHoverPointer(event)
  if (hoverPositionFrame) return

  hoverPositionFrame = window.requestAnimationFrame(() => {
    hoverPositionFrame = 0
    if (pendingHoverPointer) applyHoverCardPosition(pendingHoverPointer)
    pendingHoverPointer = null
  })
}

function cancelScheduledHoverClear() {
  if (hoverHideTimer !== null) {
    window.clearTimeout(hoverHideTimer)
    hoverHideTimer = null
  }
}

function setHoverCard(key: string, card: HoverCard, event: MouseEvent) {
  cancelScheduledHoverClear()

  const pointer = getHoverPointer(event)
  const cardAlreadyMounted = Boolean(hoverCard.value && hoverCardElement.value)

  if (activeHoverKey === key && hoverCard.value) {
    pendingHoverPointer = pointer
    if (hoverCardElement.value) applyHoverCardPosition(pointer)
    return
  }

  activeHoverKey = key

  // Move the existing mounted card before swapping its content. This makes rapid
  // project/shift switching feel instant instead of waiting for the next render.
  if (cardAlreadyMounted) {
    applyHoverCardPosition(pointer)
  }

  hoverCard.value = card

  if (hoverCardElement.value) {
    pendingHoverPointer = pointer
    window.requestAnimationFrame(() => {
      if (pendingHoverPointer) applyHoverCardPosition(pendingHoverPointer)
      pendingHoverPointer = null
    })
  } else {
    nextTick(() => applyHoverCardPosition(pointer))
  }
}

function positionHoverCard(event: MouseEvent) {
  scheduleHoverCardPosition(event)
}

function moveHoverCard(event: MouseEvent) {
  scheduleHoverCardPosition(event)
}

function scheduleClearHoverCard(delay = 90) {
  cancelScheduledHoverClear()
  hoverHideTimer = window.setTimeout(() => {
    clearHoverCard()
  }, delay)
}

function clearHoverCard() {
  cancelScheduledHoverClear()

  if (hoverPositionFrame) {
    window.cancelAnimationFrame(hoverPositionFrame)
    hoverPositionFrame = 0
  }

  activeHoverKey = ''
  pendingHoverPointer = null
  hoverCard.value = null
}

function compactDateRange(startDate?: string | null, endDate?: string | null) {
  if (!startDate && !endDate) return ''
  if (startDate && !endDate) return `${dayjs(startDate).format('DD MMM YYYY')} onwards`
  if (!startDate && endDate) return `Until ${dayjs(endDate).format('DD MMM YYYY')}`
  return `${dayjs(startDate).format('DD MMM YYYY')} - ${dayjs(endDate).format('DD MMM YYYY')}`
}

function leaveReason(leave: LeaveApplication) {
  return plainTextFromHtml(leave.reason || leave.description || '')
}

function leaveDayCount(leave: LeaveApplication) {
  const days = Number(leave.total_leave_days || 0)
  if (!Number.isFinite(days) || days <= 0) return ''
  return `${days} ${days === 1 ? 'day' : 'days'}`
}

function leaveHalfDayLabel(leave: LeaveApplication) {
  if (!leave.half_day) return ''
  if (leave.half_day_date) return `Yes · ${dayjs(leave.half_day_date).format('DD MMM YYYY')}`
  return 'Yes'
}

function shiftTimeRange(shift: ShiftAssignment) {
  if (shift.start_time && shift.end_time) return `${shift.start_time} - ${shift.end_time}`
  if (shift.start_time) return shift.start_time
  return ''
}

function showEmployeeHover(employee: Employee, date: string, event: MouseEvent) {
  const cell = getEmployeeCell(employee.name, date)

  if (cell?.type === 'leave') {
    const leave = cell.leave
    const reason = leaveReason(leave)

    setHoverCard(
      `leave:${employee.name}:${leave.leave}:${date}`,
      {
        type: 'leave',
        kicker: 'Leave Application',
        title: leave.leave_type,
        subtitle: employeeDisplayName(employee),
        badge: leave.status || 'Approved',
        badgeTone: 'red',
        accent: (colors as any).pink[500],
        rows: [
          { label: 'Employee', value: employeeDisplayName(employee) },
          { label: 'Employee ID', value: employee.name },
          { label: 'Leave Type', value: leave.leave_type },
          { label: 'Date', value: dayjs(date).format('dddd, DD MMM YYYY') },
          { label: 'Range', value: compactDateRange(leave.from_date, leave.to_date) },
          { label: 'Days', value: leaveDayCount(leave) },
          { label: 'Half Day', value: leaveHalfDayLabel(leave) },
        ],
        note: reason,
      },
      event,
    )
    return
  }

  if (cell?.type !== 'shift') {
    scheduleClearHoverCard()
    return
  }

  const shift = cell.shift
  const color = palette(shift.color)
  const accent = hasNote(shift.note) ? (colors as any).red[500] : color[500] || color[400]
  const customerLabel = shift.customer_abbreviation?.trim() || ''

  setHoverCard(
    `shift:${employee.name}:${shift.name}`,
    {
      type: 'shift',
      kicker: 'Shift Allocation',
      title: customerLabel || shift.shift_type,
      subtitle: [shift.custom_project_name, shift.shift_location].filter(Boolean).join(' · '),
      badge: cell.shifts.length > 1 ? `${cell.shifts.length} shifts` : shift.status,
      badgeTone: hasNote(shift.note) ? 'red' : 'blue',
      accent,
      rows: [
        { label: 'Employee', value: employeeDisplayName(employee) },
        { label: 'Employee ID', value: employee.name },
        { label: 'Customer', value: customerLabel },
        { label: 'Project', value: shift.custom_project_name },
        { label: 'Shift Type', value: shift.shift_type },
        { label: 'Time', value: shiftTimeRange(shift) },
        { label: 'Date', value: dayjs(date).format('dddd, DD MMM YYYY') },
        { label: 'Range', value: compactDateRange(shift.start_date, shift.end_date) },
        { label: 'Location', value: shift.shift_location },
        { label: 'Status', value: shift.status },
      ],
      note: plainTextFromHtml(shift.note),
    },
    event,
  )
}

function openProjectSpanDialog(project?: ProjectRow) {
  if (!project) return

  scheduleClearHoverCard(0)
  selectedProjectSpan.value = project
  showProjectSpanDialog.value = true
}

function showProjectHover(project: ProjectRow, segment: ProjectSegment, event: MouseEvent) {
  if (!segment.active) {
    scheduleClearHoverCard()
    return
  }

  const customerColor = normaliseHexColor(segment.customerColor)
  const fallbackColor = palette(segment.poEntered === false ? 'red' : 'green')
  const accent = customerColor ? darkenHexColor(customerColor, 0.3) : fallbackColor[500]

  setHoverCard(
    `project:${projectKey(project)}:${segment.date || ''}:${segment.days}`,
    {
      type: 'project',
      kicker: 'Project',
      title: segment.label || project.project_name,
      subtitle: [projectGroupLabel(project), segment.subline].filter(Boolean).join(' · '),
      badge: segment.poEntered ? 'PO Entered' : 'PO Missing',
      badgeTone: segment.poEntered ? 'green' : 'red',
      secondaryBadge: projectGanttStatus(project),
      secondaryBadgeTone: projectGanttStatusTone(project),
      accent,
      rows: [
        { label: 'Project ID', value: project.project },
        { label: 'Customer', value: project.customer_name || project.customer },
        { label: 'Location', value: project.custom_project_location },
        { label: 'Status', value: project.status },
        { label: 'Active', value: projectActiveValue(project) ? 'Yes' : 'No' },
        { label: 'Type', value: projectTypeLabel(project) },
        { label: 'Tasks', value: projectTaskSummary(project) },
        { label: 'Shifts Filled', value: projectShiftsFilledValue(project.shifts_filled) === true ? 'Yes' : 'No' },
        { label: 'Date Range', value: segment.subline },
        { label: 'DS Requested', value: segment.dsRequested || 0 },
        { label: 'NS Requested', value: segment.nsRequested || 0 },
        { label: 'DS Personnel', value: projectPersonnelSummary(project.ds_personnel) },
        { label: 'NS Personnel', value: projectPersonnelSummary(project.ns_personnel) },
      ],
      note: plainTextFromHtml(project.notes),
    },
    event,
  )
}

function isTodayDate(date: string) {
  return dayjs(date).isSame(dayjs(), 'day')
}

function todayMarker(date: string): DayMarker {
  return {
    type: 'today',
    title: 'Today',
    date,
  }
}

function getDayMarkers(date: string) {
  const markers = [...(dayMarkers.value[date] || [])]

  if (isTodayDate(date)) {
    markers.unshift(todayMarker(date))
  }

  return markers
}

function hasHolidayMarker(date: string) {
  return getDayMarkers(date).some((marker) => marker.type === 'holiday')
}

function hasCalendarEventMarker(date: string) {
  return getDayMarkers(date).some((marker) => marker.type === 'event')
}

function hasTodayMarker(date: string) {
  return isTodayDate(date)
}

function dayHeaderMarkerClass(date: string) {
  const hasHoliday = hasHolidayMarker(date)
  const hasEvent = hasCalendarEventMarker(date)
  const hasToday = hasTodayMarker(date)

  return {
    'year-day-marker': hasHoliday || hasEvent || hasToday,
    'year-day-marker-holiday': hasHoliday && !hasEvent && !hasToday,
    'year-day-marker-event': hasEvent && !hasHoliday && !hasToday,
    'year-day-marker-mixed': hasHoliday && hasEvent && !hasToday,
    'year-day-marker-today': hasToday,
  }
}

function dayHeaderTitle(date: string) {
  const markers = getDayMarkers(date)
  const formattedDate = dayjs(date).format('dddd, DD MMMM YYYY')

  if (!markers.length) return formattedDate

  return [
    formattedDate,
    ...markers.map((marker) => marker.title || marker.name || (marker.type === 'holiday' ? 'Holiday' : 'Event')),
  ].join(' | ')
}

function markerDateRange(marker: DayMarker) {
  if (marker.type === 'holiday' || marker.type === 'today') {
    return marker.date ? dayjs(marker.date).format('DD MMM YYYY') : ''
  }

  return compactDateRange(marker.start_date, marker.end_date)
}

function markerRowLabel(marker: DayMarker, eventNumber: number, holidayNumber: number) {
  if (marker.type === 'today') return 'Today'
  if (marker.type === 'holiday') return holidayNumber > 1 ? `Holiday ${holidayNumber}` : 'Holiday'
  return eventNumber > 1 ? `Event ${eventNumber}` : 'Event'
}

function dayMarkerSummary(markers: DayMarker[]) {
  const todayCount = markers.filter((marker) => marker.type === 'today').length
  const holidayCount = markers.filter((marker) => marker.type === 'holiday').length
  const eventCount = markers.filter((marker) => marker.type === 'event').length
  const parts = []

  if (todayCount) parts.push('Today')
  if (holidayCount) parts.push(`${holidayCount} holiday${holidayCount === 1 ? '' : 's'}`)
  if (eventCount) parts.push(`${eventCount} event${eventCount === 1 ? '' : 's'}`)

  return parts.join(' · ')
}

function dayMarkerRows(date: string, markers: DayMarker[]): HoverCardRow[] {
  const rows: HoverCardRow[] = [{ label: 'Date', value: dayjs(date).format('dddd, DD MMM YYYY') }]
  let eventNumber = 0
  let holidayNumber = 0

  for (const marker of markers) {
    if (marker.type === 'event') eventNumber += 1
    if (marker.type === 'holiday') holidayNumber += 1

    rows.push({
      label: markerRowLabel(marker, eventNumber, holidayNumber),
      value: [marker.title || marker.name, markerDateRange(marker)].filter(Boolean).join(' · '),
    })

    if (marker.type === 'event' && marker.event_type) {
      rows.push({
        label: eventNumber > 1 ? `Event ${eventNumber} Type` : 'Event Type',
        value: marker.event_type,
      })
    }
  }

  return rows
}

function dayMarkerNote(markers: DayMarker[]) {
  const notes = markers
    .map((marker) => {
      const description = plainTextFromHtml(marker.description)
      if (!description) return ''

      const title = marker.title || marker.name || (marker.type === 'holiday' ? 'Holiday' : 'Event')
      return description === title ? description : `${title}: ${description}`
    })
    .filter(Boolean)

  return notes.join('\n\n')
}

function dayMarkerBadge(markers: DayMarker[]) {
  const hasToday = markers.some((marker) => marker.type === 'today')
  const hasHoliday = markers.some((marker) => marker.type === 'holiday')
  const hasEvent = markers.some((marker) => marker.type === 'event')
  const labels = []

  if (hasToday) labels.push('Today')
  if (hasHoliday) labels.push('Holiday')
  if (hasEvent) labels.push('Event')

  return labels.join(' + ')
}

function showDayMarkerHover(date: string, event: MouseEvent) {
  const markers = getDayMarkers(date)
  if (!markers.length) {
    scheduleClearHoverCard()
    return
  }

  const hasToday = markers.some((marker) => marker.type === 'today')
  const hasHoliday = markers.some((marker) => marker.type === 'holiday')
  const hasEvent = markers.some((marker) => marker.type === 'event')
  const accent = hasToday
    ? (colors as any).yellow[500]
    : hasHoliday && hasEvent
      ? (colors as any).violet[500]
      : hasHoliday
        ? (colors as any).blue[500]
        : (colors as any).emerald[500]

  setHoverCard(
    `day-marker:${date}:${markers.map((marker) => `${marker.type}:${marker.name || marker.title}`).join('|')}`,
    {
      type: 'day-marker',
      kicker: hasToday ? 'Current Day' : 'Calendar Highlight',
      title: dayjs(date).format('dddd, DD MMMM YYYY'),
      subtitle: dayMarkerSummary(markers),
      badge: dayMarkerBadge(markers),
      badgeTone: hasToday ? 'yellow' : hasHoliday ? 'blue' : 'green',
      accent,
      rows: dayMarkerRows(date, markers),
      note: dayMarkerNote(markers),
    },
    event,
  )
}

function scrollToToday() {
  const today = dayjs().format('YYYY-MM-DD')
  const targetTodayIndex = daysOfYear.value.findIndex((day) => day.date === today)

  if (targetTodayIndex < 0) return false

  const leftOffset = 4 * DAY_COLUMN_WIDTH
  const targetLeft = Math.max(0, targetTodayIndex * DAY_COLUMN_WIDTH - leftOffset)

  if (projectScroller.value) projectScroller.value.scrollLeft = targetLeft
  if (employeeScroller.value) employeeScroller.value.scrollLeft = targetLeft

  emit('hscroll', targetLeft)
  return true
}

watch(
  () => [props.firstOfMonth, props.employeeFilters, props.shiftFilters],
  () => {
    loading.value = true
    events.fetch()
  },
  { deep: true },
)

const events = createResource({
  url: 'verto.api.planner.get_year_events',
  auto: true,
  makeParams() {
    return {
      year: props.firstOfMonth.year(),
      employee_filters: props.employeeFilters,
      shift_filters: props.shiftFilters,
    }
  },
  transform(data: YearEventsResponse) {
    return {
      mappedEvents: mapEventsToYear(data?.events || {}),
      projectRows: (data?.project_rows || []).sort((a, b) => naturalCompare(a.customer_name || a.customer || '', b.customer_name || b.customer || '') || naturalCompare(a.project_name, b.project_name)),
      dayMarkers: data?.day_markers || {},
    }
  },
  onSuccess() {
    loading.value = false
  },
  onError(error: { messages?: string[]; message?: string }) {
    loading.value = false
    raiseToast('error', error?.messages?.[0] || error?.message || 'Failed to fetch annual roster')
  },
})

const bulkMoveOrSwapShifts = createResource({
  url: 'verto.api.planner.bulk_move_or_swap_shifts',
  makeParams() {
    return pendingBulkShiftParams.value || {
      shifts: [],
      target_employee: '',
      target_date: '',
    }
  },
  onSuccess() {
    const count = pendingBulkShiftParams.value?.shifts?.length || 1
    const action = pendingBulkShiftWillSwap.value ? 'swapped' : 'moved'
    raiseToast('success', `${count} shift${count === 1 ? '' : 's'} ${action} successfully!`)
    pendingBulkShiftParams.value = null
    pendingBulkShiftWillSwap.value = false
    clearSelectedShiftCells()
    clearDragState()
    events.fetch()
  },
  onError(error: { messages?: string[]; message?: string }) {
    loading.value = false
    pendingBulkShiftParams.value = null
    pendingBulkShiftWillSwap.value = false
    clearDragState()
    raiseToast('error', error?.messages?.[0] || error?.message || 'Failed to move shifts')
  },
})


const updateProjectSpanDates = createResource({
  url: 'verto.api.planner.update_project_planner_dates',
  makeParams() {
    return pendingProjectDateUpdate.value || {
      project: '',
      project_start_date: '',
      project_end_date: '',
    }
  },
  onSuccess() {
    raiseToast('success', 'Project dates updated successfully!')
    pendingProjectDateUpdate.value = null
    events.fetch()
  },
  onError(error: { messages?: string[]; message?: string }) {
    loading.value = false
    pendingProjectDateUpdate.value = null
    raiseToast('error', error?.messages?.[0] || error?.message || 'Failed to update project dates')
  },
})

defineExpose({ events, scrollToToday })
</script>

<style scoped>
.year-section-toggle {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  min-height: 26px;
  border-radius: 6px;
  border: 1px solid rgb(209 213 219);
  background: rgb(255 255 255);
  padding: 4px 9px;
  color: rgb(55 65 81);
  font-size: 11px;
  font-weight: 600;
  line-height: 1;
}

.year-section-toggle:hover {
  background: rgb(249 250 251);
}

.year-section-toggle-inactive {
  border-color: rgb(229 231 235);
  background: rgb(249 250 251);
  color: rgb(107 114 128);
}

.year-section-toggle-icon {
  display: inline-flex;
  width: 10px;
  justify-content: center;
  font-size: 10px;
  line-height: 1;
}

.year-section-inline-toggle {
  min-height: 22px;
  padding: 3px 7px;
  font-size: 10px;
}

.year-table-resizer {
  display: flex;
  align-items: center;
  gap: 8px;
  height: 18px;
  padding: 0 10px;
  cursor: row-resize;
  user-select: none;
  touch-action: none;
  border-top: 1px solid rgb(229 231 235);
  background: linear-gradient(180deg, rgb(249 250 251), rgb(255 255 255));
}

.year-table-resizer:hover,
.year-table-resizer-active {
  background: rgb(239 246 255);
}

.year-table-resizer-line {
  height: 1px;
  min-width: 0;
  flex: 1;
  background: rgb(209 213 219);
}

.year-table-resizer-handle {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 14px;
  border-radius: 9999px;
  color: rgb(107 114 128);
  background: rgb(255 255 255);
  box-shadow: inset 0 0 0 1px rgb(209 213 219);
}

.year-table-resizer:hover .year-table-resizer-handle,
.year-table-resizer-active .year-table-resizer-handle {
  color: rgb(37 99 235);
  box-shadow: inset 0 0 0 1px rgb(147 197 253);
}

.year-table-resizer-icon {
  width: 13px;
  height: 13px;
  stroke-width: 2.2;
}

:global(body.year-table-is-resizing) {
  cursor: row-resize !important;
  user-select: none !important;
}

.year-table-stage {
  position: relative;
  display: inline-block;
  width: max-content;
  min-width: max-content;
}

.year-today-overlay {
  position: absolute;
  top: 0;
  bottom: 0;
  z-index: 5;
  pointer-events: none;
  background: rgb(250 204 21 / 0.18);
  border-left: 2px solid rgb(202 138 4 / 0.8);
  border-right: 2px solid rgb(202 138 4 / 0.8);
  box-shadow: inset 0 0 0 1px rgb(234 179 8 / 0.28);
  box-sizing: border-box;
}

.year-roster-table {
  table-layout: fixed;
  width: max-content;
  min-width: max-content;
}

.year-day-colgroup,
.year-roster-table .year-day-header,
.year-roster-table .year-cell {
  min-width: 28px !important;
  max-width: 28px !important;
  width: 28px !important;
}

.year-left-colgroup,
.year-roster-table .year-left-col,
.year-roster-table .year-left-header {
  min-width: 300px !important;
  max-width: 300px !important;
  width: 300px !important;
}

.year-roster-table th,
.year-roster-table td {
  height: 26px;
  padding: 0;
  font-size: 10px;
  line-height: 1;
  overflow: hidden;
  white-space: nowrap;
}

.year-left-col,
.year-left-header {
  position: sticky;
  left: 0;
  z-index: 10;
}

.year-left-header {
  top: 0;
  height: 52px;
  z-index: 20;
}

.year-month-header {
  position: sticky;
  top: 0;
  z-index: 6;
  height: 24px;
}

.year-day-header {
  position: sticky;
  top: 24px;
  z-index: 6;
  height: 28px;
}

.year-day-marker {
  cursor: help;
  box-shadow: inset 0 -3px 0 rgb(59 130 246 / 0.75);
}

.year-day-marker-holiday {
  background: rgb(239 246 255) !important;
  color: rgb(30 64 175);
}

.year-day-marker-event {
  background: rgb(236 253 245) !important;
  color: rgb(6 95 70);
  box-shadow: inset 0 -3px 0 rgb(16 185 129 / 0.78);
}

.year-day-marker-mixed {
  background: linear-gradient(135deg, rgb(239 246 255) 0%, rgb(239 246 255) 50%, rgb(236 253 245) 50%, rgb(236 253 245) 100%) !important;
  color: rgb(88 28 135);
  box-shadow: inset 0 -3px 0 rgb(139 92 246 / 0.78);
}

.year-day-marker-today {
  background: rgb(254 249 195) !important;
  color: rgb(113 63 18);
  box-shadow: inset 0 -3px 0 rgb(234 179 8 / 0.9);
}

.year-cell {
  font-weight: 600;
  vertical-align: middle;
}

.year-employee-shift-cell {
  border-style: solid !important;
}

.year-employee-shift-cell[draggable='true'] {
  cursor: grab;
}

.year-employee-shift-cell[draggable='true']:active {
  cursor: grabbing;
}

:global(.year-drag-preview) {
  position: fixed;
  left: -9999px;
  top: -9999px;
  z-index: 2147483647;
  max-width: 120px;
  border: 1px solid rgb(37 99 235 / 0.65);
  border-radius: 9999px;
  background: rgb(239 246 255);
  padding: 5px 10px;
  color: rgb(30 64 175);
  font-size: 11px;
  font-weight: 800;
  line-height: 1;
  white-space: nowrap;
  box-shadow: 0 8px 20px rgb(15 23 42 / 0.18);
  pointer-events: none;
}

.year-employee-shift-selected {
  outline: 2px solid rgb(37 99 235 / 0.95) !important;
  outline-offset: -2px;
  box-shadow:
    inset 0 0 0 2px rgb(37 99 235 / 0.38),
    var(--tw-ring-shadow, 0 0 #0000) !important;
  position: relative;
}

.year-employee-shift-selected::before {
  content: '';
  position: absolute;
  inset: 2px;
  border-radius: 3px;
  background: rgb(37 99 235 / 0.1);
  pointer-events: none;
}

.year-employee-drag-source {
  opacity: 0.38;
}

.year-employee-drop-target {
  position: relative;
  outline: 2px solid rgb(37 99 235 / 0.9) !important;
  outline-offset: -2px;
  background-image: linear-gradient(rgb(219 234 254 / 0.8), rgb(219 234 254 / 0.8)) !important;
  contain: paint;
}

.year-employee-drop-target-move::after,
.year-employee-drop-target-swap::after,
.year-employee-drop-target-invalid::after {
  position: absolute;
  inset: 2px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
  font-size: 9px;
  font-weight: 800;
  line-height: 1;
  pointer-events: none;
}

.year-employee-drop-target-move::after {
  content: 'MOVE';
  background: rgb(219 234 254 / 0.78);
  color: rgb(30 64 175);
}

.year-employee-drop-target-swap::after {
  content: 'SWAP';
  background: rgb(220 252 231 / 0.82);
  color: rgb(22 101 52);
}

.year-employee-drop-target-invalid {
  position: relative;
  outline: 2px solid rgb(239 68 68 / 0.9) !important;
  outline-offset: -2px;
  background-image: linear-gradient(rgb(254 226 226 / 0.82), rgb(254 226 226 / 0.82)) !important;
  contain: paint;
}

.year-employee-drop-target-invalid::after {
  content: 'BLOCKED';
  background: rgb(254 226 226 / 0.9);
  color: rgb(153 27 27);
}

.year-employee-shift-continues-left.year-month-start {
  border-left-color: transparent !important;
}

.year-employee-shift-continues-right {
  border-right-color: transparent !important;
}

.year-project-row td {
  height: 36px;
}

.year-project-cell {
  vertical-align: middle;
}

.year-project-empty-cell {
  background: rgb(249 250 251);
}

.year-project-span {
  padding: 2px 8px !important;
  border-width: 1px !important;
  border-style: solid !important;
  border-radius: 6px;
}

.year-project-span-inactive {
  font-weight: 500;
}

.year-project-span-content {
  display: flex;
  min-width: 0;
  height: 100%;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
  overflow: hidden;
  text-align: center;
  white-space: nowrap;
}

.year-project-span-title-row,
.year-project-span-meta-row {
  display: flex;
  min-width: 0;
  max-width: 100%;
  align-items: center;
  justify-content: center;
}

.year-project-span-title-row {
  width: 100%;
}

.year-project-span-meta-row {
  gap: 5px;
  line-height: 1;
}

.year-project-status-icon,
.year-project-gantt-status-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 13px;
  min-width: 13px;
  height: 13px;
  border-radius: 9999px;
  line-height: 1;
}

.year-project-inline-icon {
  width: 12px;
  height: 12px;
  stroke-width: 2.1;
}

.year-project-po-entered {
  color: rgb(22 163 74);
}

.year-project-po-missing {
  color: rgb(239 68 68);
}

.year-project-gantt-available {
  color: rgb(22 163 74);
}

.year-project-gantt-missing {
  color: rgb(239 68 68);
}

.year-project-span-name {
  min-width: 0;
  max-width: 100%;
  color: var(--year-project-span-text, rgb(31 41 55));
  font-size: 10px;
  font-weight: 700;
  line-height: 1.05;
}

.year-project-span-date {
  min-width: max-content;
  color: var(--year-project-span-muted, rgb(107 114 128));
  font-size: 10px;
  font-weight: 500;
  line-height: 1;
}

.year-project-request-group {
  display: inline-flex;
  align-items: center;
  gap: 1px;
  min-width: max-content;
  line-height: 1;
}

.year-project-request {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 12px;
  min-width: 12px;
  height: 12px;
  line-height: 1;
}

.year-project-request-icon {
  width: 11px;
  height: 11px;
  stroke-width: 2;
}

.year-project-request-ds {
  color: rgb(249 115 22);
}

.year-project-request-ns {
  color: rgb(14 165 233);
}

.year-project-request-count {
  min-width: max-content;
  color: var(--year-project-span-muted, rgb(55 65 81));
  font-size: 10px;
  font-weight: 700;
  line-height: 1;
}

.year-cell:hover {
  outline: 1px solid rgb(59 130 246 / 0.6);
  outline-offset: -1px;
}

.year-weekend {
  background-image: linear-gradient(rgb(249 250 251 / 0.7), rgb(249 250 251 / 0.7));
}

.year-month-start {
  border-left-width: 2px !important;
  border-left-color: rgb(156 163 175) !important;
}


.year-dialog-open .year-left-col,
.year-dialog-open .year-left-header,
.year-dialog-open .year-month-header,
.year-dialog-open .year-day-header,
.year-dialog-open .year-today-overlay {
  z-index: 0 !important;
}

.year-employee-search-header {
  height: 86px;
  vertical-align: top;
}

.year-employee-header-content {
  display: flex;
  min-height: 86px;
  flex-direction: column;
  justify-content: center;
  gap: 4px;
}

.year-employee-search {
  width: 100%;
  max-width: 100%;
  line-height: normal;
}

.year-employee-search :deep(input),
.year-employee-search :deep(.input),
.year-employee-search :deep(.form-control) {
  min-height: 26px;
  height: 26px;
  font-size: 11px;
}

.year-employee-legend-title {
  margin-top: 1px;
  color: rgb(107 114 128);
  font-size: 9px;
  font-weight: 600;
  line-height: 1;
}

.year-employee-legend {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 2px 8px;
}

.year-employee-legend-item {
  display: flex;
  align-items: center;
  gap: 4px;
  min-width: 0;
  overflow: hidden;
  color: rgb(107 114 128);
  font-size: 9px;
  line-height: 1.05;
  white-space: nowrap;
}

.year-employee-legend-dot {
  display: inline-block;
  width: 9px;
  min-width: 9px;
  height: 9px;
  border-radius: 9999px;
  border: 1px solid rgb(107 114 128 / 0.4);
}

.year-employee-legend-fifo {
  background: rgb(250 204 21);
}

.year-employee-legend-ds {
  background: rgb(34 197 94);
}

.year-employee-legend-ns {
  background: rgb(59 130 246);
}

.year-employee-legend-pth {
  background: rgb(168 85 247);
}


.year-project-filter-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  color: rgb(75 85 99);
  font-size: 10px;
  font-weight: 600;
  line-height: 1;
}

.year-project-filter-toggle {
  display: inline-flex;
  overflow: hidden;
  border: 1px solid rgb(209 213 219);
  border-radius: 9999px;
  background: rgb(249 250 251);
}

.year-project-filter-option {
  min-width: 42px;
  border: 0;
  background: transparent;
  padding: 3px 7px;
  color: rgb(107 114 128);
  font-size: 9px;
  font-weight: 700;
  line-height: 1;
}

.year-project-filter-option:hover {
  background: rgb(243 244 246);
}

.year-project-filter-option-active {
  background: rgb(31 41 55);
  color: white;
}

.year-project-filter-option-active:hover {
  background: rgb(31 41 55);
}

.year-project-legend-header {
  height: 112px;
  vertical-align: top;
}

.year-project-header-content {
  line-height: 1.1;
}

.year-project-header-icon {
  width: 14px;
  height: 14px;
  color: rgb(37 99 235);
  stroke-width: 1.8;
}

.year-project-legend {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 2px 8px;
}

.year-project-legend-item {
  display: flex;
  align-items: center;
  gap: 4px;
  min-width: 0;
  overflow: hidden;
  color: rgb(107 114 128);
  font-size: 9px;
  line-height: 1.05;
  white-space: nowrap;
}

.year-legend-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 12px;
  min-width: 12px;
  height: 12px;
  border-radius: 9999px;
  line-height: 1;
  stroke-width: 2;
}

.year-legend-po-entered {
  color: rgb(34 197 94);
}

.year-legend-po-missing {
  color: rgb(239 68 68);
}

.year-legend-gantt-available {
  color: rgb(22 163 74);
}

.year-legend-gantt-missing {
  color: rgb(239 68 68);
}

.year-legend-ds-requested {
  color: rgb(249 115 22);
}

.year-legend-ns-requested {
  color: rgb(14 165 233);
}


.year-hover-card {
  position: fixed;
  left: 0;
  top: 0;
  z-index: 9999;
  width: 340px;
  transform: translate3d(-9999px, -9999px, 0);
  will-change: transform;
  max-width: calc(100vw - 24px);
  pointer-events: none;
  border: 1px solid rgb(209 213 219);
  border-left: 4px solid var(--year-hover-accent, rgb(59 130 246));
  border-radius: 10px;
  background: rgb(255 255 255);
  box-shadow: 0 18px 40px rgb(15 23 42 / 0.18), 0 4px 12px rgb(15 23 42 / 0.1);
  color: rgb(31 41 55);
  max-height: calc(100vh - 24px);
  overflow-y: auto;
  overflow-x: hidden;
  overscroll-behavior: contain;
  contain: layout paint style;
  backface-visibility: hidden;
}

.year-hover-card-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
  border-bottom: 1px solid rgb(229 231 235);
  background: linear-gradient(90deg, rgb(249 250 251), rgb(255 255 255));
  padding: 10px 12px 8px;
}

.year-hover-card-kicker {
  color: rgb(107 114 128);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.05em;
  line-height: 1;
  text-transform: uppercase;
}

.year-hover-card-title {
  margin-top: 4px;
  color: rgb(17 24 39);
  font-size: 13px;
  font-weight: 700;
  line-height: 1.2;
}

.year-hover-card-subtitle {
  margin-top: 3px;
  color: rgb(75 85 99);
  font-size: 11px;
  font-weight: 500;
  line-height: 1.2;
}

.year-hover-card-badge-stack {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 4px;
  margin-left: 12px;
}

.year-hover-card-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: max-content;
  border-radius: 9999px;
  padding: 4px 8px;
  font-size: 10px;
  font-weight: 700;
  line-height: 1;
}

.year-hover-card-badge-green {
  background: rgb(220 252 231);
  color: rgb(22 101 52);
}

.year-hover-card-badge-red {
  background: rgb(254 226 226);
  color: rgb(153 27 27);
}

.year-hover-card-badge-blue {
  background: rgb(219 234 254);
  color: rgb(30 64 175);
}

.year-hover-card-badge-yellow {
  background: rgb(254 249 195);
  color: rgb(113 63 18);
}

.year-hover-card-badge-gray {
  background: rgb(243 244 246);
  color: rgb(55 65 81);
}

.year-hover-card-grid {
  display: grid;
  grid-template-columns: 92px minmax(0, 1fr);
  gap: 5px 10px;
  padding: 10px 12px;
}

.year-hover-card-label {
  color: rgb(107 114 128);
  font-size: 10px;
  font-weight: 700;
  line-height: 1.2;
  text-transform: uppercase;
}

.year-hover-card-value {
  color: rgb(31 41 55);
  font-size: 11px;
  font-weight: 600;
  line-height: 1.2;
}

.year-hover-card-project .year-hover-card-value {
  white-space: normal !important;
  overflow: visible !important;
  text-overflow: clip !important;
}

.year-hover-card-note {
  margin: 0 12px 12px;
  border: 1px solid rgb(254 202 202);
  border-radius: 8px;
  background: rgb(254 242 242);
  padding: 8px;
  color: rgb(127 29 29);
  font-size: 11px;
  font-weight: 500;
  line-height: 1.35;
  white-space: pre-line;
}

.year-hover-card-leave .year-hover-card-note {
  border-color: rgb(251 207 232);
  background: rgb(253 242 248);
  color: rgb(157 23 77);
}

.year-hover-card-day-marker .year-hover-card-note {
  border-color: rgb(191 219 254);
  background: rgb(239 246 255);
  color: rgb(30 64 175);
}

.year-project-span-date-dragging {
  position: relative;
  cursor: grabbing !important;
  outline: 2px solid rgb(245 158 11);
  outline-offset: -2px;
}

.year-project-span-date-resizing {
  overflow: visible;
}

.year-project-span-drag-handle {
  position: absolute;
  top: 4px;
  bottom: 4px;
  z-index: 12;
  width: 10px;
  border: 0;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.62);
  opacity: 0;
  box-shadow: 0 0 0 1px rgba(17, 24, 39, 0.18);
  transition: opacity 120ms ease, background 120ms ease;
}

.year-project-span:hover .year-project-span-drag-handle,
.year-project-span-date-dragging .year-project-span-drag-handle {
  opacity: 1;
}

.year-project-span-drag-handle:hover {
  background: rgba(255, 255, 255, 0.9);
}

.year-project-span-drag-start {
  left: 3px;
  cursor: ew-resize;
}

.year-project-span-drag-end {
  right: 3px;
  cursor: ew-resize;
}

.year-project-span-is-dragging,
.year-project-span-is-dragging * {
  user-select: none !important;
}

.year-project-span:hover {
  filter: saturate(1.08) brightness(0.98);
}

</style>

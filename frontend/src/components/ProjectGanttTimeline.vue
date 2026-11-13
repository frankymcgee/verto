<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import Gantt, { type GanttOptions } from 'frappe-gantt'
import { hasTimelineDates, type ScheduleRow, type ScheduleTask } from '../lib/ganttSchedule'
// The 1.2.2 package exposes the JS entry, with its stylesheet beside it.
import '../../node_modules/frappe-gantt/dist/frappe-gantt.css'

const props = defineProps<{
  rows: ScheduleRow[]
  scale: GanttOptions['view_mode']
}>()
const emit = defineEmits<{ select: [task: ScheduleTask]; 'today-available': [available: boolean] }>()

const headerHeight = 60
const rowHeight = 48
const surface = ref<HTMLElement | null>(null)
const chartHost = ref<HTMLElement | null>(null)
const period = ref('')
const taskById = computed(() => new Map(props.rows.map(({ task }) => [task.id, task])))

// A viewing-only chart needs no document-level drag listeners. Frappe Gantt
// 1.2.2 installs them even in readonly mode and has no teardown for them.
class ReadonlyGantt extends Gantt {
  bind_bar_events() {}
}

let gantt: Gantt | undefined
let renderedRows: ScheduleRow[] | undefined
let renderedScale: GanttOptions['view_mode'] | undefined
let periodMarkers: { left: number; label: string }[] = []

function updatePeriod() {
  const left = surface.value?.scrollLeft || 0
  const marker = periodMarkers.find((item) => item.left <= left + 1)
  period.value = (marker || periodMarkers.at(-1))?.label || ''
}

function chartTasks(rows: ScheduleRow[]) {
  const dated = rows.map(({ task }) => task).filter(hasTimelineDates)
  const firstDated = dated[0]
  if (!firstDated) return []

  const idByName = new Map(dated.map((task) => [task.name, task.id]))
  return rows.map(({ task }) => {
    const hasDates = hasTimelineDates(task)
    // Frappe Gantt needs dates for each row. A hidden bar anchored to an
    // existing date reserves the parent's row without extending the timeline.
    const start = new Date(hasDates ? task.start.date : firstDated.start.date)
    const end = new Date(hasDates ? task.end.date : firstDated.start.date)
    // The chart displays calendar days, while task details show the recorded times.
    start.setHours(0, 0, 0, 0)
    end.setHours(23, 59, 59, 0)
    return {
      id: task.id,
      // The Vue task column supplies the label. The upstream chart writes labels as HTML.
      name: '',
      start,
      end,
      progress: task.progress,
      dependencies: hasDates ? task.dependencies.flatMap((name) => {
        const id = idByName.get(name)
        return id && id !== task.id ? [id] : []
      }) : [],
      custom_class: !hasDates ? 'verto-gantt-undated' : task.isMilestone ? 'verto-gantt-milestone' : 'verto-gantt-task',
      color: task.color,
      color_progress: task.color ? 'rgb(0 0 0 / 0.22)' : undefined,
    }
  })
}

function scrollToEarliestTask() {
  if (!surface.value || !chartHost.value) return
  const bars = chartHost.value.querySelectorAll('.bar-wrapper:not(.verto-gantt-undated) rect.bar')
  const left = Math.min(...Array.from(bars, (bar) => Number(bar.getAttribute('x'))))
  if (Number.isFinite(left)) surface.value.scrollLeft = Math.max(0, left - 16)
}

function scrollToToday() {
  const today = chartHost.value?.querySelector<HTMLElement>('.current-date-highlight')
  if (today && surface.value) {
    // Week labels may contain today even when the week starts offscreen.
    const marker = chartHost.value?.querySelector<HTMLElement>('.current-ball-highlight')
    surface.value.scrollLeft = Math.max(0, (marker?.offsetLeft ?? today.offsetLeft) - 16)
  }
}

defineExpose({ scrollToToday })

function selectBar(event: MouseEvent) {
  const id = (event.target as Element).closest('.bar-wrapper')?.getAttribute('data-id')
  const task = id && taskById.value.get(id)
  if (task) emit('select', task)
}

watch([chartHost, () => props.rows, () => props.scale], ([host, rows, scale]) => {
  if (!host) return

  const previousLeft = surface.value?.scrollLeft || 0
  const scaleChanged = renderedScale !== scale
  if (!gantt) {
    gantt = new ReadonlyGantt(host, chartTasks(rows), {
      view_mode: scale,
      upper_header_height: 25,
      lower_header_height: 25,
      bar_height: 26,
      padding: rowHeight - 26,
      readonly: true,
      move_dependencies: false,
      today_button: false,
      infinite_padding: false,
      scroll_to: 'start',
      popup: false,
    })
  } else {
    if (renderedRows !== rows) gantt.refresh(chartTasks(rows))
    if (scaleChanged) gantt.change_view_mode(scale)
  }
  renderedRows = rows
  renderedScale = scale

  const header = host.querySelector<HTMLElement>('.grid-header')
  const width = parseFloat(header?.style.width || '') || 0
  host.parentElement?.style.setProperty('--gantt-timeline-width', `${width}px`)
  periodMarkers = Array.from(host.querySelectorAll<HTMLElement>('.upper-text'), (element) => ({
    left: element.offsetLeft,
    label: element.textContent || '',
  })).reverse()
  const todayAvailable = Boolean(host.querySelector('.current-date-highlight'))
  emit('today-available', todayAvailable)
  if (scaleChanged) {
    if (todayAvailable) scrollToToday()
    else scrollToEarliestTask()
  } else if (surface.value) {
    surface.value.scrollLeft = previousLeft
  }
  updatePeriod()
}, { flush: 'post' })
</script>

<template>
  <div
    ref="surface"
    class="project-gantt-scroll rounded-7 border border-outline-gray-2 bg-surface-base"
    role="region"
    aria-label="Project timeline"
    tabindex="0"
    :style="{ '--gantt-header-height': `${headerHeight}px`, '--gantt-row-height': `${rowHeight}px` }"
    @scroll.passive="updatePeriod"
  >
    <div class="project-gantt-grid">
      <div class="project-gantt-names border-r border-outline-gray-2 bg-surface-base">
        <div class="project-gantt-name-heading border-b border-outline-gray-2 px-3 text-sm-semibold text-ink-gray-8">
          <span>Tasks</span>
          <span v-if="period" class="text-xs font-normal text-ink-gray-6">{{ period }}</span>
        </div>
        <button
          v-for="{ task, depth } in rows"
          :key="task.id"
          type="button"
          class="project-gantt-name w-full border-b border-outline-gray-1 pe-2 text-left text-sm text-ink-gray-8 hover:bg-surface-gray-1"
          :title="task.title"
          :style="{ paddingInlineStart: `${0.5 + Math.min(depth, 4) * 0.5}rem` }"
          @click="emit('select', task)"
        >
          <span class="project-gantt-name-label" :class="{ 'font-semibold': task.isGroup }">
            {{ task.title }}
          </span>
          <span v-if="hasTimelineDates(task)" class="block text-xs text-ink-gray-5">{{ task.isMilestone ? 'Milestone · ' : '' }}{{ task.progress }}%</span>
          <span v-else class="block text-xs text-ink-gray-5">No timeline dates</span>
        </button>
      </div>
      <div ref="chartHost" class="project-gantt-chart" aria-hidden="true" @click="selectBar" />
    </div>
  </div>
</template>

<style scoped>
.project-gantt-scroll {
  overflow: auto;
  max-height: clamp(14rem, 56dvh, 42rem);
  touch-action: pan-x pan-y;
  overscroll-behavior-x: contain;
}

.project-gantt-grid {
  --gantt-name-width: clamp(7rem, 31vw, 16rem);
  display: grid;
  grid-template-columns: var(--gantt-name-width) minmax(0, 1fr);
  width: max(100%, calc(var(--gantt-name-width) + var(--gantt-timeline-width, 0px)));
  isolation: isolate;
}

.project-gantt-names {
  position: sticky;
  left: 0;
  z-index: 2;
  min-width: 0;
}

.project-gantt-name-heading {
  position: sticky;
  top: 0;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 0.25rem;
  z-index: 1;
  height: var(--gantt-header-height);
  background: inherit;
}

.project-gantt-name {
  display: block;
  height: var(--gantt-row-height);
}

.project-gantt-name-label {
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  overflow: hidden;
  overflow-wrap: anywhere;
  line-height: 1rem;
}

.project-gantt-chart {
  position: relative;
  min-width: 0;
  --g-bar-color: #bfdbfe;
  --g-progress-color: #3b82f6;
  --g-today-highlight: #1d4ed8;
  --g-header-background: var(--surface-base, #fff);
  --g-row-color: var(--surface-base, #fff);
}

.project-gantt-chart :deep(.gantt-container) {
  overflow: visible;
  border-radius: 0;
  isolation: auto;
}

.project-gantt-chart :deep(.grid-header) {
  z-index: 1;
}

.project-gantt-chart :deep(.upper-text) {
  padding-left: 4px;
  visibility: hidden;
  white-space: nowrap;
}

.project-gantt-chart :deep(.current-highlight),
.project-gantt-chart :deep(.current-ball-highlight) {
  z-index: 0;
  pointer-events: none;
}

.project-gantt-chart :deep(.side-header),
.project-gantt-chart :deep(.extras .adjust),
.project-gantt-chart :deep(.bar-label),
.project-gantt-chart :deep(.verto-gantt-undated) {
  display: none;
}

.project-gantt-chart :deep(.verto-gantt-milestone .bar) {
  stroke: #7c3aed;
  stroke-width: 2px;
}

.project-gantt-chart :deep(rect.bar),
.project-gantt-chart :deep(rect.bar-progress) {
  pointer-events: all;
}
</style>

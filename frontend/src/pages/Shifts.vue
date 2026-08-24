<!-- VERTO_SHIFTS_REMOVE_BOTTOM_GAP_2026_06_10 -->
<template>
  <section class="h-full min-h-0 bg-surface-gray-1">
    <main class="space-y-3 px-[var(--verto-page-x,0.75rem)] py-[var(--verto-page-y,0.75rem)]">
      <!-- Month Quick Action -->
      <div class="flex items-center justify-end">
        <Button
          variant="subtle"
          theme="gray"
          size="sm"
          @click="goToToday"
        >
          Today
        </Button>
      </div>

      <!-- Calendar -->
      <Card class=" px-1 py-1 overflow-hidden border border-outline-gray-1 bg-surface-white !py-1 !px-1 !mt-1">
        <!-- Month Controls -->
        <div class="flex items-center justify-between border-b border-outline-gray-1 px-3 py-3">
          <Button
            variant="subtle"
            theme="gray"
            size="sm"
            @click="updateCalendar(-1)"
          >
            ‹
          </Button>

          <div class="text-center">
            <h2 class="text-lg font-semibold text-ink-gray-9">
              {{ currentMonthName }}
            </h2>

            <p class="text-sm text-ink-gray-5">
              {{ currentYear }}
            </p>
          </div>

          <Button
            variant="subtle"
            theme="gray"
            size="sm"
            @click="updateCalendar(1)"
          >
            ›
          </Button>
        </div>

        <!-- Weekdays -->
        <div class="grid grid-cols-7 border-b border-outline-gray-1 bg-surface-gray-1 px-2 py-2 text-center text-[11px] font-semibold uppercase tracking-wide text-ink-gray-5">
          <div>Mon</div>
          <div>Tue</div>
          <div>Wed</div>
          <div>Thu</div>
          <div>Fri</div>
          <div>Sat</div>
          <div>Sun</div>
        </div>

        <!-- Loading -->
        <div
          v-if="loading"
          class="p-3"
        >
          <div class="rounded-xl bg-surface-gray-1 p-4 text-sm text-ink-gray-5">
            Loading shifts...
          </div>
        </div>

        <!-- Error -->
        <div
          v-else-if="error"
          class="p-3"
        >
          <div class="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
            {{ error }}
          </div>
        </div>

        <!-- Calendar Grid -->
        <div
          v-else
          class="grid grid-cols-7 gap-1 p-2"
        >
          <div
            v-for="blank in leadingBlanks"
            :key="`blank-start-${blank}`"
            class="min-h-12"
          />

          <button
            v-for="day in daysInMonth"
            :key="day.date"
            type="button"
            class="relative flex flex-col items-center justify-start rounded-xl px-1 py-2 text-sm font-medium transition active:scale-95"
            :class="getDayButtonClass(day.date)"
            @click="selectDate(day.date)"
          >
            <span>{{ day.dayNumber }}</span>

            <div class="mt-1 flex justify-center gap-1">
              <span
                v-if="getShiftForDate(day.date)"
                class="h-2 w-2 rounded-full ring-1 ring-white"
                :style="{ backgroundColor: getShiftDotColor(getShiftForDate(day.date)) }"
              />

              <span
                v-if="getTimesheetForDate(day.date)"
                class="h-2 w-2 rounded-full bg-green-600 ring-1 ring-white"
              />
            </div>
          </button>

          <div
            v-for="blank in trailingBlanks"
            :key="`blank-end-${blank}`"
            class="min-h-12"
          />
        </div>
      </Card>

      <!-- Selected Day Details -->
      <Card
        v-if="selectedDate && !loading && !error"
        class="overflow-hidden border border-outline-gray-1 bg-surface-white !py-1 !px-1 !mt-1"
      >
        <div class="border-b border-outline-gray-1 px-3 py-3">
          <h2 class="mt-1 text-lg font-semibold text-ink-gray-9">
            {{ formatFullDate(selectedDate) }}
          </h2>
        </div>

        <div class="p-3">
          <div class="flex items-stretch justify-between gap-3">
            <div class="min-w-0 flex-1">
              <template v-if="selectedShift">
                <h3 class="text-base font-semibold text-ink-gray-9">
                  {{ getShiftDisplayName(selectedShift) }}
                </h3>

                <p
                  v-if="!isUnavailableShift(selectedShift) && (selectedShift.custom_client || selectedShift.custom_location)"
                  class="mt-1 text-sm text-ink-gray-5"
                >
                  {{ selectedShift.custom_client || '' }}
                  <span v-if="selectedShift.custom_client && selectedShift.custom_location"> - </span>
                  {{ selectedShift.custom_location || '' }}
                </p>

                <p class="mt-2 text-sm text-ink-gray-5">
                  {{ formatDisplayDate(selectedShift.start_date) }}
                  -
                  {{ formatDisplayDate(selectedShift.end_date) }}
                </p>
              </template>

              <template v-else>
                <h3 class="text-base font-semibold text-ink-gray-9">
                  No shift allocated
                </h3>

                <p class="mt-1 text-sm text-ink-gray-5">
                  You can still submit a timesheet for this date.
                </p>
              </template>

              <p
                v-if="selectedTimesheet?.duration"
                class="mt-3 text-base font-semibold text-ink-gray-9"
              >
                {{ (selectedTimesheet.duration / 3600).toFixed(2) }} hours submitted
              </p>

              <p
                v-if="selectedTimesheet?.offline_queued"
                class="mt-2 text-sm font-medium text-amber-700"
              >
                Saved offline — waiting to sync
              </p>

              <div
                v-if="!selectedShift || !isUnavailableShift(selectedShift)"
                class="mt-4"
              >
                <Button
                  v-if="selectedTimesheet?.offline_queued"
                  variant="subtle"
                  theme="gray"
                  class="w-full justify-center"
                  disabled
                >
                  Waiting to Sync
                </Button>

                <Button
                  v-else-if="selectedTimesheet"
                  variant="solid"
                  theme="gray"
                  class="w-full justify-center"
                  @click="modifyDailyTimesheet(selectedTimesheet.name)"
                >
                  Modify Timesheet
                </Button>

                <Button
                  v-else
                  variant="solid"
                  theme="gray"
                  class="w-full justify-center"
                  @click="createDailyTimesheet(selectedDate)"
                >
                  Submit Timesheet
                </Button>
              </div>
            </div>

            <div class="flex w-16 shrink-0 items-center justify-center text-3xl">
              {{ selectedShift ? getShiftIconText(selectedShift.shift_type) : '—' }}
            </div>
          </div>
        </div>
      </Card>
    </main>
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  Button,
  Card,
} from 'frappe-ui'
import { apiRequest } from '../lib/api'

type ShiftItem = {
  name?: string
  start_date: string
  end_date: string
  employee_name?: string
  shift_type: string
  status?: string
  custom_project_name?: string
  custom_color?: string
  custom_client?: string
  custom_location?: string
  custom_shift_type_color?: string
  custom_project?: string
  is_leave?: number
}

type TimesheetItem = {
  name: string
  date: string
  start_time?: string
  end_time?: string
  duration?: number
  current_user?: string
  project_name?: string
  custom_project?: string
  link_task?: string
  offline_queued?: boolean
  offline_operation_id?: string
}

type ShiftPayload = {
  user: string
  user_fullname: string
  shifts: ShiftItem[]
  timesheets: TimesheetItem[]
}

type FrappeResponse<T> = {
  message: T
}

const router = useRouter()

const loading = ref(true)
const error = ref('')

const today = new Date()

const currentMonth = ref(today.getMonth())
const currentYear = ref(today.getFullYear())
const selectedDate = ref(formatDateString(today))

const shifts = ref<ShiftItem[]>([])
const timesheets = ref<TimesheetItem[]>([])

const currentMonthName = computed(() => {
  return new Date(currentYear.value, currentMonth.value).toLocaleString('default', {
    month: 'long',
  })
})

const leadingBlanks = computed(() => {
  const firstDay = new Date(currentYear.value, currentMonth.value, 1).getDay()
  return firstDay === 0 ? 6 : firstDay - 1
})

const daysInMonth = computed(() => {
  const total = 32 - new Date(currentYear.value, currentMonth.value, 32).getDate()
  const days: Array<{ dayNumber: number; date: string }> = []

  for (let day = 1; day <= total; day++) {
    const date = new Date(currentYear.value, currentMonth.value, day)

    days.push({
      dayNumber: day,
      date: formatDateString(date),
    })
  }

  return days
})

const trailingBlanks = computed(() => {
  const lastDay = (leadingBlanks.value + daysInMonth.value.length - 1) % 7
  return lastDay === 6 ? 0 : 6 - lastDay
})

const selectedShift = computed<ShiftItem | undefined>(() => {
  return getShiftForDate(selectedDate.value)
})

const selectedTimesheet = computed<TimesheetItem | undefined>(() => {
  return getTimesheetForDate(selectedDate.value)
})

function formatDateString(date: Date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
}

function toDateKey(value?: string | Date | null) {
  if (!value) return ''

  if (value instanceof Date) {
    return formatDateString(value)
  }

  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    return value
  }

  if (/^\d{4}-\d{2}-\d{2}/.test(value)) {
    return value.slice(0, 10)
  }

  const parsed = new Date(value)

  if (Number.isNaN(parsed.getTime())) {
    return ''
  }

  return formatDateString(parsed)
}

function getMonthRange() {
  const start = new Date(currentYear.value, currentMonth.value, 1)
  const end = new Date(currentYear.value, currentMonth.value + 1, 0)

  return {
    start_date: formatDateString(start),
    end_date: formatDateString(end),
  }
}

function isToday(date: string) {
  return date === formatDateString(new Date())
}

function getDayButtonClass(date: string) {
  const classes: string[] = []

  if (isToday(date)) {
    classes.push('bg-blue-600 text-white shadow-sm')
  } else {
    classes.push('bg-surface-gray-1 text-ink-gray-7 hover:bg-surface-gray-2')
  }

  if (selectedDate.value === date) {
    classes.push('ring-2 ring-blue-500 ring-offset-2 ring-offset-surface-white')
  }

  return classes
}

function isBlank(value?: string | null) {
  return value == null || String(value).trim() === ''
}

function getShiftForDate(date: string) {
  const selected = toDateKey(date)

  return shifts.value.find((shift) => {
    const start = toDateKey(shift.start_date)
    const end = toDateKey(shift.end_date || shift.start_date)

    return selected >= start && selected <= end
  })
}

function getTimesheetForDate(date: string) {
  const selected = toDateKey(date)

  return timesheets.value.find((entry) => {
    return toDateKey(entry.date) === selected
  })
}

function getShiftDotColor(shift?: ShiftItem) {
  if (!shift) return '#ff9f89'

  return shift.custom_shift_type_color || shift.custom_color || '#ff9f89'
}

function isUnavailableShift(shift: ShiftItem) {
  return isBlank(shift.custom_project_name) && shift.shift_type === 'U'
}

function getShiftDisplayName(shift: ShiftItem) {
  if (isUnavailableShift(shift)) {
    return 'Unavailable'
  }

  return shift.custom_project_name || 'No project allocated'
}

function formatDisplayDate(value?: string) {
  const dateKey = toDateKey(value)

  if (!dateKey) return ''

  return new Date(`${dateKey}T00:00:00`).toLocaleString('default', {
    day: 'numeric',
    month: 'short',
  })
}

function formatFullDate(value?: string) {
  const dateKey = toDateKey(value)

  if (!dateKey) return ''

  return new Date(`${dateKey}T00:00:00`).toLocaleString('default', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  })
}

function getShiftIconText(type?: string) {
  const value = type || ''

  if (value.endsWith('FI') || value === 'Fly-in') return '✈️'
  if (value.endsWith('FO') || value === 'Fly-out') return '🛫'
  if (value.endsWith('DS')) return '☀️'
  if (value.endsWith('NS')) return '🌙'
  if (value.endsWith('PTH')) return '💼'
  if (value.endsWith('SD')) return '💤'
  if (value.endsWith('U')) return '✕'

  return ''
}

function selectDate(date: string) {
  selectedDate.value = date
}

function updateCalendar(monthOffset: number) {
  let newMonth = currentMonth.value + monthOffset
  let newYear = currentYear.value

  if (newMonth < 0) {
    newMonth = 11
    newYear -= 1
  } else if (newMonth > 11) {
    newMonth = 0
    newYear += 1
  }

  currentMonth.value = newMonth
  currentYear.value = newYear

  const currentMonthPrefix = `${currentYear.value}-${String(currentMonth.value + 1).padStart(2, '0')}`

  if (!selectedDate.value.startsWith(currentMonthPrefix)) {
    selectedDate.value = formatDateString(new Date(currentYear.value, currentMonth.value, 1))
  }

  loadCalendar()
}

function goToToday() {
  const now = new Date()

  currentMonth.value = now.getMonth()
  currentYear.value = now.getFullYear()
  selectedDate.value = formatDateString(now)

  loadCalendar()
}

function createDailyTimesheet(date: string) {
  router.push({
    path: '/new/daily-timesheet',
    query: {
      date,
    },
  })
}

function modifyDailyTimesheet(name: string) {
  router.push({
    path: `/edit/daily-timesheet/${encodeURIComponent(name)}`,
  })
}

async function loadCalendar() {
  loading.value = true
  error.value = ''

  try {
    const range = getMonthRange()
    const params = new URLSearchParams(range)

    const data = await apiRequest<FrappeResponse<ShiftPayload>>(
      `/api/method/verto.api.mobile.shifts.get_shift_calendar?${params.toString()}`
    )

    shifts.value = data.message.shifts || []
    timesheets.value = data.message.timesheets || []

    const currentMonthPrefix = `${currentYear.value}-${String(currentMonth.value + 1).padStart(2, '0')}`

    if (!selectedDate.value.startsWith(currentMonthPrefix)) {
      selectedDate.value = formatDateString(new Date(currentYear.value, currentMonth.value, 1))
    }
  } catch (err) {
    if (err instanceof Error && err.message === 'Login required') {
      return
    }

    error.value = err instanceof Error ? err.message : 'Could not load shifts.'
  } finally {
    loading.value = false
  }
}

function handleOfflineQueueSynced() {
  void loadCalendar()
}

onMounted(() => {
  window.addEventListener('verto:offline-queue-synced', handleOfflineQueueSynced)
  loadCalendar()
})

onBeforeUnmount(() => {
  window.removeEventListener('verto:offline-queue-synced', handleOfflineQueueSynced)
})
</script>

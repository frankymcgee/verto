import { parseFrappeTime } from './dateTimeFields'

type TaskClock = string | number | null

export type ScheduleTaskRecord = {
  name: string
  subject?: string | null
  status?: string | null
  type?: string | null
  progress?: number | string | null
  is_group?: number | boolean | string
  is_milestone?: number | boolean | string
  exp_start_date?: string | null
  exp_end_date?: string | null
  exp_start_time?: TaskClock
  exp_end_time?: TaskClock
  depends_on_tasks?: string | null
  parent_task_name?: string | null
  color?: string | null
  color_label?: string | null
}

export type ScheduleTask = {
  id: string
  name: string
  title: string
  status: string
  type: string
  parent: string
  progress: number
  isGroup: boolean
  isMilestone: boolean
  color: string | undefined
  start: TaskDate | null
  end: TaskDate | null
  dependencies: string[]
}

type TaskDate = { date: Date; hasTime: boolean }

function taskDate(value?: string | null, time?: TaskClock): TaskDate | null {
  const parts = /^(\d{4})-(\d{2})-(\d{2})(?:[T ](\S+))?/.exec(value?.trim() || '')
  if (!parts) return null

  const [, year, month, day, clock] = parts
  const date = new Date(Number(year), Number(month) - 1, Number(day))
  if (date.getFullYear() !== Number(year) || date.getMonth() !== Number(month) - 1 || date.getDate() !== Number(day)) {
    return null
  }

  // Treat a Datetime stored at midnight as a date unless a separate Time field was set.
  const seconds = parseFrappeTime(time) ?? (parseFrappeTime(clock) || null)
  if (seconds !== null) date.setSeconds(seconds)
  return { date, hasTime: seconds !== null }
}

export function scheduleTask(row: ScheduleTaskRecord): ScheduleTask {
  const progress = Number(row.progress)
  const color = [row.color, row.color_label].find((value) => /^#(?:[\da-f]{3}|[\da-f]{6})$/i.test(value || ''))
  return {
    // Frappe Gantt uses IDs in CSS selectors. Encode code points without collisions.
    id: `task-${Array.from(row.name, (character) => character.codePointAt(0)!.toString(16)).join('-')}`,
    name: row.name,
    title: row.subject || row.name,
    status: row.status || '',
    type: row.type || '',
    parent: row.parent_task_name || '',
    progress: Number.isFinite(progress) ? Math.round(Math.max(0, Math.min(100, progress))) : 0,
    isGroup: Number(row.is_group) === 1,
    isMilestone: Number(row.is_milestone) === 1,
    color: color || undefined,
    start: taskDate(row.exp_start_date, row.exp_start_time),
    end: taskDate(row.exp_end_date, row.exp_end_time),
    dependencies: [...new Set((row.depends_on_tasks || '').split(',').map((id) => id.trim()).filter(Boolean))],
  }
}

export type TimelineTask = ScheduleTask & { start: TaskDate; end: TaskDate }

export function hasTimelineDates(task: ScheduleTask): task is TimelineTask {
  if (!task.start || !task.end) return false
  const start = task.start.date
  const end = new Date(task.end.date)
  if (!task.end.hasTime) end.setHours(23, 59, 59, 0)
  const lastDay = new Date(start)
  lastDay.setFullYear(start.getFullYear() + 10)
  return start <= end && end < lastDay
}

const dateLabel = new Intl.DateTimeFormat('en-AU', { day: 'numeric', month: 'short', year: 'numeric' })
const timeLabel = new Intl.DateTimeFormat('en-AU', { hour: '2-digit', minute: '2-digit', hour12: false })

export function formatScheduleDate(value: TaskDate | null) {
  if (!value) return '—'
  const date = dateLabel.format(value.date)
  return value.hasTime ? `${date}, ${timeLabel.format(value.date)}` : date
}

export function scheduleRange(task: ScheduleTask) {
  if (!task.start && !task.end) return 'Unscheduled'
  const start = formatScheduleDate(task.start)
  const end = formatScheduleDate(task.end)
  return start === end ? start : `${start} – ${end}`
}

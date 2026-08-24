import { apiRequest } from '../lib/api'
import { cacheApiResponse } from './offlineQueue'
import { clearOfflineReadCache } from './offlineSecurity'

export const OFFLINE_ACTOR_STORAGE_KEY = 'verto:offline-actor'

export type OfflineBootstrapPayload = {
  generated_at?: string
  user?: string
  schemas?: Record<string, any>
  shift_calendar?: {
    user?: string
    user_fullname?: string
    shifts?: any[]
    timesheets?: any[]
  }
  shift_range?: {
    start_date?: string
    end_date?: string
  }
  completed_forms?: any[]
  completed_forms_range?: {
    start_date?: string
    end_date?: string
  }
  edit_docs?: Record<string, any>
  link_options?: Record<string, Array<{ name: string; description?: string }>>
}

type FrappeResponse<T> = {
  message: T
}

function formatDate(date: Date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
}

function monthRange(year: number, month: number) {
  const start = new Date(year, month, 1)
  const end = new Date(year, month + 1, 0)

  return {
    start_date: formatDate(start),
    end_date: formatDate(end),
  }
}

function toDateKey(value?: string | null) {
  return value ? String(value).slice(0, 10) : ''
}

function filterCalendarForRange(payload: any, startDate: string, endDate: string) {
  const shifts = (payload?.shifts || []).filter((shift: any) => {
    const start = toDateKey(shift.start_date)
    const end = toDateKey(shift.end_date || shift.start_date)
    return start && end && start <= endDate && end >= startDate
  })

  const timesheets = (payload?.timesheets || []).filter((timesheet: any) => {
    const date = toDateKey(timesheet.date)
    return date && date >= startDate && date <= endDate
  })

  return {
    message: {
      user: payload?.user || '',
      user_fullname: payload?.user_fullname || '',
      shifts,
      timesheets,
      offline_cached: true,
    },
  }
}

function serialisePostFields(fields: Record<string, string>) {
  const entries = Object.entries(fields)
    .sort(([aKey, aValue], [bKey, bValue]) => {
      return `${aKey}:${aValue}`.localeCompare(`${bKey}:${bValue}`)
    })

  return JSON.stringify(entries)
}

export function getOfflineActor() {
  try {
    return String(window.localStorage.getItem(OFFLINE_ACTOR_STORAGE_KEY) || '').trim()
  } catch {
    return ''
  }
}

function setOfflineActor(user: string) {
  try {
    window.localStorage.setItem(OFFLINE_ACTOR_STORAGE_KEY, user)
  } catch {
    // Queue writes fail safe if browser storage is unavailable.
  }
}

export async function primeOfflineData() {
  if (typeof navigator !== 'undefined' && !navigator.onLine) {
    return null
  }

  const data = await apiRequest<FrappeResponse<OfflineBootstrapPayload>>(
    '/api/method/verto.api.mobile.offline.get_offline_bootstrap'
  )

  const bootstrap = data.message || {}
  const actor = bootstrap.user || bootstrap.shift_calendar?.user || ''
  const previousActor = getOfflineActor()

  if (actor && previousActor && previousActor !== actor) {
    await clearOfflineReadCache()
  }

  if (actor) {
    setOfflineActor(actor)
  }

  for (const [mobileDoctype, schema] of Object.entries(bootstrap.schemas || {})) {
    const params = new URLSearchParams({
      mobile_doctype: mobileDoctype,
    })
    const url = `/api/method/verto.api.mobile.documents.get_form_schema?${params.toString()}`
    const key = `request:GET:${url}:`

    await cacheApiResponse(
      key,
      { message: schema },
      'form-schema'
    )
  }

  const calendar = bootstrap.shift_calendar

  if (calendar) {
    const now = new Date()

    for (let offset = -2; offset <= 4; offset += 1) {
      const target = new Date(now.getFullYear(), now.getMonth() + offset, 1)
      const range = monthRange(target.getFullYear(), target.getMonth())
      const params = new URLSearchParams(range)
      const url = `/api/method/verto.api.mobile.shifts.get_shift_calendar?${params.toString()}`
      const key = `request:GET:${url}:`
      const filtered = filterCalendarForRange(
        calendar,
        range.start_date,
        range.end_date
      )

      await cacheApiResponse(key, filtered, 'shift-calendar')
    }
  }

  const completedFormsRange = bootstrap.completed_forms_range

  if (
    completedFormsRange?.start_date &&
    completedFormsRange?.end_date
  ) {
    const body = serialisePostFields({
      start_date: completedFormsRange.start_date,
      end_date: completedFormsRange.end_date,
    })
    const url = '/api/method/verto.api.fetch_records.fetch_created_records'
    const key = `request:POST:${url}:${body}`

    await cacheApiResponse(
      key,
      { message: bootstrap.completed_forms || [] },
      'completed-forms'
    )
  }

  for (const [cacheId, payload] of Object.entries(bootstrap.edit_docs || {})) {
    const separator = cacheId.indexOf(':')

    if (separator <= 0) continue

    const mobileDoctype = cacheId.slice(0, separator)
    const docname = cacheId.slice(separator + 1)
    const body = serialisePostFields({
      mobile_doctype: mobileDoctype,
      docname,
    })
    const url = '/api/method/verto.api.mobile.documents.get_mobile_doc_for_edit'
    const key = `request:POST:${url}:${body}`

    await cacheApiResponse(
      key,
      { message: payload },
      'edit-document'
    )
  }

  for (const [doctype, options] of Object.entries(bootstrap.link_options || {})) {
    await cacheApiResponse(
      `link-options:${doctype}`,
      options || [],
      `link-options:${doctype}`
    )
  }

  await cacheApiResponse(
    'offline-bootstrap:latest',
    data,
    'offline-bootstrap'
  )

  return bootstrap
}

export type DateTimeFieldType = 'Date' | 'Time' | 'Datetime'

export function isDateTimeField(fieldtype: string): fieldtype is DateTimeFieldType {
  return fieldtype === 'Date' || fieldtype === 'Time' || fieldtype === 'Datetime'
}

export function parseFrappeTime(value: unknown): number | null {
  // A Frappe Time can be serialised as seconds since midnight or as a clock string.
  if (typeof value === 'number') {
    return Number.isFinite(value) && value >= 0 && value < 86400 ? Math.floor(value) : null
  }
  if (typeof value !== 'string') return null

  const clock = /^(\d{1,2}):([0-5]\d)(?::([0-5]\d)(?:\.\d+)?)?$/.exec(value.trim())
  if (!clock || Number(clock[1]) > 23) return null
  return Number(clock[1]) * 3600 + Number(clock[2]) * 60 + Number(clock[3] || 0)
}

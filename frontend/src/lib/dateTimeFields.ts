export type DateTimeFieldType = 'Date' | 'Time' | 'Datetime'

export function isDateTimeField(fieldtype: string): fieldtype is DateTimeFieldType {
  return fieldtype === 'Date' || fieldtype === 'Time' || fieldtype === 'Datetime'
}

export const minuteTimeOptions = Array.from({ length: 24 * 60 }, (_, minuteOfDay) => {
  const hours = String(Math.floor(minuteOfDay / 60)).padStart(2, '0')
  const minutes = String(minuteOfDay % 60).padStart(2, '0')
  const time = `${hours}:${minutes}`
  return { value: time, label: time }
})

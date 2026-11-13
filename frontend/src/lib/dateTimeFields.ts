export type DateTimeFieldType = 'Date' | 'Time' | 'Datetime'

export function isDateTimeField(fieldtype: string): fieldtype is DateTimeFieldType {
  return fieldtype === 'Date' || fieldtype === 'Time' || fieldtype === 'Datetime'
}

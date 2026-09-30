export type ProjectShiftAssignmentDefaults = {
  custom_project: string
  custom_project_designation?: string
  project_name: string
  shift_location: string
  shift_type: 'DS' | 'NS'
  start_date: string
  end_date: string
}

export type PersonnelRequirement = {
  shift: 'DS' | 'NS'
  designation: string
  required_personnel: number
}

export type PersonnelAllocation = PersonnelRequirement & {
  personnel: Array<{ employee: string; employee_name: string }>
}

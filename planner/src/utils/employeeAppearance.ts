import { computed } from 'vue'
import colors from 'tailwindcss/colors'
import { usePlannerBootstrap } from './bootstrap'

// Shared by employee rows and profile hover cards.
export const defaultEmployeeAccentColor = colors.blue[500]

type Employee = { employment_type?: string | null }
type EmploymentType = { name: string; custom_planner_colour?: string | null }

export function useEmployeeAppearance() {
  const bootstrap = usePlannerBootstrap()
  const employmentTypeColours = computed(() => {
    const types: EmploymentType[] = bootstrap.data?.references?.employment_type || []
    return new Map(types.map(type => {
      const colour = String(type.custom_planner_colour || '').trim()
      // Match Frappe's Color control, including safe fallback for imported values.
      return [type.name, /^#[0-9a-f]{6}$/i.test(colour) ? colour : defaultEmployeeAccentColor]
    }))
  })
  return {
    employeeAccentColor: (employee: Employee) =>
      employmentTypeColours.value.get(employee.employment_type || '') || defaultEmployeeAccentColor,
  }
}

import { createResource } from 'frappe-ui'
import { coalesceResource } from './coalesceResource'

let bootstrap: ReturnType<typeof createResource> | undefined

export function usePlannerBootstrap() {
  if (!bootstrap) {
    bootstrap = coalesceResource(createResource({
      url: 'verto.api.planner_data.get_bootstrap',
      transform(data: any) {
        const errors = { ...bootstrap?.data?.errors }
        for (const key of Object.keys(errors)) {
          if (!data.sections || data.sections.includes(key.split('.')[0])) delete errors[key]
        }
        return { ...bootstrap?.data, ...data, errors: { ...errors, ...data.errors } }
      },
    }))
    // Home renders the resource's error and retry action.
    void bootstrap.fetch().catch(() => {})
  }
  return bootstrap
}

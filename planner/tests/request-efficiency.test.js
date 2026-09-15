import { describe, it, expect, vi } from 'vitest'
const mocks = vi.hoisted(() => ({ createResource: vi.fn(() => ({ data: null, fetch: async () => ({}) })),
  frappeRequest: vi.fn(async ({params}) => ({results: (params?.requests || []).map(() => ({data: {}}))})) }))
vi.mock('frappe-ui', async (original) => ({ ...await original(), ...mocks }))
import { usePlannerSettings } from '../src/utils/settings'
import { plannerRequest } from '../src/utils/requestCoordinator'

describe('Planner request efficiency', () => {
  it('loads settings once for navbar, apps and view preferences', () => {
    const navbar = usePlannerSettings()
    expect(usePlannerSettings()).toBe(navbar)
    expect(usePlannerSettings()).toBe(navbar)
    expect(mocks.createResource).toHaveBeenCalledTimes(1)
    expect(mocks.createResource.mock.calls[0][0].url).toBe('verto.api.planner_data.get_bootstrap')
  })
  it('snapshots queued filters and respects cancellation', async () => {
    const params = { employee_filters: { company: 'original' } }
    const request = plannerRequest({ url: 'verto.api.planner.get_year_events', params })
    params.employee_filters.company = 'changed'
    await request
    expect(mocks.frappeRequest.mock.calls.at(-1)[0].params.requests[0].params.employee_filters.company).toBe('original')
    const controller = new AbortController()
    controller.abort()
    const count = mocks.frappeRequest.mock.calls.length
    await expect(plannerRequest({ url: 'verto.api.planner.get_events', signal: controller.signal })).rejects.toThrow()
    expect(mocks.frappeRequest).toHaveBeenCalledTimes(count)
  })
})

export type PlannerScope = 'roster' | 'projects' | 'employees' | 'settings'
export const ALL_PLANNER_SCOPES: PlannerScope[] = ['roster', 'projects', 'employees', 'settings']

/** Merge event bursts, run one refresh at a time, and retain edits arriving mid-refresh. */
export function createLiveRefreshQueue(options: {
  refresh: (scopes: Set<PlannerScope>) => Promise<void>
  canRun: () => boolean
  onError?: (error: unknown) => void
  delay?: number
}) {
  const pending = new Set<PlannerScope>()
  let timer: ReturnType<typeof setTimeout> | undefined
  let running = false
  let stopped = false

  function schedule(delay = options.delay ?? 350 + Math.random() * 250) {
    if (stopped || running || timer || !pending.size) return
    // Do not reset the timer on each event: sustained imports must not starve updates.
    timer = setTimeout(flush, delay)
  }

  async function flush() {
    timer = undefined
    if (stopped || running || !options.canRun() || !pending.size) return
    const scopes = new Set(pending)
    pending.clear()
    running = true
    let failed = false
    try {
      await options.refresh(scopes)
    } catch (error) {
      failed = true
      scopes.forEach((scope) => pending.add(scope))
      options.onError?.(error)
    } finally {
      running = false
      if (!stopped) schedule(failed ? 10_000 : undefined)
    }
  }

  return {
    request(scopes: Iterable<PlannerScope>) {
      for (const scope of scopes) if (ALL_PLANNER_SCOPES.includes(scope)) pending.add(scope)
      schedule()
    },
    resume: () => schedule(),
    stop() { stopped = true; clearTimeout(timer); pending.clear() },
  }
}

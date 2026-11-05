/** Serialize refreshes and keep one trailing fetch of the newest filter values. */
export function coalesceResource<T extends { fetch: (...args: any[]) => any; reload?: any; abort?: () => void; list?: { abort?: () => void } }>(resource: T) {
  // Frappe list.fetch() discards its promise; reload() returns the actual read.
  const fetch = (resource.list ? resource.reload : resource.fetch).bind(resource)
  let inFlight: Promise<any> | null = null
  let again = false
  let disposed = false
  let latestArgs: any[] = []
  resource.fetch = (...args: any[]) => {
    if (disposed) return Promise.resolve()
    latestArgs = args
    if (inFlight) { again = true; return inFlight }
    inFlight = (async () => {
      try {
        let result, failure
        do {
          again = false
          failure = undefined
          try { result = await fetch(...latestArgs) }
          catch (error) { failure = error; await Promise.resolve() }
        } while (again && !disposed)
        if (failure) throw failure
        return result
      } finally { inFlight = null }
    })()
    return inFlight
  }
  resource.reload = resource.fetch
  return Object.assign(resource, {
    disposeRefresh() { disposed = true; again = false; (resource.list ?? resource).abort?.() },
  })
}

/** Per-tab coordination for explicitly selected reads. Never use for writes. */
export function createReadCoordinator(limit = 4) {
  let active = 0
  const queue: Array<() => void> = []
  const pending = new Map<string, Promise<unknown>>()

  function drain() {
    while (active < limit && queue.length) queue.shift()!()
  }

  function run<T>(key: string | null, operation: () => Promise<T>): Promise<T> {
    let request = key === null ? undefined : pending.get(key) as Promise<T> | undefined
    if (!request) {
      request = new Promise<T>((resolve, reject) => {
        queue.push(() => {
          active++
          Promise.resolve().then(operation).then(resolve, reject).finally(() => {
            active--
            drain()
          })
        })
      })
      if (key !== null) {
        pending.set(key, request)
        const clear = () => {
          if (pending.get(key) === request) pending.delete(key)
        }
        request.then(clear, clear)
      }
      drain()
    }
    // Resource transforms and form editors may mutate their result. Sharing the
    // transport must not share mutable state between callers.
    return request.then((result) => structuredClone(result))
  }

  return {
    run,
    // A read started after a mutation must not join a pre-mutation request.
    invalidate: () => pending.clear(),
  }
}

export function stableKey(value: unknown): string {
  return JSON.stringify(value, (_key, item) => {
    if (item && typeof item === 'object' && !Array.isArray(item)) {
      return Object.fromEntries(Object.keys(item).sort().map((key) => [key, item[key]]))
    }
    return item
  })
}

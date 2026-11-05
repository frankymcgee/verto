import { stableKey } from '../../../shared/requestCoordinator'

type Read = { method: string; params: any }
type Result = { data?: any; error?: { message: string; exc_type?: string } }
type Consumer = { resolve: (data: any) => void; reject: (error: any) => void; cleanup: () => void }
type Entry = { key: string; read: Read; consumers: Set<Consumer> }

const clone = (value: any) => value == null ? value : JSON.parse(JSON.stringify(value))

/** Collect Vue's mount/watch reads before occupying a network slot. */
export function createReadBatcher(send: (requests: Read[]) => Promise<{ results: Result[] }>, delay = 10) {
  const pending = new Map<string, Entry>()
  let queued: Entry[] = []
  let timer: ReturnType<typeof setTimeout> | undefined
  let running = false

  function schedule() {
    if (!running && !timer && queued.length) timer = setTimeout(flush, delay)
  }

  async function flush() {
    timer = undefined
    queued = queued.filter(entry => entry.consumers.size)
    const batch = queued.splice(0, 20)
    if (!batch.length) return
    running = true
    try {
      const response = await send(batch.map(entry => entry.read))
      if (!Array.isArray(response?.results) || response.results.length !== batch.length) {
        throw new Error('Invalid planner data response')
      }
      batch.forEach((entry, index) => {
        const result = response.results[index]
        for (const consumer of entry.consumers) {
          if (result.error) {
            consumer.reject(Object.assign(new Error(result.error.message), {
              messages: [result.error.message], exc_type: result.error.exc_type,
            }))
          } else consumer.resolve(clone(result.data))
        }
      })
    } catch (error) {
      const failure = error instanceof Error ? error : new Error('Unable to load planner data')
      if (!Array.isArray((failure as any).messages)) Object.assign(failure, { messages: [failure.message] })
      for (const entry of batch) for (const consumer of entry.consumers) consumer.reject(failure)
    } finally {
      for (const entry of batch) {
        for (const consumer of entry.consumers) consumer.cleanup()
        if (pending.get(entry.key) === entry) pending.delete(entry.key)
      }
      running = false
      schedule()
    }
  }

  return {
    // A read after a write must not join a response from before that write.
    invalidate() { pending.clear() },
    read(method: string, params: any, signal?: AbortSignal): Promise<any> {
      if (signal?.aborted) return Promise.reject(signal.reason || new DOMException('Aborted', 'AbortError'))
      const read = { method, params: clone(params || {}) }
      const key = stableKey(read)
      let entry = pending.get(key)
      if (!entry) {
        entry = { key, read, consumers: new Set() }
        pending.set(key, entry)
        queued.push(entry)
      }
      const target = entry
      const promise = new Promise((resolve, reject) => {
        const abort = () => {
          target.consumers.delete(consumer)
          consumer.cleanup()
          if (!target.consumers.size && pending.get(key) === target) pending.delete(key)
          reject(signal?.reason || new DOMException('Aborted', 'AbortError'))
        }
        const consumer = { resolve, reject, cleanup: () => signal?.removeEventListener('abort', abort) }
        target.consumers.add(consumer)
        signal?.addEventListener('abort', abort, { once: true })
      })
      schedule()
      return promise
    },
  }
}

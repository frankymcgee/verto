import { onBeforeUnmount, reactive } from 'vue'
import type { RavenMessage } from '../lib/ravenClient'

// Raven allows up to ten minutes for a queued AI job.
const THINKING_TIMEOUT_MS = 10 * 60_000

export function usePeriThinking() {
  const pendingChannelIds = reactive(new Set<string>())
  const timers = new Map<string, number>()
  const sendsInFlight = new Set<Set<string>>()
  let viewRevision = 0

  function stop(channelId: string) {
    for (const completed of sendsInFlight) completed.add(channelId)
    pendingChannelIds.delete(channelId)
    window.clearTimeout(timers.get(channelId))
    timers.delete(channelId)
  }

  function reset() {
    viewRevision += 1
    for (const channelId of pendingChannelIds) stop(channelId)
  }

  function start(channelId: string) {
    pendingChannelIds.add(channelId)
    window.clearTimeout(timers.get(channelId))
    timers.set(channelId, window.setTimeout(() => stop(channelId), THINKING_TIMEOUT_MS))
  }

  async function trackSend(
    send: () => Promise<RavenMessage | null>,
    getResponseChannelId: (message: RavenMessage) => string
  ) {
    const revisionAtSend = viewRevision
    const completed = new Set<string>()
    sendsInFlight.add(completed)

    try {
      const message = await send()

      // A fast reply or a channel change may already have stopped the indicator.
      if (message && revisionAtSend === viewRevision) {
        const channelId = getResponseChannelId(message)
        if (channelId && !completed.has(channelId)) start(channelId)
      }
      return message
    } finally {
      sendsInFlight.delete(completed)
    }
  }

  onBeforeUnmount(reset)

  return { pendingChannelIds, start, stop, reset, trackSend }
}

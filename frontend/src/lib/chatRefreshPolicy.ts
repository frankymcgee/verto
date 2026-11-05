export const CHAT_POLL_INTERVAL_MS = 60_000
export const CHAT_CONNECTED_REFRESH_MS = 5 * 60_000

export function shouldRefreshChat(connected: boolean, lastRefreshAt: number, now = Date.now()) {
  return !connected || now - lastRefreshAt >= CHAT_CONNECTED_REFRESH_MS
}

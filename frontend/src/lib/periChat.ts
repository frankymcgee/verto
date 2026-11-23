import type { RouteLocationRaw } from 'vue-router'
import { apiRequest } from './api'
import { useMobileBoot } from './mobileBoot'

const FLOW_PROMPT_KEY = 'verto:peri:flow-prompt'
type FlowPrompt = { id: string; user: string; message: string }

export function pendingFlowPrompt(user: string, id: string): FlowPrompt | null {
  if (!user || !id) return null
  try {
    const value = JSON.parse(sessionStorage.getItem(FLOW_PROMPT_KEY) || 'null')
    if (value?.user === user && value?.id === id && typeof value?.message === 'string') return value
  } catch { /* No pending prompt when storage is unavailable or invalid. */ }
  return null
}

export function consumeFlowPrompt() {
  // Must succeed before starting a paid run, to avoid sending it again after a reload.
  sessionStorage.removeItem(FLOW_PROMPT_KEY)
}

export async function preparePeriChatRoute(project?: string): Promise<RouteLocationRaw> {
  const { loadMobileBoot, error } = useMobileBoot()
  const boot = await loadMobileBoot()
  if (error.value) throw new Error(error.value)
  const message = project ? `Analyse the dashboard for ${project}` : ''

  if (boot.peri_chat_version === 'Flow') {
    try {
      sessionStorage.removeItem('verto_peri_autosend_message')
      sessionStorage.removeItem('verto_peri_source_project')
      consumeFlowPrompt()
    } catch { /* Normal navigation does not require storage. */ }
    const request = message ? crypto.randomUUID() : ''
    if (message) sessionStorage.setItem(FLOW_PROMPT_KEY, JSON.stringify({ id: request, user: boot.user, message }))
    return { path: '/chat/peri', query: { mode: 'ai', ...(request ? { request } : {}) } }
  }

  try { consumeFlowPrompt() } catch { /* Raven navigation does not require Flow storage. */ }
  const data = await apiRequest<{ message: any }>('/api/method/verto.api.mobile.raven.get_or_create_peri_channel')
  const value = data.message?.channel || data.message?.message || data.message
  const channel = typeof value === 'string' ? value : value?.name || value?.channel_id || value?.channel_name
  if (!channel) throw new Error('Could not determine the Ask PERI channel.')
  if (message) {
    sessionStorage.setItem('verto_peri_autosend_message', message)
    sessionStorage.setItem('verto_peri_source_project', project!)
  }
  return { path: '/chat/peri', query: { channel, mode: 'ai', ...(message ? { auto: 'analyse' } : {}) } }
}

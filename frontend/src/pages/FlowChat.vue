<template>
  <section class="flow-chat" aria-label="Ask PERI with Flow">
    <div v-if="loading" class="p-4 text-sm text-ink-gray-6" role="status">Opening PERI in Flow…</div>
    <div v-if="error" class="shrink-0 border-b p-4 text-sm" role="alert">
      <p>{{ error }}</p>
      <div v-if="!src" class="mt-3 flex flex-wrap gap-4">
        <button type="button" class="underline" @click="openChat()">Try again</button>
        <button type="button" class="underline" @click="openChat(true)">Start a new PERI chat</button>
      </div>
    </div>
    <iframe
      v-if="src"
      ref="frame"
      :src="src"
      title="PERI — Flow"
      class="flow-chat-frame"
      allow="clipboard-write"
      @load="onFrameLoad"
    />
  </section>
</template>

<script setup lang="ts">
import { inject, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { apiRequest } from '../lib/api'
import { useMobileBoot } from '../lib/mobileBoot'
import { consumeFlowPrompt, pendingFlowPrompt } from '../lib/periChat'
import { flowEditingKey, installEmbeddedFlowStyles } from '../lib/flowFrame'

const route = useRoute()
const { boot } = useMobileBoot()
const setEditing = inject(flowEditingKey, () => {})
const src = ref('')
const loading = ref(false)
const error = ref('')
const frame = ref<HTMLIFrameElement | null>(null)
const storageKey = `verto:peri:flow-session:${boot.value.user}:${boot.value.peri_flow_agent}`
let disposed = false
let removeFrameStyles: (() => void) | undefined

function rememberSession(name: string) {
  try { sessionStorage.setItem(storageKey, name) } catch { /* Session recall is optional. */ }
}

async function openChat(forceNew = false) {
  if (loading.value) return
  loading.value = true
  error.value = ''
  try {
    const prompt = pendingFlowPrompt(boot.value.user, String(route.query.request || ''))
    const body = new FormData()
    body.set('new_chat', prompt || forceNew ? '1' : '0')
    try { body.set('session', sessionStorage.getItem(storageKey) || '') } catch { /* Optional. */ }
    const { message } = await apiRequest<{ message: { url: string; session: string } }>(
      '/api/method/verto.api.mobile.flow.open_peri_chat', { method: 'POST', body }
    )
    if (disposed) return
    const url = new URL(message.url, window.location.origin)
    if (url.origin !== window.location.origin || !/^\/flow\/s\/[^/]+$/.test(url.pathname)) {
      throw new Error('Flow returned an invalid conversation URL.')
    }
    rememberSession(message.session)

    if (prompt) {
      // Consume before sending: a dropped connection must never automatically repeat a run.
      consumeFlowPrompt()
      const runBody = new FormData()
      runBody.set('session', message.session)
      runBody.set('message', prompt.message)
      try {
        await apiRequest('/api/method/frappe.flow.api.run', { method: 'POST', body: runBody })
      } catch (err) {
        error.value = `${err instanceof Error ? err.message : 'Flow could not confirm the request.'} Check the conversation before sending the project analysis again.`
      }
    }
    if (!disposed) src.value = url.pathname
  } catch (err) {
    if (!disposed) error.value = err instanceof Error ? err.message : 'Could not open Flow. Check your Flow access and configuration.'
  } finally {
    loading.value = false
  }
}

function onFrameLoad() {
  removeFrameStyles?.()
  removeFrameStyles = undefined
  try {
    const location = frame.value?.contentWindow?.location
    if (location?.pathname === '/login') {
      window.location.assign(`/login?redirect-to=${encodeURIComponent(window.location.pathname + window.location.search)}`)
      return
    }
    const doc = frame.value?.contentDocument
    if (doc && (location?.pathname === '/flow' || location?.pathname.startsWith('/flow/'))) {
      removeFrameStyles = installEmbeddedFlowStyles(doc, setEditing)
    }
  } catch { /* A browser-managed error page cannot be inspected. */ }
}

onMounted(() => { void openChat() })
onBeforeUnmount(() => {
  disposed = true
  removeFrameStyles?.()
  try {
    const path = frame.value?.contentWindow?.location.pathname || ''
    const match = path.match(/^\/flow\/s\/([^/]+)$/)
    if (match) rememberSession(decodeURIComponent(match[1]))
  } catch { /* Keep the last verified session if the frame is unavailable. */ }
})
</script>

<style scoped>
.flow-chat {
  display: flex;
  height: 100%;
  min-height: 0;
  flex-direction: column;
  overflow: clip;
  background: var(--surface-base, white);
}
.flow-chat-frame {
  display: block;
  flex: 1 1 0;
  width: 100%;
  height: 100%;
  min-height: 0;
  border: 0;
}
</style>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { Button } from 'frappe-ui'
import { apiRequest } from '../lib/api'

const route = useRoute(), state = ref<any>(null), error = ref(''), loading = ref(false)
let generation = 0, alive = true
const name = computed(() => String(route.params.jhaName || ''))
const currentPath = computed(() => state.value
  ? `/verto-mobile/voice-jha/${encodeURIComponent(state.value.current.work_summary)}?jha=${encodeURIComponent(state.value.current.name)}` : '')
const outstanding = computed(() => (state.value?.controls || []).filter((row: any) => row.status !== 'Verified').length)

async function load() {
  const request = ++generation
  state.value = null; error.value = ''; loading.value = true
  try {
    if (!navigator.onLine) throw new Error('Connect to the internet to check the current JHA revision.')
    const params = new URLSearchParams({ jha_name: name.value })
    if (typeof route.query.revision === 'string') params.set('revision', route.query.revision)
    const data = await apiRequest<any>(`/api/method/verto.api.mobile.voice_jha_fieldwork.get_jha_workpack_status?${params}`, { cache: 'no-store' })
    if (alive && generation === request) state.value = data.message
  } catch (err) {
    if (alive && generation === request) error.value = err instanceof Error ? err.message : 'Could not check revision status.'
  } finally { if (generation === request) loading.value = false }
}
function refreshWhenVisible() { if (document.visibilityState === 'visible') void load() }
watch(() => [name.value, route.query.revision], load, { immediate: true })
onMounted(() => {
  window.addEventListener('focus', refreshWhenVisible)
  window.addEventListener('online', refreshWhenVisible)
  window.addEventListener('offline', refreshWhenVisible)
  document.addEventListener('visibilitychange', refreshWhenVisible)
})
onBeforeUnmount(() => {
  alive = false; generation++
  window.removeEventListener('focus', refreshWhenVisible)
  window.removeEventListener('online', refreshWhenVisible)
  window.removeEventListener('offline', refreshWhenVisible)
  document.removeEventListener('visibilitychange', refreshWhenVisible)
})
</script>

<template>
  <section class="min-h-full bg-surface-gray-1 px-[var(--verto-page-x,0.75rem)] py-[var(--verto-page-y,0.75rem)]">
    <div class="mx-auto max-w-3xl space-y-3">
      <div class="flex items-center justify-between gap-3"><h1 class="text-xl-semibold">JHA revision check</h1><Button :loading="loading" @click="load">Check again</Button></div>
      <p v-if="loading" role="status" class="rounded-7 bg-surface-base p-4">Checking the live revision record…</p>
      <section v-if="error" role="alert" class="rounded-7 border border-red-200 bg-red-50 p-4 text-red-800"><p class="text-base-semibold">Current status could not be confirmed.</p><p class="mt-2 text-sm">{{ error }}</p></section>
      <template v-if="state">
        <section class="rounded-7 border p-4" :class="!state.is_current || state.requires_review ? 'border-amber-200 bg-amber-50' : 'border-blue-200 bg-blue-50'">
          <h2 class="text-base-semibold">{{ !state.is_current ? 'This printed copy is not the current revision.' : state.requires_review ? 'This JHA requires review.' : 'This is the current signed revision.' }}</h2>
          <p class="mt-2 text-sm">Scanned copy: {{ state.requested.name }} · Revision {{ state.requested.revision }} · {{ state.requested.status }}</p>
          <p v-if="state.revision_mismatch" class="mt-2 text-sm">The revision encoded on this copy does not match its record. Check with the supervisor.</p>
        </section>
        <section class="rounded-7 border border-outline-gray-1 bg-surface-base p-4">
          <p class="text-base-semibold">{{ state.current.title }}</p>
          <p class="mt-2 text-sm">Latest revision: {{ state.current.revision }} · {{ state.current.status }}</p>
          <p class="mt-2 text-sm">Critical-control checks: {{ outstanding }} outstanding / {{ state.controls.length }}.</p>
          <a :href="currentPath" class="mt-4 inline-block rounded-7 bg-gray-900 px-4 py-3 text-sm font-medium text-white">Open Current JHA</a>
          <p class="mt-3 text-xs text-ink-gray-6">Checked {{ state.checked_at }}. Revision and sign-on status do not replace field checks, permits, isolations or site work authorisation.</p>
        </section>
      </template>
    </div>
  </section>
</template>

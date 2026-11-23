<template>
  <div v-if="!ready" class="p-4 text-sm text-ink-gray-6" role="status">Loading Ask PERI…</div>
  <div v-else-if="error" class="p-4 text-sm" role="alert">
    <p>{{ error }}</p>
    <button type="button" class="mt-3 underline" @click="load(true)">Try again</button>
  </div>
  <FlowChat v-else-if="periChatVersion === 'Flow'" :key="String(route.query.request || '')" />
  <RavenChat v-else />
</template>

<script setup lang="ts">
import { defineAsyncComponent, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useMobileBoot } from '../lib/mobileBoot'
import FlowChat from './FlowChat.vue'

const RavenChat = defineAsyncComponent(() => import('./Chat.vue').then(module => module.default))
const route = useRoute()
const { loadMobileBoot, periChatVersion, error: bootError } = useMobileBoot()
const ready = ref(false)
const error = ref('')

async function load(force = false) {
  ready.value = false
  error.value = ''
  try {
    await loadMobileBoot(force)
    error.value = bootError.value
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Could not load Ask PERI settings.'
  } finally {
    ready.value = true
  }
}

onMounted(() => { void load() })
</script>

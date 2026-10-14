<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { getApiCacheEntriesByGroup } from '../pwa/offlineQueue'
import { jhaOfflineActor, type OfflineJhaCopy } from '../pwa/offlineJha'
const copies = ref<OfflineJhaCopy[]>([]), error = ref('')
onMounted(async () => {
  try {
    const actor = jhaOfflineActor()
    copies.value = (await getApiCacheEntriesByGroup<OfflineJhaCopy>('jha-signed-copies'))
      .map(row => row.value).filter(row => actor && row.user === actor)
  } catch { error.value = 'Could not read offline storage on this device.' }
})
</script>
<template>
  <section class="mx-auto max-w-3xl space-y-3 px-[var(--verto-page-x,0.75rem)] py-[var(--verto-page-y,0.75rem)]">
    <h1 class="text-xl-semibold">Offline JHAs</h1><p class="text-sm text-ink-gray-6">Signed copies downloaded on this device for your account. Connect to check the current revision and field conditions.</p>
    <p v-if="error" role="alert" class="text-sm text-red-700">{{ error }}</p><p v-if="!copies.length && !error" class="text-sm">No signed copies saved yet. Open a signed JHA and choose Save Signed Copy for Offline.</p>
    <a v-for="copy in copies" :key="copy.jha.name" :href="`/verto-mobile/jha/${encodeURIComponent(copy.jha.name)}?revision=${copy.jha.revision}`" class="block rounded-7 border bg-surface-base p-4"><p class="text-base-semibold">{{ copy.jha.work_summary_title }}</p><p class="mt-1 text-sm">{{ copy.jha.name }} · Revision {{ copy.jha.revision }} · {{ copy.jha.project }}</p><p class="mt-1 text-xs text-ink-gray-6">Downloaded {{ copy.saved_at }}</p></a>
  </section>
</template>

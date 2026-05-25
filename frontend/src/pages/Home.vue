<template>
  <section class="space-y-4 p-4">
    <div>
      <p class="text-sm text-gray-500">Welcome back</p>
      <h1 class="text-2xl font-semibold">Today on site</h1>
    </div>

    <div
      v-if="loading"
      class="rounded-2xl bg-white p-4 shadow-sm"
    >
      Loading mobile dashboard...
    </div>

    <div
      v-else-if="error"
      class="rounded-2xl bg-red-50 p-4 text-sm text-red-700"
    >
      {{ error }}
    </div>

    <template v-else>
      <div class="rounded-2xl bg-white p-4 shadow-sm">
        <p class="text-sm text-gray-500">API Status</p>
        <p class="mt-1 font-semibold">{{ summary?.message }}</p>
        <p class="text-sm text-gray-500">{{ summary?.user }}</p>
      </div>

      <div
        v-for="card in summary?.cards || []"
        :key="card.label"
        class="rounded-2xl bg-white p-4 shadow-sm"
      >
        <p class="text-sm text-gray-500">{{ card.label }}</p>
        <p class="mt-1 text-2xl font-semibold">{{ card.value }}</p>
        <p class="text-sm text-gray-500">{{ card.description }}</p>
      </div>
    </template>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { apiRequest } from '../lib/api'

type SummaryCard = {
  label: string
  value: number
  description: string
}

type HomeSummary = {
  user: string
  message: string
  cards: SummaryCard[]
}

type FrappeResponse<T> = {
  message: T
}

const loading = ref(true)
const error = ref('')
const summary = ref<HomeSummary | null>(null)

async function loadHomeSummary() {
  loading.value = true
  error.value = ''

  try {
    const data = await apiRequest<FrappeResponse<HomeSummary>>(
      '/api/method/verto.api.mobile.home.get_home_summary'
    )

    summary.value = data.message
  } catch (err) {
    if (err instanceof Error && err.message === 'Login required') {
      return
    }

    error.value = err instanceof Error ? err.message : 'Could not load mobile dashboard.'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadHomeSummary()
})
</script>
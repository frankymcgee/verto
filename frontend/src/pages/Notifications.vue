<template>
  <section class="space-y-3 py-4">
    <div class="flex items-center justify-between gap-2">
      <h1 class="text-lg font-semibold">Recent notifications</h1>
      <Button v-if="items.some(item => !item.is_read)" :disabled="busy" @click="markAllRead">
        Mark all as read
      </Button>
    </div>

    <div v-if="error" role="alert" class="space-y-2">
      <p>{{ error }}</p>
      <Button :disabled="busy" @click="load">Retry</Button>
    </div>
    <p v-else-if="busy && !items.length" role="status">Loading notifications…</p>
    <p v-else-if="!items.length" class="text-ink-gray-5">No recent notifications.</p>

    <ul v-if="items.length" class="space-y-2">
      <li v-for="item in items" :key="item.name" class="rounded-7 border border-outline-gray-1 bg-surface-base p-3">
        <div class="flex items-start justify-between gap-2">
          <p class="break-words font-medium">{{ item.title }}</p>
          <span v-if="!item.is_read" class="rounded bg-surface-gray-2 px-2 py-0.5 text-xs">Unread</span>
        </div>
        <p class="mt-1 whitespace-pre-line break-words text-sm text-ink-gray-7">{{ item.body }}</p>
        <p class="mt-2 text-xs text-ink-gray-5">{{ displayDate(item.creation) }}</p>
        <RouterLink v-if="mobileRoute(item.target_url)" :to="mobileRoute(item.target_url)!" class="mt-2 inline-block text-sm font-medium underline">
          Open update
        </RouterLink>
      </li>
    </ul>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { Button } from 'frappe-ui'
import { apiRequest } from '../lib/api'

type NotificationItem = {
  name: string
  title: string
  body: string
  target_url: string
  creation: string
  is_read: number
}

const endpoint = '/api/method/verto.api.mobile.notifications.'
const items = ref<NotificationItem[]>([])
const busy = ref(false)
const error = ref('')

async function fetchItems() {
  const result = await apiRequest<{ message: { items: NotificationItem[] } }>(endpoint + 'list_notifications', { cache: 'no-store' })
  items.value = result.message.items
}

async function load() {
  busy.value = true
  error.value = ''
  try {
    await fetchItems()
  } catch {
    error.value = 'Could not load notifications.'
  } finally {
    busy.value = false
  }
}

async function markAllRead() {
  const newest = items.value[0]
  if (busy.value || !newest) return
  busy.value = true
  error.value = ''
  try {
    await apiRequest(endpoint + 'mark_read', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ through: newest.name }),
    })
    await fetchItems()
  } catch {
    error.value = 'Could not update notifications.'
  } finally {
    busy.value = false
  }
}

function mobileRoute(target: string) {
  if (!target) return
  try {
    const url = new URL(target, window.location.origin)
    const base = '/verto-mobile'
    if (url.origin !== window.location.origin) return
    if (url.pathname !== base && !url.pathname.startsWith(base + '/')) return
    return (url.pathname.slice(base.length) || '/') + url.search + url.hash
  } catch {
    return undefined
  }
}

function displayDate(value: string) {
  const date = new Date(value.replace(' ', 'T'))
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString()
}

onMounted(load)
</script>

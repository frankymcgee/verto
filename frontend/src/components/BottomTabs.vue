<template>
  <nav class="fixed bottom-0 left-0 right-0 z-50 border-t bg-white">
    <div class="mx-auto grid max-w-md grid-cols-5">
      <RouterLink
        v-for="tab in tabs"
        :key="tab.to"
        :to="tab.to"
        class="flex flex-col items-center justify-center gap-1 py-2 text-xs"
        :class="route.path === tab.to ? 'text-blue-600' : 'text-gray-500'"
      >
        <component :is="tab.icon" class="h-5 w-5" />
        <span>{{ tab.label }}</span>
      </RouterLink>
    </div>
  </nav>
</template>

<script setup lang="ts">
import { useRoute } from 'vue-router'
import {
  Home,
  ClipboardList,
  CalendarDays,
  MessageCircle,
  Menu,
} from '@lucide/vue'

const route = useRoute()

const tabs = [
  { label: 'Home', to: '/', icon: Home },
  { label: 'Forms', to: '/forms', icon: ClipboardList },
  { label: 'Shifts', to: '/shifts', icon: CalendarDays },
  { label: 'Chat', to: '/chat', icon: MessageCircle },
  { label: 'More', to: '/more', icon: Menu },
]
</script>
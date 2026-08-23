<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { Avatar, MobileNav, MobileNavItem } from 'frappe-ui'
import { useMobileBoot } from '../lib/mobileBoot'

const route = useRoute()
const {
  defaultChatChannel,
  periBotName,
  periBotImageUrl,
} = useMobileBoot()

const generalChatRoute = computed(() => ({
  path: '/chat',
  query: {
    channel: defaultChatChannel.value || 'general',
  },
}))

const isHome = computed(() => route.path === '/')
const isShifts = computed(() => route.path.startsWith('/shifts'))
const isPeri = computed(() => route.path === '/chat/peri')
const isForms = computed(() =>
  route.path.startsWith('/forms') ||
  route.path.startsWith('/new/') ||
  route.path.startsWith('/edit/')
)
const isChat = computed(() =>
  route.path.startsWith('/chat') && !isPeri.value
)
</script>

<template>
  <MobileNav aria-label="Primary navigation">
    <MobileNavItem
      label="Home"
      icon="lucide-house"
      to="/"
      :active="isHome"
    />

    <MobileNavItem
      label="Shifts"
      icon="lucide-calendar-days"
      to="/shifts"
      :active="isShifts"
    />

    <MobileNavItem
      :label="`Ask ${periBotName || 'PERI'}`"
      to="/chat/peri"
      :active="isPeri"
    >
      <template #default="{ active }">
        <Avatar
          :label="periBotName || 'PERI'"
          :image="periBotImageUrl || undefined"
          size="md"
          :class="active ? 'ring-2 ring-outline-gray-4' : ''"
        />
      </template>
    </MobileNavItem>

    <MobileNavItem
      label="Forms"
      icon="lucide-clipboard-list"
      to="/forms"
      :active="isForms"
    />

    <MobileNavItem
      label="Chat"
      icon="lucide-message-circle"
      :to="generalChatRoute"
      :active="isChat"
    />
  </MobileNav>
</template>

<template>
  <component :is="compact ? MobileShell : DesktopShell" class="investigation-shell screen-only">
    <template #sidebar>
      <Sidebar v-if="!compact" v-model:collapsed="collapsed" width="252px">
        <SidebarHeader
          title="Verto Investigations"
          subtitle="Incident investigations"
          logo="/assets/verto/images/investigations.svg"
          :menu-items="appOptions"
        />
        <ScrollArea class="min-h-0 flex-1 px-2 py-3">
          <SidebarItem
            label="All investigations"
            icon="lucide-search-check"
            :active="!record"
            @click="$emit('navigate', '')"
          />
          <SidebarItem
            label="New investigation"
            icon="lucide-plus"
            :active="!!record && !record.name"
            @click="$emit('navigate', 'new')"
          />
          <template v-if="record">
            <SidebarLabel class="mt-6">Investigation sections</SidebarLabel>
            <SidebarItem
              v-for="item in tabs"
              :key="item.key"
              :label="item.label"
              :icon="sectionIcons[item.key]"
              :active="activeTab === item.key"
              @click="$emit('select-tab', item.key)"
            />
          </template>
        </ScrollArea>
        <div class="border-t border-outline-gray-2 px-2 py-3">
          <div v-if="!collapsed" class="mb-3 flex items-center gap-2 px-2">
            <Avatar :label="meta.full_name || meta.user || 'Investigator'" size="md" />
            <div class="min-w-0 text-sm text-ink-gray-7">
              <p class="truncate">{{ meta.full_name || meta.user }}</p>
              <p class="text-xs text-ink-gray-5">Confidential workspace</p>
            </div>
          </div>
          <SidebarCollapseToggle />
        </div>
      </Sidebar>
    </template>

    <PageHeaderMobile v-if="compact" :title="record?.name || 'Investigations'">
      <template #suffix>
        <Dropdown
          :options="appOptions"
          :button="{ icon: 'lucide-grid-2x2', label: 'Apps', variant: 'ghost' }"
        />
      </template>
    </PageHeaderMobile>
    <PageHeader v-else>
      <div class="flex min-w-0 flex-1 items-center gap-3">
        <PageHeaderTitle title="Investigations" />
        <span v-if="record" class="truncate text-sm text-ink-gray-5"
          >/ {{ record.name || 'New investigation' }}</span
        >
      </div>
      <Badge theme="gray" variant="outline" label="Confidential" />
      <Dropdown
        :options="appOptions"
        :button="{ label: 'Apps', iconLeft: 'lucide-grid-2x2', variant: 'ghost' }"
      />
    </PageHeader>

    <div v-if="compact && record" class="mobile-section-navigation">
      <Select
        label="Investigation section"
        :model-value="activeTab"
        :options="tabs.map((item) => ({ label: item.label, value: item.key }))"
        size="md"
        @update:model-value="$emit('select-tab', $event)"
      />
    </div>
    <slot />

    <template #nav>
      <MobileNav v-if="compact">
        <MobileNavItem
          label="Investigations"
          icon="lucide-search-check"
          :active="!record"
          @click="$emit('navigate', '')"
        />
        <MobileNavItem
          label="New investigation"
          icon="lucide-plus"
          :active="!!record && !record.name"
          @click="$emit('navigate', 'new')"
        />
      </MobileNav>
    </template>
  </component>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import {
  Avatar,
  Badge,
  DesktopShell,
  Dropdown,
  MobileNav,
  MobileNavItem,
  MobileShell,
  PageHeader,
  PageHeaderMobile,
  PageHeaderTitle,
  ScrollArea,
  Select,
  Sidebar,
  SidebarCollapseToggle,
  SidebarHeader,
  SidebarItem,
  SidebarLabel,
} from 'frappe-ui'

const props = defineProps({
  meta: { type: Object, required: true },
  record: Object,
  tabs: { type: Array, default: () => [] },
  activeTab: String,
})
const emit = defineEmits(['navigate', 'select-tab', 'open-app'])
const compact = ref(window.innerWidth <= 760)
const collapsed = ref(false)
const appOptions = computed(() => [
  { label: 'Desk', icon: 'lucide-layout-grid', onClick: () => emit('open-app', '/app') },
  ...(props.meta.apps || []).map((app) => ({
    label: app.title,
    onClick: () => emit('open-app', app.route),
  })),
])
const sectionIcons = {
  overview: 'lucide-file-text',
  team: 'lucide-users',
  evidence: 'lucide-paperclip',
  timeline: 'lucide-list-ordered',
  whys: 'lucide-git-branch',
  icam: 'lucide-network',
  actions: 'lucide-list-checks',
  review: 'lucide-clipboard-check',
}
function resize() {
  compact.value = window.innerWidth <= 760
}
onMounted(() => window.addEventListener('resize', resize))
onBeforeUnmount(() => window.removeEventListener('resize', resize))
</script>

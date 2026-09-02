<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { apiRequest } from './lib/api'
import { useMobileBoot } from './lib/mobileBoot'

type FrappeResponse<T> = {
  message: T
}

type NavigationAccess = {
  has_employee_profile?: boolean
}

const route = useRoute()
const hasEmployeeProfile = ref(false)

const {
  loadMobileBoot,
  appName,
  faviconUrl,
} = useMobileBoot()

const pageTitle = computed(() => {
  if (typeof route.meta?.title === 'string' && route.meta.title.trim()) {
    return route.meta.title.trim()
  }

  if (route.path.startsWith('/new/')) {
    return 'New Form'
  }

  if (route.path.startsWith('/edit/')) {
    return 'Edit Form'
  }

  if (route.path === '/') {
    return 'Home'
  }

  if (route.path.startsWith('/forms')) {
    return 'Forms'
  }

  if (route.path.startsWith('/shifts')) {
    return 'Shifts'
  }

  if (route.path === '/chat/peri') {
    return 'Ask PERI'
  }

  if (route.path.startsWith('/chat')) {
    return 'Chat'
  }

  return ''
})

const browserTitle = computed(() => {
  const tenantAppName = appName.value || 'Verto Mobile'
  const currentPageTitle = pageTitle.value

  if (!currentPageTitle) {
    return tenantAppName
  }

  return `${currentPageTitle} | ${tenantAppName}`
})

function getFaviconType(href: string) {
  const cleanHref = String(href || '').split('?')[0].toLowerCase()

  if (cleanHref.endsWith('.svg')) {
    return 'image/svg+xml'
  }

  if (cleanHref.endsWith('.png')) {
    return 'image/png'
  }

  if (cleanHref.endsWith('.jpg') || cleanHref.endsWith('.jpeg')) {
    return 'image/jpeg'
  }

  if (cleanHref.endsWith('.ico')) {
    return 'image/x-icon'
  }

  return ''
}

function removeExistingFavicons() {
  const existingIcons = document.querySelectorAll<HTMLLinkElement>(
    [
      'link[rel="icon"]',
      'link[rel="shortcut icon"]',
      'link[rel="apple-touch-icon"]',
      'link[rel="mask-icon"]',
    ].join(',')
  )

  existingIcons.forEach((link) => {
    link.parentNode?.removeChild(link)
  })
}

function appendIcon(rel: string, href: string, type = '') {
  const link = document.createElement('link')

  link.rel = rel
  link.href = href

  if (type) {
    link.type = type
  }

  document.head.appendChild(link)
}

function setFavicon(href: string) {
  if (!href) {
    return
  }

  const cacheBustedHref = href.includes('?')
    ? `${href}&v=${Date.now()}`
    : `${href}?v=${Date.now()}`

  const type = getFaviconType(href)

  removeExistingFavicons()

  appendIcon('icon', cacheBustedHref, type)
  appendIcon('shortcut icon', cacheBustedHref, type)
  appendIcon('apple-touch-icon', cacheBustedHref)
}

function setBrowserTitle() {
  document.title = browserTitle.value
}

async function loadNavigationAccess() {
  try {
    const response = await apiRequest<FrappeResponse<NavigationAccess>>(
      '/api/method/verto.api.mobile.navigation.get_navigation_access'
    )

    hasEmployeeProfile.value = Boolean(
      response.message?.has_employee_profile
    )
  } catch (err) {
    if (err instanceof Error && err.message === 'Login required') {
      throw err
    }

    // Fail closed if the access check cannot be completed.
    hasEmployeeProfile.value = false
  }
}

onMounted(async () => {
  await Promise.all([
    loadMobileBoot(),
    loadNavigationAccess(),
  ])
  setFavicon(faviconUrl.value)
  setBrowserTitle()
})

watch(
  () => faviconUrl.value,
  (value) => {
    setFavicon(value)
  }
)

watch(
  () => browserTitle.value,
  () => {
    setBrowserTitle()
  },
  {
    immediate: true,
  }
)
</script>

<template>
  <div
    class="min-h-screen bg-surface-gray-1 text-ink-gray-9 antialiased"
    :class="{ 'verto-no-employee-profile': !hasEmployeeProfile }"
  >
    <RouterView />
  </div>
</template>

<style>
.verto-no-employee-profile .bottom-tabs-items {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.verto-no-employee-profile .bottom-tabs-items > [title='Shifts'],
.verto-no-employee-profile .bottom-tabs-items > [title='Chat'] {
  display: none;
}
</style>
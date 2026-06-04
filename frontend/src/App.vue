<script setup lang="ts">
import { computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useMobileBoot } from './lib/mobileBoot'

const route = useRoute()

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

onMounted(async () => {
  await loadMobileBoot()
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
  <div class="min-h-screen bg-surface-gray-1 text-ink-gray-9 antialiased">
    <RouterView />
  </div>
</template>